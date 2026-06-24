"""Checked backend lifecycle helpers for search attempts."""

from __future__ import annotations

import asyncio
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
    failed: str | None = None

    def diagnostics(self) -> dict[str, int | str]:
        """Return scalar result diagnostics for cleanup observability."""

        report: dict[str, int | str] = {
            "cleanup_attempts": self.attempts,
            "cleanup_deleted": self.deleted,
            "cleanup_deferred": self.deferred,
        }
        if self.failed is not None:
            report["cleanup_failed"] = self.failed
        return report


async def cleanup_search_state(
    env_backend: EnvBackend,
    context: SearchAttemptContext,
) -> CleanupReport:
    """Clean backend search state, retrying items the backend defers.

    ``/exec/cleanup`` returns one ``ExecCleanupResult`` per item; an item whose
    states are still in flight comes back with ``status == "deferred"`` instead
    of deleted. Those item ids are resubmitted, with bounded attempts and
    backoff, until the backend drains and deletes them.

    Cleanup is housekeeping and must never mask a primary outcome, so a
    backend/transport exception is captured into the report as ``failed``
    together with the actual attempt count, rather than raised.
    ``CancelledError`` still propagates so cooperative cancellation unwinds.
    """

    if context.search_item_id is None:
        return CleanupReport(attempts=0, deleted=0, deferred=0)

    item_ids = [context.search_item_id]
    deleted_total = 0
    for attempt_index in range(context.cleanup_max_attempts):
        try:
            response = await env_backend.cleanup(item_ids)
        except Exception as error:
            return CleanupReport(
                attempts=attempt_index + 1,
                deleted=deleted_total,
                deferred=len(item_ids),
                failed=str(error),
            )
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


async def cancel_item_ids_best_effort(
    env_backend: EnvBackend,
    item_ids: list[str],
) -> None:
    """Cancel explicit backend item ids, never raising on cancel failure."""

    if not item_ids:
        return
    try:
        await env_backend.cancel(_unique_item_ids(item_ids))
    except Exception:
        return


async def cancel_search_state(
    env_backend: EnvBackend,
    context: SearchAttemptContext,
) -> ExecCancelResponse | None:
    """Cancel in-flight backend work for tree search and verifier items."""

    item_ids = _attempt_cancel_item_ids(context)
    if not item_ids:
        return None
    return await env_backend.cancel(item_ids)


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


def _attempt_cancel_item_ids(context: SearchAttemptContext) -> list[str]:
    if context.search_item_id is None:
        return []
    return _unique_item_ids([context.search_item_id, context.verify_item_id])


def _unique_item_ids(item_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(item_ids))


async def _sleep(seconds: float) -> None:
    if seconds > 0:
        await asyncio.sleep(seconds)


__all__ = [
    "CleanupReport",
    "cancel_item_ids_best_effort",
    "cancel_search_state",
    "cancel_search_state_best_effort",
    "cleanup_search_state",
]
