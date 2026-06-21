from __future__ import annotations

import asyncio

import pytest
from lean_client.exec_models import (
    ExecGoalInfo,
    ExecHypothesis,
    ExecMessage,
    ExecStepBatchResult,
    ExecStepResult,
)

from leanfoundry.proofsearch._expansion import (
    ChildState,
    expand_state,
    goal_info_to_component,
    proof_states_from_goals,
)
from leanfoundry.proofsearch._tree import (
    ActionNodeStatus,
    SearchTree,
    StateNodeStatus,
)
from leanfoundry.proofsearch.base import SearchConfig
from leanfoundry.schemas import FactorizedProofState, GoalComponent


class FakePolicyClient:
    def __init__(self, tactics: list[str]) -> None:
        self.tactics = tactics
        self.calls: list[tuple[list[FactorizedProofState], int]] = []

    async def sample_tactics(
        self,
        states,
        *,
        n: int,
        params=None,
    ) -> list[list[str]]:
        self.calls.append((list(states), n))
        return [self.tactics[:n]]

    async def sample_proofs(self, prompts, *, n: int, params=None):
        raise NotImplementedError


class FakeEnvBackend:
    def __init__(self, result: ExecStepBatchResult) -> None:
        self.result = result
        self.step_calls: list[
            tuple[str, str, list[str], tuple[int, ...] | None]
        ] = []

    async def step(
        self,
        node_id: str,
        state_token: str,
        tactics: list[str],
        *,
        goal_group: tuple[int, ...] | None = None,
        timeout_ms: int | None = None,
    ) -> ExecStepBatchResult:
        self.step_calls.append(
            (node_id, state_token, list(tactics), goal_group)
        )
        return self.result


def make_state(*, token: str | None = "root-token") -> FactorizedProofState:
    return FactorizedProofState(
        env_profile="test-env",
        goal_components=[GoalComponent(target="P", pretty="|- P")],
        pretty_state="|- P",
        state_token=token,
    )


def test_goal_info_to_component_preserves_structured_goal_data() -> None:
    goal = ExecGoalInfo(
        target="P x",
        pretty="x : Nat\n|- P x",
        name="case.left",
        hypotheses=[
            ExecHypothesis(name="x", type="Nat"),
            ExecHypothesis(name="h", type="P x", value="proof"),
        ],
    )

    component = goal_info_to_component(goal)

    assert component.target == "P x"
    assert component.pretty == "x : Nat\n|- P x"
    assert component.name == "case.left"
    assert component.hypotheses[0].name == "x"
    assert component.hypotheses[1].value == "proof"


def test_proof_states_split_bundles_coupled_and_splits_independent() -> None:
    # Goals 0 and 2 are metavariable-coupled; goal 1 is independent. The
    # coupled pair stays in one child; the independent goal splits off, each
    # carrying the goal subset (focus) it resumes from the shared token.
    children = proof_states_from_goals(
        make_state(),
        state_token="child-token",
        goals=[
            ExecGoalInfo(target="A", pretty="|- A", sibling_dep=[2]),
            ExecGoalInfo(target="B", pretty="|- B"),
            ExecGoalInfo(target="C", pretty="|- C", sibling_dep=[0]),
        ],
    )

    assert len(children) == 2
    coupled, independent = children
    assert coupled.focus == (0, 2)
    assert [g.target for g in coupled.state.goal_components] == ["A", "C"]
    assert coupled.state.state_token == "child-token"
    assert independent.focus == (1,)
    assert [g.target for g in independent.state.goal_components] == ["B"]


def test_proof_states_single_group_steps_whole_state_without_focus() -> None:
    # A single coupling group is the whole state, so it needs no narrowing:
    # focus is None and the child steps whole-state (no goal.continue).
    children = proof_states_from_goals(
        make_state(),
        state_token="child-token",
        goals=[ExecGoalInfo(target="A", pretty="|- A")],
    )

    assert len(children) == 1
    assert isinstance(children[0], ChildState)
    assert children[0].focus is None
    assert [g.target for g in children[0].state.goal_components] == ["A"]


def test_proof_states_reject_invalid_sibling_dependency() -> None:
    with pytest.raises(ValueError, match="sibling_dep"):
        proof_states_from_goals(
            make_state(),
            state_token="child-token",
            goals=[ExecGoalInfo(target="A", pretty="|- A", sibling_dep=[1])],
        )


