from __future__ import annotations

from leanfoundry.proofsearch._backprop import (
    backpropagate_action,
    backpropagate_actions,
    update_value_backup,
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

    backpropagate_action(action)

    assert action.visit_count == 1
    assert tree.root.visit_count == 1
    assert tree.root.status is StateNodeStatus.OPEN


def test_backpropagate_action_accumulates_repeated_visits() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "simp", prior=1.0)
    tree.mark_action_dead(action, message="failed")

    backpropagate_action(action)
    backpropagate_action(action)

    assert action.visit_count == 2
    assert tree.root.visit_count == 2


def test_backpropagate_action_accumulates_ancestor_action_visits() -> None:
    tree = SearchTree.create("search", make_state(1))
    root_action = tree.add_action(tree.root, "constructor", prior=1.0)
    child_state = tree.add_child_state(
        root_action,
        make_state(1, token="child"),
    )
    child_action = tree.add_action(child_state, "trivial", prior=1.0)
    tree.mark_action_proved(child_action)

    backpropagate_action(child_action)
    backpropagate_action(child_action)

    assert child_action.visit_count == 2
    assert child_state.visit_count == 2
    assert root_action.visit_count == 2
    assert tree.root.visit_count == 2


def test_backpropagate_action_default_does_not_update_values() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "bad", prior=1.0)
    tree.mark_action_dead(action, message="failed")

    backpropagate_action(action)

    assert action.value_estimate is None
    assert tree.root.value_estimate is None


def test_backpropagate_action_walks_to_root() -> None:
    tree = SearchTree.create("search", make_state(1))
    root_action = tree.add_action(tree.root, "constructor", prior=1.0)
    child_state = tree.add_child_state(
        root_action,
        make_state(1, token="child"),
    )
    child_action = tree.add_action(child_state, "trivial", prior=1.0)
    tree.mark_action_proved(child_action)

    backpropagate_action(child_action)

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

    backpropagate_actions([first, second])

    assert first.visit_count == 1
    assert second.visit_count == 1
    assert tree.root.visit_count == 2


def test_backpropagate_actions_forwards_value_update_flag() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "bad", prior=1.0)
    tree.mark_action_dead(action, message="failed")

    backpropagate_actions([action], update_values=True)

    assert action.value_estimate == 0.0
    assert tree.root.value_estimate == 0.0


def test_backpropagate_actions_default_does_not_update_values() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "bad", prior=1.0)
    tree.mark_action_dead(action, message="failed")

    backpropagate_actions([action])

    assert action.value_estimate is None
    assert tree.root.value_estimate is None


def test_backpropagate_action_can_update_and_or_values() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    left = tree.add_child_state(action, make_state(1, token="left"))
    right = tree.add_child_state(action, make_state(1, token="right"))
    left.value_estimate = 0.5
    right.value_estimate = 0.25

    backpropagate_action(action, update_values=True)

    assert action.value_estimate == 0.125
    assert tree.root.value_estimate == 0.125


def test_value_backup_assigns_terminal_action_values() -> None:
    tree = SearchTree.create("search", make_state(1))
    proved_action = tree.add_action(tree.root, "trivial", prior=0.5)
    dead_action = tree.add_action(tree.root, "bad", prior=0.5)
    tree.mark_action_proved(proved_action)
    tree.mark_action_dead(dead_action, message="failed")

    update_value_backup(dead_action)
    update_value_backup(proved_action)

    assert dead_action.value_estimate == 0.0
    assert proved_action.value_estimate == 1.0
    assert tree.root.value_estimate == 1.0


def test_value_backup_uses_max_over_state_actions() -> None:
    tree = SearchTree.create("search", make_state(1))
    weak_action = tree.add_action(tree.root, "weak", prior=0.5)
    strong_action = tree.add_action(tree.root, "strong", prior=0.5)
    weak_action.value_estimate = 0.25
    strong_action.value_estimate = 0.75

    update_value_backup(weak_action)

    assert tree.root.value_estimate == 0.75


def test_value_backup_walks_value_updates_to_root() -> None:
    tree = SearchTree.create("search", make_state(1))
    root_action = tree.add_action(tree.root, "constructor", prior=1.0)
    child_state = tree.add_child_state(
        root_action,
        make_state(1, token="child"),
    )
    child_action = tree.add_action(child_state, "trivial", prior=1.0)
    tree.mark_action_proved(child_action)

    update_value_backup(child_action)

    assert child_action.value_estimate == 1.0
    assert child_state.value_estimate == 1.0
    assert root_action.value_estimate == 1.0
    assert tree.root.value_estimate == 1.0


def test_value_backup_uses_terminal_state_values_in_and_product() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    proved_child, disproved_child = tree.add_child_states(
        action,
        [
            (make_state(0, token="proved-child"), None),
            (make_state(1, token="disproved-child"), None),
        ],
    )
    tree.mark_state_disproved(disproved_child, message="negation proof")
    assert proved_child.status is StateNodeStatus.PROVED

    update_value_backup(action)

    assert action.value_estimate == 0.0
    assert tree.root.value_estimate == 0.0


def test_value_backup_uses_proved_state_value_in_and_product() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    left, right = tree.add_child_states(
        action,
        [
            (make_state(0, token="left"), None),
            (make_state(0, token="right"), None),
        ],
    )
    assert left.status is StateNodeStatus.PROVED
    assert right.status is StateNodeStatus.PROVED

    update_value_backup(action)

    assert action.value_estimate == 1.0
    assert tree.root.value_estimate == 1.0


def test_value_backup_uses_proved_child_value_for_open_action() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    child = tree.add_child_state(action, make_state(1, token="child"))
    child.status = StateNodeStatus.PROVED

    update_value_backup(action)

    assert action.value_estimate == 1.0
    assert tree.root.value_estimate == 1.0


def test_value_backup_uses_disproved_state_value_in_and_product() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "constructor", prior=1.0)
    left, right = tree.add_child_states(
        action,
        [
            (make_state(1, token="left"), None),
            (make_state(1, token="right"), None),
        ],
    )
    left.status = StateNodeStatus.DISPROVED
    right.value_estimate = 0.5

    update_value_backup(action)

    assert action.value_estimate == 0.0
    assert tree.root.value_estimate == 0.0


def test_value_backup_assigns_disproved_state_value() -> None:
    tree = SearchTree.create("search", make_state(1))
    tree.mark_state_disproved(tree.root, message="negation proof")

    update_value_backup(tree.add_action(tree.root, "unused", prior=1.0))

    assert tree.root.value_estimate == 0.0


def test_value_backup_clears_state_value_when_actions_have_no_values() -> None:
    tree = SearchTree.create("search", make_state(1))
    action = tree.add_action(tree.root, "try_something", prior=1.0)
    tree.root.value_estimate = 0.75

    update_value_backup(action)

    assert action.value_estimate is None
    assert tree.root.value_estimate is None
