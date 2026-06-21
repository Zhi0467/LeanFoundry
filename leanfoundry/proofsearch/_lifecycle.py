"""Checked backend lifecycle helpers for search attempts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from lean_client.exec_models import ExecCancelResponse, ExecCleanupResponse

from leanfoundry.env_backend import EnvBackend
from leanfoundry.proofsearch.base import SearchAttemptContext


@dataclass(frozen=True, slots=True)
class CleanupReport:
    """Summary of checked search-state cleanup."""

    attempts: int
    deleted: int
    deferred: int

    def diagnostics(self) -> dict[str, int]:
        """Return scalar result diagnostics for cleanup observability."""

        return {
            "cleanup_attempts": self.attempts,
            "cleanup_deleted": self.deleted,
            "cleanup_deferred": self.deferred,
        }


async def cleanup_search_state(
    env_backend: EnvBackend,
    context: SearchAttemptContext,
) -> CleanupReport:
    """Clean backend search state with bounded deferred retries."""

    if context.search_item_id is None:
        return CleanupReport(attempts=0, deleted=0, deferred=0)

    item_ids = [context.search_item_id]
    last_response: ExecCleanupResponse | None = None
    for attempt_index in range(context.cleanup_max_attempts):
        last_response = await env_backend.cleanup(item_ids)
        deferred = _response_items(last_response, "deferred")
        if not deferred:
            return CleanupReport(
                attempts=attempt_index + 1,
                deleted=_response_count(last_response, "deleted"),
                deferred=0,
            )
        item_ids = deferred
        if attempt_index + 1 < context.cleanup_max_attempts:
            await _sleep(context.cleanup_backoff_seconds)

    assert last_response is not None
    return CleanupReport(
        attempts=context.cleanup_max_attempts,
        deleted=_response_count(last_response, "deleted"),
        deferred=_response_count(last_response, "deferred"),
    )


async def cancel_search_state(
    env_backend: EnvBackend,
    context: SearchAttemptContext,
) -> ExecCancelResponse | None:
    """Cancel in-flight backend work for the search-state item."""

    if context.search_item_id is None:
        return None
    return await env_backend.cancel([context.search_item_id])


async def _sleep(seconds: float) -> None:
    if seconds > 0:
        await asyncio.sleep(seconds)


def _response_items(response: object, field_name: str) -> list[str]:
    value = getattr(response, field_name, None)
    if value is None:
        return []
    if isinstance(value, dict):
        return [str(key) for key in value]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    if isinstance(value, bool):
        return []
    return []


def _response_count(response: object, field_name: str) -> int:
    value: Any = getattr(response, field_name, None)
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return len(value)
    except TypeError:
        return 1


__all__ = [
    "CleanupReport",
    "cancel_search_state",
    "cleanup_search_state",
]
