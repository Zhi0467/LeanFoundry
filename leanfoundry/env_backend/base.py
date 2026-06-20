"""Public Lean execution backend protocol.

The method signatures and return types are lean-client's /exec wire models.
This Protocol exists so the search engine depends on an interface it can fake
in tests and swap for another backend implementation (e.g. the Extension A
router) — not so LeanFoundry can keep its own copy of the wire schema.
"""

from __future__ import annotations

from typing import Protocol

from lean_client.exec_models import (
    ExecCreateStatesResponse,
    ExecLimitsResponse,
    ExecStatsResponse,
    ExecStepBatchResult,
    ExecVerifyResult,
)
from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel


class EnvBackendConfig(LeanFoundryModel):
    """Connection settings for a running Lean execution backend."""

    api_url: str = Field(description="Base URL for the running /exec server.")
    env_profile: str = Field(
        default="default",
        description="Default execution environment profile for requests.",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional auth token for the backend transport.",
    )
    timeout_ms: int = Field(
        default=5000,
        ge=1,
        description="Default per-call timeout passed to the backend.",
    )
    acquire_timeout_ms: int | None = Field(
        default=None,
        description="Timeout for acquiring a compatible Lean worker.",
    )
    step_timeout_ms: int | None = Field(
        default=None,
        description="Timeout for Lean execution after worker acquisition.",
    )
    http_timeout_seconds: int = Field(
        default=60,
        ge=1,
        description="HTTP client timeout for backend requests.",
    )
    retries: int = Field(
        default=3,
        ge=0,
        description="Transport-level retry count for retryable failures.",
    )


class EnvBackend(Protocol):
    """Algorithm-agnostic Lean execution interface."""

    async def connect(self) -> None:
        """Open transport and size batching from /exec/limits."""

    async def close(self) -> None:
        """Release transport and background batching resources."""

    async def limits(self) -> ExecLimitsResponse:
        """Return enforced backend caps and batching recommendations."""

    async def create_states(
        self,
        item_id: str,
        code: str,
        *,
        env_profile: str | None = None,
    ) -> ExecCreateStatesResponse:
        """Initialize proof states from a Lean block with sorry goals."""

    async def step(
        self,
        node_id: str,
        state_token: str,
        tactics: list[str],
        *,
        goal_group: tuple[int, ...] | None = None,
        timeout_ms: int | None = None,
    ) -> ExecStepBatchResult:
        """Expand one proof state with N tactics.

        This is the search hot path. The backend coalesces concurrent step
        calls from independent theorem searches into one /exec/step_batch
        request, so callers submit one state at a time and never assemble
        cross-theorem batches themselves.

        ``goal_group`` resumes an exact subset of the state's goals (by their
        public positions) as one focused subtree before running the tactics —
        how a split child node resumes itself from a shared parent token.
        """

    async def verify_one(
        self,
        item_id: str,
        code: str,
        theorem_name: str,
        *,
        allowed_axioms: list[str] | None = None,
        env_profile: str | None = None,
    ) -> ExecVerifyResult:
        """Certify one complete Lean proof through the warm execution pool."""

    async def cleanup(self, item_ids: list[str]) -> object:
        """Delete backend state associated with completed item ids."""

    async def cancel(self, item_ids: list[str]) -> object:
        """Cancel in-flight backend work for item ids."""

    async def stats(self) -> ExecStatsResponse:
        """Return backend operational stats."""
