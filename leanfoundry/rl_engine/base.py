"""Public RL engine protocol."""

from __future__ import annotations

from typing import Protocol

from pydantic import Field

from leanfoundry.policy import PolicyClient
from leanfoundry.schemas import TrainingSample
from leanfoundry.schemas._base import LeanFoundryModel


class Checkpoint(LeanFoundryModel):
    """Identifier for a model checkpoint visible to search."""

    checkpoint_id: str = Field(description="Stable checkpoint identifier.")
    uri: str | None = Field(
        default=None,
        description="Optional storage URI or serving endpoint.",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Small string metadata for reproducibility.",
    )


class RLEngineBase(Protocol):
    """Adapter boundary between LeanFoundry and a training orchestrator."""

    async def submit_samples(self, samples: list[TrainingSample]) -> None:
        """Submit verified samples to the training engine."""

    async def get_policy_client(self) -> PolicyClient:
        """Return the current policy client."""

    async def current_checkpoint(self) -> str:
        """Return the current checkpoint identifier."""

    async def wait_for_update(self) -> Checkpoint:
        """Block until a new checkpoint is ready."""
