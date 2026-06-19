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
    expand_state,
    goal_info_to_component,
    proof_state_from_goals,
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
        self.step_calls: list[tuple[str, str, list[str]]] = []

    async def step(
        self,
        node_id: str,
        state_token: str,
        tactics: list[str],
        *,
        timeout_ms: int | None = None,
    ) -> ExecStepBatchResult:
        self.step_calls.append((node_id, state_token, list(tactics)))
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


def test_proof_state_from_goals_preserves_whole_backend_state() -> None:
    parent_state = make_state()
    goals = [
        ExecGoalInfo(target="A", pretty="|- A", sibling_dep=[2]),
        ExecGoalInfo(target="B", pretty="|- B"),
        ExecGoalInfo(target="C", pretty="|- C", sibling_dep=[0]),
    ]

    child = proof_state_from_goals(
        parent_state,
        state_token="child-token",
        goals=goals,
    )

    assert [goal.target for goal in child.goal_components] == ["A", "B", "C"]
    assert child.state_token == "child-token"


def test_proof_states_from_goals_returns_one_resumable_child() -> None:
    children = proof_states_from_goals(
        make_state(),
        state_token="child-token",
        goals=[
            ExecGoalInfo(target="A", pretty="|- A"),
            ExecGoalInfo(target="B", pretty="|- B"),
        ],
    )

    assert len(children) == 1
    assert [goal.target for goal in children[0].goal_components] == ["A", "B"]


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
        )
    ]
    assert outcome.tactic_calls_used == 2
    assert tree.tactic_calls_made == 2
    assert outcome.actions[0].tactic == "-- try constructor\nconstructor"
    assert outcome.actions[0].prior == pytest.approx(2 / 3)
    assert outcome.actions[0].children[0].state.state_token == "child-token"
    assert outcome.actions[1].status is ActionNodeStatus.PROVED
    assert tree.root.status is StateNodeStatus.PROVED


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
