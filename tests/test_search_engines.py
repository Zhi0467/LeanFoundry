from __future__ import annotations

import asyncio

from lean_client.exec_models import (
    ExecCreateStatesResponse,
    ExecCreateStatesResult,
    ExecGoalInfo,
    ExecLimitsResponse,
    ExecMessage,
    ExecStateInfo,
    ExecStepBatchResult,
    ExecStepResult,
    ExecVerifyResult,
)

from leanfoundry.proofsearch import (
    SearchAlgorithm,
    SearchConfig,
    SearchStatus,
    build_engine,
    run_search_batch,
)
from leanfoundry.proofsearch._selection import (
    BestFirstSelection,
    PuctSelection,
)
from leanfoundry.proofsearch.and_or import AndOrSearchEngine
from leanfoundry.proofsearch.direct import DirectSearchEngine
from leanfoundry.schemas import TheoremSpec


class FakePolicyClient:
    def __init__(
        self,
        *,
        proof_batches: list[list[str]] | None = None,
        tactic_batches: list[list[str]] | None = None,
    ) -> None:
        self.proof_batches = proof_batches or []
        self.tactic_batches = tactic_batches or []
        self.proof_prompts: list[str] = []
        self.tactic_calls: list[tuple[str | None, int]] = []

    async def sample_tactics(
        self,
        states,
        *,
        n: int,
        params=None,
    ) -> list[list[str]]:
        state = states[0]
        self.tactic_calls.append((state.state_token, n))
        return [self.tactic_batches.pop(0)[:n]]

    async def sample_proofs(
        self,
        prompts,
        *,
        n: int,
        params=None,
    ) -> list[list[str]]:
        self.proof_prompts.append(prompts[0])
        return [self.proof_batches.pop(0)[:n]]


class FakeValueClient:
    def __init__(self, values_by_target: dict[str, float]) -> None:
        self.values_by_target = values_by_target
        self.calls: list[list[str]] = []

    async def estimate(self, states) -> list[float]:
        targets = [
            state.goal_components[0].target
            for state in states
            if state.goal_components
        ]
        self.calls.append(targets)
        return [self.values_by_target[target] for target in targets]


class FakeEnvBackend:
    def __init__(
        self,
        *,
        create_states: list[ExecStateInfo] | None = None,
        step_results: list[ExecStepBatchResult] | None = None,
        verify_results: list[ExecVerifyResult] | None = None,
    ) -> None:
        self.create_states_result = create_states or []
        self.step_results = step_results or []
        self.verify_results = verify_results or []
        self.create_calls: list[tuple[str, str]] = []
        self.step_calls: list[
            tuple[str, str, list[str], tuple[int, ...] | None]
        ] = []
        self.verify_calls: list[tuple[str, str, str]] = []
        self.cleanup_calls: list[list[str]] = []

    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def limits(self) -> ExecLimitsResponse:
        return ExecLimitsResponse(
            max_items_per_step_batch=16,
            max_tactics_per_step_item=8,
            max_attempts_per_step_batch=64,
            max_create_items_per_request=16,
            max_pantograph_workers=4,
            max_lean_processes_per_env_profile=4,
            max_in_flight_exec_requests=4,
            max_queued_exec_requests=128,
            max_state_store_bytes=1_000_000,
            max_acquire_timeout_ms=5000,
            max_step_timeout_ms=5000,
            recommended_items_per_step_batch=8,
            recommended_in_flight_step_batches=2,
        )

    async def create_states(
        self,
        item_id: str,
        code: str,
        *,
        env_profile: str | None = None,
    ) -> ExecCreateStatesResponse:
        self.create_calls.append((item_id, code))
        return ExecCreateStatesResponse(
            items=[
                ExecCreateStatesResult(
                    item_id=item_id,
                    status="open",
                    states=self.create_states_result,
                )
            ]
        )

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
        result = self.step_results.pop(0)
        return result.model_copy(update={"node_id": node_id})

    async def verify_one(
        self,
        item_id: str,
        code: str,
        theorem_name: str,
        *,
        allowed_axioms: list[str] | None = None,
        env_profile: str | None = None,
    ) -> ExecVerifyResult:
        self.verify_calls.append((item_id, code, theorem_name))
        if self.verify_results:
            return self.verify_results.pop(0).model_copy(
                update={"item_id": item_id}
            )
        return ExecVerifyResult(
            item_id=item_id,
            status="accepted",
            theorem_name=theorem_name,
        )

    async def cleanup(self, item_ids: list[str]) -> object:
        self.cleanup_calls.append(item_ids)
        return object()

    async def cancel(self, item_ids: list[str]) -> object:
        return object()

    async def stats(self) -> object:
        return object()


