from __future__ import annotations

import pytest

from leanfoundry.proofsearch._backprop import (
    backpropagate_action,
    backpropagate_actions,
)
from leanfoundry.proofsearch._tree import (
    ActionNodeStatus,
    SearchTree,
    StateNodeStatus,
)
from leanfoundry.schemas import FactorizedProofState, GoalComponent


def make_state(
    goal_count: int,
    *,
    token: str = "token",
) -> FactorizedProofState:
    goals = [
        GoalComponent(target=f"P{index}", pretty=f"|- P{index}")
        for index in range(goal_count)
    ]
    return FactorizedProofState(
        env_profile="test-env",
        goal_components=goals,
        pretty_state="\n".join(goal.pretty for goal in goals),
        state_token=token,
    )


def test_backpropagate_action_updates_action_and_root_visits() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "simp", prior=1.0)
    tree.mark_action_dead(action, message="failed")

    result = backpropagate_action(tree, action)

    assert result.action_visits == 1
    assert result.state_visits == 1
    assert action.visit_count == 1
    assert tree.root.visit_count == 1
    assert tree.root.status is StateNodeStatus.OPEN


def test_backpropagate_action_walks_to_root() -> None:
    tree = SearchTree.create("search", make_state(1))
    root_action = tree.add_action(tree.root, "constructor", prior=1.0)
    child_state = tree.add_child_state(
        root_action,
        make_state(1, token="child"),
    )
    child_action = tree.add_action(child_state, "trivial", prior=1.0)
    tree.mark_action_proved(child_action)

    result = backpropagate_action(tree, child_action)

    assert result.action_visits == 2
    assert result.state_visits == 2
    assert child_action.visit_count == 1
    assert child_state.visit_count == 1
    assert root_action.visit_count == 1
    assert tree.root.visit_count == 1
    assert root_action.status is ActionNodeStatus.PROVED
    assert tree.root.status is StateNodeStatus.PROVED


def test_backpropagate_actions_handles_one_expansion_batch() -> None:
    tree = SearchTree.create("search", make_state(1))
    first = tree.add_action(tree.root, "simp", prior=0.5)
    second = tree.add_action(tree.root, "omega", prior=0.5)
    tree.mark_action_dead(first, message="failed")
    tree.mark_action_dead(second, message="failed")

    result = backpropagate_actions(tree, [first, second])

    assert result.action_visits == 2
    assert result.state_visits == 2
    assert first.visit_count == 1
    assert second.visit_count == 1
    assert tree.root.visit_count == 2


def test_backpropagate_rejects_non_positive_visit_counts() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "simp", prior=1.0)

    with pytest.raises(ValueError, match="positive"):
        backpropagate_action(tree, action, visits=0)
