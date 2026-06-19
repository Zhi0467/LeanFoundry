import sqlite3
from pathlib import Path
from typing import Any

from leanfoundry.proofsearch import SearchConfig
from leanfoundry.schemas.records import (
    ATypeDataRecord,
    FormalStatementStagingRecord,
    TheoremRecord,
)
from leanfoundry.schemas.trajectory import TrajectoryRecord
from leanfoundry.schemas.value import ValueLabel

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "leanfoundry"
    / "schemas"
    / "migrations"
    / "0001_initial.sql"
)

# Python model fields that exist in memory but have no direct SQL column.
# They are either search-time-only fields or fields serialized into a
# different column at storage time.
_MODEL_FIELDS_NOT_IN_SQL: dict[type[Any], set[str]] = {
    TheoremRecord: {
        "theorem_name",  # used at search/verify time, not stored
        "allowed_axioms",  # used at search/verify time, not stored
    },
    TrajectoryRecord: {
        "proof_tree",  # serialized as JSON into the tactic_sequence column
    },
    ValueLabel: {
        "state",  # pretty-printed into proof_state_pretty at storage time
    },
}

# SQL columns with no direct Python model field because they are derived or
# assigned at storage time rather than coming from the Python object directly.
_EXTRA_SQL_COLUMNS: dict[str, set[str]] = {
    "trajectories": {
        "tactic_sequence",  # JSON serialization of TrajectoryRecord.proof_tree
    },
    "state_value_labels": {
        "id",  # assigned at insert
        "proof_state_pretty",  # pretty-print of ValueLabel.state
    },
}

TABLE_MODELS: dict[str, type[Any]] = {
    "theorems": TheoremRecord,
    "a_type_data": ATypeDataRecord,
    "formal_statements_staging": FormalStatementStagingRecord,
    "trajectories": TrajectoryRecord,
    "state_value_labels": ValueLabel,
}


def _apply_initial_migration() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(MIGRATION_PATH.read_text())
    return conn


def _sql_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _expected_columns(table: str, model: type[Any]) -> set[str]:
    fields = set(model.model_fields.keys())
    fields -= _MODEL_FIELDS_NOT_IN_SQL.get(model, set())
    fields |= _EXTRA_SQL_COLUMNS.get(table, set())
    return fields


def test_initial_migration_applies_and_columns_match_python_models() -> None:
    conn = _apply_initial_migration()

    for table, model in TABLE_MODELS.items():
        sql_cols = _sql_columns(conn, table)
        expected = _expected_columns(table, model)
        assert sql_cols == expected, (
            f"{table}: SQL has {sql_cols - expected!r} not in model, "
            f"model has {expected - sql_cols!r} not in SQL"
        )


def test_state_value_labels_rejects_invalid_disproved_positive() -> None:
    conn = _apply_initial_migration()
    conn.execute(
        """
        INSERT INTO theorems (id, lean_statement, env_profile, header, source)
        VALUES ('thm', 'theorem t : True := by trivial', 'env', '', 'test')
        """
    )

    try:
        conn.execute(
            """
            INSERT INTO state_value_labels (
              id, theorem_id, env_profile, proof_state_hash, label,
              weight, disproved, model_version
            )
            VALUES ('label', 'thm', 'env', 'state', 1, 1.0, TRUE, 0)
            """
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("disproved labels must be negative")


def test_search_config_exposes_design_derived_search_budget_fields() -> None:
    fields = SearchConfig.model_fields

    for field_name in {
        "max_tactic_calls",
        "tactics_per_expansion",
        "try_negation",
        "censored_negative_weight",
        "min_censored_negative_effort",
    }:
        assert field_name in fields
        assert fields[field_name].description
