from __future__ import annotations

import pytest

from leanfoundry.proofsearch._budgets import (
    charge_tactic_calls,
    count_tactic_attempts,
    has_tactic_budget,
    remaining_tactic_calls,
)
from leanfoundry.proofsearch._selection import (
    BestFirstSelection,
    PuctSelection,
    empirical_action_priors,
    select_action,
    select_frontier_state,
    select_hardest_child,
)
from leanfoundry.proofsearch._tree import (
    ActionNodeStatus,
    SearchTree,
    StateNodeStatus,
)
from leanfoundry.proofsearch.base import SearchConfig
from leanfoundry.schemas import FactorizedProofState, GoalComponent
from lean_client.exec_models import ExecStepResult


def make_state(
    goal_count: int,
    *,
    token: str = "state-token",
) -> FactorizedProofState:
    goals = [
        GoalComponent(target=f"P{index}", pretty=f"|- P{index}")
        for index in range(goal_count)
    ]
    pretty_state = "\n".join(goal.pretty for goal in goals)
    return FactorizedProofState(
        env_profile="test-env",
        goal_components=goals,
        pretty_state=pretty_state,
        state_token=token,
    )


def test_or_state_is_proved_when_one_action_is_proved() -> None:
    tree = SearchTree.create("search", make_state(1))
    failed_action = tree.add_action(tree.root, "simp", prior=0.4)
    proved_action = tree.add_action(tree.root, "trivial", prior=0.6)

    tree.mark_action_dead(failed_action, message="tactic failed")
    assert tree.root.status is StateNodeStatus.OPEN

    tree.mark_action_proved(proved_action)

    assert proved_action.status is ActionNodeStatus.PROVED
    assert tree.root.status is StateNodeStatus.PROVED
    assert tree.root.proved_action() is proved_action


def test_state_node_ids_preserve_search_id_for_backend_grouping() -> None:
    tree = SearchTree.create("search:item", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    child = tree.add_child_state(action, make_state(1, token="child"))

    assert tree.root.node_id == "search:item:0"
    assert child.node_id == "search:item:1"
    assert action.action_id == "search:item:0#a0"


def test_and_action_requires_all_children_to_be_proved() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    left = tree.add_child_state(action, make_state(1, token="left"))
    right = tree.add_child_state(action, make_state(1, token="right"))

    with pytest.raises(ValueError, match="child states"):
        tree.mark_action_proved(action)

    left_action = tree.add_action(left, "trivial", prior=1.0)
    tree.mark_action_proved(left_action)

    assert left.status is StateNodeStatus.PROVED
    assert right.status is StateNodeStatus.OPEN
    assert action.status is ActionNodeStatus.OPEN
    assert tree.root.status is StateNodeStatus.OPEN

    right_action = tree.add_action(right, "trivial", prior=1.0)
    tree.mark_action_proved(right_action)

    assert action.status is ActionNodeStatus.PROVED
    assert tree.root.status is StateNodeStatus.PROVED


def test_terminal_action_cannot_receive_children() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "trivial", prior=1.0)
    tree.mark_action_proved(action)

    with pytest.raises(ValueError, match="terminal action"):
        tree.add_child_state(action, make_state(1, token="late"))


def test_and_action_dies_when_any_child_is_disproved() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    left = tree.add_child_state(action, make_state(1, token="left"))
    tree.add_child_state(action, make_state(1, token="right"))

    tree.mark_state_disproved(left, message="negation proof")

    assert left.status is StateNodeStatus.DISPROVED
    assert action.status is ActionNodeStatus.DEAD
    assert tree.root.status is StateNodeStatus.OPEN


def test_unresolved_state_remains_open_after_dead_actions() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "omega", prior=1.0)

    tree.mark_action_dead(action, message="timeout")

    assert action.status is ActionNodeStatus.DEAD
    assert tree.root.status is StateNodeStatus.OPEN


def test_budget_accounting_counts_backend_results() -> None:
    config = SearchConfig(max_tactic_calls=5)

    assert has_tactic_budget(config, 0)
    assert remaining_tactic_calls(config, 3) == 2

    backend_results = [
        ExecStepResult(tactic="simp", status="complete"),
        ExecStepResult(tactic="bad", status="error"),
        ExecStepResult(tactic="retry", status="overloaded"),
    ]

    assert count_tactic_attempts(backend_results) == 2
    assert charge_tactic_calls(
        config=config,
        tactic_calls_used=3,
        completed_attempts=count_tactic_attempts(backend_results),
    ) == 5

    with pytest.raises(ValueError, match="exceed"):
        charge_tactic_calls(
            config=config,
            tactic_calls_used=4,
            completed_attempts=2,
        )

    with pytest.raises(ValueError, match="tactic_calls_used"):
        charge_tactic_calls(
            config=config,
            tactic_calls_used=-1,
            completed_attempts=1,
        )


def test_empirical_priors_preserve_first_seen_full_tactic_text() -> None:
    tactic_with_comment = "-- use the constructor\nconstructor"
    samples = [
        tactic_with_comment,
        "simp",
        tactic_with_comment,
        "trivial",
    ]

    assert empirical_action_priors(samples) == [
        (tactic_with_comment, 0.5),
        ("simp", 0.25),
        ("trivial", 0.25),
    ]


def test_select_action_uses_prior_visits_and_stable_ties() -> None:
    tree = SearchTree.create("search", make_state(1))
    first = tree.add_action(tree.root, "first", prior=0.5)
    second = tree.add_action(tree.root, "second", prior=0.5)
    third = tree.add_action(tree.root, "third", prior=0.75)

    assert select_action(tree.root) is third

    third.visit_count = 10
    assert select_action(tree.root) is first

    first.visit_count = 3
    second.visit_count = 3
    assert select_action(tree.root) is first


def test_select_frontier_uses_value_free_hardest_child() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    easy = tree.add_child_state(action, make_state(1, token="easy"))
    hard = tree.add_child_state(action, make_state(3, token="hard"))

    assert select_hardest_child(action) is hard
    assert select_frontier_state(tree.root) is hard

    hard_action = tree.add_action(hard, "exact h", prior=1.0)
    tree.mark_action_proved(hard_action)

    assert select_frontier_state(tree.root) is easy


def test_puct_selection_wraps_frontier_descent() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    easy = tree.add_child_state(action, make_state(1, token="easy"))
    hard = tree.add_child_state(action, make_state(3, token="hard"))

    assert PuctSelection().select(tree) is hard

    hard_action = tree.add_action(hard, "exact h", prior=1.0)
    tree.mark_action_proved(hard_action)

    assert PuctSelection().select(tree) is easy


def test_best_first_selection_uses_leaf_value_estimates() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    low = tree.add_child_state(action, make_state(1, token="low"))
    high = tree.add_child_state(action, make_state(1, token="high"))
    low.value_estimate = 0.1
    high.value_estimate = 0.9

    assert BestFirstSelection().select(tree) is high


def test_best_first_selection_uses_configured_missing_value_score() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    unknown = tree.add_child_state(action, make_state(1, token="unknown"))
    known = tree.add_child_state(action, make_state(1, token="known"))
    known.value_estimate = 0.2

    assert BestFirstSelection().select(tree) is known
    assert (
        BestFirstSelection(missing_value_score=0.5).select(tree)
        is unknown
    )
