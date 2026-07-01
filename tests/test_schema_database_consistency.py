import sqlite3
import types
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

from pydantic.fields import FieldInfo

from leanfoundry.proofsearch import SearchConfig
from leanfoundry.schemas.records import (
    ATypeDataRecord,
    AttemptLifecycleRecord,
    ExtractionFailureRecord,
    FormalStatementStagingRecord,
    NegationAttemptRecord,
    TheoremRecord,
)
from leanfoundry.schemas.trajectory import TrajectoryRecord
from leanfoundry.schemas.trajectory import PolicyExample
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
    TrajectoryRecord: {
        "proof_tree",  # serialized as JSON into the tactic_sequence column
    },
    ValueLabel: {
        "state",  # pretty-printed into proof_state_pretty at storage time
    },
    PolicyExample: {
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
    "policy_examples": {
        "id",  # assigned at insert
        "proof_state_hash",  # derived from PolicyExample.state
        "proof_state_pretty",  # pretty-print of PolicyExample.state
        "created_at",  # assigned by SQLite
    },
}

_SQL_DERIVED_NOT_NULL_COLUMNS: dict[str, set[str]] = {
    "state_value_labels": {
        "id",  # assigned at insert
        "proof_state_hash",  # derived from ValueLabel.state when omitted
    },
    "policy_examples": {
        "id",  # assigned at insert
        "proof_state_hash",  # derived from PolicyExample.state
    },
}

_EXTRA_SQL_COLUMN_AFFINITIES: dict[str, dict[str, str]] = {
    "theorems": {
        "allowed_axioms": "TEXT",
    },
    "trajectories": {
        "tactic_sequence": "TEXT",
    },
    "state_value_labels": {
        "id": "TEXT",
        "proof_state_pretty": "TEXT",
    },
    "policy_examples": {
        "id": "TEXT",
        "proof_state_hash": "TEXT",
        "proof_state_pretty": "TEXT",
        "created_at": "NUMERIC",
    },
}

_TIMESTAMP_COLUMNS = {
    "added_at",
    "created_at",
    "pass_rate_updated_at",
    "next_retry_at",
    "updated_at",
}

_VALID_SQL_ROWS: dict[str, dict[str, Any]] = {
    "theorems": {
        "id": "thm",
        "lean_statement": "theorem t : True := by trivial",
        "env_profile": "env",
        "header": "",
        "source": "test",
    },
    "formal_statements_staging": {
        "id": "stmt",
        "lean_statement": "theorem t : True := by trivial",
        "env_profile": "env",
    },
    "policy_examples": {
        "id": "policy",
        "env_profile": "env",
        "proof_state_hash": "state",
        "proof_prefix": "",
        "tactic": "trivial",
        "depth": 0,
    },
    "state_value_labels": {
        "id": "label",
        "env_profile": "env",
        "proof_state_hash": "state",
        "label": 0,
        "weight": 1.0,
        "disproved": False,
        "model_version": 0,
    },
    "attempt_lifecycle_outbox": {
        "id": "lifecycle",
        "theorem_id": "thm",
        "env_profile": "env",
        "attempt_id": "attempt",
        "backend_item_id": "attempt:search",
        "lifecycle_stage": "cleanup",
        "lifecycle_status": "deferred",
    },
    "extraction_failures": {
        "id": "failure",
        "theorem_id": "thm",
        "env_profile": "env",
        "failure_kind": "rendering",
        "message": "render failed",
    },
    "negation_attempts": {
        "id": "negation",
        "theorem_id": "thm",
        "env_profile": "env",
        "source_node_id": "node",
        "negated_target": "True",
        "status": "proved",
        "proved": True,
        "tactic_calls_used": 1,
        "payload_json": "{}",
    },
}