def theorem(
    statement: str = "theorem t : True := by\n  sorry",
) -> TheoremSpec:
    return TheoremSpec(
        lean_statement=statement,
        env_profile="test-env",
        header="",
        source="test",
        theorem_name="t",
    )


def root_state(token: str = "root-token") -> ExecStateInfo:
    return ExecStateInfo(
        state_token=token,
        goals=[ExecGoalInfo(target="True", pretty="|- True")],
    )


def test_build_engine_dispatches_supported_algorithms() -> None:
    assert isinstance(build_engine(SearchConfig()), AndOrSearchEngine)
    assert isinstance(
        build_engine(SearchConfig(algorithm=SearchAlgorithm.DIRECT)),
        DirectSearchEngine,
    )
    assert isinstance(
        build_engine(SearchConfig(algorithm=SearchAlgorithm.SELF_CORRECT)),
        DirectSearchEngine,
    )
    assert isinstance(
        build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE)),
        AndOrSearchEngine,
    )
    assert isinstance(
        build_engine(SearchConfig(algorithm=SearchAlgorithm.BEST_FIRST)),
        AndOrSearchEngine,
    )


def test_build_engine_wires_tree_selection_hyperparameters() -> None:
    puct_engine = build_engine(
        SearchConfig(
            algorithm=SearchAlgorithm.PUCT_TREE,
            puct_exploration_weight=2.5,
        )
    )
    best_first_engine = build_engine(
        SearchConfig(
            algorithm=SearchAlgorithm.BEST_FIRST,
            best_first_missing_value_score=-1.0,
        )
    )

    assert isinstance(puct_engine, AndOrSearchEngine)
    assert puct_engine.selection_strategy == PuctSelection(c_explore=2.5)
    assert isinstance(best_first_engine, AndOrSearchEngine)
    assert best_first_engine.selection_strategy == BestFirstSelection(
        missing_value_score=-1.0,
    )


def test_direct_engine_accepts_first_verified_candidate() -> None:
    engine = DirectSearchEngine()
    policy = FakePolicyClient(
        proof_batches=[
            [
                "theorem t : True := by\n  exact bad",
                "theorem t : True := by\n  trivial",
            ]
        ]
    )
    env = FakeEnvBackend(
        verify_results=[
            ExecVerifyResult(
                item_id="verify",
                status="rejected",
                theorem_name="t",
                messages=[ExecMessage(severity="error", data="unknown bad")],
            ),
            ExecVerifyResult(
                item_id="verify",
                status="accepted",
                theorem_name="t",
            ),
        ]
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.DIRECT,
                max_tactic_calls=1,
                max_direct_candidates=2,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.search_budget_used == 2
    assert result.proof_tree is not None
    assert result.proof_tree.verified
    assert env.verify_calls[1][1].endswith("trivial")
    assert policy.proof_prompts == ["theorem t : True := by\n  sorry"]


def test_self_correct_feeds_back_verifier_message() -> None:
    engine = DirectSearchEngine(self_correct=True)
    policy = FakePolicyClient(
        proof_batches=[
            ["theorem t : True := by\n  exact bad"],
            ["theorem t : True := by\n  trivial"],
        ]
    )
    env = FakeEnvBackend(
        verify_results=[
            ExecVerifyResult(
                item_id="verify",
                status="rejected",
                theorem_name="t",
                messages=[ExecMessage(severity="error", data="unknown bad")],
            ),
            ExecVerifyResult(
                item_id="verify",
                status="accepted",
                theorem_name="t",
            ),
        ]
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.SELF_CORRECT,
                max_tactic_calls=1,
                max_direct_candidates=2,
                direct_candidates_per_round=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.search_budget_used == 2
    assert "unknown bad" in policy.proof_prompts[1]


def test_tree_engine_extracts_and_verifies_single_tactic_proof() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(tactic_batches=[["trivial"]])
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="trivial", status="complete")],
            )
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=4,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.search_budget_used == 1
    assert result.proof_tree is not None
    assert result.proof_tree.roots[0].tactic == "trivial"
    assert result.proof_tree.rendered_lean == (
        "theorem t : True := by\n  trivial"
    )
    assert result.proof_tree.verified
    assert env.cleanup_calls


