"""Private expansion helpers for AND/OR tree search."""

from __future__ import annotations

from dataclasses import dataclass

from lean_client.exec_models import ExecGoalInfo, ExecStepResult

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, PolicyContext
from leanfoundry.proofsearch._budgets import (
    charge_tactic_calls,
    count_tactic_attempts,
    has_tactic_budget,
    step_result_ran_lean,
)
from leanfoundry.proofsearch._lean_tokens import (
    find_forbidden_proof_placeholder_token,
)
from leanfoundry.proofsearch._negation import (
    NEGATION_ACTION_TACTIC,
    NegationOutcome,
    maybe_apply_negation,
)
from leanfoundry.proofsearch._selection import empirical_action_priors
from leanfoundry.proofsearch._tree import (
    ActionNode,
    ActionNodeStatus,
    SearchTree,
    StateNode,
    StateNodeStatus,
)
from leanfoundry.proofsearch.base import SearchConfig
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
    LocalContextEntry,
    NegationAttempt,
    TheoremSpec,
)

_FATAL_OPERATIONAL_STATUSES = frozenset({"invalid_state_token", "cancelled"})


class BackendProtocolError(ValueError):
    """Raised when backend results violate LeanFoundry's step contract."""


@dataclass(frozen=True, slots=True)
class ExpansionOutcome:
    """Result of expanding one frontier state."""

    actions: list[ActionNode]
    tactic_calls_used: int
    operational_status: str | None = None
    negation_attempts: tuple[NegationAttempt, ...] = ()
    initialized_negation: bool = False

    @property
    def made_progress(self) -> bool:
        return (
            bool(self.actions)
            or self.tactic_calls_used > 0
            or self.initialized_negation
        )


@dataclass(frozen=True, slots=True)
class ChildState:
    """One child OR state plus how it resumes from the parent token.

    ``focus`` is the goal subset (public positions in the parent action's
    result token) this child owns, or None when the child is the whole result
    state and so steps whole-state without a ``goal.continue``.
    """

    state: FactorizedProofState
    focus: tuple[int, ...] | None


