from __future__ import annotations

import asyncio
import sqlite3

import pytest
from lean_client.exec_models import (
    ExecCancelResponse,
    ExecCleanupResponse,
    ExecCleanupResult,
)

from leanfoundry.proofsearch import SearchResult, SearchStatus
from leanfoundry.replay import (
    SQLiteReplayStore,
    persist_search_result,
    reconcile_attempt_lifecycle,
    reconcile_attempt_lifecycle_periodically,
)
from leanfoundry.replay.sqlite_store import MIGRATION_PATH
from leanfoundry.schemas import (
    AttemptLifecycleRecord,
    ExtractionFailure,
    FactorizedProofState,
    GoalComponent,
    NegationAttempt,
    NegationTacticAttempt,
    PolicyExample,
    TheoremRecord,
    TheoremSpec,
    TrainingArtifacts,
    TrajectoryRecord,
)


def theorem_record(**updates) -> TheoremRecord:
    data = {
        "id": "thm",
        "lean_statement": "theorem t : True := by\n  sorry",
        "env_profile": "env",
        "header": "",
        "source": "test",
    }
    data.update(updates)
    return TheoremRecord(**data)


def proof_state() -> FactorizedProofState:
    return FactorizedProofState(
        env_profile="env",
        goal_components=[GoalComponent(target="True", pretty="|- True")],
        pretty_state="|- True",
        state_token="token",
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


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()
    return row == (table,)


def test_sqlite_store_applies_policy_examples_migration_to_existing_db(
    tmp_path,
) -> None:
    db_path = tmp_path / "legacy.db"
    migration = MIGRATION_PATH.read_text()
    start = migration.index("-- Positive per-state tactic examples")
    end = migration.index("-- Supervised value labels")
    legacy_migration = migration[:start] + migration[end:]
    conn = sqlite3.connect(db_path)
    conn.executescript(legacy_migration)
    conn.close()

    store = SQLiteReplayStore(db_path)
    store.close()

    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'policy_examples'
        """
    ).fetchone()
    assert row == ("policy_examples",)
    theorem_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(theorems)")
    }
    assert "theorem_name" in theorem_columns
    assert "allowed_axioms" in theorem_columns
    lifecycle_table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'attempt_lifecycle_outbox'
        """
    ).fetchone()
    assert lifecycle_table == ("attempt_lifecycle_outbox",)
    extraction_table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'extraction_failures'
        """
    ).fetchone()
    assert extraction_table == ("extraction_failures",)
    negation_table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'negation_attempts'
        """
    ).fetchone()
    assert negation_table == ("negation_attempts",)
    staging_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(formal_statements_staging)")
    }
    assert "header" in staging_columns