def test_tree_engine_renders_branching_proof_shape() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(
        tactic_batches=[
            ["constructor"],
            ["trivial"],
            ["trivial"],
        ]
    )
    env = FakeEnvBackend(
        create_states=[
            ExecStateInfo(
                state_token="root-token",
                goals=[
                    ExecGoalInfo(target="True ∧ True", pretty="|- True ∧ True")
                ],
            )
        ],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="constructor",
                        status="open",
                        state_token="split-token",
                        goals=[
                            ExecGoalInfo(target="True", pretty="|- True"),
                            ExecGoalInfo(target="True", pretty="|- True"),
                        ],
                    )
                ],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="trivial", status="complete")],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="trivial", status="complete")],
            ),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem("theorem t : True ∧ True := by\n  sorry"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=5,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.proof_tree is not None
    assert len(result.proof_tree.roots[0].children) == 2
    assert result.proof_tree.rendered_lean == (
        "theorem t : True ∧ True := by\n"
        "  constructor\n"
        "  · trivial\n"
        "  · trivial"
    )
    assert env.step_calls[1][3] == (0,)
    assert env.step_calls[2][3] == (1,)


def test_tree_engine_rejects_split_coupled_multi_goal_extraction() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(
        tactic_batches=[
            ["splitter"],
            ["solve_coupled"],
            ["solve_independent"],
        ]
    )
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="splitter",
                        status="open",
                        state_token="split-token",
                        goals=[
                            ExecGoalInfo(
                                target="A",
                                pretty="|- A",
                                sibling_dep=[1],
                            ),
                            ExecGoalInfo(
                                target="B",
                                pretty="|- B",
                                sibling_dep=[0],
                            ),
                            ExecGoalInfo(target="C", pretty="|- C"),
                        ],
                    )
                ],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="solve_coupled",
                        status="complete",
                    )
                ],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="solve_independent",
                        status="complete",
                    )
                ],
            ),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=5,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.ERROR
    assert "multiple focused goals" in result.diagnostics["extraction_error"]
    assert env.step_calls[1][3] == (0, 1)
    assert env.step_calls[2][3] == (2,)
    assert env.verify_calls == []


def test_best_first_tree_uses_child_values_for_next_frontier() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.BEST_FIRST))
    policy = FakePolicyClient(
        tactic_batches=[
            ["constructor"],
            ["right_proof"],
            ["left_proof"],
        ]
    )
    values = FakeValueClient({"left": 0.1, "right": 0.9})
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="constructor",
                        status="open",
                        state_token="split-token",
                        goals=[
                            ExecGoalInfo(target="left", pretty="|- left"),
                            ExecGoalInfo(target="right", pretty="|- right"),
                        ],
                    )
                ],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(tactic="right_proof", status="complete")
                ],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(tactic="left_proof", status="complete")
                ],
            ),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            policy_client=policy,
            value_client=values,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.BEST_FIRST,
                max_tactic_calls=5,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert values.calls == [["left", "right"]]
    assert env.step_calls[1][3] == (1,)
    assert env.step_calls[2][3] == (0,)


def test_tree_engine_aborts_on_operational_step_status() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(tactic_batches=[["simp"]])
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="simp",
                        status="invalid_state_token",
                        messages=[
                            ExecMessage(
                                severity="error",
                                data="expired token",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=5,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.ERROR
    assert result.search_budget_used == 0
    assert result.diagnostics["operational_status"] == "invalid_state_token"
    assert env.cleanup_calls


def test_run_search_batch_honors_concurrency_driver_surface() -> None:
    policy = FakePolicyClient(
        proof_batches=[
            ["theorem t : True := by\n  trivial"],
            ["theorem t : True := by\n  trivial"],
        ]
    )
    env = FakeEnvBackend()

    results = asyncio.run(
        run_search_batch(
            [theorem(), theorem()],
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.DIRECT,
                max_direct_candidates=1,
            ),
            max_concurrent=1,
        )
    )

    assert [result.status for result in results] == [
        SearchStatus.PROVED,
        SearchStatus.PROVED,
    ]
    assert len(env.verify_calls) == 2
