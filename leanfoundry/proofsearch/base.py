"""Public search engine contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol

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

    algorithm: SearchAlgorithm = Field(
        default=SearchAlgorithm.TACTIC_BEAM,
        description="Search strategy to run for this theorem.",
    )
    max_tactic_calls: int = Field(
        default=100,
        ge=1,
        description="Hard budget on Lean tactic attempts for one theorem.",
    )
    tactics_per_expansion: int = Field(
        default=8,
        ge=1,
        description="Number of policy tactic candidates per expanded state.",
    )
    try_negation: bool = Field(
        default=False,
        description="Whether search may prove negated single-goal states.",
    )
    value_mode: Literal["bonded", "unbonded"] = Field(
        default="unbonded",
        description=(
            "bonded: LeanFoundry wraps the policy endpoint with a "
            "task token to get value estimates from the same model, "
            "and owns writing state_value_labels (proved=1, "
            "censored-negative=0 low-weight, disproved=0 full-weight). "
            "unbonded: training repo supplies its own ValueClient and "
            "LeanFoundry does not write state_value_labels at all."
        ),
    )
    censored_negative_weight: float = Field(
        default=0.25,
        ge=0,
        description="Training weight for searched-but-unproved states.",
    )
    min_censored_negative_effort: int = Field(
        default=50,
        ge=1,
        description="Tactics tried before emitting a censored negative.",
    )


class SearchResult(LeanFoundryModel):
    """Persistable summary of one theorem search attempt."""

    theorem_id: str | None = Field(
        default=None,
        description="The theorem id when the input theorem came from storage.",
    )
    status: SearchStatus = Field(
        description="Final search outcome for this theorem attempt."
    )
    proof_tree: ProofTree | None = Field(
        default=None,
        description="Solved proof projection, present only when proof exists.",
    )
    search_budget_used: int = Field(
        default=0,
        ge=0,
        description="Number of Lean tactic attempts consumed by the search.",
    )
    diagnostics: dict[str, float | int | str] = Field(
        default_factory=dict,
        description="Small scalar metrics useful for debugging and reporting.",
    )


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
