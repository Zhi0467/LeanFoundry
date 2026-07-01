from __future__ import annotations

from leanfoundry.proofsearch import SearchResult, SearchStatus
from leanfoundry.proofsearch.to_rows import to_training_rows
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
    PolicyExample,
    ProofTree,
    SelfCorrectTrace,
    SelfCorrectTurn,
    TheoremSpec,
    TrainingArtifacts,
)


def _theorem() -> TheoremSpec:
    return TheoremSpec(
        id="thm-1",
        theorem_name="t",
        lean_statement="theorem t : True := by",
        env_profile="lean4.29.1_mathlib_5e932f97",
        header="import Mathlib",
        source="unit",
    )


def _state() -> FactorizedProofState:
    return FactorizedProofState(
        env_profile="lean4.29.1_mathlib_5e932f97",
        goal_components=[
            GoalComponent(target="True", pretty="⊢ True", hypotheses=[])
        ],
        pretty_state="case main\n⊢ True",
        state_token="token-1",
    )


def test_to_training_rows_emits_verified_whole_proof_rows() -> None:
    theorem = _theorem()
    result = SearchResult(
        attempt_id="attempt-1",
        verify_item_id="verify-1",
        theorem_id=theorem.id,
        status=SearchStatus.PROVED,
        training_artifacts=TrainingArtifacts(
            proof_candidates=[
                ProofTree(
                    rendered_lean="by\n  trivial",
                    verified=True,
                ),
                ProofTree(
                    rendered_lean="by\n  sorry",
                    verified=False,
                ),
            ]
        ),
        search_budget_used=1,
    )

    rows = to_training_rows(result, theorem)

    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "whole_proof"
    assert row.prompt == "import Mathlib\n\ntheorem t : True := by"
    assert row.response == "by\n  trivial"
    assert row.reward == 1.0
    assert row.group_key == "attempt-1"
    assert row.meta["lf_kind"] == "whole_proof"
    assert row.meta["env_profile"] == theorem.env_profile
    assert row.segments[0].trainable


def test_to_training_rows_emits_tactic_rows() -> None:
    theorem = _theorem()
    result = SearchResult(
        attempt_id="attempt-1",
        search_item_id="search-1",
        theorem_id=theorem.id,
        status=SearchStatus.PROVED,
        training_artifacts=TrainingArtifacts(
            policy_examples=[
                PolicyExample(
                    state=_state(),
                    proof_prefix="constructor",
                    tactic=" trivial ",
                    theorem_id=theorem.id,
                    env_profile=theorem.env_profile,
                    depth=2,
                    model_version=7,
                )
            ]
        ),
        search_budget_used=3,
    )

    rows = to_training_rows(result, theorem)

    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "tactic"
    assert row.prompt == "case main\n⊢ True"
    assert row.response == "trivial"
    assert row.group_key == "attempt-1"
    assert row.meta["lf_kind"] == "tactic"
    assert row.meta["depth"] == 2
    assert row.meta["state_token"] == "token-1"
    assert row.meta["proof_prefix"] == "constructor"
    assert row.meta["model_version"] == 7
    assert row.segments[0].text == "trivial"
    assert row.segments[0].trainable


def test_to_training_rows_emits_self_correct_rows() -> None:
    theorem = _theorem()
    result = SearchResult(
        attempt_id="attempt-1",
        theorem_id=theorem.id,
        status=SearchStatus.PROVED,
        training_artifacts=TrainingArtifacts(
            self_correct_traces=[
                SelfCorrectTrace(
                    turns=[
                        SelfCorrectTurn(
                            turn_index=1,
                            proof="bad proof",
                            verifier_status="rejected",
                            verifier_feedback="error: bad proof",
                            verify_item_id="verify:1",
                            accepted=False,
                        ),
                        SelfCorrectTurn(
                            turn_index=2,
                            proof="good proof",
                            verifier_status="accepted",
                            verify_item_id="verify:2",
                            accepted=True,
                        ),
                    ]
                )
            ]
        ),
        search_budget_used=2,
    )

    rows = to_training_rows(result, theorem)

    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "self_correct"
    assert "Previous proof attempt:\nbad proof" in row.prompt
    assert "Verifier feedback:\nerror: bad proof" in row.prompt
    assert row.response == "good proof"
    assert row.reward == 1.0
    assert row.meta["previous_verify_item_id"] == "verify:1"
    assert row.meta["verify_item_id"] == "verify:2"
    assert row.meta["turn_index"] == 2
    assert len(row.segments) == 1
    assert row.segments[0].text == "good proof"
    assert row.segments[0].trainable


def test_to_training_rows_can_emit_failed_self_correct_negatives() -> None:
    theorem = _theorem()
    result = SearchResult(
        attempt_id="attempt-1",
        theorem_id=theorem.id,
        status=SearchStatus.PROVED,
        training_artifacts=TrainingArtifacts(
            self_correct_traces=[
                SelfCorrectTrace(
                    turns=[
                        SelfCorrectTurn(
                            turn_index=1,
                            proof="bad proof",
                            verifier_status="rejected",
                            verifier_feedback="error: bad proof",
                            verify_item_id="verify:1",
                            accepted=False,
                        ),
                        SelfCorrectTurn(
                            turn_index=2,
                            proof="still bad",
                            verifier_status="rejected",
                            verifier_feedback="error: still bad",
                            verify_item_id="verify:2",
                            accepted=False,
                        ),
                        SelfCorrectTurn(
                            turn_index=3,
                            proof="good proof",
                            verifier_status="accepted",
                            verify_item_id="verify:3",
                            accepted=True,
                        ),
                    ]
                )
            ]
        ),
        search_budget_used=3,
    )

    rows = to_training_rows(
        result,
        theorem,
        include_failed_self_correct_negatives=True,
    )

    assert [row.response for row in rows] == [
        "bad proof",
        "still bad",
        "good proof",
    ]
    assert [row.reward for row in rows] == [0.0, 0.0, 1.0]
    assert rows[0].prompt == "import Mathlib\n\ntheorem t : True := by"
    assert "Previous proof attempt:\nbad proof" in rows[1].prompt
    assert rows[0].meta["self_correct_objective"] == "failed_negative"
    assert rows[1].meta["self_correct_objective"] == "failed_negative"
    assert rows[1].meta["previous_verify_item_id"] == "verify:1"
    assert rows[2].meta["lf_kind"] == "self_correct"


def test_to_training_rows_returns_empty_for_missing_artifacts() -> None:
    rows = to_training_rows(
        SearchResult(status=SearchStatus.ERROR),
        _theorem(),
    )

    assert rows == []
