"""Conservative synthetic-negation checks for tree search."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from lean_client.exec_models import ExecGoalInfo, ExecStepResult

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient
from leanfoundry.proofsearch._budgets import (
    charge_tactic_calls,
    count_tactic_attempts,
    step_result_ran_lean,
)
from leanfoundry.proofsearch._lean_tokens import (
    find_forbidden_proof_placeholder_token,
)
from leanfoundry.proofsearch._tree import (
    ActionNode,
    ActionNodeStatus,
    SearchTree,
    StateNode,
)
from leanfoundry.proofsearch.base import SearchConfig
from leanfoundry.proofsearch.provenance import should_try_negation
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
    LocalContextEntry,
    NegationAttempt,
    NegationTacticAttempt,
    TheoremSpec,
)

NEGATION_ACTION_TACTIC = "__leanfoundry_negation_check__"
_LEAN_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'.]*")
_FATAL_OPERATIONAL_STATUSES = frozenset({"invalid_state_token", "cancelled"})


@dataclass(frozen=True, slots=True)
class NegationOutcome:
    """Result of one synthetic negation check."""

    actions: list[ActionNode]
    tactic_calls_used: int
    operational_status: str | None = None
    attempts: tuple[NegationAttempt, ...] = ()
    initialized: bool = False


async def maybe_apply_negation(
    tree: SearchTree,
    state_node: StateNode,
    *,
    theorem: TheoremSpec | None,
    policy_client: PolicyClient,
    env_backend: EnvBackend,
    config: SearchConfig,
    max_tactics_per_step_item: int | None = None,
    advance_after_initialization: bool = True,
) -> NegationOutcome:
    """Initialize or advance negation search for one single-goal state.

    This is deliberately conservative. It renders a standalone negated theorem
    only when the local context can be represented as simple Lean binders. The
    tactics used to prove the synthetic negation are not policy positives for
    the original state; a successful check marks the original state DISPROVED.
    """

    existing_action = _open_childless_negation_action(state_node)
    if existing_action is not None:
        return await _advance_negation_action(
            tree,
            state_node,
            existing_action,
            policy_client=policy_client,
            env_backend=env_backend,
            config=config,
            max_tactics_per_step_item=max_tactics_per_step_item,
        )

    if not _should_attempt_negation(state_node, theorem, config):
        return NegationOutcome(actions=[], tactic_calls_used=0)
    if _has_negation_action(state_node):
        return NegationOutcome(actions=[], tactic_calls_used=0)

    action = tree.add_action(
        state_node,
        NEGATION_ACTION_TACTIC,
        prior=_negation_action_prior(config),
    )
    action.disproves_parent = True
    assert theorem is not None
    rendered = _render_negated_theorem(theorem, state_node)
    if rendered is None:
        tree.mark_action_dead(
            action,
            message="negation unsupported for this proof state",
        )
        return NegationOutcome(
            actions=[action],
            tactic_calls_used=0,
            attempts=(
                _negation_attempt(
                    state_node,
                    status="unsupported",
                ),
            ),
        )

    response = await env_backend.create_states(
        tree.search_id,
        rendered.code,
        env_profile=theorem.env_profile,
    )
    if len(response.items) != 1:
        tree.mark_action_dead(
            action,
            message="negation create_states returned multiple items",
        )
        return NegationOutcome(
            actions=[action],
            tactic_calls_used=0,
            attempts=(
                _negation_attempt(
                    state_node,
                    status="create_protocol_error",
                    rendered=rendered,
                ),
            ),
        )
    item = response.items[0]
    if item.status != "open" or len(item.states) != 1:
        tree.mark_action_dead(
            action,
            message=f"negation initialization status: {item.status}",
        )
        return NegationOutcome(
            actions=[action],
            tactic_calls_used=0,
            attempts=(
                _negation_attempt(
                    state_node,
                    status=f"create_{item.status}",
                    rendered=rendered,
                ),
            ),
        )

    action.negation_state = _state_info_to_proof_state(
        theorem,
        item.states[0],
    )
    action.negation_rendered_lean = rendered.code
    action.negation_theorem_name = rendered.theorem_name
    tree.add_child_state(action, action.negation_state)
    return NegationOutcome(
        actions=[],
        tactic_calls_used=0,
        initialized=True,
    )


async def _advance_negation_action(
    tree: SearchTree,
    state_node: StateNode,
    action: ActionNode,
    *,
    policy_client: PolicyClient,
    env_backend: EnvBackend,
    config: SearchConfig,
    max_tactics_per_step_item: int | None,
) -> NegationOutcome:
    rendered = _rendered_negation_from_action(action)
    negation_state = action.negation_state
    if rendered is None or negation_state is None:
        tree.mark_action_dead(
            action,
            message="negation action missing initialized backend state",
        )
        return NegationOutcome(
            actions=[action],
            tactic_calls_used=0,
            attempts=(
                _negation_attempt(
                    state_node,
                    status="internal_protocol_error",
                    rendered=rendered,
                ),
            ),
        )

    remaining_budget = config.max_tactic_calls - tree.tactic_calls_made
    if remaining_budget < 1:
        tree.mark_action_dead(action, message="negation budget exhausted")
        return NegationOutcome(
            actions=[action],
            tactic_calls_used=0,
            attempts=(
                _negation_attempt(
                    state_node,
                    status="budget_exhausted",
                    rendered=rendered,
                ),
            ),
        )
    tactic_limit = min(config.tactics_per_expansion, remaining_budget)
    if max_tactics_per_step_item is not None:
        tactic_limit = min(tactic_limit, max_tactics_per_step_item)

    sampled_batches = await policy_client.sample_tactics(
        [negation_state],
        n=tactic_limit,
    )
    sampled_tactics = _single_policy_batch(sampled_batches)
    tactics = [
        tactic
        for tactic in sampled_tactics
        if tactic not in action.negation_tried_tactics
    ]
    if not tactics:
        status = "policy_empty"
        message = "negation policy returned none"
        if sampled_tactics:
            status = "policy_repeated"
            message = "negation policy returned only tried tactics"
        tree.mark_action_dead(action, message=message)
        return NegationOutcome(
            actions=[action],
            tactic_calls_used=0,
            attempts=(
                _negation_attempt(
                    state_node,
                    status=status,
                    rendered=rendered,
                    negation_state=negation_state,
                ),
            ),
        )

    step_item_id = _negation_step_item_id(state_node, action)
    step_batch_result = await env_backend.step(
        step_item_id,
        negation_state.state_token or "",
        tactics,
    )
    if len(step_batch_result.results) != len(tactics):
        raise ValueError("negation step result count did not match tactics")
    completed_attempts = count_tactic_attempts(step_batch_result.results)
    tree.tactic_calls_made = charge_tactic_calls(
        config=config,
        tactic_calls_used=tree.tactic_calls_made,
        completed_attempts=completed_attempts,
    )
    for step_result in step_batch_result.results:
        if step_result_ran_lean(step_result):
            action.negation_tried_tactics.add(step_result.tactic)

    fatal_result = _first_fatal_operational_result(step_batch_result.results)
    if fatal_result is not None:
        tree.mark_action_dead(
            action,
            message=f"negation operational status: {fatal_result.status}",
        )
        return NegationOutcome(
            actions=[action],
            tactic_calls_used=completed_attempts,
            operational_status=fatal_result.status,
            attempts=(
                _negation_attempt(
                    state_node,
                    status="operational",
                    rendered=rendered,
                    negation_state=negation_state,
                    step_item_id=step_item_id,
                    tactic_attempts=_tactic_attempts(
                        step_batch_result.results
                    ),
                    tactic_calls_used=completed_attempts,
                    operational_status=fatal_result.status,
                ),
            ),
        )

    proved_tactic = _proved_negation_tactic(step_batch_result.results)
    if proved_tactic is None:
        action.failure_message = "negation not proved"
        return NegationOutcome(
            actions=[action],
            tactic_calls_used=completed_attempts,
            attempts=(
                _negation_attempt(
                    state_node,
                    status="not_proved",
                    rendered=rendered,
                    negation_state=negation_state,
                    step_item_id=step_item_id,
                    tactic_attempts=_tactic_attempts(
                        step_batch_result.results
                    ),
                    tactic_calls_used=completed_attempts,
                ),
            ),
        )

    tree.mark_action_dead(
        action,
        message=f"negation proved by: {proved_tactic}",
    )
    tree.mark_state_disproved(
        state_node,
        message=f"negation proved by: {proved_tactic}",
    )
    if _is_initial_state(state_node):
        tree.mark_state_disproved(
            tree.root,
            message=f"initial negation proved by: {proved_tactic}",
        )
    return NegationOutcome(
        actions=[action],
        tactic_calls_used=completed_attempts,
        attempts=(
            _negation_attempt(
                state_node,
                status="proved",
                rendered=rendered,
                negation_state=negation_state,
                step_item_id=step_item_id,
                tactic_attempts=_tactic_attempts(step_batch_result.results),
                tactic_calls_used=completed_attempts,
                proved=True,
                proved_tactic=proved_tactic,
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class _RenderedNegation:
    code: str
    theorem_name: str


def _negation_attempt(
    state_node: StateNode,
    *,
    status: str,
    rendered: _RenderedNegation | None = None,
    negation_state: FactorizedProofState | None = None,
    step_item_id: str | None = None,
    tactic_attempts: list[NegationTacticAttempt] | None = None,
    tactic_calls_used: int = 0,
    proved: bool = False,
    proved_tactic: str | None = None,
    operational_status: str | None = None,
) -> NegationAttempt:
    goal = state_node.state.goal_components[0]
    return NegationAttempt(
        source_node_id=state_node.node_id,
        source_state=state_node.state,
        negated_target=goal.target,
        rendered_lean=rendered.code if rendered is not None else None,
        theorem_name=(
            rendered.theorem_name if rendered is not None else None
        ),
        negation_state=negation_state,
        step_item_id=step_item_id,
        status=status,
        tactic_attempts=tactic_attempts or [],
        tactic_calls_used=tactic_calls_used,
        proved=proved,
        proved_tactic=proved_tactic,
        operational_status=operational_status,
    )


def _tactic_attempts(
    step_results: list[ExecStepResult],
) -> list[NegationTacticAttempt]:
    return [
        NegationTacticAttempt(
            tactic=step_result.tactic,
            status=step_result.status,
            messages=_step_messages(step_result),
        )
        for step_result in step_results
        if step_result_ran_lean(step_result)
    ]


def collect_new_negation_attempts(
    tree: SearchTree,
) -> tuple[NegationAttempt, ...]:
    """Return newly proved synthetic-negation subtree artifacts."""

    attempts: list[NegationAttempt] = []
    for action in _iter_actions(tree.root):
        if not action.disproves_parent:
            continue
        if not action.disproof_proved:
            continue
        if action.negation_attempt_recorded:
            continue
        action.negation_attempt_recorded = True
        rendered = _rendered_negation_from_action(action)
        negation_root = action.children[0] if action.children else None
        proved_action = (
            negation_root.proved_action()
            if negation_root is not None
            else None
        )
        proved_tactic = (
            proved_action.tactic if proved_action is not None else None
        )
        step_item_id = (
            proved_action.parent_state.node_id
            if proved_action is not None
            else None
        )
        attempts.append(
            _negation_attempt(
                action.parent_state,
                status="proved",
                rendered=rendered,
                negation_state=(
                    negation_root.state
                    if negation_root is not None
                    else action.negation_state
                ),
                step_item_id=step_item_id,
                tactic_attempts=_proved_subtree_tactic_attempts(
                    proved_action
                ),
                tactic_calls_used=action.visit_count,
                proved=True,
                proved_tactic=proved_tactic,
            )
        )
    return tuple(attempts)


def _iter_actions(state_node: StateNode) -> list[ActionNode]:
    actions: list[ActionNode] = []
    for action in state_node.actions:
        actions.append(action)
        for child in action.children:
            actions.extend(_iter_actions(child))
    return actions


def _proved_subtree_tactic_attempts(
    action: ActionNode | None,
) -> list[NegationTacticAttempt]:
    if action is None:
        return []
    status = "complete"
    if action.children:
        status = "proved_subtree"
    return [
        NegationTacticAttempt(
            tactic=action.tactic,
            status=status,
            messages=[],
        )
    ]


def _step_messages(step_result: ExecStepResult) -> list[str]:
    return [
        f"{message.severity}: {message.data}"
        for message in step_result.messages
    ]


def _should_attempt_negation(
    state_node: StateNode,
    theorem: TheoremSpec | None,
    config: SearchConfig,
) -> bool:
    return (
        config.try_negation
        and theorem is not None
        and should_try_negation(theorem)
        and len(state_node.state.goal_components) == 1
        and state_node.state.state_token is not None
        and not state_node.is_terminal
    )


def _has_negation_action(state_node: StateNode) -> bool:
    return any(
        action.tactic == NEGATION_ACTION_TACTIC
        for action in state_node.actions
    )


def _open_childless_negation_action(
    state_node: StateNode,
) -> ActionNode | None:
    for action in state_node.actions:
        if (
            action.tactic == NEGATION_ACTION_TACTIC
            and action.status is ActionNodeStatus.OPEN
            and not action.children
        ):
            return action
    return None


def _negation_action_prior(config: SearchConfig) -> float:
    return 1.0 / (config.tactics_per_expansion + 1)


def _rendered_negation_from_action(
    action: ActionNode,
) -> _RenderedNegation | None:
    if (
        action.negation_rendered_lean is None
        or action.negation_theorem_name is None
    ):
        return None
    return _RenderedNegation(
        code=action.negation_rendered_lean,
        theorem_name=action.negation_theorem_name,
    )


def _negation_step_item_id(
    state_node: StateNode,
    action: ActionNode,
) -> str:
    return f"{state_node.node_id}:negation:{action.visit_count + 1}"


def _render_negated_theorem(
    theorem: TheoremSpec,
    state_node: StateNode,
) -> _RenderedNegation | None:
    goal = state_node.state.goal_components[0]
    binders: list[str] = []
    for hypothesis in goal.hypotheses:
        binder = _hypothesis_binder(hypothesis)
        if binder is None:
            return None
        binders.append(binder)
    theorem_name = _negation_theorem_name(state_node)
    binder_text = f" {' '.join(binders)}" if binders else ""
    declaration = (
        f"theorem {theorem_name}{binder_text} : "
        f"¬ ({goal.target}) := by\n  sorry"
    )
    if theorem.header:
        declaration = f"{theorem.header.rstrip()}\n\n{declaration}"
    return _RenderedNegation(code=declaration, theorem_name=theorem_name)


def _hypothesis_binder(hypothesis: LocalContextEntry) -> str | None:
    if hypothesis.name is None:
        return None
    if _LEAN_IDENT_RE.fullmatch(hypothesis.name) is None:
        return None
    if not hypothesis.type.strip():
        return None
    # Local definitions are abstracted as typed parameters. A proof of the
    # negated target for every value of the parameter is stronger than proving
    # it under the original local definition, so success stays sound.
    return f"({hypothesis.name} : {hypothesis.type})"


def _negation_theorem_name(state_node: StateNode) -> str:
    digest = hashlib.sha1(state_node.node_id.encode("utf-8")).hexdigest()
    return f"leanfoundry_neg_{digest[:12]}"


def _state_info_to_proof_state(
    theorem: TheoremSpec,
    state_info,
) -> FactorizedProofState:
    components = [
        _goal_info_to_component(goal_info) for goal_info in state_info.goals
    ]
    return FactorizedProofState(
        env_profile=theorem.env_profile,
        goal_components=components,
        pretty_state="\n\n".join(component.pretty for component in components),
        state_token=state_info.state_token,
    )


def _goal_info_to_component(goal: ExecGoalInfo) -> GoalComponent:
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


def _single_policy_batch(sampled_batches: list[list[str]]) -> list[str]:
    if len(sampled_batches) != 1:
        raise ValueError("policy_client must return one tactic batch")
    return sampled_batches[0]


def _first_fatal_operational_result(
    step_results: list[ExecStepResult],
) -> ExecStepResult | None:
    for step_result in step_results:
        if step_result.status in _FATAL_OPERATIONAL_STATUSES:
            return step_result
    return None


def _proved_negation_tactic(
    step_results: list[ExecStepResult],
) -> str | None:
    for step_result in step_results:
        if not step_result_ran_lean(step_result):
            continue
        if find_forbidden_proof_placeholder_token(step_result.tactic):
            continue
        if step_result.status == "complete":
            return step_result.tactic
    return None


def _is_initial_state(state_node: StateNode) -> bool:
    from leanfoundry.proofsearch._tree_init import (
        SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
    )

    parent_action = state_node.parent_action
    return (
        parent_action is not None
        and parent_action.tactic == SYNTHETIC_INITIALIZATION_ACTION_TACTIC
    )


__all__ = [
    "NEGATION_ACTION_TACTIC",
    "NegationOutcome",
    "collect_new_negation_attempts",
    "maybe_apply_negation",
]
