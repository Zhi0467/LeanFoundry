"""Public concurrent search driver helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.proofsearch.base import SearchConfig, SearchResult
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
) -> list[SearchResult]:
    """Run independent theorem searches concurrently under an in-flight cap."""

    if max_concurrent is None:
        limits = await env_backend.limits()
        max_concurrent = max(1, limits.max_in_flight_exec_requests)
    if max_concurrent < 1:
        raise ValueError("max_concurrent must be positive")

    engine = build_engine(config)
    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_one(theorem: TheoremSpec) -> SearchResult:
        async with semaphore:
            return await engine.search(
                theorem,
                policy_client=policy_client,
                value_client=value_client,
                env_backend=env_backend,
                config=config,
            )

    return await asyncio.gather(*(run_one(theorem) for theorem in theorems))


__all__ = [
    "run_search_batch",
]
