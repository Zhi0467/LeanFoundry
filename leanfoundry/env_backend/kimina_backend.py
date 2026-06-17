"""Adapter for the current lean-client /exec facade.

This is intentionally the only module in LeanFoundry that imports lean_client.
Everything else depends on EnvBackend.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from leanfoundry.env_backend.base import EnvBackendConfig
from leanfoundry.schemas import (
    CreateStateItem,
    CreateStatesResponse,
    ExecLimits,
    StepBatchItem,
    StepBatchResponse,
    VerifyItem,
    VerifyResponse,
)


class KiminaEnvBackend:
    """EnvBackend adapter backed by lean_client.AsyncLeanExecBackend."""

    def __init__(self, config: EnvBackendConfig) -> None:
        self.config = config
        self._backend: Any | None = None

    async def connect(self) -> None:
        from lean_client import AsyncLeanExecBackend

        self._backend = await AsyncLeanExecBackend.connect(
            self.config.api_url,
            env_profile=self.config.env_profile,
            api_key=self.config.api_key,
            timeout_ms=self.config.timeout_ms,
            acquire_timeout_ms=self.config.acquire_timeout_ms,
            step_timeout_ms=self.config.step_timeout_ms,
            http_timeout=self.config.http_timeout_seconds,
            n_retries=self.config.retries,
        )

    async def close(self) -> None:
        if self._backend is not None:
            await self._backend.aclose()
            self._backend = None

    async def limits(self) -> ExecLimits:
        response = await self._require_backend().limits()
        return ExecLimits.model_validate(response.model_dump())

    async def create_states(
        self,
        *,
        env_profile: str,
        items: Sequence[CreateStateItem],
    ) -> CreateStatesResponse:
        from lean_client import ExecCreateStateItem

        lean_items = []
        for item in items:
            dumped = item.model_dump()
            lean_items.append(ExecCreateStateItem.model_validate(dumped))
        response = await self._require_backend().create_states_batch(
            lean_items,
            env_profile=env_profile,
        )
        return CreateStatesResponse.model_validate(response.model_dump())

    async def step_batch(
        self,
        items: Sequence[StepBatchItem],
    ) -> StepBatchResponse:
        from lean_client import ExecStepBatchItem

        lean_items = []
        for item in items:
            dumped = item.model_dump()
            lean_items.append(ExecStepBatchItem.model_validate(dumped))
        response = await self._require_backend().step_batch(lean_items)
        return StepBatchResponse.model_validate(response.model_dump())

    async def verify(
        self,
        *,
        env_profile: str,
        items: Sequence[VerifyItem],
    ) -> VerifyResponse:
        from lean_client import ExecVerifyItem

        lean_items = [
            ExecVerifyItem.model_validate(item.model_dump()) for item in items
        ]
        response = await self._require_backend().verify(
            lean_items,
            env_profile=env_profile,
        )
        return VerifyResponse.model_validate(response.model_dump())

    async def cleanup(self, item_ids: Sequence[str]) -> Any:
        return await self._require_backend().cleanup(list(item_ids))

    async def cancel(self, item_ids: Sequence[str]) -> Any:
        return await self._require_backend().cancel(list(item_ids))

    async def stats(self) -> Any:
        return await self._require_backend().stats()

    def _require_backend(self) -> Any:
        if self._backend is None:
            raise RuntimeError("EnvBackend is not connected")
        return self._backend
