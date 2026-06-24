"""SQLite replay-store implementation."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

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


class SQLiteReplayStore:
    """Durable replay store backed by one SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._apply_initial_migration_if_needed()

    def close(self) -> None:
        """Close the underlying SQLite connection."""

        self._conn.close()

    async def put_theorem(self, theorem: TheoremRecord) -> None:
        """Insert or update one theorem statement."""

        self._conn.execute(
            """
            INSERT INTO theorems (
              id, lean_statement, informal_statement, env_profile, header,
              initial_lean_block, difficulty_estimate, pass_rate_current,
              pass_rate_updated_at, source, split, added_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              lean_statement=excluded.lean_statement,
              informal_statement=excluded.informal_statement,
              env_profile=excluded.env_profile,
              header=excluded.header,
              initial_lean_block=excluded.initial_lean_block,
              difficulty_estimate=excluded.difficulty_estimate,
              pass_rate_current=excluded.pass_rate_current,
              pass_rate_updated_at=excluded.pass_rate_updated_at,
              source=excluded.source,
              split=excluded.split
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
        self._conn.commit()

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        self._conn.commit()

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
        self._conn.commit()

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        self._conn.commit()

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
        self._conn.commit()

    def _apply_initial_migration_if_needed(self) -> None:
        row = self._conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'theorems'
            """
        ).fetchone()
        if row is not None:
            return
        self._conn.executescript(MIGRATION_PATH.read_text())
        self._conn.commit()


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
