"""Public search engine contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import Field

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.schemas import ProofTree, TheoremSpec
from leanfoundry.schemas._base import LeanFoundryModel


class SearchAlgorithm(StrEnum):
    """Search modes called out by the design roadmap."""

    DIRECT = "direct"
    SELF_CORRECT = "self_correct"
    TACTIC_BEAM = "tactic_beam"
    BEST_FIRST = "best_first"
    PUCT_TREE = "puct_tree"
    OPTIMISTIC = "optimistic"
    MCGS = "mcgs"
    AND_OR_MCGS = "and_or_mcgs"


class SearchStatus(StrEnum):
    """Top-level result status for one theorem search."""

    PROVED = "proved"
    DISPROVED = "disproved"
    EXHAUSTED = "exhausted"
    ERROR = "error"
    CANCELLED = "cancelled"


class SearchConfig(LeanFoundryModel):
    """Algorithm-neutral search configuration."""

    algorithm: SearchAlgorithm = SearchAlgorithm.TACTIC_BEAM
    max_tactic_calls: int = 100
    tactics_per_expansion: int = 8
    try_negation: bool = False
    value_mode: str = "unbonded"
    censored_negative_weight: float = 0.25
    min_censored_negative_effort: int = 50


class SearchResult(LeanFoundryModel):
    """Persistable summary of one theorem search attempt."""

    theorem_id: str | None = None
    status: SearchStatus
    proof_tree: ProofTree | None = None
    search_budget_used: int = 0
    diagnostics: dict[str, float | int | str] = Field(default_factory=dict)


class SearchEngine(Protocol):
    """Common interface for all LeanFoundry search algorithms."""

    async def search(
        self,
        theorem: TheoremSpec,
        *,
        policy_client: PolicyClient,
        value_client: ValueClient | None,
        env_backend: EnvBackend,
        config: SearchConfig,
    ) -> SearchResult:
        """Run proof search for one theorem."""
