"""Theorem schemas."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel


class TheoremSpec(LeanFoundryModel):
    """In-memory theorem request passed to search."""

    lean_statement: str = Field(
        min_length=1,
        description="Lean theorem statement, usually with no completed proof.",
    )
    env_profile: str = Field(
        min_length=1,
        description="Pinned Lean/Mathlib environment for this theorem.",
    )
    header: str = Field(
        description="Lean import/options prefix before the statement.",
    )
    source: str = Field(
        default="unknown",
        min_length=1,
        description="Dataset/provenance label; gates behavior like negation.",
    )
    id: str | None = Field(
        default=None,
        description="Durable theorem id, if this came from the theorem store.",
    )
    theorem_name: str | None = Field(
        default=None,
        description="Name used for final verification and axiom printing.",
    )
    informal_statement: str | None = Field(
        default=None,
        description="Natural-language statement, if available.",
    )
    initial_lean_block: str | None = Field(
        default=None,
        description="Optional Lean block with sorry placeholders.",
    )
    allowed_axioms: list[str] | None = Field(
        default=None,
        description="Axiom allow-list; None uses verifier default.",
    )
