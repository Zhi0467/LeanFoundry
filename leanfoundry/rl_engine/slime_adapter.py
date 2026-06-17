"""Slime adapter placeholder.

This file is intentionally the only Slime-named module. The implementation will
be added after a pinned Slime commit and compatibility tests are chosen.
"""

from __future__ import annotations

from leanfoundry.policy import PolicyClient
from leanfoundry.rl_engine.base import Checkpoint
from leanfoundry.schemas import TrainingSample


class SlimeAdapter:
    """Adapter for a pinned Slime release."""

    async def submit_samples(self, samples: list[TrainingSample]) -> None:
        raise NotImplementedError("SlimeAdapter is not implemented yet")

    async def get_policy_client(self) -> PolicyClient:
        raise NotImplementedError("SlimeAdapter is not implemented yet")

    async def current_checkpoint(self) -> str:
        raise NotImplementedError("SlimeAdapter is not implemented yet")

    async def wait_for_update(self) -> Checkpoint:
        raise NotImplementedError("SlimeAdapter is not implemented yet")
