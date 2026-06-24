"""Search-result to replay-store writer."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import nullcontext
from typing import ContextManager

from leanfoundry.proofsearch.base import SearchResult
from leanfoundry.replay.base import ReplayStore
from leanfoundry.replay.ids import stable_hash, stable_id
from leanfoundry.schemas import (
    ATypeDataRecord,
    PolicyExample,
    TheoremRecord,
    TheoremSpec,
    TrajectoryRecord,
    ValueLabel,
)


@dataclass(frozen=True, slots=True)
class ReplayWriteReport:
    """Small counters from persisting one search result."""

    theorem_id: str
    trajectories: int
    policy_examples: int
    value_labels: int
    a_type_data: int

    def diagnostics(self) -> dict[str, float | int | str]:
        """Return scalar diagnostics suitable for SearchResult."""

        return {
            "replay_theorem_id": self.theorem_id,
            "replay_trajectories": self.trajectories,
            "replay_policy_examples": self.policy_examples,
            "replay_value_labels": self.value_labels,
            "replay_a_type_data": self.a_type_data,
        }


async def persist_search_result(
    replay_store: ReplayStore,
    theorem: TheoremSpec,
    result: SearchResult,
    *,
    model_version: int = 0,
    proof_type: str = "proof_search",
) -> SearchResult:
    """Persist a theorem attempt and add write diagnostics to the result."""

    theorem_id = theorem.id or theorem_record_id(theorem)
    async with _transaction_context(replay_store):
        await replay_store.put_theorem(_theorem_record(theorem, theorem_id))

        artifacts = result.training_artifacts
        policy_examples: list[PolicyExample] = []
        value_labels: list[ValueLabel] = []
        a_type_records: list[ATypeDataRecord] = []
        if artifacts is not None:
            policy_examples = [
                _policy_example_for_store(
                    example,
                    theorem_id=theorem_id,
                    model_version=model_version,
                )
                for example in artifacts.policy_examples
            ]
            value_labels = [
                _value_label_for_store(
                    label,
                    theorem_id=theorem_id,
                    model_version=model_version,
                )
                for label in artifacts.value_labels
            ]
            a_type_records = [
                _a_type_record_for_proof_candidate(
                    theorem,
                    theorem_id=theorem_id,
                    rendered_lean=proof_tree.rendered_lean,
                    tactic_sequence=proof_tree.model_dump_json(),
                    model_version=model_version,
                )
                for proof_tree in artifacts.proof_candidates
                if proof_tree.verified
            ]
        await replay_store.put_policy_examples(policy_examples)
        await replay_store.put_value_labels(value_labels)
        for record in a_type_records:
            await replay_store.put_a_type_data(record)

        trajectory = _trajectory_record(
            theorem,
            result,
            theorem_id=theorem_id,
            model_version=model_version,
            proof_type=proof_type,
        )
        await replay_store.put_trajectory(trajectory)

    report = ReplayWriteReport(
        theorem_id=theorem_id,
        trajectories=1,
        policy_examples=len(policy_examples),
        value_labels=len(value_labels),
        a_type_data=len(a_type_records),
    )
    diagnostics = dict(result.diagnostics)
    diagnostics.update(report.diagnostics())
    return result.model_copy(
        update={
            "theorem_id": theorem_id,
            "diagnostics": diagnostics,
        }
    )


class _AsyncTransactionContext:
    def __init__(self, context: ContextManager[None]) -> None:
        self.context = context

    async def __aenter__(self) -> None:
        self.context.__enter__()

    async def __aexit__(self, exc_type, exc, traceback) -> bool | None:
        return self.context.__exit__(exc_type, exc, traceback)


def _transaction_context(
    replay_store: ReplayStore,
) -> _AsyncTransactionContext:
    transaction = getattr(replay_store, "transaction", None)
    if transaction is None:
        return _AsyncTransactionContext(nullcontext())
    return _AsyncTransactionContext(transaction())


def theorem_record_id(theorem: TheoremSpec) -> str:
    """Return the durable theorem id, deriving one for ad hoc specs."""

    if theorem.id is not None:
        return theorem.id
    return stable_id(
        "theorem",
        {
            "lean_statement": theorem.lean_statement,
            "env_profile": theorem.env_profile,
            "header": theorem.header,
            "source": theorem.source,
            "initial_lean_block": theorem.initial_lean_block,
        },
    )


def _theorem_record(theorem: TheoremSpec, theorem_id: str) -> TheoremRecord:
    return TheoremRecord(
        id=theorem_id,
        lean_statement=theorem.lean_statement,
        env_profile=theorem.env_profile,
        header=theorem.header,
        source=theorem.source,
        theorem_name=theorem.theorem_name,
        informal_statement=theorem.informal_statement,
        initial_lean_block=theorem.initial_lean_block,
        allowed_axioms=theorem.allowed_axioms,
    )


def _policy_example_for_store(
    example: PolicyExample,
    *,
    theorem_id: str,
    model_version: int,
) -> PolicyExample:
    return example.model_copy(
        update={
            "theorem_id": example.theorem_id or theorem_id,
            "model_version": model_version,
        }
    )


def _value_label_for_store(
    label: ValueLabel,
    *,
    theorem_id: str,
    model_version: int,
) -> ValueLabel:
    return label.model_copy(
        update={
            "theorem_id": label.theorem_id or theorem_id,
            "model_version": model_version,
        }
    )


def _a_type_record_for_proof_candidate(
    theorem: TheoremSpec,
    *,
    theorem_id: str,
    rendered_lean: str,
    tactic_sequence: str,
    model_version: int,
) -> ATypeDataRecord:
    proof_hash = stable_hash(rendered_lean)
    return ATypeDataRecord(
        id=stable_id(
            "a_type",
            {
                "theorem_id": theorem_id,
                "env_profile": theorem.env_profile,
                "proof_hash": proof_hash,
                "model_version": model_version,
            },
        ),
        theorem_id=theorem_id,
        env_profile=theorem.env_profile,
        header=theorem.header,
        lean_proof=rendered_lean,
        proof_hash=proof_hash,
        verified_by_backend=True,
        proof_type="whole_proof",
        tactic_sequence=tactic_sequence,
        source="search_found",
        model_version=model_version,
    )


def _trajectory_record(
    theorem: TheoremSpec,
    result: SearchResult,
    *,
    theorem_id: str,
    model_version: int,
    proof_type: str,
) -> TrajectoryRecord:
    whole_proof = None
    if result.proof_tree is not None and result.proof_tree.verified:
        whole_proof = result.proof_tree.rendered_lean
    return TrajectoryRecord(
        id=stable_id(
            "trajectory",
            {
                "theorem_id": theorem_id,
                "attempt_id": result.attempt_id,
                "search_item_id": result.search_item_id,
                "verify_item_id": result.verify_item_id,
                "status": result.status.value,
                "search_budget_used": result.search_budget_used,
                "model_version": model_version,
            },
        ),
        theorem_id=theorem_id,
        env_profile=theorem.env_profile,
        proof_type=proof_type,
        whole_proof=whole_proof,
        proof_tree=result.proof_tree,
        search_budget_used=result.search_budget_used,
        model_version=model_version,
    )


__all__ = [
    "ReplayWriteReport",
    "persist_search_result",
    "theorem_record_id",
]