def test_expand_state_calls_policy_and_backend_once() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(
        [
            "-- try constructor\nconstructor",
            "simp",
            "-- try constructor\nconstructor",
        ]
    )
    step_result = ExecStepBatchResult(
        node_id=tree.root.node_id,
        results=[
            ExecStepResult(
                tactic="normalized constructor",
                status="open",
                state_token="child-token",
                goals=[ExecGoalInfo(target="A", pretty="|- A")],
            ),
            ExecStepResult(tactic="simp", status="complete"),
        ],
    )
    env_backend = FakeEnvBackend(step_result)

    outcome = asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=env_backend,
            config=SearchConfig(max_tactic_calls=5, tactics_per_expansion=3),
        )
    )

    assert policy.calls[0][1] == 3
    assert env_backend.step_calls == [
        (
            "search:0",
            "root-token",
            ["-- try constructor\nconstructor", "simp"],
            None,
        )
    ]
    assert outcome.tactic_calls_used == 2
    assert tree.tactic_calls_made == 2
    assert outcome.actions[0].tactic == "-- try constructor\nconstructor"
    assert outcome.actions[0].prior == pytest.approx(2 / 3)
    assert outcome.actions[0].children[0].state.state_token == "child-token"
    assert outcome.actions[1].status is ActionNodeStatus.PROVED
    assert tree.root.status is StateNodeStatus.PROVED


def test_expand_state_splits_goals_and_focuses_child_step() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["constructor"])
    # constructor yields a coupled pair (goals 0, 2) and an independent goal 1.
    backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[
                ExecStepResult(
                    tactic="constructor",
                    status="open",
                    state_token="result-token",
                    goals=[
                        ExecGoalInfo(
                            target="A", pretty="|- A", sibling_dep=[2]
                        ),
                        ExecGoalInfo(target="B", pretty="|- B"),
                        ExecGoalInfo(
                            target="C", pretty="|- C", sibling_dep=[0]
                        ),
                    ],
                )
            ],
        )
    )

    outcome = asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=backend,
            config=SearchConfig(max_tactic_calls=10, tactics_per_expansion=1),
        )
    )

    # The root has no focus, so it stepped whole-state.
    assert backend.step_calls[0][3] is None
    action = outcome.actions[0]
    assert action.status is ActionNodeStatus.OPEN
    assert [child.focus for child in action.children] == [(0, 2), (1,)]
    coupled_child, independent_child = action.children
    coupled_targets = [g.target for g in coupled_child.state.goal_components]
    assert coupled_targets == ["A", "C"]

    # Expanding the independent split child resumes only its goal subset: the
    # next step carries goal_group equal to that child's focus.
    leaf_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=independent_child.node_id,
            results=[ExecStepResult(tactic="trivial", status="complete")],
        )
    )
    asyncio.run(
        expand_state(
            tree,
            independent_child,
            policy_client=FakePolicyClient(["trivial"]),
            env_backend=leaf_backend,
            config=SearchConfig(max_tactic_calls=10, tactics_per_expansion=1),
        )
    )

    assert leaf_backend.step_calls[0][3] == (1,)
    assert independent_child.status is StateNodeStatus.PROVED


def test_expand_state_respects_per_step_item_cap() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["a", "b", "c", "d"])
    backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[ExecStepResult(tactic="a", status="error")],
        )
    )

    asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=backend,
            config=SearchConfig(max_tactic_calls=10, tactics_per_expansion=4),
            max_tactics_per_step_item=1,
        )
    )

    # tactics_per_expansion=4 and budget=10, but the per-step-item cap is 1.
    assert policy.calls[0][1] == 1
    assert backend.step_calls[0][2] == ["a"]


def test_expand_state_surfaces_operational_status_without_budget() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["simp"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[
                ExecStepResult(
                    tactic="simp",
                    status="invalid_state_token",
                    messages=[
                        ExecMessage(
                            severity="error",
                            data="state token expired",
                        )
                    ],
                )
            ],
        )
    )

    outcome = asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=env_backend,
            config=SearchConfig(max_tactic_calls=5, tactics_per_expansion=1),
        )
    )

    assert outcome.actions == []
    assert outcome.tactic_calls_used == 0
    assert outcome.operational_status == "invalid_state_token"
    assert tree.tactic_calls_made == 0
    assert tree.root.failure_message == "error: state token expired"


def test_expand_state_rejects_mixed_overloaded_and_executed_results() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["trivial", "simp"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[
                ExecStepResult(tactic="trivial", status="complete"),
                ExecStepResult(
                    tactic="simp",
                    status="overloaded",
                    messages=[
                        ExecMessage(
                            severity="error",
                            data="worker unavailable",
                        )
                    ],
                ),
            ],
        )
    )

    with pytest.raises(ValueError, match="overloaded mixed"):
        asyncio.run(
            expand_state(
                tree,
                tree.root,
                policy_client=policy,
                env_backend=env_backend,
                config=SearchConfig(
                    max_tactic_calls=5,
                    tactics_per_expansion=2,
                ),
            )
        )

    assert tree.tactic_calls_made == 1
    assert tree.root.actions == []
    assert tree.root.status is StateNodeStatus.OPEN
    assert tree.root.failure_message is None


