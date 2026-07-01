"""Durable data-store record schemas."""

from __future__ import annotations

from typing import Literal

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
    verified_by_backend: bool = Field(
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
    header: str = Field(
        default="",
        description="Lean import/options prefix used to check the statement.",
    )
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


class AttemptLifecycleRecord(LeanFoundryModel):
    """Durable backend lifecycle item for cleanup/cancel reconciliation."""

    id: str = Field(description="Stable lifecycle record id.")
    theorem_id: str = Field(description="Theorem tied to this attempt.")
    env_profile: str = Field(description="Pinned Lean/Mathlib environment.")
    attempt_id: str = Field(description="Search attempt id.")
    backend_item_id: str = Field(description="Backend /exec item id.")
    lifecycle_stage: Literal["cleanup", "cancel"] = Field(
        description="Backend lifecycle operation that produced this record.",
    )
    lifecycle_status: str = Field(
        description="Last observed item status, for example deferred/failed.",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Cleanup/cancel attempts already made for this item.",
    )
    max_retries: int | None = Field(
        default=None,
        ge=0,
        description="Bounded retry count used by the original attempt.",
    )
    last_error: str | None = Field(
        default=None,
        description="Transport or backend error from the last operation.",
    )
    next_retry_at: str | None = Field(
        default=None,
        description="Scheduler timestamp for future reconciliation.",
    )
    terminal: bool = Field(
        default=False,
        description="Whether this lifecycle item needs no further action.",
    )
    created_at: str | None = Field(
        default=None,
        description="Storage timestamp, if assigned by the store.",
    )
    updated_at: str | None = Field(
        default=None,
        description="Last storage update timestamp, if assigned by the store.",
    )


class ExtractionFailureRecord(LeanFoundryModel):
    """Durable extraction/rendering failure tied to a search attempt."""

    id: str = Field(description="Stable extraction-failure record id.")
    theorem_id: str = Field(description="Theorem tied to this failure.")
    env_profile: str = Field(description="Pinned Lean/Mathlib environment.")
    attempt_id: str | None = Field(
        default=None,
        description="Search attempt id, if the runner allocated one.",
    )
    failure_kind: Literal["rendering", "verification", "unsupported"] = Field(
        description="Failure class from TrainingArtifacts.failures.",
    )
    message: str = Field(description="Human-readable failure detail.")
    node_id: str | None = Field(
        default=None,
        description="Runtime node id if the failure localizes to one node.",
    )
    model_version: int | None = Field(
        default=None,
        description="Model iteration that produced the failed artifact.",
    )
    created_at: str | None = Field(
        default=None,
        description="Storage timestamp, if assigned by the store.",
    )


class NegationAttemptRecord(LeanFoundryModel):
    """Durable synthetic-negation proof attempt."""

    id: str = Field(description="Stable negation-attempt record id.")
    theorem_id: str = Field(description="Theorem tied to this attempt.")
    env_profile: str = Field(description="Pinned Lean/Mathlib environment.")
    attempt_id: str | None = Field(
        default=None,
        description="Search attempt id, if the runner allocated one.",
    )
    source_node_id: str = Field(
        description="Runtime state node whose negation was checked."
    )
    negated_target: str = Field(description="Lean target wrapped in negation.")
    status: str = Field(description="Negation attempt outcome.")
    proved: bool = Field(description="Whether the negation closed.")
    proved_tactic: str | None = Field(
        default=None,
        description="Tactic that proved the negation, if any.",
    )
    tactic_calls_used: int = Field(
        ge=0,
        description="Lean tactic attempts charged for this negation check.",
    )
    rendered_lean: str | None = Field(
        default=None,
        description="Synthetic negated theorem submitted to Lean.",
    )
    payload_json: str = Field(
        description="Full serialized NegationAttempt artifact.",
    )
    model_version: int | None = Field(
        default=None,
        description="Model iteration that produced this attempt.",
    )
    created_at: str | None = Field(
        default=None,
        description="Storage timestamp, if assigned by the store.",
    )
