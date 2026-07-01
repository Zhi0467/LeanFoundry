from __future__ import annotations

import asyncio
import json
import sqlite3

import pytest

from lean_client.exec_models import (
    ExecCancelResponse,
    ExecCancelResult,
    ExecCleanupResponse,
    ExecCleanupResult,
    ExecCreateStatesResponse,
    ExecCreateStatesResult,
    ExecGoalInfo,
    ExecLimitsResponse,
    ExecMessage,
    ExecStateInfo,
    ExecStepBatchResult,
    ExecStepResult,
    ExecVerifyItem,
    ExecVerifyResponse,
    ExecVerifyResult,
)

import leanfoundry.proofsearch.and_or as and_or_module
from leanfoundry.proofsearch import (
    SearchAlgorithm,
    SearchAttemptContext,
    SearchConfig,
    SearchStatus,
    build_engine,
    run_search_batch,
)
from leanfoundry.proofsearch._selection import (
    BestFirstSelection,
    PuctSelection,
)
from leanfoundry.proofsearch._tree import SearchTree
from leanfoundry.proofsearch._tree_init import (
    InitializedSearchTree,
    SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
)
from leanfoundry.proofsearch.and_or import AndOrSearchEngine
from leanfoundry.proofsearch.direct import DirectSearchEngine
from leanfoundry.replay import SQLiteReplayStore
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
    TheoremSpec,
)


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
        context=None,
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
        cleanup_results: list[object] | None = None,
    ) -> None:
        self.create_states_result = create_states or []
        self.step_results = step_results or []
        self.verify_results = verify_results or []
        self.cleanup_results = cleanup_results or []
        self.create_calls: list[tuple[str, str]] = []
        self.step_calls: list[
            tuple[str, str, list[str], tuple[int, ...] | None]
        ] = []
        self.verify_calls: list[tuple[str, str, str]] = []
        self.verify_batch_calls: list[list[str]] = []
        self.cleanup_calls: list[list[str]] = []
        self.cancel_calls: list[list[str]] = []
        self.events: list[tuple[str, str]] = []

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
        self.events.append(("create", item_id))
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
        self.events.append(("step", node_id))
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
        self.events.append(("verify", item_id))
        if self.verify_results:
            return self.verify_results.pop(0).model_copy(
                update={"item_id": item_id}
            )
        return ExecVerifyResult(
            item_id=item_id,
            status="accepted",
            theorem_name=theorem_name,
        )

    async def verify(
        self,
        items: list[ExecVerifyItem],
        *,
        env_profile: str | None = None,
    ) -> ExecVerifyResponse:
        self.verify_batch_calls.append([item.item_id for item in items])
        results = [
            await self.verify_one(
                item.item_id,
                item.code,
                item.theorem_name,
                allowed_axioms=item.allowed_axioms,
                env_profile=env_profile,
            )
            for item in items
        ]
        return ExecVerifyResponse(items=results)

    async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
        self.cleanup_calls.append(item_ids)
        self.events.append(("cleanup", ",".join(item_ids)))
        if self.cleanup_results:
            return self.cleanup_results.pop(0)
        return cleanup_response(deleted=item_ids)

    async def cancel(self, item_ids: list[str]) -> ExecCancelResponse:
        self.cancel_calls.append(item_ids)
        self.events.append(("cancel", ",".join(item_ids)))
        return ExecCancelResponse(
            items=[
                ExecCancelResult(item_id=item_id, status="drained")
                for item_id in item_ids
            ]
        )

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


def tree_attempt(attempt_id: str = "attempt") -> SearchAttemptContext:
    return SearchAttemptContext(
        attempt_id=attempt_id,
        search_item_id=f"{attempt_id}:search",
        verify_item_id=f"{attempt_id}:verify",
    )


def direct_attempt(attempt_id: str = "attempt") -> SearchAttemptContext:
    return SearchAttemptContext(
        attempt_id=attempt_id,
        search_item_id=None,
        verify_item_id=f"{attempt_id}:verify",
    )


def cleanup_response(
    *,
    deleted: list[str] | None = None,
    deferred: list[str] | None = None,
) -> ExecCleanupResponse:
    items = [
        ExecCleanupResult(
            item_id=item_id,
            status="deleted",
            deleted_states=1,
            deleted_bytes=1,
        )
        for item_id in (deleted or [])
    ]
    items += [
        ExecCleanupResult(
            item_id=item_id,
            status="deferred",
            reason="in_flight",
            deleted_states=0,
            deleted_bytes=0,
        )
        for item_id in (deferred or [])
    ]
    return ExecCleanupResponse(deleted_items=items)


def root_state(token: str = "root-token") -> ExecStateInfo:
    return ExecStateInfo(
        state_token=token,
        goals=[ExecGoalInfo(target="True", pretty="|- True")],
    )