def test_expand_state_surfaces_all_overloaded_results_without_budget() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["trivial", "simp"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[
                ExecStepResult(
                    tactic="trivial",
                    status="overloaded",
                    messages=[
                        ExecMessage(
                            severity="error",
                            data="worker unavailable",
                        )
                    ],
                ),
                ExecStepResult(tactic="simp", status="overloaded"),
            ],
        )
    )

    outcome = asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=env_backend,
            config=SearchConfig(max_tactic_calls=5, tactics_per_expansion=2),
        )
    )

    assert outcome.actions == []
    assert outcome.tactic_calls_used == 0
    assert outcome.operational_status == "overloaded"
    assert tree.tactic_calls_made == 0
    assert tree.root.failure_message == "error: worker unavailable"


def test_expand_state_discards_partial_actions_on_fatal_status() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["trivial", "simp"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[
                ExecStepResult(tactic="trivial", status="complete"),
                ExecStepResult(
                    tactic="simp",
                    status="cancelled",
                    messages=[
                        ExecMessage(
                            severity="error",
                            data="item cancelled",
                        )
                    ],
                ),
            ],
        )
    )

    outcome = asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=env_backend,
            config=SearchConfig(max_tactic_calls=5, tactics_per_expansion=2),
        )
    )

    assert outcome.actions == []
    assert outcome.tactic_calls_used == 1
    assert outcome.operational_status == "cancelled"
    assert tree.tactic_calls_made == 1
    assert tree.root.status is StateNodeStatus.OPEN
    assert tree.root.failure_message == "error: item cancelled"


def test_expand_state_treats_open_empty_goals_as_structurally_proved() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["trivial"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[
                ExecStepResult(
                    tactic="trivial",
                    status="open",
                    state_token="empty-token",
                    goals=[],
                )
            ],
        )
    )

    outcome = asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=env_backend,
            config=SearchConfig(max_tactic_calls=5, tactics_per_expansion=1),
        )
    )

    assert outcome.actions[0].status is ActionNodeStatus.PROVED
    assert tree.root.status is StateNodeStatus.PROVED


def test_expand_state_skips_already_tried_tactics() -> None:
    tree = SearchTree.create("search", make_state())
    tree.add_action(tree.root, "simp", prior=1.0)
    policy = FakePolicyClient(["simp", "omega"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[ExecStepResult(tactic="omega", status="complete")],
        )
    )

    asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=env_backend,
            config=SearchConfig(max_tactic_calls=5, tactics_per_expansion=2),
        )
    )

    assert env_backend.step_calls[0][2] == ["omega"]
    assert [action.tactic for action in tree.root.actions] == ["simp", "omega"]


def test_expand_state_rejects_short_backend_result_list() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["simp", "omega"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[ExecStepResult(tactic="simp", status="complete")],
        )
    )

    with pytest.raises(ValueError, match="result count"):
        asyncio.run(
            expand_state(
                tree,
                tree.root,
                policy_client=policy,
                env_backend=env_backend,
                config=SearchConfig(
                    max_tactic_calls=5,
                    tactics_per_expansion=2,
                ),
            )
        )

    assert tree.tactic_calls_made == 0


def test_expand_state_marks_error_result_dead_with_message() -> None:
    tree = SearchTree.create("search", make_state())
    policy = FakePolicyClient(["bad"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(
            node_id=tree.root.node_id,
            results=[
                ExecStepResult(
                    tactic="bad",
                    status="error",
                    messages=[ExecMessage(severity="error", data="failed")],
                )
            ],
        )
    )

    outcome = asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=env_backend,
            config=SearchConfig(max_tactic_calls=5, tactics_per_expansion=1),
        )
    )

    assert outcome.actions[0].status is ActionNodeStatus.DEAD
    assert outcome.actions[0].failure_message == "error: failed"
    assert tree.root.status is StateNodeStatus.OPEN


def test_expand_state_does_nothing_without_budget() -> None:
    tree = SearchTree.create("search", make_state())
    tree.tactic_calls_made = 1
    policy = FakePolicyClient(["simp"])
    env_backend = FakeEnvBackend(
        ExecStepBatchResult(node_id=tree.root.node_id)
    )

    outcome = asyncio.run(
        expand_state(
            tree,
            tree.root,
            policy_client=policy,
            env_backend=env_backend,
            config=SearchConfig(max_tactic_calls=1),
        )
    )

    assert outcome.actions == []
    assert outcome.tactic_calls_used == 0
    assert policy.calls == []
    assert env_backend.step_calls == []
