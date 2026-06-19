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
    completed_attempts = count_tactic_attempts(step_batch_result.results)
    tree.tactic_calls_made = charge_tactic_calls(
        config=config,
        tactic_calls_used=tree.tactic_calls_made,
        completed_attempts=completed_attempts,
    )

    prior_by_tactic = dict(new_priors)
    actions = [
        _attach_step_result(
            tree,
            state_node,
            step_result,
            prior=prior_by_tactic[step_result.tactic],
        )
        for step_result in step_batch_result.results
    ]
    return ExpansionOutcome(
        actions=actions,
        tactic_calls_used=completed_attempts,
    )


def proof_states_from_goals(
    parent_state: FactorizedProofState,
    *,
    state_token: str,
    goals: list[ExecGoalInfo],
) -> list[FactorizedProofState]:
    """Convert wire goals into bundled child proof states."""

    child_states: list[FactorizedProofState] = []
    for group in _goal_coupling_groups(goals):
        components = [goal_info_to_component(goals[index]) for index in group]
        child_states.append(
            FactorizedProofState(
                env_profile=parent_state.env_profile,
                goal_components=components,
                pretty_state=_render_pretty_state(components),
                state_token=state_token,
            )
        )
    return child_states


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
    prior: float,
) -> ActionNode:
    action = tree.add_action(state_node, step_result.tactic, prior=prior)
    if step_result.status == "complete":
        tree.mark_action_proved(action)
        return action
    if step_result.status != "open":
        tree.mark_action_dead(
            action,
            message=_step_failure_message(step_result),
        )
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
    "proof_states_from_goals",
]