def test_sqlite_store_applies_verifier_field_migration_to_v2_db(
    tmp_path,
) -> None:
    db_path = tmp_path / "legacy-v2.db"
    migration = MIGRATION_PATH.read_text()
    migration = migration.replace("  theorem_name TEXT,\n", "")
    migration = migration.replace("  allowed_axioms TEXT,\n", "")
    conn = sqlite3.connect(db_path)
    conn.executescript(migration)
    conn.execute("PRAGMA user_version = 2")
    conn.close()

    store = SQLiteReplayStore(db_path)
    store.close()

    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    theorem_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(theorems)")
    }
    assert "theorem_name" in theorem_columns
    assert "allowed_axioms" in theorem_columns
    lifecycle_table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'attempt_lifecycle_outbox'
        """
    ).fetchone()
    assert lifecycle_table == ("attempt_lifecycle_outbox",)
    extraction_table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'extraction_failures'
        """
    ).fetchone()
    assert extraction_table == ("extraction_failures",)
    negation_table = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'negation_attempts'
        """
    ).fetchone()
    assert negation_table == ("negation_attempts",)
    staging_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(formal_statements_staging)")
    }
    assert "header" in staging_columns


def test_sqlite_store_upgrades_v4_db_to_current_schema(
    tmp_path,
) -> None:
    db_path = tmp_path / "legacy-v4.db"
    migration = MIGRATION_PATH.read_text()
    extraction_start = migration.index("-- Extraction/rendering failures")
    policy_start = migration.index("-- Positive per-state tactic examples")
    legacy_migration = (
        migration[:extraction_start] + migration[policy_start:]
    )
    conn = sqlite3.connect(db_path)
    conn.executescript(legacy_migration)
    conn.execute("PRAGMA user_version = 4")
    conn.close()

    store = SQLiteReplayStore(db_path)
    store.close()

    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    assert _table_exists(conn, "extraction_failures")
    assert _table_exists(conn, "negation_attempts")
    staging_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(formal_statements_staging)")
    }
    assert "header" in staging_columns


def test_sqlite_store_upgrades_v5_db_to_current_schema(
    tmp_path,
) -> None:
    db_path = tmp_path / "legacy-v5.db"
    migration = MIGRATION_PATH.read_text()
    negation_start = migration.index("-- Synthetic negation proof attempts")
    policy_start = migration.index("-- Positive per-state tactic examples")
    legacy_migration = migration[:negation_start] + migration[policy_start:]
    conn = sqlite3.connect(db_path)
    conn.executescript(legacy_migration)
    conn.execute("PRAGMA user_version = 5")
    conn.close()

    store = SQLiteReplayStore(db_path)
    store.close()

    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    assert _table_exists(conn, "negation_attempts")
    staging_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(formal_statements_staging)")
    }
    assert "header" in staging_columns


def test_sqlite_store_upgrades_v6_db_with_staging_header(
    tmp_path,
) -> None:
    db_path = tmp_path / "legacy-v6.db"
    migration = MIGRATION_PATH.read_text()
    migration = migration.replace("  header TEXT NOT NULL DEFAULT '',\n", "")
    conn = sqlite3.connect(db_path)
    conn.executescript(migration)
    conn.execute(
        """
        INSERT INTO formal_statements_staging (
          id, lean_statement, env_profile, syntax_checked
        )
        VALUES ('stmt', 'theorem t : True := by trivial', 'env', TRUE)
        """
    )
    conn.execute("PRAGMA user_version = 6")
    conn.commit()
    conn.close()

    store = SQLiteReplayStore(db_path)
    store.close()

    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    row = conn.execute(
        "SELECT header FROM formal_statements_staging WHERE id = 'stmt'"
    ).fetchone()
    assert row == ("",)


def test_sqlite_store_round_trips_theorem_verifier_metadata(
    tmp_path,
) -> None:
    store = SQLiteReplayStore(tmp_path / "replay.db")
    record = theorem_record(
        theorem_name="my_theorem",
        allowed_axioms=["Classical.choice", "propext"],
    )

    asyncio.run(store.put_theorem(record))
    fetched = asyncio.run(store.get_theorem("thm"))

    assert fetched is not None
    assert fetched.theorem_name == "my_theorem"
    assert fetched.allowed_axioms == ["Classical.choice", "propext"]
    store.close()


def test_sqlite_store_rejects_verifier_metadata_identity_collision(
    tmp_path,
) -> None:
    store = SQLiteReplayStore(tmp_path / "replay.db")
    asyncio.run(
        store.put_theorem(
            theorem_record(
                theorem_name="my_theorem",
                allowed_axioms=["Classical.choice"],
            )
        )
    )

    with pytest.raises(ValueError, match="allowed_axioms"):
        asyncio.run(
            store.put_theorem(
                theorem_record(
                    theorem_name="my_theorem",
                    allowed_axioms=["propext"],
                )
            )
        )

    store.close()


def test_sqlite_store_rejects_theorem_id_identity_collision(tmp_path) -> None:
    store = SQLiteReplayStore(tmp_path / "replay.db")
    asyncio.run(store.put_theorem(theorem_record()))

    with pytest.raises(ValueError, match="lean_statement"):
        asyncio.run(
            store.put_theorem(
                theorem_record(
                    lean_statement="theorem t : False := by\n  sorry"
                )
            )
        )

    store.close()


def test_sqlite_store_rejects_default_env_profile(tmp_path) -> None:
    store = SQLiteReplayStore(tmp_path / "replay.db")

    with pytest.raises(ValueError, match="default env_profile"):
        asyncio.run(
            store.put_theorem(
                theorem_record(env_profile="default")
            )
        )

    store.close()


def test_persist_search_result_rolls_back_partial_attempt(tmp_path) -> None:
    class FailingTrajectoryStore(SQLiteReplayStore):
        async def put_trajectory(
            self,
            trajectory: TrajectoryRecord,
        ) -> None:
            raise RuntimeError("trajectory write failed")

    db_path = tmp_path / "replay.db"
    store = FailingTrajectoryStore(db_path)
    theorem = TheoremSpec(
        id="thm",
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="env",
        header="",
        source="test",
    )
    result = SearchResult(
        theorem_id="thm",
        status=SearchStatus.ERROR,
        training_artifacts=TrainingArtifacts(
            policy_examples=[
                PolicyExample(
                    state=proof_state(),
                    tactic="trivial",
                    env_profile="env",
                    depth=0,
                )
            ]
        ),
    )

    with pytest.raises(RuntimeError, match="trajectory write failed"):
        asyncio.run(persist_search_result(store, theorem, result))
    store.close()

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM theorems").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM policy_examples"
    ).fetchone()[0] == 0


def test_persist_search_result_rejects_default_env_profile(tmp_path) -> None:
    store = SQLiteReplayStore(tmp_path / "replay.db")
    theorem = TheoremSpec(
        id="thm",
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="default",
        header="",
        source="test",
    )
    result = SearchResult(status=SearchStatus.ERROR)

    with pytest.raises(ValueError, match="default env_profile"):
        asyncio.run(persist_search_result(store, theorem, result))

    store.close()


def test_persist_search_result_writes_extraction_failures(
    tmp_path,
) -> None:
    store = SQLiteReplayStore(tmp_path / "replay.db")
    theorem = TheoremSpec(
        id="thm",
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="env",
        header="",
        source="test",
    )
    result = SearchResult(
        attempt_id="attempt",
        theorem_id="thm",
        status=SearchStatus.ERROR,
        training_artifacts=TrainingArtifacts(
            failures=[
                ExtractionFailure(
                    kind="rendering",
                    message="unsupported split goal rendering",
                    node_id="node-1",
                )
            ]
        ),
    )

    persisted = asyncio.run(
        persist_search_result(store, theorem, result, model_version=7)
    )
    store.close()

    assert persisted.diagnostics["replay_extraction_failures"] == 1
    conn = sqlite3.connect(tmp_path / "replay.db")
    row = conn.execute(
        """
        SELECT theorem_id, env_profile, attempt_id, failure_kind, message,
               node_id, model_version
        FROM extraction_failures
        """
    ).fetchone()
    assert row == (
        "thm",
        "env",
        "attempt",
        "rendering",
        "unsupported split goal rendering",
        "node-1",
        7,
    )


def test_persist_search_result_writes_negation_attempts(
    tmp_path,
) -> None:
    store = SQLiteReplayStore(tmp_path / "replay.db")
    theorem = TheoremSpec(
        id="thm",
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="env",
        header="",
        source="test",
    )
    attempt = NegationAttempt(
        source_node_id="node-1",
        source_state=proof_state(),
        negated_target="True",
        rendered_lean="theorem neg : ¬ (True) := by\n  exact not_true",
        theorem_name="neg",
        status="proved",
        tactic_attempts=[
            NegationTacticAttempt(
                tactic="exact not_true",
                status="complete",
            )
        ],
        tactic_calls_used=1,
        proved=True,
        proved_tactic="exact not_true",
    )
    result = SearchResult(
        attempt_id="attempt",
        theorem_id="thm",
        status=SearchStatus.DISPROVED,
        training_artifacts=TrainingArtifacts(negation_attempts=[attempt]),
    )

    persisted = asyncio.run(
        persist_search_result(store, theorem, result, model_version=7)
    )
    store.close()

    assert persisted.diagnostics["replay_negation_attempts"] == 1
    conn = sqlite3.connect(tmp_path / "replay.db")
    row = conn.execute(
        """
        SELECT theorem_id, env_profile, attempt_id, source_node_id,
               negated_target, status, proved, proved_tactic,
               tactic_calls_used, rendered_lean, model_version, payload_json
        FROM negation_attempts
        """
    ).fetchone()
    assert row[:11] == (
        "thm",
        "env",
        "attempt",
        "node-1",
        "True",
        "proved",
        1,
        "exact not_true",
        1,
        "theorem neg : ¬ (True) := by\n  exact not_true",
        7,
    )
    assert "exact not_true" in row[11]


def test_persist_search_result_writes_cleanup_lifecycle_record(
    tmp_path,
) -> None:
    store = SQLiteReplayStore(tmp_path / "replay.db")
    theorem = TheoremSpec(
        id="thm",
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="env",
        header="",
        source="test",
    )
    result = SearchResult(
        attempt_id="attempt",
        search_item_id="attempt:search",
        verify_item_id="attempt:verify",
        theorem_id="thm",
        status=SearchStatus.ERROR,
        diagnostics={
            "cleanup_attempts": 2,
            "cleanup_max_attempts": 2,
            "cleanup_deferred": 1,
            "cleanup_deferred_item_ids": '["attempt:search"]',
        },
    )

    persisted = asyncio.run(persist_search_result(store, theorem, result))
    store.close()

    assert persisted.diagnostics["replay_attempt_lifecycle_records"] == 1
    conn = sqlite3.connect(tmp_path / "replay.db")
    row = conn.execute(
        """
        SELECT theorem_id, env_profile, attempt_id, backend_item_id,
               lifecycle_stage, lifecycle_status, retry_count, max_retries,
               terminal
        FROM attempt_lifecycle_outbox
        """
    ).fetchone()
    assert row == (
        "thm",
        "env",
        "attempt",
        "attempt:search",
        "cleanup",
        "deferred",
        2,
        2,
        0,
    )


def test_reconcile_attempt_lifecycle_marks_cleanup_deleted(
    tmp_path,
) -> None:
    class CleanupEnv:
        async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
            assert item_ids == ["attempt:search"]
            return ExecCleanupResponse(
                deleted_items=[
                    ExecCleanupResult(
                        item_id="attempt:search",
                        status="deleted",
                        deleted_states=1,
                        deleted_bytes=1,
                    )
                ]
            )

        async def cancel(self, item_ids: list[str]) -> ExecCancelResponse:
            raise AssertionError("unused")

    store = SQLiteReplayStore(tmp_path / "replay.db")
    asyncio.run(store.put_theorem(theorem_record()))
    asyncio.run(
        store.put_attempt_lifecycle_records([lifecycle_record()])
    )

    report = asyncio.run(reconcile_attempt_lifecycle(store, CleanupEnv()))
    pending = asyncio.run(store.get_pending_attempt_lifecycle_records())
    store.close()

    assert report.diagnostics() == {
        "lifecycle_records_seen": 1,
        "lifecycle_cleanup_attempted": 1,
        "lifecycle_cancel_attempted": 0,
        "lifecycle_terminal": 1,
        "lifecycle_pending": 0,
        "lifecycle_failed": 0,
        "lifecycle_orphaned": 0,
    }
    assert pending == []
    conn = sqlite3.connect(tmp_path / "replay.db")
    row = conn.execute(
        """
        SELECT lifecycle_status, retry_count, terminal, last_error
        FROM attempt_lifecycle_outbox
        """
    ).fetchone()
    assert row == ("deleted", 1, 1, None)


def test_reconcile_attempt_lifecycle_orphans_deferred_cleanup(
    tmp_path,
) -> None:
    class DeferredCleanupEnv:
        async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
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

        async def cancel(self, item_ids: list[str]) -> ExecCancelResponse:
            raise AssertionError("unused")

    store = SQLiteReplayStore(tmp_path / "replay.db")
    asyncio.run(store.put_theorem(theorem_record()))
    asyncio.run(
        store.put_attempt_lifecycle_records(
            [lifecycle_record(retry_count=2, max_retries=2)]
        )
    )

    report = asyncio.run(
        reconcile_attempt_lifecycle(store, DeferredCleanupEnv())
    )
    store.close()

    assert report.orphaned == 1
    conn = sqlite3.connect(tmp_path / "replay.db")
    row = conn.execute(
        """
        SELECT lifecycle_status, retry_count, terminal, last_error
        FROM attempt_lifecycle_outbox
        """
    ).fetchone()
    assert row == (
        "orphaned",
        3,
        1,
        "cleanup remained deferred after max_retries",
    )


def test_lifecycle_scheduler_alerts_on_orphaned_cleanup(
    tmp_path,
) -> None:
    class DeferredCleanupEnv:
        async def cleanup(self, item_ids: list[str]) -> ExecCleanupResponse:
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

        async def cancel(self, item_ids: list[str]) -> ExecCancelResponse:
            raise AssertionError("unused")

    async def no_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    alerts = []
    sleeps = []
    store = SQLiteReplayStore(tmp_path / "replay.db")
    asyncio.run(store.put_theorem(theorem_record()))
    asyncio.run(
        store.put_attempt_lifecycle_records(
            [lifecycle_record(retry_count=0, max_retries=0)]
        )
    )

    report = asyncio.run(
        reconcile_attempt_lifecycle_periodically(
            store,
            DeferredCleanupEnv(),
            interval_seconds=0.25,
            max_passes=2,
            alert_sink=alerts.append,
            sleep=no_sleep,
        )
    )
    store.close()

    assert report.passes == 2
    assert sleeps == [0.25]
    assert len(report.alerts) == 1
    assert alerts == list(report.alerts)
    assert report.alerts[0].severity == "critical"
    assert report.alerts[0].diagnostics["lifecycle_orphaned"] == 1
    assert report.diagnostics()["lifecycle_scheduler_passes"] == 2
    assert report.diagnostics()["lifecycle_alerts"] == 1
