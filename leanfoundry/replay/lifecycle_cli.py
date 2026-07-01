"""Command-line lifecycle reconciliation for replay stores."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from leanfoundry.env_backend import EnvBackend, EnvBackendConfig
from leanfoundry.env_backend import make_env_backend
from leanfoundry.replay.lifecycle import (
    LifecycleOperatorAlert,
    reconcile_attempt_lifecycle_periodically,
)
from leanfoundry.replay.sqlite_store import SQLiteReplayStore


StoreFactory = Callable[[Path], Any]
BackendFactory = Callable[[EnvBackendConfig], EnvBackend]


async def async_main(
    argv: Sequence[str] | None = None,
    *,
    store_factory: StoreFactory = SQLiteReplayStore,
    backend_factory: BackendFactory = make_env_backend,
) -> int:
    """Run lifecycle reconciliation from parsed CLI arguments."""

    args = _parse_args(argv)
    store = store_factory(args.replay_db)
    backend = backend_factory(_env_backend_config(args))
    alerts: list[LifecycleOperatorAlert] = []

    def alert_sink(alert: LifecycleOperatorAlert) -> None:
        alerts.append(alert)
        print(
            json.dumps(_alert_payload(alert), sort_keys=True),
            file=sys.stderr,
            flush=True,
        )

    try:
        await backend.connect()
        report = await reconcile_attempt_lifecycle_periodically(
            store,
            backend,
            interval_seconds=args.interval_seconds,
            limit=args.limit,
            max_passes=None if args.forever else args.max_passes,
            alert_sink=alert_sink,
        )
    finally:
        await backend.close()
        close = getattr(store, "close", None)
        if close is not None:
            close()

    print(json.dumps(report.diagnostics(), sort_keys=True))
    return _exit_code(alerts, fail_on_alert=args.exit_nonzero_on_alert)


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entrypoint."""

    return asyncio.run(async_main(argv))


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Retry pending Lean backend cleanup/cancel lifecycle rows from a "
            "SQLite replay store."
        )
    )
    parser.add_argument("--replay-db", type=Path, required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--env-profile", default="default")
    parser.add_argument("--api-key")
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--acquire-timeout-ms", type=int)
    parser.add_argument("--step-timeout-ms", type=int)
    parser.add_argument("--http-timeout-seconds", type=int, default=60)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-overloaded-retries", type=int, default=0)
    parser.add_argument("--overload-backoff-seconds", type=float, default=0.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-passes", type=int, default=1)
    parser.add_argument(
        "--forever",
        action="store_true",
        help="Run periodic reconciliation until the process is stopped.",
    )
    parser.add_argument(
        "--exit-nonzero-on-alert",
        action="store_true",
        help="Return 1 for warning alerts and 2 for critical alerts.",
    )
    return parser.parse_args(argv)


def _env_backend_config(args: argparse.Namespace) -> EnvBackendConfig:
    return EnvBackendConfig(
        api_url=args.api_url,
        env_profile=args.env_profile,
        api_key=args.api_key,
        timeout_ms=args.timeout_ms,
        acquire_timeout_ms=args.acquire_timeout_ms,
        step_timeout_ms=args.step_timeout_ms,
        http_timeout_seconds=args.http_timeout_seconds,
        retries=args.retries,
        max_overloaded_retries=args.max_overloaded_retries,
        overload_backoff_seconds=args.overload_backoff_seconds,
    )


def _alert_payload(alert: LifecycleOperatorAlert) -> dict[str, Any]:
    return {
        "severity": alert.severity,
        "message": alert.message,
        "diagnostics": alert.diagnostics,
    }


def _exit_code(
    alerts: list[LifecycleOperatorAlert],
    *,
    fail_on_alert: bool,
) -> int:
    if not fail_on_alert or not alerts:
        return 0
    if any(alert.severity == "critical" for alert in alerts):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["async_main", "main"]
