"""Private deterministic selection helpers for the AND/OR tree."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt
from typing import Protocol

from leanfoundry.proofsearch._tree import (
    ActionNode,
    ActionNodeStatus,
    SearchTree,
    StateNode,
    StateNodeStatus,
)


class SelectionStrategy(Protocol):
    """Pluggable selector for the tree-search wedge."""

    def select(self, tree: SearchTree) -> StateNode | None:
        """Return the next open frontier state, if one exists."""


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


@dataclass(frozen=True, slots=True)
class PuctSelection:
    """PUCT-style descent through OR actions and AND children."""

    c_explore: float = 1.0

    def select(self, tree: SearchTree) -> StateNode | None:
        """Select a frontier state using prior/value UCB descent."""

        return select_frontier_state(
            tree.root,
            c_explore=self.c_explore,
        )


@dataclass(frozen=True, slots=True)
class BestFirstSelection:
    """Global best-first selector over open leaf states."""

    missing_value_score: float = 0.0

    def select(self, tree: SearchTree) -> StateNode | None:
        """Select the open unexpanded leaf with highest value estimate."""

        candidates = list(_open_leaf_states(tree.root))
        if not candidates:
            return select_frontier_state(tree.root)
        indexed_candidates = list(enumerate(candidates))
        _index, state_node = max(
            indexed_candidates,
            key=lambda item: (
                item[1].value_estimate
                if item[1].value_estimate is not None
                else self.missing_value_score,
                item[1].open_goal_count,
                -item[1].visit_count,
                -item[0],
            ),
        )
        return state_node


def _open_leaf_states(root: StateNode) -> list[StateNode]:
    pending = [root]
    leaves: list[StateNode] = []
    while pending:
        state_node = pending.pop(0)
        if state_node.status is not StateNodeStatus.OPEN:
            continue
        open_children = [
            child
            for action in state_node.actions
            if action.status is ActionNodeStatus.OPEN
            for child in action.children
            if child.status is StateNodeStatus.OPEN
        ]
        if not open_children:
            if not state_node.is_expanded:
                leaves.append(state_node)
            continue
        pending.extend(open_children)
    return leaves


__all__ = [
    "BestFirstSelection",
    "PuctSelection",
    "SelectionStrategy",
    "action_ucb_score",
    "empirical_action_priors",
    "select_action",
    "select_frontier_state",
    "select_hardest_child",
]
