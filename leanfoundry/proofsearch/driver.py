"""Public concurrent search driver helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.proofsearch._common import (
    make_attempt_context,
    result_with_attempt_context,
)
from leanfoundry.proofsearch._lifecycle import (
    cancel_search_state_best_effort,
    cleanup_search_state_best_effort,
)
from leanfoundry.proofsearch.base import (
    SearchAlgorithm,
    SearchAttemptContext,
    SearchConfig,
    SearchResult,
    SearchStatus,
)
from leanfoundry.proofsearch.factory import build_engine
from leanfoundry.schemas import TheoremSpec


async def run_search_batch(
    theorems: Sequence[TheoremSpec],
    *,
    policy_client: PolicyClient,
    value_client: ValueClient | None,
    env_backend: EnvBackend,
    config: SearchConfig,
    max_concurrent: int | None = None,
    attempt_contexts: Sequence[SearchAttemptContext] | None = None,
) -> list[SearchResult]:
    """Run independent theorem searches concurrently under an in-flight cap."""

    if attempt_contexts is not None and len(attempt_contexts) != len(
        theorems
    ):
        raise ValueError("attempt_contexts must match theorem count")
    if max_concurrent is None:
        limits = await env_backend.limits()
        max_concurrent = max(1, limits.max_in_flight_exec_requests)
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be positive")

    engine = build_engine(config)
    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_one(index: int, theorem: TheoremSpec) -> SearchResult:
        if attempt_contexts is None:
            attempt_context = make_attempt_context(
                theorem,
                kind=config.algorithm.value,
                uses_search_state=_uses_search_state(config.algorithm),
            )
        else:
            attempt_context = attempt_contexts[index]
        async with semaphore:
            try:
                return await engine.search(
                    theorem,
                    attempt_context=attempt_context,
                    policy_client=policy_client,
                    value_client=value_client,
                    env_backend=env_backend,
                    config=config,
                )
            except asyncio.CancelledError:
                await cancel_search_state_best_effort(
                    env_backend,
                    attempt_context,
                )
                await cleanup_search_state_best_effort(
                    env_backend,
                    attempt_context,
                )
                raise
            except Exception as error:
                return _runner_error_result(
                    theorem,
                    attempt_context,
                    error,
                )

    # run_one defines per-theorem runner semantics: every theorem yields a
    # SearchResult, so one theorem's failure never fails the batch or orphans
    # its siblings. CancelledError still unwinds the whole gather.
    return await asyncio.gather(
        *(
            run_one(index, theorem)
            for index, theorem in enumerate(theorems)
        )
    )


def _runner_error_result(
    theorem: TheoremSpec,
    attempt_context: SearchAttemptContext,
    error: Exception,
) -> SearchResult:
    """Isolate one theorem's unexpected failure as its own ERROR result.

    The engine already attempts cleanup for any search state it owned before
    re-raising, so the runner only records the failure. Returning a result
    instead of propagating keeps a single bad theorem from failing the batch.
    """

    return result_with_attempt_context(
        SearchResult(
            theorem_id=theorem.id,
            status=SearchStatus.ERROR,
            diagnostics={
                "operational_status": "runner_exception",
                "failure_message": str(error),
            },
        ),
        attempt_context,
    )


def _uses_search_state(algorithm: SearchAlgorithm) -> bool:
    return algorithm not in {
        SearchAlgorithm.DIRECT,
        SearchAlgorithm.SELF_CORRECT,
    }


__all__ = [
    "run_search_batch",
]
