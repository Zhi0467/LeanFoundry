"""Theorem schemas."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel


class TheoremSpec(LeanFoundryModel):
    """In-memory theorem request passed to search."""

    lean_statement: str = Field(min_length=1)
    env_profile: str = Field(min_length=1)
    header: str
    source: str = Field(default="unknown", min_length=1)
    id: str | None = None
    theorem_name: str | None = None
    informal_statement: str | None = None
    initial_lean_block: str | None = None
    allowed_axioms: list[str] | None = None