def factorized_state(token: str = "state-token") -> FactorizedProofState:
    return FactorizedProofState(
        env_profile="test-env",
        goal_components=[GoalComponent(target="True", pretty="|- True")],
        pretty_state="|- True",
        state_token=token,
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
            attempt_context=direct_attempt("direct-attempt"),
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
    assert result.attempt_id == "direct-attempt"
    assert result.search_item_id is None
    assert result.verify_item_id == "direct-attempt:verify"
    assert result.proof_tree is not None
    assert result.proof_tree.verified
    assert result.training_artifacts is not None
    attempts = result.training_artifacts.direct_verification_attempts
    assert [attempt.verifier_status for attempt in attempts] == [
        "rejected",
        "accepted",
    ]
    assert [attempt.accepted for attempt in attempts] == [False, True]
    assert attempts[0].verify_item_id == "direct-attempt:verify:1"
    assert attempts[1].proof.endswith("trivial")
    assert env.verify_calls[0][0] == "direct-attempt:verify:1"
    assert env.verify_calls[1][0] == "direct-attempt:verify:2"
    assert env.verify_calls[1][1].endswith("trivial")
    assert env.verify_batch_calls == [
        ["direct-attempt:verify:1", "direct-attempt:verify:2"]
    ]
    assert env.cleanup_calls == []
    assert policy.proof_prompts == ["theorem t : True := by\n  sorry"]


def test_direct_engine_verifies_full_candidate_pool_after_success() -> None:
    engine = DirectSearchEngine()
    policy = FakePolicyClient(
        proof_batches=[
            [
                "theorem t : True := by\n  trivial",
                "theorem t : True := by\n  exact bad",
                "theorem t : True := by\n  exact True.intro",
            ]
        ]
    )
    env = FakeEnvBackend(
        verify_results=[
            ExecVerifyResult(
                item_id="verify",
                status="accepted",
                theorem_name="t",
            ),
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
            attempt_context=direct_attempt("direct-pass-k"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.DIRECT,
                max_direct_candidates=3,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.search_budget_used == 3
    assert result.proof_tree is not None
    assert result.proof_tree.rendered_lean.endswith("trivial")
    assert result.training_artifacts is not None
    artifacts = result.training_artifacts
    attempts = artifacts.direct_verification_attempts
    assert [attempt.verifier_status for attempt in attempts] == [
        "accepted",
        "rejected",
        "accepted",
    ]
    assert [attempt.accepted for attempt in attempts] == [
        True,
        False,
        True,
    ]
    assert [
        proof.rendered_lean for proof in artifacts.proof_candidates
    ] == [
        "theorem t : True := by\n  trivial",
        "theorem t : True := by\n  exact True.intro",
    ]
    assert artifacts.diagnostics["proof_candidates"] == 2
    assert artifacts.diagnostics["direct_verification_attempts"] == 3
    assert [call[0] for call in env.verify_calls] == [
        "direct-pass-k:verify:1",
        "direct-pass-k:verify:2",
        "direct-pass-k:verify:3",
    ]
    assert env.verify_batch_calls == [
        [
            "direct-pass-k:verify:1",
            "direct-pass-k:verify:2",
            "direct-pass-k:verify:3",
        ]
    ]
    assert env.verify_calls[1][1].endswith("exact bad")
    assert env.verify_calls[2][1].endswith("True.intro")


def test_direct_engine_exhaustion_keeps_rejected_attempt_trace() -> None:
    engine = DirectSearchEngine()
    policy = FakePolicyClient(
        proof_batches=[["theorem t : True := by\n  exact bad"]]
    )
    env = FakeEnvBackend(
        verify_results=[
            ExecVerifyResult(
                item_id="verify",
                status="rejected",
                theorem_name="t",
                messages=[ExecMessage(severity="error", data="unknown bad")],
            )
        ]
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=direct_attempt("direct-exhausted"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.DIRECT,
                max_direct_candidates=1,
            ),
        )
    )

    assert result.status is SearchStatus.EXHAUSTED
    assert result.training_artifacts is not None
    attempts = result.training_artifacts.direct_verification_attempts
    assert len(attempts) == 1
    assert attempts[0].candidate_index == 1
    assert attempts[0].verifier_feedback == "rejected\nerror: unknown bad"
    assert not attempts[0].accepted


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
            attempt_context=direct_attempt("self-correct-attempt"),
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
    assert result.training_artifacts is not None
    traces = result.training_artifacts.self_correct_traces
    assert len(traces) == 1
    assert [turn.accepted for turn in traces[0].turns] == [False, True]
    assert traces[0].turns[0].verifier_feedback == (
        "rejected\nerror: unknown bad"
    )
    assert traces[0].turns[1].verify_item_id == (
        "self-correct-attempt:verify:2"
    )
    attempts = result.training_artifacts.direct_verification_attempts
    assert [attempt.verifier_status for attempt in attempts] == [
        "rejected",
        "accepted",
    ]


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
            attempt_context=tree_attempt("tree-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=4,
                tactics_per_expansion=1,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.search_budget_used == 1
    assert result.attempt_id == "tree-attempt"
    assert result.search_item_id == "tree-attempt:search"
    assert result.verify_item_id == "tree-attempt:verify"
    assert result.proof_tree is not None
    assert result.proof_tree.roots[0].tactic == "trivial"
    assert result.proof_tree.rendered_lean == (
        "theorem t : True := by\n  trivial"
    )
    assert result.proof_tree.verified
    assert result.training_artifacts is not None
    assert len(result.training_artifacts.proof_candidates) == 1
    assert result.training_artifacts.policy_examples[0].tactic == "trivial"
    assert result.training_artifacts.value_labels[0].label == 1
    assert env.create_calls[0][0] == "tree-attempt:search"
    assert env.verify_calls[0][0] == "tree-attempt:verify"
    assert env.cleanup_calls == [["tree-attempt:search"]]
    assert env.events[-2:] == [
        ("verify", "tree-attempt:verify"),
        ("cleanup", "tree-attempt:search"),
    ]


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
            attempt_context=tree_attempt("branch-attempt"),
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
    assert result.training_artifacts is not None
    examples = result.training_artifacts.policy_examples
    observed = [(example.proof_prefix, example.tactic) for example in examples]
    assert observed == [
        ("", "constructor"),
        ("constructor", "trivial"),
        ("constructor", "trivial"),
    ]
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
            attempt_context=tree_attempt("coupled-attempt"),
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
    assert result.proof_tree is None
    assert "multiple focused goals" in result.diagnostics["extraction_error"]
    assert result.diagnostics["proof_artifact_status"] == (
        "unsupported_extraction"
    )
    assert result.training_artifacts is not None
    examples = result.training_artifacts.policy_examples
    observed = [(example.proof_prefix, example.tactic) for example in examples]
    assert observed == [
        ("", "splitter"),
        ("splitter", "solve_coupled"),
        ("splitter", "solve_independent"),
    ]
    assert result.training_artifacts.failures[0].kind == "unsupported"
    assert result.training_artifacts.failures[0].node_id == (
        "coupled-attempt:search:2"
    )
    assert env.step_calls[1][3] == (0, 1)
    assert env.step_calls[2][3] == (2,)
    assert env.verify_calls == []


def test_tree_engine_verify_rejection_keeps_path_a_artifacts() -> None:
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
        verify_results=[
            ExecVerifyResult(
                item_id="verify",
                status="rejected",
                theorem_name="t",
                messages=[ExecMessage(severity="error", data="bad render")],
            )
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=tree_attempt("verify-reject-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=2,
                tactics_per_expansion=1,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.ERROR
    assert result.proof_tree is not None
    assert not result.proof_tree.verified
    assert result.training_artifacts is not None
    assert result.training_artifacts.proof_candidates == []
    assert result.training_artifacts.policy_examples[0].tactic == "trivial"
    assert result.training_artifacts.policy_examples[0].proof_prefix == ""
    assert result.training_artifacts.value_labels[0].label == 1
    label = result.training_artifacts.value_labels[0]
    assert label.tactics_tried_on_subtree == 1
    assert result.training_artifacts.failures[0].kind == "verification"


def test_tree_engine_initial_complete_emits_no_synthetic_rows() -> None:
    class CompleteCreateEnv(FakeEnvBackend):
        async def create_states(
            self,
            item_id: str,
            code: str,
            *,
            env_profile: str | None = None,
        ) -> ExecCreateStatesResponse:
            self.create_calls.append((item_id, code))
            self.events.append(("create", item_id))
            return ExecCreateStatesResponse(
                items=[
                    ExecCreateStatesResult(
                        item_id=item_id,
                        status="complete",
                        states=[],
                    )
                ]
            )

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    env = CompleteCreateEnv()

    result = asyncio.run(
        engine.search(
            theorem("theorem t : True := by\n  trivial"),
            attempt_context=tree_attempt("initial-complete-attempt"),
            policy_client=FakePolicyClient(tactic_batches=[]),
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.training_artifacts is not None
    assert result.training_artifacts.policy_examples == []
    assert result.training_artifacts.value_labels == []
    assert result.training_artifacts.proof_candidates


def test_tree_engine_counts_proved_alternatives_from_one_expansion() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(tactic_batches=[["trivial", "exact True.intro"]])
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(tactic="trivial", status="complete"),
                    ExecStepResult(
                        tactic="exact True.intro",
                        status="complete",
                    ),
                ],
            )
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=tree_attempt("alternatives-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=2,
                tactics_per_expansion=2,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.training_artifacts is not None
    assert result.proof_tree is not None
    assert result.proof_tree.roots[0].tactic == "trivial"
    assert result.training_artifacts.diagnostics["proved_actions"] == 2
    assert result.training_artifacts.diagnostics["proved_alternatives"] == 1
    tactics = sorted(
        example.tactic
        for example in result.training_artifacts.policy_examples
    )
    assert tactics == ["exact True.intro", "trivial"]


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
            attempt_context=tree_attempt("best-first-attempt"),
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
            attempt_context=tree_attempt("token-attempt"),
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


def test_tree_engine_exhausted_open_root_emits_censored_value_only() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(tactic_batches=[["bad"]])
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="bad",
                        status="error",
                        messages=[
                            ExecMessage(
                                severity="error",
                                data="unknown tactic",
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
            attempt_context=tree_attempt("exhausted-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
                value_mode="bonded",
                censored_negative_weight=0.2,
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.EXHAUSTED
    assert result.training_artifacts is not None
    assert result.training_artifacts.policy_examples == []
    assert result.training_artifacts.proof_candidates == []
    assert len(result.training_artifacts.value_labels) == 1
    label = result.training_artifacts.value_labels[0]
    assert label.label == 0
    assert label.weight == 0.2
    assert not label.disproved
    assert label.tactics_tried_on_subtree == 1


def test_tree_engine_maps_explicit_disproved_root(monkeypatch) -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    env = FakeEnvBackend()
    policy = FakePolicyClient()

    async def initialize_disproved_tree(
        _env_backend,
        _theorem,
        *,
        search_id: str,
    ) -> InitializedSearchTree:
        synthetic_root_state = FactorizedProofState(
            env_profile="test-env",
            goal_components=[],
            pretty_state="theorem t : True := by\n  sorry",
            state_token=None,
        )
        tree = SearchTree.create(search_id, synthetic_root_state)
        initialization_action = tree.add_action(
            tree.root,
            SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
            prior=1.0,
        )
        initial_state = tree.add_child_state(
            initialization_action,
            factorized_state("disproved-root"),
        )
        tree.mark_state_disproved(initial_state, message="negation proof")
        tree.mark_state_disproved(tree.root, message="root disproved")
        return InitializedSearchTree(tree=tree, initial_code="")

    monkeypatch.setattr(
        and_or_module,
        "initialize_search_tree",
        initialize_disproved_tree,
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=tree_attempt("disproved-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                value_mode="bonded",
            ),
        )
    )

    assert result.status is SearchStatus.DISPROVED
    assert result.training_artifacts is not None
    assert result.proof_tree is None
    assert env.verify_calls == []
    assert env.cleanup_calls == [["disproved-attempt:search"]]
    assert len(result.training_artifacts.value_labels) == 1
    label = result.training_artifacts.value_labels[0]
    assert label.label == 0
    assert label.weight == 1.0
    assert label.disproved
    assert label.state.state_token == "disproved-root"


def test_tree_engine_try_negation_marks_eligible_state_disproved() -> None:
    class NegationEnv(FakeEnvBackend):
        async def create_states(
            self,
            item_id: str,
            code: str,
            *,
            env_profile: str | None = None,
        ) -> ExecCreateStatesResponse:
            self.create_calls.append((item_id, code))
            self.events.append(("create", item_id))
            if len(self.create_calls) == 1:
                states = [root_state()]
            else:
                assert "¬ (True)" in code
                states = [root_state("negation-token")]
            return ExecCreateStatesResponse(
                items=[
                    ExecCreateStatesResult(
                        item_id=item_id,
                        status="open",
                        states=states,
                    )
                ]
            )

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(
        tactic_batches=[
            ["bad"],
            ["exact not_true"],
        ]
    )
    env = NegationEnv(
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="bad", status="error")],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="exact not_true",
                        status="complete",
                    )
                ],
            ),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem().model_copy(update={"source": "autoformalized"}),
            attempt_context=tree_attempt("negation-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=2,
                tactics_per_expansion=1,
                try_negation=True,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.DISPROVED
    assert result.search_budget_used == 2
    assert len(env.create_calls) == 2
    assert env.step_calls[1][1] == "negation-token"
    assert result.training_artifacts is not None
    assert len(result.training_artifacts.policy_examples) == 1
    policy_example = result.training_artifacts.policy_examples[0]
    assert policy_example.state.state_token == "negation-token"
    assert policy_example.tactic == "exact not_true"
    assert policy_example.proof_prefix == ""
    assert len(result.training_artifacts.negation_attempts) == 1
    negation_attempt = result.training_artifacts.negation_attempts[0]
    assert negation_attempt.status == "proved"
    assert negation_attempt.proved
    assert negation_attempt.proved_tactic == "exact not_true"
    assert negation_attempt.tactic_calls_used == 1
    assert negation_attempt.step_item_id is not None
    assert negation_attempt.rendered_lean is not None
    assert "¬ (True)" in negation_attempt.rendered_lean
    assert negation_attempt.tactic_attempts[0].status == "complete"
    assert len(result.training_artifacts.value_labels) == 1
    label = result.training_artifacts.value_labels[0]
    assert label.label == 0
    assert label.disproved
    assert label.weight == 1.0


def test_tree_engine_retries_open_negation_action() -> None:
    class NegationEnv(FakeEnvBackend):
        async def create_states(
            self,
            item_id: str,
            code: str,
            *,
            env_profile: str | None = None,
        ) -> ExecCreateStatesResponse:
            self.create_calls.append((item_id, code))
            self.events.append(("create", item_id))
            if len(self.create_calls) == 1:
                states = [root_state()]
            else:
                assert "¬ (True)" in code
                states = [root_state("negation-token")]
            return ExecCreateStatesResponse(
                items=[
                    ExecCreateStatesResult(
                        item_id=item_id,
                        status="open",
                        states=states,
                    )
                ]
            )

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(
        tactic_batches=[
            ["bad"],
            ["exact failed_negation"],
            ["exact not_true"],
        ]
    )
    env = NegationEnv(
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="bad", status="error")],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="exact failed_negation",
                        status="error",
                    )
                ],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="exact not_true",
                        status="complete",
                    )
                ],
            ),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem().model_copy(update={"source": "autoformalized"}),
            attempt_context=tree_attempt("negation-retry-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=3,
                tactics_per_expansion=1,
                try_negation=True,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.DISPROVED
    assert result.search_budget_used == 3
    assert len(env.create_calls) == 2
    assert [call[0] for call in policy.tactic_calls] == [
        "root-token",
        "negation-token",
        "negation-token",
    ]
    assert [call[0] for call in env.step_calls] == [
        "negation-retry-attempt:search:1",
        "negation-retry-attempt:search:2",
        "negation-retry-attempt:search:2",
    ]
    assert result.training_artifacts is not None
    statuses = [
        attempt.status
        for attempt in result.training_artifacts.negation_attempts
    ]
    assert statuses == ["proved"]
    examples = result.training_artifacts.policy_examples
    observed_examples = [
        (example.state.state_token, example.tactic)
        for example in examples
    ]
    assert observed_examples == [
        ("negation-token", "exact not_true")
    ]


def test_tree_engine_searches_nested_negation_subgoals() -> None:
    class NegationEnv(FakeEnvBackend):
        async def create_states(
            self,
            item_id: str,
            code: str,
            *,
            env_profile: str | None = None,
        ) -> ExecCreateStatesResponse:
            self.create_calls.append((item_id, code))
            self.events.append(("create", item_id))
            if len(self.create_calls) == 1:
                states = [root_state()]
            else:
                assert "¬ (True)" in code
                states = [root_state("negation-token")]
            return ExecCreateStatesResponse(
                items=[
                    ExecCreateStatesResult(
                        item_id=item_id,
                        status="open",
                        states=states,
                    )
                ]
            )

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(
        tactic_batches=[
            ["bad"],
            ["intro h"],
            ["exact h"],
        ]
    )
    env = NegationEnv(
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="bad", status="error")],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="intro h",
                        status="open",
                        state_token="neg-subgoal-token",
                        goals=[
                            ExecGoalInfo(
                                target="False",
                                pretty="h : True\n|- False",
                            )
                        ],
                    )
                ],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="exact h",
                        status="complete",
                    )
                ],
            ),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem().model_copy(update={"source": "autoformalized"}),
            attempt_context=tree_attempt("negation-nested-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=3,
                tactics_per_expansion=1,
                try_negation=True,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.DISPROVED
    assert result.search_budget_used == 3
    assert [call[0] for call in policy.tactic_calls] == [
        "root-token",
        "negation-token",
        "neg-subgoal-token",
    ]
    assert result.training_artifacts is not None
    examples = result.training_artifacts.policy_examples
    assert [
        (
            example.state.state_token,
            example.proof_prefix,
            example.tactic,
        )
        for example in examples
    ] == [
        ("negation-token", "", "intro h"),
        ("neg-subgoal-token", "intro h", "exact h"),
    ]
    assert len(result.training_artifacts.negation_attempts) == 1
    negation_attempt = result.training_artifacts.negation_attempts[0]
    assert negation_attempt.status == "proved"
    assert negation_attempt.proved
    assert negation_attempt.proved_tactic == "intro h"
    assert negation_attempt.tactic_calls_used == 2
    assert negation_attempt.tactic_attempts[0].status == "proved_subtree"
    assert len(result.training_artifacts.value_labels) == 1
    assert result.training_artifacts.value_labels[0].disproved


def test_tree_engine_try_negation_abstracts_local_definitions() -> None:
    def local_definition_state(token: str = "root-token") -> ExecStateInfo:
        return ExecStateInfo(
            state_token=token,
            goals=[
                ExecGoalInfo(
                    target="n = n",
                    pretty="n : Nat := 0\n|- n = n",
                    hypotheses=[
                        {
                            "name": "n",
                            "type": "Nat",
                            "value": "0",
                        }
                    ],
                )
            ],
        )

    class NegationEnv(FakeEnvBackend):
        async def create_states(
            self,
            item_id: str,
            code: str,
            *,
            env_profile: str | None = None,
        ) -> ExecCreateStatesResponse:
            self.create_calls.append((item_id, code))
            self.events.append(("create", item_id))
            if len(self.create_calls) == 1:
                states = [local_definition_state()]
            else:
                assert "(n : Nat)" in code
                assert ":= 0" not in code
                assert "¬ (n = n)" in code
                states = [root_state("negation-token")]
            return ExecCreateStatesResponse(
                items=[
                    ExecCreateStatesResult(
                        item_id=item_id,
                        status="open",
                        states=states,
                    )
                ]
            )

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(
        tactic_batches=[
            ["bad"],
            ["exact absurd_n_eq_n"],
        ]
    )
    env = NegationEnv(
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="bad", status="error")],
            ),
            ExecStepBatchResult(
                node_id="placeholder",
                results=[
                    ExecStepResult(
                        tactic="exact absurd_n_eq_n",
                        status="complete",
                    )
                ],
            ),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem().model_copy(update={"source": "autoformalized"}),
            attempt_context=tree_attempt("negation-local-def-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=2,
                tactics_per_expansion=1,
                try_negation=True,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.DISPROVED
    assert len(env.create_calls) == 2
    assert result.training_artifacts is not None
    assert len(result.training_artifacts.negation_attempts) == 1
    negation_attempt = result.training_artifacts.negation_attempts[0]
    assert negation_attempt.status == "proved"
    assert negation_attempt.rendered_lean is not None
    assert "(n : Nat)" in negation_attempt.rendered_lean
    assert ":= 0" not in negation_attempt.rendered_lean
    assert "¬ (n = n)" in negation_attempt.rendered_lean


def test_tree_engine_try_negation_is_provenance_gated() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(tactic_batches=[["bad"]])
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="bad", status="error")],
            )
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem().model_copy(update={"source": "leandojo"}),
            attempt_context=tree_attempt("negation-gated-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
                try_negation=True,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
        )
    )

    assert result.status is SearchStatus.EXHAUSTED
    assert len(env.create_calls) == 1
    assert len(env.step_calls) == 1
    assert result.training_artifacts is not None
    assert result.training_artifacts.value_labels[0].disproved is False


