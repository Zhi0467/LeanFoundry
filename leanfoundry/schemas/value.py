"""Value-label schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel
from leanfoundry.schemas.proof_state import FactorizedProofState


class ValueLabel(LeanFoundryModel):
    """Supervised value label extracted from search traces."""

    state: FactorizedProofState = Field(
        description="Proof state that the value model should learn to score."
    )
    label: Literal[0, 1] = Field(
        description="1 means proved; 0 means negative or disproved."
    )
    weight: float = Field(
        default=1.0,
        ge=0,
        description="Loss weight; censored negatives are downweighted.",
    )
    disproved: bool = Field(
        default=False,
        description="True only when search proved the negated goal.",
    )
    theorem_id: str | None = Field(
        default=None,
        description="Source theorem id for this label, if available.",
    )
    env_profile: str = Field(
        description="Pinned Lean/Mathlib environment for the labeled state."
    )
    proof_state_hash: str | None = Field(
        default=None,
        description="Diagnostic or dedup hash for the proof state.",
    )
    depth: int | None = Field(
        default=None,
        ge=0,
        description="Search depth where this state appeared.",
    )
    tactics_tried_on_subtree: int | None = Field(
        default=None,
        ge=0,
        description="Effort spent below this state before labeling it.",
    )
    model_version: int = Field(
        description="Policy/value model iteration that produced this label."
    )
