"""Replay-store reconciliation for backend lifecycle outbox rows."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable

from lean_client.exec_models import ExecCancelResult, ExecCleanupResult

from leanfoundry.env_backend import EnvBackend
from leanfoundry.replay.base import ReplayStore
from leanfoundry.schemas import AttemptLifecycleRecord


@dataclass(frozen=True, slots=True)
class LifecycleReconciliationReport:
    """Counters from one lifecycle reconciliation pass."""

    records_seen: int
    cleanup_attempted: int
    cancel_attempted: int
    terminal: int
    pending: int
    failed: int
    orphaned: int

    def diagnostics(self) -> dict[str, int]:
        """Return scalar diagnostics for logs or metrics."""

        return {
            "lifecycle_records_seen": self.records_seen,
            "lifecycle_cleanup_attempted": self.cleanup_attempted,
            "lifecycle_cancel_attempted": self.cancel_attempted,
            "lifecycle_terminal": self.terminal,
            "lifecycle_pending": self.pending,
            "lifecycle_failed": self.failed,
            "lifecycle_orphaned": self.orphaned,
        }


@dataclass(frozen=True, slots=True)
class LifecycleOperatorAlert:
    """Operator-facing alert emitted by lifecycle reconciliation."""

    severity: str
    message: str
    diagnostics: dict[str, int]


@dataclass(frozen=True, slots=True)
class LifecycleSchedulerReport:
    """Summary from one bounded periodic reconciliation run."""

    passes: int
    reports: tuple[LifecycleReconciliationReport, ...]
    alerts: tuple[LifecycleOperatorAlert, ...]

    def diagnostics(self) -> dict[str, int]:
        """Aggregate scalar diagnostics across scheduler passes."""

        diagnostics: dict[str, int] = {
            "lifecycle_scheduler_passes": self.passes
        }
        for report in self.reports:
            for key, value in report.diagnostics().items():
                diagnostics[key] = diagnostics.get(key, 0) + value
        diagnostics["lifecycle_alerts"] = len(self.alerts)
        return diagnostics


AlertSink = Callable[[LifecycleOperatorAlert], None | Awaitable[None]]


async def reconcile_attempt_lifecycle(
    replay_store: ReplayStore,
    env_backend: EnvBackend,
    *,
    limit: int | None = None,
) -> LifecycleReconciliationReport:
    """Retry pending cleanup/cancel lifecycle rows and persist outcomes."""

    records = await replay_store.get_pending_attempt_lifecycle_records(
        limit=limit,
    )
    updated: list[AttemptLifecycleRecord] = []
    cleanup_attempted = 0
    cancel_attempted = 0
    failed = 0
    orphaned = 0
    for record in records:
        if record.lifecycle_stage == "cleanup":
            cleanup_attempted += 1
            reconciled = await _reconcile_cleanup(record, env_backend)
        else:
            cancel_attempted += 1
            reconciled = await _reconcile_cancel(record, env_backend)
        if reconciled.lifecycle_status == "failed":
            failed += 1
        if reconciled.lifecycle_status == "orphaned":
            orphaned += 1
        updated.append(reconciled)
    if updated:
        await replay_store.put_attempt_lifecycle_records(updated)
    terminal = sum(1 for record in updated if record.terminal)
    return LifecycleReconciliationReport(
        records_seen=len(records),
        cleanup_attempted=cleanup_attempted,
        cancel_attempted=cancel_attempted,
        terminal=terminal,
        pending=len(updated) - terminal,
        failed=failed,
        orphaned=orphaned,
    )


async def reconcile_attempt_lifecycle_periodically(
    replay_store: ReplayStore,
    env_backend: EnvBackend,
    *,
    interval_seconds: float,
    limit: int | None = None,
    max_passes: int | None = None,
    alert_sink: AlertSink | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> LifecycleSchedulerReport:
    """Run lifecycle reconciliation on a fixed interval.

    ``max_passes=None`` runs forever. Tests and one-shot maintenance commands
    should pass a finite value.
    """

    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")
    if max_passes is not None and max_passes < 1:
        raise ValueError("max_passes must be positive when provided")

    reports: list[LifecycleReconciliationReport] = []
    alerts: list[LifecycleOperatorAlert] = []
    passes = 0
    while max_passes is None or passes < max_passes:
        report = await reconcile_attempt_lifecycle(
            replay_store,
            env_backend,
            limit=limit,
        )
        reports.append(report)
        passes += 1
        alert = _alert_for_report(report)
        if alert is not None:
            alerts.append(alert)
            if alert_sink is not None:
                maybe_awaitable = alert_sink(alert)
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
        if max_passes is not None and passes >= max_passes:
            break
        await sleep(interval_seconds)
    return LifecycleSchedulerReport(
        passes=passes,
        reports=tuple(reports),
        alerts=tuple(alerts),
    )


async def _reconcile_cleanup(
    record: AttemptLifecycleRecord,
    env_backend: EnvBackend,
) -> AttemptLifecycleRecord:
    retry_count = record.retry_count + 1
    try:
        response = await env_backend.cleanup([record.backend_item_id])
    except Exception as error:
        return _updated_record(
            record,
            status="failed",
            retry_count=retry_count,
            terminal=False,
            last_error=str(error),
        )
    result = _cleanup_result_for_item(response.deleted_items, record)
    if result is None:
        return _updated_record(
            record,
            status="failed",
            retry_count=retry_count,
            terminal=False,
            last_error="cleanup response omitted backend item",
        )
    if result.status == "deleted":
        return _updated_record(
            record,
            status="deleted",
            retry_count=retry_count,
            terminal=True,
            last_error=None,
        )
    if _should_orphan(record, retry_count):
        return _updated_record(
            record,
            status="orphaned",
            retry_count=retry_count,
            terminal=True,
            last_error="cleanup remained deferred after max_retries",
        )
    return _updated_record(
        record,
        status="deferred",
        retry_count=retry_count,
        terminal=False,
        last_error=result.reason,
    )


async def _reconcile_cancel(
    record: AttemptLifecycleRecord,
    env_backend: EnvBackend,
) -> AttemptLifecycleRecord:
    retry_count = record.retry_count + 1
    try:
        response = await env_backend.cancel([record.backend_item_id])
    except Exception as error:
        return _updated_record(
            record,
            status="failed",
            retry_count=retry_count,
            terminal=False,
            last_error=str(error),
        )
    result = _cancel_result_for_item(response.items, record)
    if result is None:
        return _updated_record(
            record,
            status="failed",
            retry_count=retry_count,
            terminal=False,
            last_error="cancel response omitted backend item",
        )
    terminal = result.status in {"cleaned", "drained"}
    return _updated_record(
        record,
        status=result.status,
        retry_count=retry_count,
        terminal=terminal,
        last_error=None,
    )


def _cleanup_result_for_item(
    results: list[ExecCleanupResult],
    record: AttemptLifecycleRecord,
) -> ExecCleanupResult | None:
    for result in results:
        if result.item_id == record.backend_item_id:
            return result
    return None


def _cancel_result_for_item(
    results: list[ExecCancelResult],
    record: AttemptLifecycleRecord,
) -> ExecCancelResult | None:
    for result in results:
        if result.item_id == record.backend_item_id:
            return result
    return None


def _should_orphan(
    record: AttemptLifecycleRecord,
    retry_count: int,
) -> bool:
    return record.max_retries is not None and retry_count > record.max_retries


def _updated_record(
    record: AttemptLifecycleRecord,
    *,
    status: str,
    retry_count: int,
    terminal: bool,
    last_error: str | None,
) -> AttemptLifecycleRecord:
    return record.model_copy(
        update={
            "lifecycle_status": status,
            "retry_count": retry_count,
            "terminal": terminal,
            "last_error": last_error,
            "next_retry_at": None,
        }
    )


def _alert_for_report(
    report: LifecycleReconciliationReport,
) -> LifecycleOperatorAlert | None:
    if report.orphaned:
        return LifecycleOperatorAlert(
            severity="critical",
            message="lifecycle reconciliation orphaned backend items",
            diagnostics=report.diagnostics(),
        )
    if report.failed:
        return LifecycleOperatorAlert(
            severity="warning",
            message="lifecycle reconciliation failed for backend items",
            diagnostics=report.diagnostics(),
        )
    return None


__all__ = [
    "LifecycleOperatorAlert",
    "LifecycleReconciliationReport",
    "LifecycleSchedulerReport",
    "reconcile_attempt_lifecycle",
    "reconcile_attempt_lifecycle_periodically",
]