def test_tree_engine_reports_mixed_overloaded_backend_protocol_error() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(tactic_batches=[["trivial", "simp"]])
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
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
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=tree_attempt("mixed-overload-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=5,
                tactics_per_expansion=2,
            ),
        )
    )

    assert result.status is SearchStatus.ERROR
    assert result.search_budget_used == 1
    assert result.diagnostics["operational_status"] == (
        "backend_protocol_error"
    )
    assert "overloaded mixed" in result.diagnostics["failure_message"]
    assert env.verify_calls == []
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
    assert [result.attempt_id for result in results]
    assert env.cleanup_calls == []


def test_run_search_batch_uses_runner_provided_direct_verify_ids() -> None:
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
            attempt_contexts=[
                direct_attempt("direct-one"),
                direct_attempt("direct-two"),
            ],
        )
    )

    assert [result.attempt_id for result in results] == [
        "direct-one",
        "direct-two",
    ]
    assert [call[0] for call in env.verify_calls] == [
        "direct-one:verify:1",
        "direct-two:verify:1",
    ]
    assert env.cleanup_calls == []


def test_run_search_batch_rejects_duplicate_ids_before_backend() -> None:
    env = FakeEnvBackend()

    with pytest.raises(ValueError, match="duplicate attempt_id"):
        asyncio.run(
            run_search_batch(
                [theorem(), theorem()],
                policy_client=FakePolicyClient(),
                value_client=None,
                env_backend=env,
                config=SearchConfig(algorithm=SearchAlgorithm.DIRECT),
                attempt_contexts=[
                    direct_attempt("dup"),
                    direct_attempt("dup"),
                ],
            )
        )

    assert env.events == []


