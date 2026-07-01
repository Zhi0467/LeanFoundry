"""Adapter binding the EnvBackend protocol to lean_client's exec backend.

This is the only module in LeanFoundry that constructs the lean_client backend
façade. Every other module depends on the EnvBackend protocol, not on this
class. Calls forward straight to AsyncLeanExecBackend with no schema
round-tripping, because the protocol already speaks lean_client's wire types.
"""

from __future__ import annotations

from lean_client import AsyncLeanExecBackend
from lean_client.exec_models import (
    ExecCancelResponse,
    ExecCleanupResponse,
    ExecCreateStatesResponse,
    ExecLimitsResponse,
    ExecStatsResponse,
    ExecStepBatchResult,
    ExecVerifyItem,
    ExecVerifyResponse,
    ExecVerifyResult,
)

from leanfoundry.env_backend.base import EnvBackendConfig


class KiminaEnvBackend:
    """EnvBackend backed by lean_client.AsyncLeanExecBackend."""

    def __init__(self, config: EnvBackendConfig) -> None:
        self.config = config
        self._backend: AsyncLeanExecBackend | None = None

    async def connect(self) -> None:
        self._backend = await AsyncLeanExecBackend.connect(
            self.config.api_url,
            env_profile=self.config.env_profile,
            api_key=self.config.api_key,
            timeout_ms=self.config.timeout_ms,
            acquire_timeout_ms=self.config.acquire_timeout_ms,
            step_timeout_ms=self.config.step_timeout_ms,
            http_timeout=self.config.http_timeout_seconds,
            n_retries=self.config.retries,
            max_overloaded_retries=self.config.max_overloaded_retries,
            overload_backoff_seconds=self.config.overload_backoff_seconds,
        )

    async def close(self) -> None:
        if self._backend is not None:
            await self._backend.aclose()
            self._backend = None

    async def limits(self) -> ExecLimitsResponse:
        return await self._require_backend().limits()

    async def create_states(
        self,
        item_id: str,
        code: str,
        *,
        env_profile: str | None = None,
    ) -> ExecCreateStatesResponse:
        return await self._require_backend().create_states(
            item_id,
            code,
            env_profile=env_profile,
        )

    async def step(
        self,
        node_id: str,
        state_token: str,
        tactics: list[str],
        *,
        goal_group: tuple[int, ...] | None = None,
        timeout_ms: int | None = None,
    ) -> ExecStepBatchResult:
        return await self._require_backend().step(
            node_id,
            state_token,
            tactics,
            timeout_ms=timeout_ms,
            goal_group=list(goal_group) if goal_group is not None else None,
        )

    async def verify_one(
        self,
        item_id: str,
        code: str,
        theorem_name: str,
        *,
        allowed_axioms: list[str] | None = None,
        env_profile: str | None = None,
    ) -> ExecVerifyResult:
        return await self._require_backend().verify_one(
            item_id,
            code,
            theorem_name,
            allowed_axioms=allowed_axioms,
            env_profile=env_profile,
        )

    async def verify(
        self,
        items: list[ExecVerifyItem],
        *,
        env_profile: str | None = None,
    ) -> ExecVerifyResponse:
        return await self._require_backend().verify(
            items,
            env_profile=env_profile,
        )

    async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
        return await self._require_backend().cleanup(item_ids)

    async def cancel(self, item_ids: list[str]) -> ExecCancelResponse:
        return await self._require_backend().cancel(item_ids)

    async def stats(self) -> ExecStatsResponse:
        return await self._require_backend().stats()

    def _require_backend(self) -> AsyncLeanExecBackend:
        if self._backend is None:
            raise RuntimeError("EnvBackend is not connected")
        return self._backend
