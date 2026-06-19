"""Private expansion helpers for AND/OR tree search."""

from __future__ import annotations

from dataclasses import dataclass

from lean_client.exec_models import ExecGoalInfo, ExecStepResult

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient
from leanfoundry.proofsearch._budgets import (
    charge_tactic_calls,
    count_tactic_attempts,
    has_tactic_budget,
    step_result_ran_lean,
)
from leanfoundry.proofsearch._selection import empirical_action_priors
from leanfoundry.proofsearch._tree import ActionNode, SearchTree, StateNode
from leanfoundry.proofsearch.base import SearchConfig
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
    LocalContextEntry,
)


@dataclass(frozen=True, slots=True)
class ExpansionOutcome:
    """Result of expanding one frontier state."""

    actions: list[ActionNode]
    tactic_calls_used: int
    operational_status: str | None = None


async def expand_state(
    tree: SearchTree,
    state_node: StateNode,
    *,
    policy_client: PolicyClient,
    env_backend: EnvBackend,
    config: SearchConfig,
) -> ExpansionOutcome:
    """Sample tactics and expand one open OR state."""

    if state_node.is_terminal:
        return ExpansionOutcome(actions=[], tactic_calls_used=0)
    if state_node.state.state_token is None:
        raise ValueError("cannot expand a state without state_token")
    if not has_tactic_budget(config, tree.tactic_calls_made):
        return ExpansionOutcome(actions=[], tactic_calls_used=0)

    tactic_limit = min(
        config.tactics_per_expansion,
        config.max_tactic_calls - tree.tactic_calls_made,
    )
    sampled_batches = await policy_client.sample_tactics(
        [state_node.state],
        n=tactic_limit,
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
        return ExpansionOutcome(actions=[], tactic_calls_used=0)

    tactics = [tactic for tactic, _prior in new_priors]
    step_batch_result = await env_backend.step(
        state_node.node_id,
        state_node.state.state_token,
        tactics,
    )
    if len(step_batch_result.results) != len(new_priors):
        raise ValueError("backend step result count did not match tactics")
    completed_attempts = count_tactic_attempts(step_batch_result.results)
    tree.tactic_calls_made = charge_tactic_calls(
        config=config,
        tactic_calls_used=tree.tactic_calls_made,
        completed_attempts=completed_attempts,
    )

    actions: list[ActionNode] = []
    operational_status: str | None = None
    for index, step_result in enumerate(step_batch_result.results):
        tactic, prior = new_priors[index]
        if not step_result_ran_lean(step_result):
            operational_status = step_result.status
            state_node.failure_message = _step_failure_message(step_result)
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
    return ExpansionOutcome(
        actions=actions,
        tactic_calls_used=completed_attempts,
        operational_status=operational_status,
    )


def proof_state_from_goals(
    parent_state: FactorizedProofState,
    *,
    state_token: str,
    goals: list[ExecGoalInfo],
) -> FactorizedProofState:
    """Convert one backend post-step state into one child proof state."""

    components = [goal_info_to_component(goal) for goal in goals]
    return FactorizedProofState(
        env_profile=parent_state.env_profile,
        goal_components=components,
        pretty_state=_render_pretty_state(components),
        state_token=state_token,
    )


def proof_states_from_goals(
    parent_state: FactorizedProofState,
    *,
    state_token: str,
    goals: list[ExecGoalInfo],
) -> list[FactorizedProofState]:
    """Return the v0 whole-state child for a backend post-step state.

    The backend currently returns one token for the whole state, and
    ``EnvBackend.step`` does not expose focused goal stepping. Splitting
    independent goals into separate child nodes is deferred until the protocol
    can resume those bundles soundly.
    """

    if not goals:
        return []
    return [
        proof_state_from_goals(
            parent_state,
            state_token=state_token,
            goals=goals,
        )
    ]


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

    for child_state in proof_states_from_goals(
        state_node.state,
        state_token=step_result.state_token,
        goals=step_result.goals,
    ):
        tree.add_child_state(action, child_state)
    return action


def _single_policy_batch(sampled_batches: list[list[str]]) -> list[str]:
    if len(sampled_batches) != 1:
        raise ValueError("policy_client must return one tactic batch")
    return sampled_batches[0]


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
    "ExpansionOutcome",
    "expand_state",
    "goal_info_to_component",
    "proof_state_from_goals",
    "proof_states_from_goals",
]