def test_run_search_batch_persists_path_a_artifacts(tmp_path) -> None:
    db_path = tmp_path / "replay.db"
    store = SQLiteReplayStore(db_path)
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

    results = asyncio.run(
        run_search_batch(
            [theorem().model_copy(update={"id": "thm"})],
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
                value_mode="bonded",
                min_censored_negative_effort=1,
            ),
            max_concurrent=1,
            replay_store=store,
            model_version=7,
        )
    )
    store.close()

    result = results[0]
    assert result.status is SearchStatus.PROVED
    assert result.theorem_id == "thm"
    assert result.diagnostics["replay_trajectories"] == 1
    assert result.diagnostics["replay_policy_examples"] == 1
    assert result.diagnostics["replay_value_labels"] == 1
    assert result.diagnostics["replay_a_type_data"] == 1

    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT COUNT(*) FROM theorems WHERE added_at IS NOT NULL"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM trajectories WHERE created_at IS NOT NULL"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM a_type_data WHERE created_at IS NOT NULL"
    ).fetchone()[0] == 1
    policy_row = conn.execute(
        """
        SELECT theorem_id, proof_prefix, tactic, model_version
        FROM policy_examples
        """
    ).fetchone()
    assert policy_row == ("thm", "", "trivial", 7)
    value_row = conn.execute(
        """
        SELECT theorem_id, label, weight, tactics_tried_on_subtree,
               model_version
        FROM state_value_labels
        """
    ).fetchone()
    assert value_row == ("thm", 1, 1.0, 1, 7)


