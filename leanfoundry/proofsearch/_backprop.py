"""Private backpropagation helpers for AND/OR tree search."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from leanfoundry.proofsearch._tree import ActionNode, SearchTree, StateNode


@dataclass(frozen=True, slots=True)
class BackpropagationResult:
    """Counts updated during one backpropagation call."""

    action_visits: int
    state_visits: int


def backpropagate_action(
    tree: SearchTree,
    action: ActionNode,
    *,
    visits: int = 1,
) -> BackpropagationResult:
    """Increment visits from one evaluated action back to the root."""

    if visits < 1:
        raise ValueError("visits must be positive")

    tree.refresh_from_action(action)
    action.visit_count += visits
    action_visits = visits
    state_visits = 0

    state_node: StateNode | None = action.parent_state
    while state_node is not None:
        state_node.visit_count += visits
        state_visits += visits

        parent_action = state_node.parent_action
        if parent_action is None:
            break
        parent_action.visit_count += visits
        action_visits += visits
        state_node = parent_action.parent_state

    return BackpropagationResult(
        action_visits=action_visits,
        state_visits=state_visits,
    )


def backpropagate_actions(
    tree: SearchTree,
    actions: Iterable[ActionNode],
) -> BackpropagationResult:
    """Backpropagate every executed action from one expansion."""

    total_action_visits = 0
    total_state_visits = 0
    for action in actions:
        result = backpropagate_action(tree, action)
        total_action_visits += result.action_visits
        total_state_visits += result.state_visits
    return BackpropagationResult(
        action_visits=total_action_visits,
        state_visits=total_state_visits,
    )


__all__ = [
    "BackpropagationResult",
    "backpropagate_action",
    "backpropagate_actions",
]
