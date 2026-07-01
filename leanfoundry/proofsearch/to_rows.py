"""Framework-neutral conversion from search results to training rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from leanfoundry.policy.http_client import (
    default_proof_prompt,
    default_tactic_prompt,
)
from leanfoundry.proofsearch.base import SearchResult
from leanfoundry.schemas import (
    FactorizedProofState,
    SelfCorrectTrace,
    SelfCorrectTurn,
    TheoremSpec,
)


@dataclass(frozen=True, slots=True)
class TrainingSegment:
    """One response segment with its loss-mask role."""

    text: str
    trainable: bool


@dataclass(frozen=True, slots=True)
class TrainingRow:
    """Framework-neutral row consumed by trainer adapters."""

    kind: Literal["tactic", "whole_proof", "self_correct"]
    prompt: str
    response: str
    reward: float
    group_key: str
    meta: dict[str, object]
    segments: tuple[TrainingSegment, ...] = ()


def to_training_rows(
    result: SearchResult,
    theorem: TheoremSpec,
    *,
    include_whole_proofs: bool = True,
    include_failed_self_correct_negatives: bool = False,
    tactic_prompt: Callable[
        [FactorizedProofState],
        str,
    ] = default_tactic_prompt,
    proof_prompt: Callable[[TheoremSpec], str] = default_proof_prompt,
) -> list[TrainingRow]:
    """Collapse a search result into framework-neutral training rows."""

    artifacts = result.training_artifacts
    if artifacts is None:
        return []

    group_key = _group_key(result, theorem)
    rows: list[TrainingRow] = []

    if include_whole_proofs:
        for proof_candidate in artifacts.proof_candidates:
            if not proof_candidate.verified:
                continue
            response = proof_candidate.rendered_lean.strip()
            if not response:
                continue
            rows.append(
                TrainingRow(
                    kind="whole_proof",
                    prompt=proof_prompt(theorem),
                    response=response,
                    reward=1.0,
                    group_key=group_key,
                    meta=_base_meta(result, theorem, lf_kind="whole_proof"),
                    segments=(TrainingSegment(response, True),),
                )
            )

    for example in artifacts.policy_examples:
        response = example.tactic.strip()
        if not response:
            continue
        meta = _base_meta(result, theorem, lf_kind="tactic")
        meta.update(
            {
                "depth": example.depth,
                "state_token": example.state.state_token,
                "proof_prefix": example.proof_prefix,
                "model_version": example.model_version,
            }
        )
        rows.append(
            TrainingRow(
                kind="tactic",
                prompt=tactic_prompt(example.state),
                response=response,
                reward=1.0,
                group_key=group_key,
                meta=meta,
                segments=(TrainingSegment(response, True),),
            )
        )

    for trace in artifacts.self_correct_traces:
        rows.extend(
            _self_correct_rows(
                trace,
                result,
                theorem,
                group_key=group_key,
                proof_prompt=proof_prompt,
                include_failed_negatives=(
                    include_failed_self_correct_negatives
                ),
            )
        )

    return rows


def _self_correct_rows(
    trace: SelfCorrectTrace,
    result: SearchResult,
    theorem: TheoremSpec,
    *,
    group_key: str,
    proof_prompt: Callable[[TheoremSpec], str],
    include_failed_negatives: bool,
) -> list[TrainingRow]:
    rows: list[TrainingRow] = []
    if include_failed_negatives:
        rows.extend(
            _failed_self_correct_rows(
                trace,
                result,
                theorem,
                group_key=group_key,
                proof_prompt=proof_prompt,
            )
        )
    for previous, current in zip(trace.turns, trace.turns[1:], strict=False):
        if not current.accepted:
            continue
        response = current.proof.strip()
        if not response:
            continue
        meta = _base_meta(result, theorem, lf_kind="self_correct")
        meta.update(
            {
                "previous_verify_item_id": previous.verify_item_id,
                "previous_verifier_status": previous.verifier_status,
                "verify_item_id": current.verify_item_id,
                "turn_index": current.turn_index,
            }
        )
        rows.append(
            TrainingRow(
                kind="self_correct",
                prompt=_self_correct_prompt(
                    theorem,
                    previous,
                    proof_prompt=proof_prompt,
                ),
                response=response,
                reward=1.0,
                group_key=group_key,
                meta=meta,
                segments=(TrainingSegment(response, True),),
            )
        )
    return rows


def _failed_self_correct_rows(
    trace: SelfCorrectTrace,
    result: SearchResult,
    theorem: TheoremSpec,
    *,
    group_key: str,
    proof_prompt: Callable[[TheoremSpec], str],
) -> list[TrainingRow]:
    rows: list[TrainingRow] = []
    for index, turn in enumerate(trace.turns):
        if turn.accepted:
            continue
        response = turn.proof.strip()
        if not response:
            continue
        meta = _base_meta(result, theorem, lf_kind="self_correct")
        meta.update(
            {
                "self_correct_objective": "failed_negative",
                "verify_item_id": turn.verify_item_id,
                "turn_index": turn.turn_index,
                "verifier_status": turn.verifier_status,
            }
        )
        if index > 0:
            previous = trace.turns[index - 1]
            meta.update(
                {
                    "previous_verify_item_id": previous.verify_item_id,
                    "previous_verifier_status": previous.verifier_status,
                }
            )
        rows.append(
            TrainingRow(
                kind="self_correct",
                prompt=_self_correct_turn_prompt(
                    trace,
                    index,
                    theorem,
                    proof_prompt=proof_prompt,
                ),
                response=response,
                reward=0.0,
                group_key=group_key,
                meta=meta,
                segments=(TrainingSegment(response, True),),
            )
        )
    return rows


def _self_correct_turn_prompt(
    trace: SelfCorrectTrace,
    turn_index: int,
    theorem: TheoremSpec,
    *,
    proof_prompt: Callable[[TheoremSpec], str],
) -> str:
    if turn_index == 0:
        return proof_prompt(theorem)
    return _self_correct_prompt(
        theorem,
        trace.turns[turn_index - 1],
        proof_prompt=proof_prompt,
    )


def _self_correct_prompt(
    theorem: TheoremSpec,
    previous: SelfCorrectTurn,
    *,
    proof_prompt: Callable[[TheoremSpec], str],
) -> str:
    return (
        f"{proof_prompt(theorem)}\n\n"
        "Previous proof attempt:\n"
        f"{previous.proof.strip()}\n\n"
        "Verifier feedback:\n"
        f"{previous.verifier_feedback.strip()}\n\n"
        "Write a corrected Lean proof."
    )


def _group_key(result: SearchResult, theorem: TheoremSpec) -> str:
    if result.attempt_id:
        return result.attempt_id
    if theorem.id:
        return theorem.id
    if result.theorem_id:
        return result.theorem_id
    return theorem.lean_statement


def _base_meta(
    result: SearchResult,
    theorem: TheoremSpec,
    *,
    lf_kind: str,
) -> dict[str, object]:
    return {
        "lf_kind": lf_kind,
        "theorem_id": theorem.id or result.theorem_id,
        "theorem_name": theorem.theorem_name,
        "env_profile": theorem.env_profile,
        "source": theorem.source,
        "attempt_id": result.attempt_id,
        "search_item_id": result.search_item_id,
        "verify_item_id": result.verify_item_id,
        "search_status": result.status.value,
        "search_budget_used": result.search_budget_used,
    }


__all__ = [
    "TrainingRow",
    "TrainingSegment",
    "to_training_rows",
]
