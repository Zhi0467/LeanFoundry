"""Private deterministic selection helpers for the AND/OR tree."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from math import sqrt

from leanfoundry.proofsearch._tree import (
    ActionNode,
    ActionNodeStatus,
    StateNode,
    StateNodeStatus,
)


def empirical_action_priors(
    tactic_samples: Sequence[str],
) -> list[tuple[str, float]]:
    """Return first-seen tactic strings with empirical sample frequencies."""

    if not tactic_samples:
        return []
    counts = Counter(tactic_samples)
    total = len(tactic_samples)
    priors: list[tuple[str, float]] = []
    seen: set[str] = set()
    for tactic in tactic_samples:
        if tactic in seen:
            continue
        seen.add(tactic)
        priors.append((tactic, counts[tactic] / total))
    return priors


def action_ucb_score(action: ActionNode, *, c_explore: float = 1.0) -> float:
    """Return prior-only PUCT/UCB score when no value estimate exists."""

    exploit = (
        action.value_estimate if action.value_estimate is not None else 0.0
    )
    parent_visits = max(1, action.parent_state.visit_count)
    explore = (
        c_explore
        * action.prior
        * sqrt(parent_visits)
        / (1 + action.visit_count)
    )
    return exploit + explore


def select_action(
    state_node: StateNode,
    *,
    c_explore: float = 1.0,
) -> ActionNode | None:
    """Choose the best open action from an OR state."""

    candidates = [
        (index, action)
        for index, action in enumerate(state_node.actions)
        if action.status is ActionNodeStatus.OPEN
    ]
    if not candidates:
        return None
    _, action = max(
        candidates,
        key=lambda item: (
            action_ucb_score(item[1], c_explore=c_explore),
            -item[1].visit_count,
            -item[0],
        ),
    )
    return action


def select_hardest_child(action: ActionNode) -> StateNode | None:
    """Choose the value-free hardest open child of an AND action."""

    candidates = [
        (index, child)
        for index, child in enumerate(action.children)
        if child.status is StateNodeStatus.OPEN
    ]
    if not candidates:
        return None
    _, child = max(
        candidates,
        key=lambda item: (
            item[1].open_goal_count,
            -item[1].visit_count,
            -item[0],
        ),
    )
    return child


def select_frontier_state(
    root: StateNode,
    *,
    c_explore: float = 1.0,
) -> StateNode | None:
    """Walk OR/AND links until an expandable open state is reached."""

    node = root
    while node.status is StateNodeStatus.OPEN and node.is_expanded:
        action = select_action(node, c_explore=c_explore)
        if action is None:
            return node
        child = select_hardest_child(action)
        if child is None:
            return node
        node = child
    if node.status is StateNodeStatus.OPEN:
        return node
    return None


__all__ = [
    "action_ucb_score",
    "empirical_action_priors",
    "select_action",
    "select_frontier_state",
    "select_hardest_child",
]
