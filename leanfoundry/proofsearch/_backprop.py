"""Private backpropagation helpers for AND/OR tree search."""

from __future__ import annotations

from collections.abc import Iterable

from leanfoundry.proofsearch._tree import ActionNode, StateNode


def backpropagate_action(action: ActionNode) -> None:
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


def backpropagate_actions(actions: Iterable[ActionNode]) -> None:
    """Backpropagate every executed action from one expansion.

    If an expansion executes N tactic candidates, the frontier state and its
    ancestors receive N visits. This keeps each state's visit count equal to
    the sum of its outgoing action visits.
    """

    for action in actions:
        backpropagate_action(action)


__all__ = [
    "backpropagate_action",
    "backpropagate_actions",
]
