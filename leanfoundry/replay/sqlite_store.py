"""SQLite replay-store implementation."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from leanfoundry.replay.ids import stable_hash, stable_id
from leanfoundry.schemas import (
    ATypeDataRecord,
    PolicyExample,
    TheoremRecord,
    TrajectoryRecord,
    ValueLabel,
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "migrations"
    / "0001_initial.sql"
)
POLICY_EXAMPLES_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "migrations"
    / "0002_policy_examples.sql"
)
SCHEMA_VERSION = 2


class SQLiteReplayStore:
    """Durable replay store backed by one SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._in_transaction = False
        self._apply_migrations()

    def close(self) -> None:
        """Close the underlying SQLite connection."""

        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Run several store writes atomically."""

        if self._in_transaction:
            yield
            return
        self._conn.execute("BEGIN")
        self._in_transaction = True
        try:
            yield
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()
        finally:
            self._in_transaction = False

    async def put_theorem(self, theorem: TheoremRecord) -> None:
        """Insert or update one theorem statement."""

        existing = await self.get_theorem(theorem.id)
        if existing is not None:
            _validate_theorem_identity(existing, theorem)
            self._conn.execute(
                """
                UPDATE theorems
                SET difficulty_estimate = ?,
                    pass_rate_current = ?,
                    pass_rate_updated_at = ?
                WHERE id = ?
                """,
                (
                    theorem.difficulty_estimate,
                    theorem.pass_rate_current,
                    theorem.pass_rate_updated_at,
                    theorem.id,
                ),
            )
            self._commit_if_needed()
            return
        self._conn.execute(
            """
            INSERT INTO theorems (
              id, lean_statement, informal_statement, env_profile, header,
              initial_lean_block, difficulty_estimate, pass_rate_current,
              pass_rate_updated_at, source, split, added_at
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              COALESCE(?, CURRENT_TIMESTAMP)
            )
            """,
            (
                theorem.id,
                theorem.lean_statement,
                theorem.informal_statement,
                theorem.env_profile,
                theorem.header,
                theorem.initial_lean_block,
                theorem.difficulty_estimate,
                theorem.pass_rate_current,
                theorem.pass_rate_updated_at,
                theorem.source,
                theorem.split,
                theorem.added_at,
            ),
        )
        self._commit_if_needed()

    async def get_theorem(self, theorem_id: str) -> TheoremRecord | None:
        """Fetch one theorem statement by id."""

        row = self._conn.execute(
            """
            SELECT
              id, lean_statement, informal_statement, env_profile, header,
              initial_lean_block, difficulty_estimate, pass_rate_current,
              pass_rate_updated_at, source, split, added_at
            FROM theorems
            WHERE id = ?
            """,
            (theorem_id,),
        ).fetchone()
        if row is None:
            return None
        return TheoremRecord(**dict(row))

    async def put_a_type_data(self, sample: ATypeDataRecord) -> None:
        """Insert one verified theorem/proof training sample."""

        self._conn.execute(
            """
            INSERT OR REPLACE INTO a_type_data (
              id, theorem_id, env_profile, header, lean_proof, proof_hash,
              verified_by_backend, proof_type, tactic_sequence,
              correction_input, source, model_version, created_at
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              COALESCE(?, CURRENT_TIMESTAMP)
            )
            """,
            (
                sample.id,
                sample.theorem_id,
                sample.env_profile,
                sample.header,
                sample.lean_proof,
                sample.proof_hash,
                sample.verified_by_backend,
                sample.proof_type,
                sample.tactic_sequence,
                sample.correction_input,
                sample.source,
                sample.model_version,
                sample.created_at,
            ),
        )
        self._commit_if_needed()

    async def put_policy_examples(
        self,
        examples: Sequence[PolicyExample],
    ) -> None:
        """Insert positive per-state tactic-policy examples."""

        rows = [_policy_example_row(example) for example in examples]
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO policy_examples (
              id, theorem_id, env_profile, proof_state_hash,
              proof_state_pretty, proof_prefix, tactic, depth, model_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._commit_if_needed()

    async def put_trajectory(self, trajectory: TrajectoryRecord) -> None:
        """Insert one search trajectory."""

        tactic_sequence = None
        if trajectory.proof_tree is not None:
            tactic_sequence = trajectory.proof_tree.model_dump_json()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO trajectories (
              id, theorem_id, env_profile, proof_type, whole_proof,
              tactic_sequence, search_budget_used, is_subproof,
              parent_trajectory_id, model_version, created_at
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              COALESCE(?, CURRENT_TIMESTAMP)
            )
            """,
            (
                trajectory.id,
                trajectory.theorem_id,
                trajectory.env_profile,
                trajectory.proof_type,
                trajectory.whole_proof,
                tactic_sequence,
                trajectory.search_budget_used,
                trajectory.is_subproof,
                trajectory.parent_trajectory_id,
                trajectory.model_version,
                trajectory.created_at,
            ),
        )
        self._commit_if_needed()

    async def put_value_labels(self, labels: Sequence[ValueLabel]) -> None:
        """Insert value labels extracted from search."""

        rows = [_value_label_row(label) for label in labels]
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO state_value_labels (
              id, theorem_id, env_profile, proof_state_hash,
              proof_state_pretty, label, weight, disproved, depth,
              tactics_tried_on_subtree, model_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._commit_if_needed()

    def _apply_migrations(self) -> None:
        row = self._conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'theorems'
            """
        ).fetchone()
        if row is None:
            self._conn.executescript(MIGRATION_PATH.read_text())
            self._set_schema_version(SCHEMA_VERSION)
            self._conn.commit()
            return
        if self._schema_version() < 2:
            migration = POLICY_EXAMPLES_MIGRATION_PATH.read_text()
            self._conn.executescript(migration)
            self._set_schema_version(2)
            self._conn.commit()

    def _schema_version(self) -> int:
        row = self._conn.execute("PRAGMA user_version").fetchone()
        return int(row[0])

    def _set_schema_version(self, version: int) -> None:
        self._conn.execute(f"PRAGMA user_version = {version}")

    def _commit_if_needed(self) -> None:
        if not self._in_transaction:
            self._conn.commit()


def _validate_theorem_identity(
    existing: TheoremRecord,
    incoming: TheoremRecord,
) -> None:
    identity_fields = (
        "lean_statement",
        "env_profile",
        "header",
        "initial_lean_block",
        "source",
    )
    for field_name in identity_fields:
        if getattr(existing, field_name) != getattr(incoming, field_name):
            raise ValueError(
                "theorem id collision with different identity field: "
                f"{field_name}"
            )


def _policy_example_row(example: PolicyExample) -> tuple[object, ...]:
    proof_state_hash = stable_hash(example.state)
    row_id = stable_id(
        "policy_example",
        {
            "theorem_id": example.theorem_id,
            "env_profile": example.env_profile,
            "proof_state_hash": proof_state_hash,
            "proof_prefix": example.proof_prefix,
            "tactic": example.tactic,
            "depth": example.depth,
            "model_version": example.model_version,
        },
    )
    return (
        row_id,
        example.theorem_id,
        example.env_profile,
        proof_state_hash,
        example.state.pretty_state,
        example.proof_prefix,
        example.tactic,
        example.depth,
        example.model_version,
    )


def _value_label_row(label: ValueLabel) -> tuple[object, ...]:
    proof_state_hash = label.proof_state_hash or stable_hash(label.state)
    row_id = stable_id(
        "value_label",
        {
            "theorem_id": label.theorem_id,
            "env_profile": label.env_profile,
            "proof_state_hash": proof_state_hash,
            "label": label.label,
            "weight": label.weight,
            "disproved": label.disproved,
            "depth": label.depth,
            "tactics_tried_on_subtree": label.tactics_tried_on_subtree,
            "model_version": label.model_version,
        },
    )
    return (
        row_id,
        label.theorem_id,
        label.env_profile,
        proof_state_hash,
        label.state.pretty_state,
        label.label,
        label.weight,
        label.disproved,
        label.depth,
        label.tactics_tried_on_subtree,
        label.model_version,
    )


__all__ = [
    "SQLiteReplayStore",
]
