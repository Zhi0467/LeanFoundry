from __future__ import annotations

import asyncio
import sqlite3

import pytest

from leanfoundry.proofsearch import SearchResult, SearchStatus
from leanfoundry.replay import SQLiteReplayStore, persist_search_result
from leanfoundry.replay.sqlite_store import MIGRATION_PATH
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
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
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
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
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
    theorem_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(theorems)")
    }
    assert "theorem_name" in theorem_columns
    assert "allowed_axioms" in theorem_columns


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
