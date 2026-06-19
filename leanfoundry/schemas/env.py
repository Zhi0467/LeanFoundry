"""Environment profile schemas."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel


class EnvProfile(LeanFoundryModel):
    """Pinned Lean and Mathlib execution environment."""

    lean_version: str = Field(
        min_length=1,
        description="Exact Lean version used to execute proofs.",
    )
    mathlib_commit: str = Field(
        min_length=7,
        description="Mathlib git commit used by this environment.",
    )
    imports: list[str] = Field(
        default_factory=list,
        description="Lean imports expected in this environment.",
    )
    header: str = Field(description="Full Lean import/options header text.")
    header_hash: str = Field(
        min_length=1,
        description="Hash of the header used for worker reuse and routing.",
    )
    loogle_index_path: str | None = Field(
        default=None,
        description="Optional Loogle index path for this profile.",
    )
    premise_index_path: str | None = Field(
        default=None,
        description="Optional path to the premise index for this profile.",
    )


class StateRecord(LeanFoundryModel):
    """Backend-owned state-token metadata."""

    token: str = Field(description="Opaque state token exposed to clients.")
    path: str = Field(description="Backend-local file path for saved state.")
    env_profile: str = Field(description="Env profile for this state.")
    header_hash: str = Field(description="Header hash for state routing.")
    lean_version: str = Field(description="Lean version used to create state.")
    mathlib_commit: str = Field(description="Mathlib commit used for state.")
    imports: list[str] = Field(
        default_factory=list,
        description="Lean imports loaded for this state.",
    )
    raw_bytes: int = Field(
        ge=0,
        description="Serialized state size in bytes.",
    )
    created_at: float = Field(description="Backend creation timestamp.")
    last_accessed_at: float = Field(description="Last access timestamp.")
    ttl_seconds: int = Field(
        ge=1,
        description="Time-to-live before backend may evict this state.",
    )
