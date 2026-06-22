"""Checked backend lifecycle helpers for search attempts."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass

from lean_client.exec_models import ExecCancelResponse

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
    """Clean backend search state, retrying items the backend defers.

    ``/exec/cleanup`` returns one ``ExecCleanupResult`` per item; an item whose
    states are still in flight comes back with ``status == "deferred"`` instead
    of deleted. Those item ids are resubmitted, with bounded attempts and
    backoff, until the backend drains and deletes them.
    """

    if context.search_item_id is None:
        return CleanupReport(attempts=0, deleted=0, deferred=0)

    item_ids = [context.search_item_id]
    deleted_total = 0
    for attempt_index in range(context.cleanup_max_attempts):
        response = await env_backend.cleanup(item_ids)
        deleted_total += sum(
            1
            for result in response.deleted_items
            if result.status == "deleted"
        )
        deferred_item_ids = [
            result.item_id
            for result in response.deleted_items
            if result.status == "deferred"
        ]
        if not deferred_item_ids:
            return CleanupReport(
                attempts=attempt_index + 1,
                deleted=deleted_total,
                deferred=0,
            )
        item_ids = deferred_item_ids
        if attempt_index + 1 < context.cleanup_max_attempts:
            await _sleep(context.cleanup_backoff_seconds)

    return CleanupReport(
        attempts=context.cleanup_max_attempts,
        deleted=deleted_total,
        deferred=len(item_ids),
    )


async def cancel_search_state(
    env_backend: EnvBackend,
    context: SearchAttemptContext,
) -> ExecCancelResponse | None:
    """Cancel in-flight backend work for the search-state item."""

    if context.search_item_id is None:
        return None
    return await env_backend.cancel([context.search_item_id])


async def cleanup_search_state_best_effort(
    env_backend: EnvBackend,
    context: SearchAttemptContext,
) -> Mapping[str, int | str]:
    """Clean owned search state, returning diagnostics and never raising.

    Cleanup is housekeeping. It must never mask an already computed search
    result or a primary exception, so a failed cleanup is recorded as a
    ``cleanup_failed`` diagnostic instead of propagating. ``CancelledError``
    is not swallowed, so cooperative cancellation still unwinds.
    """

    try:
        report = await cleanup_search_state(env_backend, context)
    except Exception as error:
        return {
            "cleanup_attempts": context.cleanup_max_attempts,
            "cleanup_deleted": 0,
            "cleanup_failed": str(error),
        }
    return report.diagnostics()


async def cancel_search_state_best_effort(
    env_backend: EnvBackend,
    context: SearchAttemptContext,
) -> None:
    """Cancel in-flight backend work, never raising on cancel failure.

    Like cleanup, cancellation is best-effort during unwind: a failed cancel
    must not replace the ``CancelledError`` being propagated. The
    ``CancelledError`` itself is not swallowed.
    """

    try:
        await cancel_search_state(env_backend, context)
    except Exception:
        return


async def _sleep(seconds: float) -> None:
    if seconds > 0:
        await asyncio.sleep(seconds)


__all__ = [
    "CleanupReport",
    "cancel_search_state",
    "cancel_search_state_best_effort",
    "cleanup_search_state",
    "cleanup_search_state_best_effort",
]
