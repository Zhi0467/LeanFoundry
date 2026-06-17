"""Public Lean execution backend protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from leanfoundry.schemas import (
    CreateStateItem,
    CreateStatesResponse,
    ExecLimits,
    StepBatchItem,
    StepBatchResponse,
    VerifyItem,
    VerifyResponse,
)
from leanfoundry.schemas._base import LeanFoundryModel


class EnvBackendConfig(LeanFoundryModel):
    """Connection settings for a running Lean execution backend."""

    api_url: str
    env_profile: str = "default"
    api_key: str | None = None
    timeout_ms: int = 5000
    acquire_timeout_ms: int | None = None
    step_timeout_ms: int | None = None
    http_timeout_seconds: int = 60
    retries: int = 3


class EnvBackend(Protocol):
    """Algorithm-agnostic Lean execution interface."""

    async def connect(self) -> None:
        """Open transport and discover backend limits."""

    async def close(self) -> None:
        """Release transport and background batching resources."""

    async def limits(self) -> ExecLimits:
        """Return enforced backend caps and batching recommendations."""

    async def create_states(
        self,
        *,
        env_profile: str,
        items: Sequence[CreateStateItem],
    ) -> CreateStatesResponse:
        """Initialize proof states from Lean blocks with sorry goals."""

    async def step_batch(
        self,
        items: Sequence[StepBatchItem],
    ) -> StepBatchResponse:
        """Execute one batch of proof-state expansion items."""

    async def verify(
        self,
        *,
        env_profile: str,
        items: Sequence[VerifyItem],
    ) -> VerifyResponse:
        """Certify complete Lean proofs through the warm execution pool."""

    async def cleanup(self, item_ids: Sequence[str]) -> Any:
        """Delete backend state associated with completed item ids."""

    async def cancel(self, item_ids: Sequence[str]) -> Any:
        """Cancel in-flight backend work for item ids."""

    async def stats(self) -> Any:
        """Return backend operational stats."""