async def expand_state(
    tree: SearchTree,
    state_node: StateNode,
    *,
    policy_client: PolicyClient,
    env_backend: EnvBackend,
    config: SearchConfig,
    theorem: TheoremSpec | None = None,
    max_tactics_per_step_item: int | None = None,
) -> ExpansionOutcome:
    """Sample tactics and expand one open OR state."""

    if state_node.is_terminal:
        return ExpansionOutcome(actions=[], tactic_calls_used=0)
    if state_node.state.state_token is None:
        raise ValueError("cannot expand a state without state_token")
    if not has_tactic_budget(config, tree.tactic_calls_made):
        return ExpansionOutcome(actions=[], tactic_calls_used=0)
    if _has_open_negation_action(state_node):
        negation_outcome = await maybe_apply_negation(
            tree,
            state_node,
            theorem=theorem,
            policy_client=policy_client,
            env_backend=env_backend,
            config=config,
            max_tactics_per_step_item=max_tactics_per_step_item,
        )
        return ExpansionOutcome(
            actions=negation_outcome.actions,
            tactic_calls_used=negation_outcome.tactic_calls_used,
            operational_status=negation_outcome.operational_status,
            negation_attempts=negation_outcome.attempts,
            initialized_negation=negation_outcome.initialized,
        )

    tactic_limit = min(
        config.tactics_per_expansion,
        config.max_tactic_calls - tree.tactic_calls_made,
    )
    if max_tactics_per_step_item is not None:
        tactic_limit = min(tactic_limit, max_tactics_per_step_item)
    sampled_batches = await policy_client.sample_tactics(
        [state_node.state],
        n=tactic_limit,
        context=[_policy_context_for_state(state_node)],
    )
    tactic_samples = _single_policy_batch(sampled_batches)
    priors = empirical_action_priors(tactic_samples)
    existing_tactics = {action.tactic for action in state_node.actions}
    # Keep priors on the original sample denominator, even after removing
    # already-tried tactics; this preserves the policy's empirical confidence.
    new_priors = [
        (tactic, prior)
        for tactic, prior in priors
        if tactic not in existing_tactics
    ]
    if not new_priors:
        negation_outcome = await _maybe_apply_source_negation(
            tree,
            state_node,
            theorem=theorem,
            policy_client=policy_client,
            env_backend=env_backend,
            config=config,
            max_tactics_per_step_item=max_tactics_per_step_item,
        )
        return ExpansionOutcome(
            actions=negation_outcome.actions,
            tactic_calls_used=negation_outcome.tactic_calls_used,
            operational_status=negation_outcome.operational_status,
            negation_attempts=negation_outcome.attempts,
            initialized_negation=negation_outcome.initialized,
        )

    tactics = [tactic for tactic, _prior in new_priors]
    step_batch_result = await env_backend.step(
        state_node.node_id,
        state_node.state.state_token,
        tactics,
        goal_group=state_node.focus,
    )
    if len(step_batch_result.results) != len(new_priors):
        raise ValueError("backend step result count did not match tactics")
    completed_attempts = count_tactic_attempts(step_batch_result.results)
    tree.tactic_calls_made = charge_tactic_calls(
        config=config,
        tactic_calls_used=tree.tactic_calls_made,
        completed_attempts=completed_attempts,
    )

    fatal_result = _first_fatal_operational_result(step_batch_result.results)
    if fatal_result is not None:
        state_node.failure_message = _step_failure_message(fatal_result)
        return ExpansionOutcome(
            actions=[],
            tactic_calls_used=completed_attempts,
            operational_status=fatal_result.status,
        )

    first_overloaded_result = _first_overloaded_result(
        step_batch_result.results
    )
    if first_overloaded_result is not None and completed_attempts > 0:
        raise BackendProtocolError(
            "backend returned overloaded mixed with executed step results"
        )

    actions: list[ActionNode] = []
    for index, step_result in enumerate(step_batch_result.results):
        tactic, prior = new_priors[index]
        if not step_result_ran_lean(step_result):
            continue
        actions.append(
            _attach_step_result(
                tree,
                state_node,
                step_result,
                tactic=tactic,
                prior=prior,
            )
        )
    operational_status = None
    if not actions and first_overloaded_result is not None:
        operational_status = first_overloaded_result.status
        state_node.failure_message = _step_failure_message(
            first_overloaded_result
        )
    if (
        operational_status is None
        and state_node.status is not StateNodeStatus.PROVED
    ):
        negation_outcome = await _maybe_apply_source_negation(
            tree,
            state_node,
            theorem=theorem,
            policy_client=policy_client,
            env_backend=env_backend,
            config=config,
            max_tactics_per_step_item=max_tactics_per_step_item,
            advance_after_initialization=False,
        )
        actions.extend(negation_outcome.actions)
        completed_attempts += negation_outcome.tactic_calls_used
        operational_status = negation_outcome.operational_status
        negation_attempts = negation_outcome.attempts
        initialized_negation = negation_outcome.initialized
    else:
        negation_attempts = ()
        initialized_negation = False
    return ExpansionOutcome(
        actions=actions,
        tactic_calls_used=completed_attempts,
        operational_status=operational_status,
        negation_attempts=negation_attempts,
        initialized_negation=initialized_negation,
    )


def proof_states_from_goals(
    parent_state: FactorizedProofState,
    *,
    state_token: str,
    goals: list[ExecGoalInfo],
) -> list[ChildState]:
    """Split a backend post-step state into child OR states by coupling.

    Goals are grouped by the transitive closure of their metavariable coupling
    (``sibling_dep``). A single group is the whole state and resumes
    whole-state (``focus=None``); multiple groups each become a child that
    resumes its own goal subset via ``goal_group``. Independent subgoals thus
    become separate AND children that search can prove in parallel branches.
    """

    if not goals:
        return []
    groups = _goal_coupling_groups(goals)
    if len(groups) == 1:
        return [
            ChildState(
                state=_proof_state_for_group(
                    parent_state,
                    state_token=state_token,
                    goals=goals,
                    indices=groups[0],
                ),
                focus=None,
            )
        ]
    return [
        ChildState(
            state=_proof_state_for_group(
                parent_state,
                state_token=state_token,
                goals=goals,
                indices=group,
            ),
            focus=tuple(group),
        )
        for group in groups
    ]


def _proof_state_for_group(
    parent_state: FactorizedProofState,
    *,
    state_token: str,
    goals: list[ExecGoalInfo],
    indices: list[int],
) -> FactorizedProofState:
    components = [goal_info_to_component(goals[index]) for index in indices]
    return FactorizedProofState(
        env_profile=parent_state.env_profile,
        goal_components=components,
        pretty_state=_render_pretty_state(components),
        state_token=state_token,
    )


