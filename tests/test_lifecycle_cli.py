from __future__ import annotations

import asyncio
import json
from pathlib import Path

from lean_client.exec_models import (
    ExecCancelResponse,
    ExecCleanupResponse,
    ExecCleanupResult,
)

from leanfoundry.env_backend import EnvBackendConfig
from leanfoundry.replay import SQLiteReplayStore
from leanfoundry.replay.lifecycle_cli import async_main
from leanfoundry.schemas import AttemptLifecycleRecord, TheoremRecord


def theorem_record() -> TheoremRecord:
    return TheoremRecord(
        id="thm",
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="env",
        header="",
        source="test",
    )


def lifecycle_record(**updates) -> AttemptLifecycleRecord:
    data = {
        "id": "life",
        "theorem_id": "thm",
        "env_profile": "env",
        "attempt_id": "attempt",
        "backend_item_id": "attempt:search",
        "lifecycle_stage": "cleanup",
        "lifecycle_status": "deferred",
        "retry_count": 0,
        "max_retries": 2,
    }
    data.update(updates)
    return AttemptLifecycleRecord(**data)


class DeletingBackend:
    def __init__(self, config: EnvBackendConfig) -> None:
        self.config = config
        self.connected = False
        self.closed = False
        self.cleanup_calls: list[list[str]] = []

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
        self.cleanup_calls.append(item_ids)
        return ExecCleanupResponse(
            deleted_items=[
                ExecCleanupResult(
                    item_id=item_ids[0],
                    status="deleted",
                    deleted_states=1,
                    deleted_bytes=1,
                )
            ]
        )

    async def cancel(self, item_ids: list[str]) -> ExecCancelResponse:
        raise AssertionError("unused")


class DeferredBackend(DeletingBackend):
    async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
        self.cleanup_calls.append(item_ids)
        return ExecCleanupResponse(
            deleted_items=[
                ExecCleanupResult(
                    item_id=item_ids[0],
                    status="deferred",
                    reason="in_flight",
                    deleted_states=0,
                    deleted_bytes=0,
                )
            ]
        )


def test_lifecycle_cli_reconciles_sqlite_store(
    tmp_path: Path,
    capsys,
) -> None:
    db_path = tmp_path / "replay.db"
    store = SQLiteReplayStore(db_path)
    asyncio.run(store.put_theorem(theorem_record()))
    asyncio.run(store.put_attempt_lifecycle_records([lifecycle_record()]))
    store.close()
    backends: list[DeletingBackend] = []

    def backend_factory(config: EnvBackendConfig) -> DeletingBackend:
        backend = DeletingBackend(config)
        backends.append(backend)
        return backend

    exit_code = asyncio.run(
        async_main(
            [
                "--replay-db",
                str(db_path),
                "--api-url",
                "http://lean.local",
                "--env-profile",
                "env",
            ],
            backend_factory=backend_factory,
        )
    )

    captured = capsys.readouterr()
    diagnostics = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert diagnostics["lifecycle_records_seen"] == 1
    assert diagnostics["lifecycle_terminal"] == 1
    assert diagnostics["lifecycle_alerts"] == 0
    assert len(backends) == 1
    assert backends[0].connected
    assert backends[0].closed
    assert backends[0].config.api_url == "http://lean.local"
    assert backends[0].config.env_profile == "env"
    reopened = SQLiteReplayStore(db_path)
    pending = asyncio.run(reopened.get_pending_attempt_lifecycle_records())
    reopened.close()
    assert pending == []


def test_lifecycle_cli_can_exit_nonzero_on_alert(
    tmp_path: Path,
    capsys,
) -> None:
    db_path = tmp_path / "replay.db"
    store = SQLiteReplayStore(db_path)
    asyncio.run(store.put_theorem(theorem_record()))
    asyncio.run(
        store.put_attempt_lifecycle_records(
            [lifecycle_record(retry_count=1, max_retries=1)]
        )
    )
    store.close()

    exit_code = asyncio.run(
        async_main(
            [
                "--replay-db",
                str(db_path),
                "--api-url",
                "http://lean.local",
                "--exit-nonzero-on-alert",
            ],
            backend_factory=DeferredBackend,
        )
    )

    captured = capsys.readouterr()
    diagnostics = json.loads(captured.out)
    alert = json.loads(captured.err)
    assert exit_code == 2
    assert diagnostics["lifecycle_orphaned"] == 1
    assert diagnostics["lifecycle_alerts"] == 1
    assert alert["severity"] == "critical"
    assert alert["diagnostics"]["lifecycle_orphaned"] == 1
