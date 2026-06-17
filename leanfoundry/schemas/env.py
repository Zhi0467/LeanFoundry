"""Environment profile schemas."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel


class EnvProfile(LeanFoundryModel):
    """Pinned Lean and Mathlib execution environment."""

    lean_version: str = Field(min_length=1)
    mathlib_commit: str = Field(min_length=7)
    imports: list[str] = Field(default_factory=list)
    header: str
    header_hash: str = Field(min_length=1)
    loogle_index_path: str | None = None
    premise_index_path: str | None = None


class StateRecord(LeanFoundryModel):
    """Backend-owned state-token metadata."""

    token: str
    path: str
    env_profile: str
    header_hash: str
    lean_version: str
    mathlib_commit: str
    imports: list[str] = Field(default_factory=list)
    raw_bytes: int = Field(ge=0)
    created_at: float
    last_accessed_at: float
    ttl_seconds: int = Field(ge=1)