def test_run_search_batch_persists_runner_exception(tmp_path) -> None:
    class RaisingPolicyClient(FakePolicyClient):
        async def sample_proofs(
            self,
            prompts,
            *,
            n: int,
            params=None,
        ) -> list[list[str]]:
            raise RuntimeError("policy unavailable")

    db_path = tmp_path / "replay.db"
    store = SQLiteReplayStore(db_path)

    results = asyncio.run(
        run_search_batch(
            [theorem().model_copy(update={"id": "thm"})],
            policy_client=RaisingPolicyClient(),
            value_client=None,
            env_backend=FakeEnvBackend(),
            config=SearchConfig(
                algorithm=SearchAlgorithm.DIRECT,
                max_direct_candidates=1,
            ),
            max_concurrent=1,
            replay_store=store,
        )
    )
    store.close()

    result = results[0]
    assert result.status is SearchStatus.ERROR
    assert result.diagnostics["operational_status"] == "runner_exception"
    assert result.diagnostics["replay_trajectories"] == 1
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM trajectories").fetchone()[0] == 1


def test_tree_engine_retries_deferred_cleanup_after_verification() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    context = SearchAttemptContext(
        attempt_id="cleanup-attempt",
        search_item_id="cleanup-attempt:search",
        verify_item_id="cleanup-attempt:verify",
        cleanup_max_attempts=2,
    )
    policy = FakePolicyClient(tactic_batches=[["trivial"]])
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="trivial", status="complete")],
            )
        ],
        cleanup_results=[
            cleanup_response(deferred=["cleanup-attempt:search"]),
            cleanup_response(deleted=["cleanup-attempt:search"]),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=context,
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.diagnostics["cleanup_attempts"] == 2
    assert result.diagnostics["cleanup_deleted"] == 1
    assert result.diagnostics["cleanup_deferred"] == 0
    assert env.cleanup_calls == [
        ["cleanup-attempt:search"],
        ["cleanup-attempt:search"],
    ]
    assert env.events[-3:] == [
        ("verify", "cleanup-attempt:verify"),
        ("cleanup", "cleanup-attempt:search"),
        ("cleanup", "cleanup-attempt:search"),
    ]


def test_tree_engine_reports_bounded_deferred_cleanup_ids() -> None:
    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    context = SearchAttemptContext(
        attempt_id="cleanup-open-attempt",
        search_item_id="cleanup-open-attempt:search",
        verify_item_id="cleanup-open-attempt:verify",
        cleanup_max_attempts=2,
    )
    policy = FakePolicyClient(tactic_batches=[["trivial"]])
    env = FakeEnvBackend(
        create_states=[root_state()],
        step_results=[
            ExecStepBatchResult(
                node_id="placeholder",
                results=[ExecStepResult(tactic="trivial", status="complete")],
            )
        ],
        cleanup_results=[
            cleanup_response(deferred=["cleanup-open-attempt:search"]),
            cleanup_response(deferred=["cleanup-open-attempt:search"]),
        ],
    )

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=context,
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.diagnostics["cleanup_attempts"] == 2
    assert result.diagnostics["cleanup_max_attempts"] == 2
    assert result.diagnostics["cleanup_deferred"] == 1
    assert json.loads(
        result.diagnostics["cleanup_deferred_item_ids"]
    ) == ["cleanup-open-attempt:search"]


def test_tree_engine_cleans_search_state_on_unexpected_error() -> None:
    class RaisingPolicyClient(FakePolicyClient):
        async def sample_tactics(
            self,
            states,
            *,
            n: int,
            params=None,
            context=None,
        ) -> list[list[str]]:
            raise RuntimeError("policy unavailable")

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    env = FakeEnvBackend(create_states=[root_state()])

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=tree_attempt("unexpected-error-attempt"),
            policy_client=RaisingPolicyClient(),
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.ERROR
    assert "policy unavailable" in result.diagnostics["failure_message"]
    assert env.cancel_calls == []
    assert env.cleanup_calls == [["unexpected-error-attempt:search"]]


def test_tree_engine_does_not_cleanup_before_search_state_exists() -> None:
    class LimitsErrorEnv(FakeEnvBackend):
        async def limits(self) -> ExecLimitsResponse:
            raise RuntimeError("limits unavailable")

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    env = LimitsErrorEnv()

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=tree_attempt("limits-error-attempt"),
            policy_client=FakePolicyClient(tactic_batches=[["trivial"]]),
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.ERROR
    assert "limits unavailable" in result.diagnostics["failure_message"]
    assert env.create_calls == []
    assert env.cleanup_calls == []


def test_run_search_batch_isolates_one_theorem_failure() -> None:
    class FlakyPolicyClient(FakePolicyClient):
        def __init__(self) -> None:
            super().__init__()
            self.proof_calls = 0

        async def sample_proofs(
            self,
            prompts,
            *,
            n: int,
            params=None,
        ) -> list[list[str]]:
            self.proof_prompts.append(prompts[0])
            self.proof_calls += 1
            if self.proof_calls == 1:
                raise RuntimeError("policy unavailable")
            return [["theorem t : True := by\n  trivial"]]

    policy = FlakyPolicyClient()
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

    statuses = [result.status for result in results]
    assert statuses.count(SearchStatus.ERROR) == 1
    assert statuses.count(SearchStatus.PROVED) == 1
    error_result = next(
        result for result in results if result.status is SearchStatus.ERROR
    )
    assert error_result.diagnostics["operational_status"] == (
        "runner_exception"
    )
    assert "policy unavailable" in error_result.diagnostics[
        "failure_message"
    ]
    assert error_result.attempt_id is not None
    assert len(env.verify_calls) == 1


def test_tree_engine_cleanup_failure_preserves_proved_result() -> None:
    class CleanupFailingEnv(FakeEnvBackend):
        async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
            self.cleanup_calls.append(item_ids)
            self.events.append(("cleanup", ",".join(item_ids)))
            raise RuntimeError("cleanup backend down")

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    policy = FakePolicyClient(tactic_batches=[["trivial"]])
    env = CleanupFailingEnv(
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
            attempt_context=tree_attempt("cleanup-fail-attempt"),
            policy_client=policy,
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.PROVED
    assert result.proof_tree is not None
    assert result.proof_tree.verified
    assert result.diagnostics["cleanup_failed"] == "cleanup backend down"
    assert env.cleanup_calls == [["cleanup-fail-attempt:search"]]


def test_tree_engine_cleanup_failure_does_not_mask_unexpected_error() -> None:
    class RaisingPolicyClient(FakePolicyClient):
        async def sample_tactics(
            self,
            states,
            *,
            n: int,
            params=None,
            context=None,
        ) -> list[list[str]]:
            raise RuntimeError("policy unavailable")

    class CleanupFailingEnv(FakeEnvBackend):
        async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
            self.cleanup_calls.append(item_ids)
            self.events.append(("cleanup", ",".join(item_ids)))
            raise RuntimeError("cleanup backend down")

    engine = build_engine(SearchConfig(algorithm=SearchAlgorithm.PUCT_TREE))
    env = CleanupFailingEnv(create_states=[root_state()])

    result = asyncio.run(
        engine.search(
            theorem(),
            attempt_context=tree_attempt("mask-error-attempt"),
            policy_client=RaisingPolicyClient(),
            value_client=None,
            env_backend=env,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=1,
                tactics_per_expansion=1,
            ),
        )
    )

    assert result.status is SearchStatus.ERROR
    assert "policy unavailable" in result.diagnostics["failure_message"]
    assert result.diagnostics["cleanup_failed"] == "cleanup backend down"
    assert env.cleanup_calls == [["mask-error-attempt:search"]]


def test_run_search_batch_cancel_calls_cancel_then_cleanup() -> None:
    class BlockingStepEnv(FakeEnvBackend):
        def __init__(self) -> None:
            super().__init__(
                create_states=[root_state()],
                cleanup_results=[
                    cleanup_response(deferred=["cancel-attempt:search"]),
                    cleanup_response(deleted=["cancel-attempt:search"]),
                ],
            )
            self.step_started = asyncio.Event()

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
            self.events.append(("step", node_id))
            self.step_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    async def run_and_cancel() -> BlockingStepEnv:
        policy = FakePolicyClient(tactic_batches=[["trivial"]])
        env = BlockingStepEnv()
        task = asyncio.create_task(
            run_search_batch(
                [theorem()],
                policy_client=policy,
                value_client=None,
                env_backend=env,
                config=SearchConfig(
                    algorithm=SearchAlgorithm.PUCT_TREE,
                    max_tactic_calls=1,
                    tactics_per_expansion=1,
                ),
                max_concurrent=1,
                attempt_contexts=[
                    SearchAttemptContext(
                        attempt_id="cancel-attempt",
                        search_item_id="cancel-attempt:search",
                        verify_item_id="cancel-attempt:verify",
                        cleanup_max_attempts=2,
                    )
                ],
            )
        )
        await env.step_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return env

    env = asyncio.run(run_and_cancel())

    assert env.cancel_calls == [
        ["cancel-attempt:search", "cancel-attempt:verify"]
    ]
    assert env.cleanup_calls == [
        ["cancel-attempt:search"],
        ["cancel-attempt:search"],
    ]
    assert env.events[-3:] == [
        ("cancel", "cancel-attempt:search,cancel-attempt:verify"),
        ("cleanup", "cancel-attempt:search"),
        ("cleanup", "cancel-attempt:search"),
    ]


def test_cancelled_tree_search_persists_lifecycle_records(
    tmp_path,
) -> None:
    class CancelFailingBlockingStepEnv(FakeEnvBackend):
        def __init__(self) -> None:
            super().__init__(
                create_states=[root_state()],
                cleanup_results=[
                    cleanup_response(
                        deferred=["cancel-persist-attempt:search"]
                    ),
                ],
            )
            self.step_started = asyncio.Event()

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
            self.events.append(("step", node_id))
            self.step_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def cancel(self, item_ids: list[str]) -> ExecCancelResponse:
            self.cancel_calls.append(item_ids)
            self.events.append(("cancel", ",".join(item_ids)))
            raise RuntimeError("cancel backend down")

    async def run_and_cancel(db_path) -> CancelFailingBlockingStepEnv:
        policy = FakePolicyClient(tactic_batches=[["trivial"]])
        env = CancelFailingBlockingStepEnv()
        store = SQLiteReplayStore(db_path)
        task = asyncio.create_task(
            run_search_batch(
                [theorem()],
                policy_client=policy,
                value_client=None,
                env_backend=env,
                config=SearchConfig(
                    algorithm=SearchAlgorithm.PUCT_TREE,
                    max_tactic_calls=1,
                    tactics_per_expansion=1,
                ),
                max_concurrent=1,
                attempt_contexts=[
                    SearchAttemptContext(
                        attempt_id="cancel-persist-attempt",
                        search_item_id="cancel-persist-attempt:search",
                        verify_item_id="cancel-persist-attempt:verify",
                        cleanup_max_attempts=1,
                    )
                ],
                replay_store=store,
            )
        )
        await env.step_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        store.close()
        return env

    db_path = tmp_path / "replay.db"
    env = asyncio.run(run_and_cancel(db_path))

    assert env.cancel_calls == [
        ["cancel-persist-attempt:search", "cancel-persist-attempt:verify"]
    ]
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT lifecycle_stage, lifecycle_status, backend_item_id, last_error
        FROM attempt_lifecycle_outbox
        ORDER BY lifecycle_stage, backend_item_id
        """
    ).fetchall()
    assert rows == [
        (
            "cancel",
            "failed",
            "cancel-persist-attempt:search",
            "cancel backend down",
        ),
        (
            "cancel",
            "failed",
            "cancel-persist-attempt:verify",
            "cancel backend down",
        ),
        (
            "cleanup",
            "deferred",
            "cancel-persist-attempt:search",
            None,
        ),
    ]


def test_direct_search_cancel_cancels_active_verify_item() -> None:
    class BlockingVerifyEnv(FakeEnvBackend):
        def __init__(self) -> None:
            super().__init__()
            self.verify_started = asyncio.Event()

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
            self.events.append(("verify", item_id))
            self.verify_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    async def run_and_cancel() -> BlockingVerifyEnv:
        env = BlockingVerifyEnv()
        task = asyncio.create_task(
            run_search_batch(
                [theorem()],
                policy_client=FakePolicyClient(
                    proof_batches=[["theorem t : True := by\n  trivial"]]
                ),
                value_client=None,
                env_backend=env,
                config=SearchConfig(
                    algorithm=SearchAlgorithm.DIRECT,
                    max_direct_candidates=1,
                ),
                max_concurrent=1,
                attempt_contexts=[direct_attempt("direct-cancel")],
            )
        )
        await env.verify_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return env

    env = asyncio.run(run_and_cancel())

    assert env.cancel_calls == [["direct-cancel:verify:1"]]


def test_direct_search_cancel_persists_active_verify_lifecycle(
    tmp_path,
) -> None:
    class BlockingVerifyEnv(FakeEnvBackend):
        def __init__(self) -> None:
            super().__init__()
            self.verify_started = asyncio.Event()

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
            self.events.append(("verify", item_id))
            self.verify_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    async def run_and_cancel(db_path) -> BlockingVerifyEnv:
        env = BlockingVerifyEnv()
        store = SQLiteReplayStore(db_path)
        task = asyncio.create_task(
            run_search_batch(
                [theorem()],
                policy_client=FakePolicyClient(
                    proof_batches=[["theorem t : True := by\n  trivial"]]
                ),
                value_client=None,
                env_backend=env,
                config=SearchConfig(
                    algorithm=SearchAlgorithm.DIRECT,
                    max_direct_candidates=1,
                ),
                max_concurrent=1,
                attempt_contexts=[direct_attempt("direct-cancel-replay")],
                replay_store=store,
            )
        )
        await env.verify_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        store.close()
        return env

    db_path = tmp_path / "replay.db"
    env = asyncio.run(run_and_cancel(db_path))

    assert env.cancel_calls == [["direct-cancel-replay:verify:1"]]
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT lifecycle_stage, lifecycle_status, backend_item_id, terminal
        FROM attempt_lifecycle_outbox
        """
    ).fetchone()
    assert row == (
        "cancel",
        "drained",
        "direct-cancel-replay:verify:1",
        1,
    )