_SQL_CHECK_CASES: dict[str, list[tuple[str, Any]]] = {
    "theorems": [
        ("lean_statement", ""),
        ("env_profile", ""),
        ("source", ""),
    ],
    "formal_statements_staging": [
        ("semantic_judge_score", -0.1),
        ("semantic_judge_score", 1.1),
    ],
    "policy_examples": [
        ("depth", -1),
    ],
    "state_value_labels": [
        ("label", 2),
        ("weight", -0.1),
        ("depth", -1),
        ("tactics_tried_on_subtree", -1),
    ],
    "attempt_lifecycle_outbox": [
        ("env_profile", ""),
        ("attempt_id", ""),
        ("backend_item_id", ""),
        ("lifecycle_stage", "unknown"),
        ("lifecycle_status", ""),
        ("retry_count", -1),
        ("max_retries", -1),
    ],
    "extraction_failures": [
        ("env_profile", ""),
        ("failure_kind", "unknown"),
        ("message", ""),
    ],
    "negation_attempts": [
        ("env_profile", ""),
        ("source_node_id", ""),
        ("negated_target", ""),
        ("status", ""),
        ("tactic_calls_used", -1),
        ("payload_json", ""),
    ],
}

TABLE_MODELS: dict[str, type[Any]] = {
    "theorems": TheoremRecord,
    "a_type_data": ATypeDataRecord,
    "formal_statements_staging": FormalStatementStagingRecord,
    "trajectories": TrajectoryRecord,
    "attempt_lifecycle_outbox": AttemptLifecycleRecord,
    "extraction_failures": ExtractionFailureRecord,
    "negation_attempts": NegationAttemptRecord,
    "policy_examples": PolicyExample,
    "state_value_labels": ValueLabel,
}


def _sql_column_info(
    conn: sqlite3.Connection,
    table: str,
) -> dict[str, dict[str, Any]]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {
        row[1]: {
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "primary_key": bool(row[5]),
        }
        for row in rows
    }


