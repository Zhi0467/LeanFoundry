"""Public evaluation runner protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from leanfoundry.policy import PolicyClient
from leanfoundry.proofsearch import SearchConfig
from leanfoundry.schemas import EvalArtifactManifest, TheoremSpec


class EvalRunner(Protocol):
    """Run a benchmark against a fixed model and search configuration."""

    async def run(
        self,
        *,
        benchmark: Sequence[TheoremSpec],
        policy_client: PolicyClient,
        search_config: SearchConfig,
    ) -> EvalArtifactManifest:
        """Produce an eval artifact manifest for downstream reporting."""
