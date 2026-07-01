"""Public replay-buffer storage protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from leanfoundry.schemas import (
    ATypeDataRecord,
    AttemptLifecycleRecord,
    ExtractionFailureRecord,
    NegationAttemptRecord,
    TheoremRecord,
    PolicyExample,
    TrajectoryRecord,
    ValueLabel,
)


class ReplayStore(Protocol):
    """Durable storage interface for theorem, trajectory, and value data."""

    async def put_theorem(self, theorem: TheoremRecord) -> None:
        """Insert or update one theorem statement."""

    async def get_theorem(self, theorem_id: str) -> TheoremRecord | None:
        """Fetch one theorem statement by id."""

    async def put_a_type_data(self, sample: ATypeDataRecord) -> None:
        """Insert one verified theorem/proof training sample."""

    async def put_policy_examples(
        self,
        examples: Sequence[PolicyExample],
    ) -> None:
        """Insert positive per-state tactic-policy examples."""

    async def put_trajectory(self, trajectory: TrajectoryRecord) -> None:
        """Insert one search trajectory."""

    async def put_attempt_lifecycle_records(
        self,
        records: Sequence[AttemptLifecycleRecord],
    ) -> None:
        """Insert backend cleanup/cancel lifecycle records."""

    async def put_extraction_failures(
        self,
        records: Sequence[ExtractionFailureRecord],
    ) -> None:
        """Insert extraction/rendering failure records."""

    async def put_negation_attempts(
        self,
        records: Sequence[NegationAttemptRecord],
    ) -> None:
        """Insert synthetic-negation proof attempt records."""

    async def get_pending_attempt_lifecycle_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[AttemptLifecycleRecord]:
        """Fetch non-terminal lifecycle records ready for reconciliation."""

    async def put_value_labels(self, labels: Sequence[ValueLabel]) -> None:
        """Insert value labels extracted from search."""