def _sqlite_affinity(sql_type: str) -> str:
    normalized = sql_type.upper()
    if "INT" in normalized:
        return "INTEGER"
    if any(fragment in normalized for fragment in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if "BLOB" in normalized or not normalized:
        return "BLOB"
    if any(fragment in normalized for fragment in ("REAL", "FLOA", "DOUB")):
        return "REAL"
    return "NUMERIC"


def _apply_initial_migration() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(MIGRATION_PATH.read_text())
    return conn


def _sql_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return set(_sql_column_info(conn, table))


def _expected_columns(table: str, model: type[Any]) -> set[str]:
    fields = set(model.model_fields.keys())
    fields -= _MODEL_FIELDS_NOT_IN_SQL.get(model, set())
    fields |= _EXTRA_SQL_COLUMNS.get(table, set())
    return fields


def _expected_affinity(
    table: str,
    column: str,
    model: type[Any],
) -> str:
    extra_affinity = _EXTRA_SQL_COLUMN_AFFINITIES.get(table, {}).get(column)
    if extra_affinity is not None:
        return extra_affinity
    if column in _TIMESTAMP_COLUMNS:
        return "NUMERIC"
    field = model.model_fields[column]
    annotation = _strip_optional(field.annotation)
    origin = get_origin(annotation)
    if origin is Literal:
        literal_types = {type(value) for value in get_args(annotation)}
        if literal_types == {int}:
            return "INTEGER"
        if literal_types == {str}:
            return "TEXT"
    if annotation is bool:
        return "NUMERIC"
    if annotation is int:
        return "INTEGER"
    if annotation is float:
        return "REAL"
    if annotation is str:
        return "TEXT"
    raise AssertionError(
        f"{table}.{column}: no SQL affinity mapping for {annotation!r}"
    )


def _strip_optional(annotation: object) -> object:
    origin = get_origin(annotation)
    if origin not in {types.UnionType, Union}:
        return annotation
    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(args) == 1:
        return args[0]
    return annotation


def _insert_row(
    conn: sqlite3.Connection,
    table: str,
    row: dict[str, Any],
) -> None:
    columns = list(row)
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    conn.execute(
        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
        tuple(row[column] for column in columns),
    )


def test_initial_migration_applies_and_columns_match_python_models() -> None:
    conn = _apply_initial_migration()

    for table, model in TABLE_MODELS.items():
        sql_cols = _sql_columns(conn, table)
        expected = _expected_columns(table, model)
        assert sql_cols == expected, (
            f"{table}: SQL has {sql_cols - expected!r} not in model, "
            f"model has {expected - sql_cols!r} not in SQL"
        )


def test_initial_migration_nullability_matches_python_models() -> None:
    conn = _apply_initial_migration()

    for table, model in TABLE_MODELS.items():
        sql_info = _sql_column_info(conn, table)
        derived_not_null = _SQL_DERIVED_NOT_NULL_COLUMNS.get(table, set())
        for column in _expected_columns(table, model):
            if column in _EXTRA_SQL_COLUMNS.get(table, set()):
                continue
            field = model.model_fields[column]
            if field.is_required():
                assert sql_info[column]["notnull"], (
                    f"{table}.{column} is required by {model.__name__} "
                    "but nullable in SQL"
                )
                continue
            if column in derived_not_null:
                assert sql_info[column]["notnull"]
                continue
            if _field_default_is_sql_not_null(field):
                assert sql_info[column]["notnull"], (
                    f"{table}.{column} has a non-null model default "
                    "but is nullable in SQL"
                )
                assert sql_info[column]["default"] is not None, (
                    f"{table}.{column} has a non-null model default "
                    "but no SQL default"
                )


def test_initial_migration_type_affinity_matches_python_models() -> None:
    conn = _apply_initial_migration()

    for table, model in TABLE_MODELS.items():
        sql_info = _sql_column_info(conn, table)
        for column in _expected_columns(table, model):
            expected_affinity = _expected_affinity(table, column, model)
            actual_affinity = _sqlite_affinity(sql_info[column]["type"])
            assert actual_affinity == expected_affinity, (
                f"{table}.{column}: SQL affinity {actual_affinity!r} "
                f"does not match {model.__name__} field "
                f"{expected_affinity!r}"
            )


def test_initial_migration_checks_match_python_model_constraints() -> None:
    for table, invalid_cases in _SQL_CHECK_CASES.items():
        for column, invalid_value in invalid_cases:
            conn = _apply_initial_migration()
            row = dict(_VALID_SQL_ROWS[table])
            row[column] = invalid_value
            try:
                _insert_row(conn, table, row)
            except sqlite3.IntegrityError:
                continue
            raise AssertionError(
                f"{table}.{column} accepted invalid value "
                f"{invalid_value!r}"
            )


def _field_default_is_sql_not_null(field: FieldInfo) -> bool:
    if field.is_required():
        return False
    default = field.get_default(call_default_factory=False)
    return default is not None


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
        "max_direct_candidates",
        "tactics_per_expansion",
        "puct_exploration_weight",
        "best_first_missing_value_score",
        "direct_candidates_per_round",
        "try_negation",
        "censored_negative_weight",
        "min_censored_negative_effort",
    }:
        assert field_name in fields
        assert fields[field_name].description


def test_policy_example_stores_markovian_and_prefix_formulations() -> None:
    from leanfoundry.schemas import FactorizedProofState, GoalComponent
    from leanfoundry.schemas.trajectory import PolicyExample

    state = FactorizedProofState(
        env_profile="env",
        goal_components=[GoalComponent(target="True", pretty="|- True")],
        pretty_state="|- True",
        state_token="token",
    )

    example = PolicyExample(
        state=state,
        proof_prefix="constructor\nleft",
        tactic="trivial",
        env_profile="env",
        depth=2,
    )

    assert example.state is state
    assert example.proof_prefix == "constructor\nleft"
    assert example.tactic == "trivial"


def test_atype_data_uses_backend_neutral_verification_name() -> None:
    fields = ATypeDataRecord.model_fields

    assert "verified_by_backend" in fields
    assert "verified_by_kimina" not in fields
