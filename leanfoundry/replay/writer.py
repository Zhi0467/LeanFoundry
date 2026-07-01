"""Search-result to replay-store writer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from contextlib import nullcontext
from typing import Any, ContextManager

from leanfoundry.env_profiles import validate_theorem_env_profile
from leanfoundry.replay.base import ReplayStore
from leanfoundry.replay.ids import stable_hash, stable_id
from leanfoundry.schemas import (
    ATypeDataRecord,
    AttemptLifecycleRecord,
    ExtractionFailure,
    ExtractionFailureRecord,
    NegationAttempt,
    NegationAttemptRecord,
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
    attempt_lifecycle_records: int
    extraction_failures: int
    negation_attempts: int

    def diagnostics(self) -> dict[str, float | int | str]:
        """Return scalar diagnostics suitable for SearchResult."""

        return {
            "replay_theorem_id": self.theorem_id,
            "replay_trajectories": self.trajectories,
            "replay_policy_examples": self.policy_examples,
            "replay_value_labels": self.value_labels,
            "replay_a_type_data": self.a_type_data,
            "replay_attempt_lifecycle_records": (
                self.attempt_lifecycle_records
            ),
            "replay_extraction_failures": self.extraction_failures,
            "replay_negation_attempts": self.negation_attempts,
        }


async def persist_search_result(
    replay_store: ReplayStore,
    theorem: TheoremSpec,
    result: Any,
    *,
    model_version: int = 0,
    proof_type: str = "proof_search",
) -> Any:
    """Persist a theorem attempt and add write diagnostics to the result."""

    validate_theorem_env_profile(theorem)
    theorem_id = theorem.id or theorem_record_id(theorem)
    async with _transaction_context(replay_store):
        await replay_store.put_theorem(_theorem_record(theorem, theorem_id))

        artifacts = result.training_artifacts
        policy_examples: list[PolicyExample] = []
        value_labels: list[ValueLabel] = []
        a_type_records: list[ATypeDataRecord] = []
        extraction_failure_records: list[ExtractionFailureRecord] = []
        negation_attempt_records: list[NegationAttemptRecord] = []
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
            extraction_failure_records = [
                _extraction_failure_record(
                    failure,
                    theorem,
                    result,
                    theorem_id=theorem_id,
                    model_version=model_version,
                )
                for failure in artifacts.failures
            ]
            negation_attempt_records = [
                _negation_attempt_record(
                    attempt,
                    theorem,
                    result,
                    theorem_id=theorem_id,
                    model_version=model_version,
                )
                for attempt in artifacts.negation_attempts
            ]
        await replay_store.put_policy_examples(policy_examples)
        await replay_store.put_value_labels(value_labels)
        for record in a_type_records:
            await replay_store.put_a_type_data(record)
        await replay_store.put_extraction_failures(extraction_failure_records)
        await replay_store.put_negation_attempts(negation_attempt_records)

        attempt_lifecycle_records = _attempt_lifecycle_records_for_result(
            theorem,
            result,
            theorem_id=theorem_id,
        )
        await replay_store.put_attempt_lifecycle_records(
            attempt_lifecycle_records
        )

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
        attempt_lifecycle_records=len(attempt_lifecycle_records),
        extraction_failures=len(extraction_failure_records),
        negation_attempts=len(negation_attempt_records),
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
        # SQLiteReplayStore transactions are safe under concurrent batch writes
        # because its async methods perform synchronous DB work without awaits.
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
    identity: dict[str, object] = {
        "lean_statement": theorem.lean_statement,
        "env_profile": theorem.env_profile,
        "header": theorem.header,
        "source": theorem.source,
        "initial_lean_block": theorem.initial_lean_block,
    }
    if theorem.theorem_name is not None:
        identity["theorem_name"] = theorem.theorem_name
    if theorem.allowed_axioms is not None:
        identity["allowed_axioms"] = theorem.allowed_axioms
    return stable_id(
        "theorem",
        identity,
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


def _extraction_failure_record(
    failure: ExtractionFailure,
    theorem: TheoremSpec,
    result: Any,
    *,
    theorem_id: str,
    model_version: int,
) -> ExtractionFailureRecord:
    return ExtractionFailureRecord(
        id=stable_id(
            "extraction_failure",
            {
                "theorem_id": theorem_id,
                "attempt_id": result.attempt_id,
                "kind": failure.kind,
                "message": failure.message,
                "node_id": failure.node_id,
                "model_version": model_version,
            },
        ),
        theorem_id=theorem_id,
        env_profile=theorem.env_profile,
        attempt_id=result.attempt_id,
        failure_kind=failure.kind,
        message=failure.message,
        node_id=failure.node_id,
        model_version=model_version,
    )


def _negation_attempt_record(
    attempt: NegationAttempt,
    theorem: TheoremSpec,
    result: Any,
    *,
    theorem_id: str,
    model_version: int,
) -> NegationAttemptRecord:
    payload_json = attempt.model_dump_json()
    return NegationAttemptRecord(
        id=stable_id(
            "negation_attempt",
            {
                "theorem_id": theorem_id,
                "attempt_id": result.attempt_id,
                "source_node_id": attempt.source_node_id,
                "status": attempt.status,
                "proved_tactic": attempt.proved_tactic,
                "payload_hash": stable_hash(payload_json),
                "model_version": model_version,
            },
        ),
        theorem_id=theorem_id,
        env_profile=theorem.env_profile,
        attempt_id=result.attempt_id,
        source_node_id=attempt.source_node_id,
        negated_target=attempt.negated_target,
        status=attempt.status,
        proved=attempt.proved,
        proved_tactic=attempt.proved_tactic,
        tactic_calls_used=attempt.tactic_calls_used,
        rendered_lean=attempt.rendered_lean,
        payload_json=payload_json,
        model_version=model_version,
    )


def _attempt_lifecycle_records_for_result(
    theorem: TheoremSpec,
    result: Any,
    *,
    theorem_id: str,
) -> list[AttemptLifecycleRecord]:
    if result.attempt_id is None:
        return []
    diagnostics = result.diagnostics
    records: list[AttemptLifecycleRecord] = []
    records.extend(
        _cleanup_lifecycle_records(
            theorem,
            result,
            theorem_id=theorem_id,
            diagnostics=diagnostics,
        )
    )
    records.extend(
        _cancel_lifecycle_records(
            theorem,
            result,
            theorem_id=theorem_id,
            diagnostics=diagnostics,
        )
    )
    return records


def _cleanup_lifecycle_records(
    theorem: TheoremSpec,
    result: Any,
    *,
    theorem_id: str,
    diagnostics: dict[str, float | int | str],
) -> list[AttemptLifecycleRecord]:
    item_ids = _json_string_list(
        diagnostics.get("cleanup_deferred_item_ids")
    )
    cleanup_failed = diagnostics.get("cleanup_failed")
    if cleanup_failed is not None and not item_ids and result.search_item_id:
        item_ids = [result.search_item_id]
    if not item_ids:
        return []
    status = "failed" if cleanup_failed is not None else "deferred"
    return [
        _attempt_lifecycle_record(
            theorem,
            result,
            theorem_id=theorem_id,
            backend_item_id=item_id,
            lifecycle_stage="cleanup",
            lifecycle_status=status,
            retry_count=_int_diagnostic(diagnostics, "cleanup_attempts"),
            max_retries=_optional_int_diagnostic(
                diagnostics,
                "cleanup_max_attempts",
            ),
            last_error=(
                str(cleanup_failed) if cleanup_failed is not None else None
            ),
            terminal=False,
        )
        for item_id in item_ids
    ]


def _cancel_lifecycle_records(
    theorem: TheoremSpec,
    result: Any,
    *,
    theorem_id: str,
    diagnostics: dict[str, float | int | str],
) -> list[AttemptLifecycleRecord]:
    records: list[AttemptLifecycleRecord] = []
    cancel_failed = diagnostics.get("cancel_failed")
    if cancel_failed is not None:
        failed_item_ids = _json_string_list(
            diagnostics.get("cancel_failed_item_ids")
        )
        for item_id in failed_item_ids:
            records.append(
                _attempt_lifecycle_record(
                    theorem,
                    result,
                    theorem_id=theorem_id,
                    backend_item_id=item_id,
                    lifecycle_stage="cancel",
                    lifecycle_status="failed",
                    retry_count=1,
                    max_retries=None,
                    last_error=str(cancel_failed),
                    terminal=False,
                )
            )
    for item in _json_cancel_items(diagnostics.get("cancel_items")):
        records.append(
            _attempt_lifecycle_record(
                theorem,
                result,
                theorem_id=theorem_id,
                backend_item_id=item["item_id"],
                lifecycle_stage="cancel",
                lifecycle_status=item["status"],
                retry_count=1,
                max_retries=None,
                last_error=None,
                terminal=item["status"] in {"cleaned", "drained"},
            )
        )
    return records


def _attempt_lifecycle_record(
    theorem: TheoremSpec,
    result: Any,
    *,
    theorem_id: str,
    backend_item_id: str,
    lifecycle_stage: str,
    lifecycle_status: str,
    retry_count: int,
    max_retries: int | None,
    last_error: str | None,
    terminal: bool,
) -> AttemptLifecycleRecord:
    assert result.attempt_id is not None
    return AttemptLifecycleRecord(
        id=stable_id(
            "attempt_lifecycle",
            {
                "theorem_id": theorem_id,
                "attempt_id": result.attempt_id,
                "backend_item_id": backend_item_id,
                "lifecycle_stage": lifecycle_stage,
            },
        ),
        theorem_id=theorem_id,
        env_profile=theorem.env_profile,
        attempt_id=result.attempt_id,
        backend_item_id=backend_item_id,
        lifecycle_stage=lifecycle_stage,
        lifecycle_status=lifecycle_status,
        retry_count=retry_count,
        max_retries=max_retries,
        last_error=last_error,
        terminal=terminal,
    )


def _json_string_list(value: float | int | str | None) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str):
        raise ValueError("expected JSON string diagnostic")
    decoded = json.loads(value)
    if not isinstance(decoded, list) or not all(
        isinstance(item, str) for item in decoded
    ):
        raise ValueError("expected JSON list of strings")
    return decoded


def _json_cancel_items(
    value: float | int | str | None,
) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, str):
        raise ValueError("expected JSON string diagnostic")
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        raise ValueError("expected JSON list")
    items: list[dict[str, str]] = []
    for item in decoded:
        if not isinstance(item, dict):
            raise ValueError("expected JSON object")
        item_id = item.get("item_id")
        status = item.get("status")
        if not isinstance(item_id, str) or not isinstance(status, str):
            raise ValueError("cancel item requires item_id and status")
        items.append({"item_id": item_id, "status": status})
    return items


def _int_diagnostic(
    diagnostics: dict[str, float | int | str],
    key: str,
) -> int:
    value = diagnostics.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an int diagnostic")
    return value


def _optional_int_diagnostic(
    diagnostics: dict[str, float | int | str],
    key: str,
) -> int | None:
    value = diagnostics.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an int diagnostic")
    return value


def _trajectory_record(
    theorem: TheoremSpec,
    result: Any,
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