def _goal_coupling_groups(goals: list[ExecGoalInfo]) -> list[list[int]]:
    parents = list(range(len(goals)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for index, goal in enumerate(goals):
        for sibling_index in goal.sibling_dep:
            if sibling_index < 0 or sibling_index >= len(goals):
                raise ValueError("goal sibling_dep index out of range")
            union(index, sibling_index)

    groups_by_root: dict[int, list[int]] = {}
    for index in range(len(goals)):
        groups_by_root.setdefault(find(index), []).append(index)
    return sorted(groups_by_root.values(), key=lambda group: group[0])


def goal_info_to_component(goal: ExecGoalInfo) -> GoalComponent:
    """Convert lean-client goal wire data into a proof-state component."""

    return GoalComponent(
        target=goal.target,
        pretty=goal.pretty or goal.target,
        hypotheses=[
            LocalContextEntry(
                name=hypothesis.name,
                type=hypothesis.type,
                value=hypothesis.value,
            )
            for hypothesis in goal.hypotheses
        ],
        name=goal.name,
    )


def _attach_step_result(
    tree: SearchTree,
    state_node: StateNode,
    step_result: ExecStepResult,
    *,
    tactic: str,
    prior: float,
) -> ActionNode:
    action = tree.add_action(state_node, tactic, prior=prior)
    forbidden_token = find_forbidden_proof_placeholder_token(tactic)
    if forbidden_token is not None:
        tree.mark_action_dead(
            action,
            message=(
                "forbidden proof placeholder token: "
                f"{forbidden_token}"
            ),
        )
        return action
    if step_result.status == "complete":
        tree.mark_action_proved(action)
        return action
    if step_result.status == "error":
        tree.mark_action_dead(
            action,
            message=_step_failure_message(step_result),
        )
        return action
    if step_result.status != "open":
        raise ValueError(
            f"unexpected executed step status: {step_result.status}"
        )
    if not step_result.goals:
        tree.mark_action_proved(action)
        return action
    if step_result.state_token is None:
        tree.mark_action_dead(
            action,
            message="open step result did not include state_token",
        )
        return action

    for child in proof_states_from_goals(
        state_node.state,
        state_token=step_result.state_token,
        goals=step_result.goals,
    ):
        tree.add_child_state(action, child.state, focus=child.focus)
    return action


def _single_policy_batch(sampled_batches: list[list[str]]) -> list[str]:
    if len(sampled_batches) != 1:
        raise ValueError("policy_client must return one tactic batch")
    return sampled_batches[0]


async def _maybe_apply_source_negation(
    tree: SearchTree,
    state_node: StateNode,
    *,
    theorem: TheoremSpec | None,
    policy_client: PolicyClient,
    env_backend: EnvBackend,
    config: SearchConfig,
    max_tactics_per_step_item: int | None,
    advance_after_initialization: bool = True,
) -> NegationOutcome:
    if state_node.is_negation_context:
        return NegationOutcome(actions=[], tactic_calls_used=0)
    return await maybe_apply_negation(
        tree,
        state_node,
        theorem=theorem,
        policy_client=policy_client,
        env_backend=env_backend,
        config=config,
        max_tactics_per_step_item=max_tactics_per_step_item,
        advance_after_initialization=advance_after_initialization,
    )


def _has_open_negation_action(state_node: StateNode) -> bool:
    return any(
        action.tactic == NEGATION_ACTION_TACTIC
        and action.status is ActionNodeStatus.OPEN
        and not action.children
        for action in state_node.actions
    )


def _policy_context_for_state(state_node: StateNode) -> PolicyContext:
    return PolicyContext(proof_prefix=_proof_prefix_for_state(state_node))


def _proof_prefix_for_state(state_node: StateNode) -> str:
    from leanfoundry.proofsearch._tree_init import (
        SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
    )

    tactics: list[str] = []
    action = state_node.parent_action
    while action is not None:
        if action.tactic not in {
            SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
            NEGATION_ACTION_TACTIC,
        }:
            tactics.append(action.tactic)
        action = action.parent_state.parent_action
    return "\n".join(reversed(tactics))


def _first_fatal_operational_result(
    step_results: list[ExecStepResult],
) -> ExecStepResult | None:
    for step_result in step_results:
        if step_result.status in _FATAL_OPERATIONAL_STATUSES:
            return step_result
    return None


def _first_overloaded_result(
    step_results: list[ExecStepResult],
) -> ExecStepResult | None:
    for step_result in step_results:
        if step_result.status == "overloaded":
            return step_result
    return None


def _render_pretty_state(components: list[GoalComponent]) -> str:
    return "\n\n".join(component.pretty for component in components)


def _step_failure_message(step_result: ExecStepResult) -> str:
    if not step_result.messages:
        return step_result.status
    return "\n".join(
        f"{message.severity}: {message.data}"
        for message in step_result.messages
    )


__all__ = [
    "BackendProtocolError",
    "ChildState",
    "ExpansionOutcome",
    "expand_state",
    "goal_info_to_component",
    "proof_states_from_goals",
]
