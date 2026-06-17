"""Lean /exec request and response schemas owned by LeanFoundry."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel

ExecStatus = Literal[
    "open",
    "complete",
    "error",
    "invalid_state_token",
    "overloaded",
    "cancelled",
]
VerifyStatus = Literal[
    "accepted",
    "rejected",
    "error",
    "overloaded",
    "cancelled",
]
MessageSeverity = Literal["trace", "info", "warning", "error"]


class ExecPos(LeanFoundryModel):
    """Source position reported by Lean."""

    line: int = Field(ge=1)
    col: int = Field(ge=0)


class ExecMessage(LeanFoundryModel):
    """Structured Lean diagnostic message."""

    severity: MessageSeverity
    data: str
    pos: ExecPos | None = None
    end_pos: ExecPos | None = None


class ExecDiagnostics(LeanFoundryModel):
    """Execution timing diagnostics returned by the backend."""

    acquire_ms: float = Field(ge=0)
    lean_ms: float = Field(ge=0)
    debug: dict[str, float | int | str] | None = None


class TimeoutConfig(LeanFoundryModel):
    """Common per-item timeout controls."""

    acquire_timeout_ms: int = Field(default=5000, ge=1)
    step_timeout_ms: int = Field(default=5000, ge=1)
    debug: bool = False


class CreateStateItem(TimeoutConfig):
    """One Lean block used to create sorry-root proof states."""

    item_id: str = Field(min_length=1)
    code: str = Field(min_length=1)


class Hypothesis(LeanFoundryModel):
    """One local-context hypothesis."""

    type: str
    name: str | None = None
    value: str | None = None


class GoalInfo(LeanFoundryModel):
    """Structured goal info returned by step execution."""

    target: str
    pretty: str = ""
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    name: str | None = None
    sibling_dep: list[int] = Field(default_factory=list)


class StateInfo(LeanFoundryModel):
    """Opaque state token plus the visible goals it represents."""

    state_token: str = Field(min_length=1)
    goals: list[GoalInfo] = Field(default_factory=list)


class CreateStatesResult(LeanFoundryModel):
    """Result for one create-states item."""

    item_id: str
    status: ExecStatus
    states: list[StateInfo] = Field(default_factory=list)
    messages: list[ExecMessage] = Field(default_factory=list)
    diagnostics: ExecDiagnostics | None = None


class CreateStatesResponse(LeanFoundryModel):
    """Batch response for create-states."""

    items: list[CreateStatesResult]


class StepBatchItem(TimeoutConfig):
    """One proof-state expansion item: one state token, many tactics."""

    node_id: str = Field(min_length=1)
    state_token: str = Field(min_length=1)
    tactics: list[str] = Field(min_length=1)


class StepResult(LeanFoundryModel):
    """Result of applying one tactic candidate."""

    tactic: str
    status: ExecStatus
    state_token: str | None = None
    goals: list[GoalInfo] = Field(default_factory=list)
    messages: list[ExecMessage] = Field(default_factory=list)


class StepBatchResult(LeanFoundryModel):
    """Results for one proof-state expansion item."""

    node_id: str
    results: list[StepResult] = Field(default_factory=list)
    diagnostics: ExecDiagnostics | None = None


class StepBatchResponse(LeanFoundryModel):
    """Batch response for step execution."""

    items: list[StepBatchResult]


class VerifyItem(TimeoutConfig):
    """One complete Lean proof submitted for reward-grade certification."""

    item_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    theorem_name: str = Field(min_length=1)
    allowed_axioms: list[str] | None = None


class VerifyResult(LeanFoundryModel):
    """Verification result for one complete proof."""

    item_id: str
    status: VerifyStatus
    theorem_name: str
    axioms: list[str] = Field(default_factory=list)
    messages: list[ExecMessage] = Field(default_factory=list)
    diagnostics: ExecDiagnostics | None = None


class VerifyResponse(LeanFoundryModel):
    """Batch response for proof verification."""

    items: list[VerifyResult]


class ExecLimits(LeanFoundryModel):
    """Backend-enforced safety caps and client batching recommendations."""

    max_pantograph_workers: int = Field(ge=1)
    max_lean_processes_per_env_profile: int = Field(ge=1)
    max_items_per_step_batch: int = Field(ge=1)
    max_tactics_per_step_item: int = Field(ge=1)
    max_attempts_per_step_batch: int = Field(ge=1)
    max_create_items_per_request: int = Field(ge=1)
    max_in_flight_exec_requests: int = Field(ge=1)
    max_queued_exec_requests: int = Field(ge=0)
    max_state_store_bytes: int = Field(ge=1)
    allow_unbounded_exec: bool = False
    max_acquire_timeout_ms: int = Field(ge=1)
    max_step_timeout_ms: int = Field(ge=1)
    recommended_items_per_step_batch: int = Field(ge=1)
    recommended_in_flight_step_batches: int = Field(ge=1)
    single_process: bool = True
    same_item_id_pipelining: bool = False
    cleanup_policy: str = "defer_while_in_flight"
