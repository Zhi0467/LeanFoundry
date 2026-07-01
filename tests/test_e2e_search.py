"""End-to-end search tests against a live kimina-lean-server.

These are the only tests that exercise the real Lean ``/exec`` contract
through LeanFoundry's EnvBackend and lean-client's streaming microbatcher.
Every other test in the suite fakes ``EnvBackend``, so a runtime tree can reach
``PROVED`` (each tactic accepted per-step) while the *assembled* whole proof is
rejected by final ``/exec/verify`` -- exactly the runtime-PROVED-vs-final
divergence that the per-step Path-A grounding makes possible, and that no faked
backend can catch.

The core invariant asserted here is that, driven through the real backend and
the client microbatcher, the runtime tree reaching ``proved`` is *equivalent*
to final verification accepting the assembled proof. A rendering/assembly
regression (notably for ``constructor`` split children) breaks that equivalence
and turns these red.

Opt-in only, so the default ``pytest`` run stays hermetic. Enable with::

    LEANFOUNDRY_E2E=1 \\
    LEANFOUNDRY_E2E_API_URL=http://localhost:8000 \\
    uv run --no-dev --with pytest pytest tests/test_e2e_search.py

Optional: ``LEANFOUNDRY_E2E_ENV_PROFILE`` (default ``default``) and
``LEANFOUNDRY_E2E_API_KEY``.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from leanfoundry.env_backend import EnvBackendConfig
from leanfoundry.env_backend.kimina_backend import KiminaEnvBackend
from leanfoundry.proofsearch import (
    SearchAlgorithm,
    SearchAttemptContext,
    SearchConfig,
    SearchResult,
    SearchStatus,
    run_search_batch,
)
from leanfoundry.schemas import FactorizedProofState, TheoremSpec

_API_URL = os.environ.get("LEANFOUNDRY_E2E_API_URL")
_ENV_PROFILE = os.environ.get("LEANFOUNDRY_E2E_ENV_PROFILE", "default")
_API_KEY = os.environ.get("LEANFOUNDRY_E2E_API_KEY")

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("LEANFOUNDRY_E2E") != "1" or not _API_URL,
        reason=(
            "live e2e disabled; set LEANFOUNDRY_E2E=1 and "
            "LEANFOUNDRY_E2E_API_URL to run against a kimina-lean-server"
        ),
    ),
]


class _ScriptedPolicy:
    """Scripted policy so the e2e is reproducible against real Lean.

    Tactic sampling returns ``constructor`` for conjunction goals and
    ``trivial`` otherwise. Whole-proof sampling returns caller-provided
    candidates. The model is irrelevant here: the backend/client contract is
    what is under test.
    """

    def __init__(
        self,
        *,
        proof_batches: Sequence[Sequence[str]] | None = None,
        tactic_barrier_count: int | None = None,
    ) -> None:
        self._proof_batches = [
            list(batch) for batch in proof_batches or []
        ]
        self._tactic_barrier_count = tactic_barrier_count
        self._tactic_state_count = 0
        self._tactic_barrier_event: asyncio.Event | None = None
        self._tactic_barrier_lock: asyncio.Lock | None = None
        self.proof_prompts: list[str] = []

    async def sample_tactics(
        self,
        states: Sequence[FactorizedProofState],
        *,
        n: int,
        params: Mapping[str, Any] | None = None,
        context=None,
    ) -> list[list[str]]:
        await self._wait_for_tactic_barrier(len(states))
        return [[_closing_tactic(state)][:n] for state in states]

    async def sample_proofs(
        self,
        prompts: Sequence[str],
        *,
        n: int,
        params: Mapping[str, Any] | None = None,
    ) -> list[list[str]]:
        if len(prompts) != 1:
            raise AssertionError("direct search should prompt one theorem")
        if not self._proof_batches:
            raise AssertionError("no scripted proof batch left")
        self.proof_prompts.extend(prompts)
        return [self._proof_batches.pop(0)[:n]]

    async def _wait_for_tactic_barrier(self, state_count: int) -> None:
        if self._tactic_barrier_count is None:
            return
        event = self._tactic_event()
        async with self._tactic_lock():
            self._tactic_state_count += state_count
            if self._tactic_state_count >= self._tactic_barrier_count:
                event.set()
        await asyncio.wait_for(event.wait(), timeout=5)

    def _tactic_event(self) -> asyncio.Event:
        if self._tactic_barrier_event is None:
            self._tactic_barrier_event = asyncio.Event()
        return self._tactic_barrier_event

    def _tactic_lock(self) -> asyncio.Lock:
        if self._tactic_barrier_lock is None:
            self._tactic_barrier_lock = asyncio.Lock()
        return self._tactic_barrier_lock


class _RecordingKiminaEnvBackend(KiminaEnvBackend):
    """Kimina backend that records client microbatch sizes."""

    def __init__(self, config: EnvBackendConfig) -> None:
        super().__init__(config)
        self.step_batch_sizes: list[int] = []

    async def connect(self) -> None:
        await super().connect()
        backend = self._require_backend()
        backend.batcher.max_wait_ms = 50
        backend.batcher.max_items = max(backend.batcher.max_items, 3)
        original_step_batch = backend.env.step_batch

        async def recording_step_batch(items: list[Any]) -> Any:
            self.step_batch_sizes.append(len(items))
            return await original_step_batch(items)

        backend.env.step_batch = recording_step_batch


def _closing_tactic(state: FactorizedProofState) -> str:
    target = state.goal_components[0].target if state.goal_components else ""
    if "∧" in target or "And" in target:
        return "constructor"
    return "trivial"


def _backend_config() -> EnvBackendConfig:
    return EnvBackendConfig(
        api_url=_API_URL,
        env_profile=_ENV_PROFILE,
        api_key=_API_KEY,
    )


def _theorem(statement: str, theorem_name: str) -> TheoremSpec:
    return TheoremSpec(
        lean_statement=statement,
        env_profile=_ENV_PROFILE,
        header="",
        source="e2e",
        id=theorem_name,
        theorem_name=theorem_name,
    )


def _attempt_context(
    theorem_name: str,
    *,
    uses_search_state: bool,
) -> SearchAttemptContext:
    attempt_id = f"e2e-{theorem_name}-{uuid.uuid4().hex}"
    return SearchAttemptContext(
        attempt_id=attempt_id,
        search_item_id=(
            f"{attempt_id}:search" if uses_search_state else None
        ),
        verify_item_id=f"{attempt_id}:verify",
    )


def _uses_search_state(config: SearchConfig) -> bool:
    return config.algorithm not in {
        SearchAlgorithm.DIRECT,
        SearchAlgorithm.SELF_CORRECT,
    }


def _run_e2e_search(
    theorems: Sequence[TheoremSpec],
    *,
    policy: _ScriptedPolicy,
    config: SearchConfig,
    max_concurrent: int,
    backend: KiminaEnvBackend | None = None,
) -> list[SearchResult]:
    async def _drive() -> list[SearchResult]:
        active_backend = backend or KiminaEnvBackend(_backend_config())
        await active_backend.connect()
        try:
            contexts = [
                _attempt_context(
                    theorem.theorem_name or theorem.id or "anonymous",
                    uses_search_state=_uses_search_state(config),
                )
                for theorem in theorems
            ]
            return await run_search_batch(
                theorems,
                policy_client=policy,
                value_client=None,
                env_backend=active_backend,
                config=config,
                max_concurrent=max_concurrent,
                attempt_contexts=contexts,
            )
        finally:
            await active_backend.close()

    return asyncio.run(_drive())


def _run_single_e2e(
    statement: str,
    theorem_name: str,
    *,
    policy: _ScriptedPolicy,
    config: SearchConfig,
) -> SearchResult:
    results = _run_e2e_search(
        [_theorem(statement, theorem_name)],
        policy=policy,
        config=config,
        max_concurrent=1,
    )
    assert len(results) == 1
    return results[0]


def _assert_runtime_matches_final_verify(result: SearchResult) -> None:
    """The whole point: runtime-proved iff final-verify accepted."""

    assert result.training_artifacts is not None
    runtime_proved = (
        result.training_artifacts.diagnostics.get("root_runtime_status")
        == "proved"
    )
    final_accepted = result.status is SearchStatus.PROVED
    assert runtime_proved == final_accepted, (
        "runtime tree status and final /exec/verify disagree: "
        f"runtime_proved={runtime_proved}, status={result.status.value}, "
        f"verifier_status={result.diagnostics.get('verifier_status')!r}"
    )


def _tree_config(max_tactic_calls: int = 8) -> SearchConfig:
    return SearchConfig(
        algorithm=SearchAlgorithm.PUCT_TREE,
        max_tactic_calls=max_tactic_calls,
        tactics_per_expansion=1,
    )


def test_e2e_streaming_single_tactic_tree_matches_final_verify() -> None:
    result = _run_single_e2e(
        "theorem lf_e2e_true : True := by\n  sorry",
        "lf_e2e_true",
        policy=_ScriptedPolicy(),
        config=_tree_config(),
    )

    _assert_runtime_matches_final_verify(result)
    assert result.status is SearchStatus.PROVED
    assert result.proof_tree is not None and result.proof_tree.verified
    assert result.diagnostics.get("verifier_status") == "accepted"


def test_e2e_streaming_split_tree_matches_final_verify() -> None:
    # constructor splits the conjunction into two focused goals, then renders
    # `· trivial` bullets -- the assembly path most likely to diverge from a
    # per-step-PROVED runtime tree.
    result = _run_single_e2e(
        "theorem lf_e2e_and : True ∧ True := by\n  sorry",
        "lf_e2e_and",
        policy=_ScriptedPolicy(),
        config=_tree_config(),
    )

    _assert_runtime_matches_final_verify(result)
    assert result.status is SearchStatus.PROVED
    assert result.proof_tree is not None and result.proof_tree.verified
    assert len(result.proof_tree.roots[0].children) == 2


def test_e2e_streaming_nested_split_tree_matches_final_verify() -> None:
    result = _run_single_e2e(
        "theorem lf_e2e_nested_and : True ∧ (True ∧ True) := by\n  sorry",
        "lf_e2e_nested_and",
        policy=_ScriptedPolicy(),
        config=_tree_config(max_tactic_calls=12),
    )

    _assert_runtime_matches_final_verify(result)
    assert result.status is SearchStatus.PROVED
    assert result.proof_tree is not None and result.proof_tree.verified
    assert result.search_budget_used == 5


def test_e2e_streaming_tree_coalesces_concurrent_steps() -> None:
    backend = _RecordingKiminaEnvBackend(_backend_config())
    theorem_names = [
        "lf_e2e_stream_one",
        "lf_e2e_stream_two",
        "lf_e2e_stream_three",
    ]

    results = _run_e2e_search(
        [
            _theorem(f"theorem {name} : True := by\n  sorry", name)
            for name in theorem_names
        ],
        policy=_ScriptedPolicy(tactic_barrier_count=len(theorem_names)),
        config=_tree_config(),
        max_concurrent=len(theorem_names),
        backend=backend,
    )

    assert sorted(result.theorem_id for result in results) == sorted(
        theorem_names
    )
    assert all(result.status is SearchStatus.PROVED for result in results)
    assert any(size >= 2 for size in backend.step_batch_sizes), (
        "expected concurrent streaming steps to coalesce into a multi-item "
        f"/exec/step_batch call, got {backend.step_batch_sizes}"
    )


def test_e2e_streaming_direct_proof_verifies() -> None:
    result = _run_single_e2e(
        "theorem lf_e2e_direct : True := by\n  sorry",
        "lf_e2e_direct",
        policy=_ScriptedPolicy(
            proof_batches=[
                ["theorem lf_e2e_direct : True := by\n  trivial"]
            ]
        ),
        config=SearchConfig(
            algorithm=SearchAlgorithm.DIRECT,
            max_direct_candidates=1,
        ),
    )

    assert result.status is SearchStatus.PROVED
    assert result.proof_tree is not None and result.proof_tree.verified
    assert result.search_budget_used == 1


def test_e2e_streaming_direct_rejection_exhausts() -> None:
    result = _run_single_e2e(
        "theorem lf_e2e_direct_bad : True := by\n  sorry",
        "lf_e2e_direct_bad",
        policy=_ScriptedPolicy(
            proof_batches=[
                ["theorem lf_e2e_direct_bad : True := by\n  exact 0"]
            ]
        ),
        config=SearchConfig(
            algorithm=SearchAlgorithm.DIRECT,
            max_direct_candidates=1,
        ),
    )

    assert result.status is SearchStatus.EXHAUSTED
    assert result.search_budget_used == 1
    assert result.diagnostics["verify_attempts"] == 1
    assert result.diagnostics["last_feedback"]


def test_e2e_streaming_self_correct_uses_verifier_feedback() -> None:
    policy = _ScriptedPolicy(
        proof_batches=[
            ["theorem lf_e2e_self_correct : True := by\n  exact 0"],
            ["theorem lf_e2e_self_correct : True := by\n  trivial"],
        ]
    )

    result = _run_single_e2e(
        "theorem lf_e2e_self_correct : True := by\n  sorry",
        "lf_e2e_self_correct",
        policy=policy,
        config=SearchConfig(
            algorithm=SearchAlgorithm.SELF_CORRECT,
            max_direct_candidates=2,
            direct_candidates_per_round=1,
        ),
    )

    assert result.status is SearchStatus.PROVED
    assert result.search_budget_used == 2
    assert len(policy.proof_prompts) == 2
    assert "Previous verifier feedback:" in policy.proof_prompts[1]
