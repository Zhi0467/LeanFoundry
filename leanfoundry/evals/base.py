"""Public evaluation runner protocol."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.proofsearch import SearchConfig
from leanfoundry.schemas import (
    BenchmarkManifest,
    EvalArtifactManifest,
    TheoremSpec,
)


class EvalRunner(Protocol):
    """Run a benchmark against a fixed model and search configuration."""

    async def run(
        self,
        *,
        benchmark: Sequence[TheoremSpec],
        policy_client: PolicyClient,
        env_backend: EnvBackend,
        search_config: SearchConfig,
        value_client: ValueClient | None = None,
        benchmark_manifest: BenchmarkManifest | None = None,
        artifact_dir: str | Path | None = None,
    ) -> EvalArtifactManifest:
        """Produce an eval artifact manifest for downstream reporting."""
