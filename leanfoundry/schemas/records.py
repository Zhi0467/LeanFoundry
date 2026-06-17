"""Durable data-store record schemas."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel
from leanfoundry.schemas.theorem import TheoremSpec


class TheoremRecord(TheoremSpec):
    """B-type theorem statement record."""

    id: str
    difficulty_estimate: float | None = None
    pass_rate_current: float | None = None
    pass_rate_updated_at: str | None = None
    split: str = "train"
    added_at: str | None = None


class ATypeDataRecord(LeanFoundryModel):
    """Verified theorem/proof training sample."""

    id: str
    theorem_id: str
    env_profile: str
    header: str
    lean_proof: str
    proof_hash: str
    verified_by_kimina: bool = True
    proof_type: str | None = None
    tactic_sequence_json: str | None = None
    correction_input: str | None = None
    source: str
    model_version: int | None = None
    created_at: str | None = None


class FormalStatementStagingRecord(LeanFoundryModel):
    """Autoformalized statement waiting for theorem promotion."""

    id: str
    informal_source: str | None = None
    informal_statement: str | None = None
    lean_statement: str
    env_profile: str
    formalizer_version: str | None = None
    semantic_judge_score: float | None = Field(default=None, ge=0, le=1)
    syntax_checked: bool = False
    dedup_hash: str | None = None
    promoted_to_theorems: bool = False
