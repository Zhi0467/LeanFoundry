"""Private backpropagation helpers for AND/OR tree search."""

from __future__ import annotations

from collections.abc import Iterable

from leanfoundry.proofsearch._tree import (
    ActionNode,
    ActionNodeStatus,
    StateNode,
    StateNodeStatus,
)


def backpropagate_action(
    action: ActionNode,
    *,
    update_values: bool = False,
) -> None:
    """Increment visits from one executed action back to the root.

    Status propagation is owned by ``SearchTree`` mutation methods. Backprop
    only accounts for executed tactic attempts, so each action contributes one
    visit to itself, its parent state, and each ancestor action/state.
    """

    action.visit_count += 1

    state_node: StateNode | None = action.parent_state
    while state_node is not None:
        state_node.visit_count += 1

        parent_action = state_node.parent_action
        if parent_action is None:
            break
        parent_action.visit_count += 1
        state_node = parent_action.parent_state
    if update_values:
        update_value_backup(action)


def backpropagate_actions(
    actions: Iterable[ActionNode],
    *,
    update_values: bool = False,
) -> None:
    """Backpropagate every executed action from one expansion.

    If an expansion executes N tactic candidates, the frontier state and its
    ancestors receive N visits. This keeps each state's visit count equal to
    the sum of its outgoing action visits.
    """

    for action in actions:
        backpropagate_action(action, update_values=update_values)


def update_value_backup(action: ActionNode) -> None:
    """Recompute AND/OR value estimates from one action to the root."""

    current_action: ActionNode | None = action
    while current_action is not None:
        _refresh_action_value(current_action)
        parent_state = current_action.parent_state
        _refresh_state_value(parent_state)
        current_action = parent_state.parent_action


def _refresh_action_value(action: ActionNode) -> None:
    if action.status is ActionNodeStatus.PROVED:
        action.value_estimate = 1.0
        return
    if action.status is ActionNodeStatus.DEAD:
        action.value_estimate = 0.0
        return
    child_values = [_state_value(child) for child in action.children]
    if not child_values or any(value is None for value in child_values):
        return
    product = 1.0
    for value in child_values:
        product *= value
    action.value_estimate = product


def _refresh_state_value(state_node: StateNode) -> None:
    if state_node.status is StateNodeStatus.PROVED:
        state_node.value_estimate = 1.0
        return
    if state_node.status is StateNodeStatus.DISPROVED:
        state_node.value_estimate = 0.0
        return
    action_values = [
        action.value_estimate
        for action in state_node.actions
        if action.value_estimate is not None
    ]
    if action_values:
        state_node.value_estimate = max(action_values)
    else:
        state_node.value_estimate = None


def _state_value(state_node: StateNode) -> float | None:
    if state_node.status is StateNodeStatus.PROVED:
        return 1.0
    if state_node.status is StateNodeStatus.DISPROVED:
        return 0.0
    return state_node.value_estimate


__all__ = [
    "backpropagate_action",
    "backpropagate_actions",
    "update_value_backup",
]
