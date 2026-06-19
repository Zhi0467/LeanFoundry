"""Durable data-store record schemas."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel
from leanfoundry.schemas.theorem import TheoremSpec


class TheoremRecord(TheoremSpec):
    """B-type theorem statement record."""

    id: str = Field(description="Durable theorem id.")
    difficulty_estimate: float | None = Field(
        default=None,
        description="Optional estimated theorem difficulty.",
    )
    pass_rate_current: float | None = Field(
        default=None,
        description="Current measured solve rate for frontier selection.",
    )
    pass_rate_updated_at: str | None = Field(
        default=None,
        description="Timestamp for pass_rate_current.",
    )
    split: str = Field(
        default="train",
        description="Dataset split: train, validation, test, or staging.",
    )
    added_at: str | None = Field(
        default=None,
        description="Storage timestamp, if assigned by the store.",
    )


class ATypeDataRecord(LeanFoundryModel):
    """Verified theorem/proof training sample."""

    id: str = Field(description="Durable training sample id.")
    theorem_id: str = Field(description="Theorem proved by this sample.")
    env_profile: str = Field(description="Environment used to verify proof.")
    header: str = Field(description="Lean header used with this proof.")
    lean_proof: str = Field(description="Complete verified Lean proof.")
    proof_hash: str = Field(description="Dedup hash of the proof text.")
    verified_by_kimina: bool = Field(
        default=True,
        description="Whether this proof passed the backend verifier.",
    )
    proof_type: str | None = Field(
        default=None,
        description="Training format: whole_proof, tactic_sequence, etc.",
    )
    tactic_sequence: str | None = Field(
        default=None,
        description="Serialized proof tree or flattened tactic data.",
    )
    correction_input: str | None = Field(
        default=None,
        description="Compiler feedback context for self-correction data.",
    )
    source: str = Field(description="Origin of this verified proof sample.")
    model_version: int | None = Field(
        default=None,
        description="Model iteration that found this proof, when applicable.",
    )
    created_at: str | None = Field(
        default=None,
        description="Storage timestamp, if assigned by the store.",
    )


class FormalStatementStagingRecord(LeanFoundryModel):
    """Autoformalized statement waiting for theorem promotion."""

    id: str = Field(description="Durable staging record id.")
    informal_source: str | None = Field(
        default=None,
        description="Source document or benchmark for the informal statement.",
    )
    informal_statement: str | None = Field(
        default=None,
        description="Natural-language statement being formalized.",
    )
    lean_statement: str = Field(description="Generated Lean statement.")
    env_profile: str = Field(description="Environment used for syntax checks.")
    formalizer_version: str | None = Field(
        default=None,
        description="Formalizer model or prompt version.",
    )
    semantic_judge_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="LLM judge confidence in semantic faithfulness.",
    )
    syntax_checked: bool = Field(
        default=False,
        description="Whether Lean accepted the statement with sorry body.",
    )
    dedup_hash: str | None = Field(
        default=None,
        description="Dedup hash for the generated statement.",
    )
    promoted_to_theorems: bool = Field(
        default=False,
        description="Whether this record has entered the theorem table.",
    )
