"""Direct whole-proof search engines."""

from __future__ import annotations

import asyncio

from lean_client.exec_models import ExecVerifyItem

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.proofsearch._common import (
    result_with_attempt_context,
    theorem_name_for_verify,
    verifier_feedback,
)
from leanfoundry.proofsearch._direct_utils import (
    direct_error_result,
    direct_prompt,
    direct_terminal_result,
    proof_tree_for_direct_candidate,
    single_proof_batch,
)
from leanfoundry.proofsearch._lifecycle import (
    SearchCancelledWithDiagnostics,
    cancel_item_ids_best_effort,
)
from leanfoundry.proofsearch.base import (
    SearchAttemptContext,
    SearchConfig,
    SearchEngine,
    SearchResult,
    SearchStatus,
)
from leanfoundry.schemas import (
    DirectVerificationAttempt,
    ProofTree,
    SelfCorrectTrace,
    SelfCorrectTurn,
    TheoremSpec,
    TrainingArtifacts,
)


class DirectSearchEngine(SearchEngine):
    """Verify whole-proof candidates sampled from the policy client."""

    def __init__(self, *, self_correct: bool = False) -> None:
        self.self_correct = self_correct

    async def search(
        self,
        theorem: TheoremSpec,
        *,
        attempt_context: SearchAttemptContext,
        policy_client: PolicyClient,
        value_client: ValueClient | None,
        env_backend: EnvBackend,
        config: SearchConfig,
    ) -> SearchResult:
        """Run direct whole-proof search for one theorem."""

        theorem_name = theorem_name_for_verify(theorem)
        if theorem_name is None:
            return result_with_attempt_context(
                direct_error_result(
                    theorem,
                    "theorem_name is required for final verification",
                ),
                attempt_context,
            )

        attempts_used = 0
        feedback: str | None = None
        direct_attempts: list[DirectVerificationAttempt] = []
        self_correct_turns: list[SelfCorrectTurn] = []
        accepted_proof_trees: list[ProofTree] = []
        first_accepted_proof_tree: ProofTree | None = None
        while attempts_used < config.max_direct_candidates:
            round_limit = (
                config.direct_candidates_per_round
                if self.self_correct
                else config.max_direct_candidates
            )
            candidate_limit = min(
                round_limit,
                config.max_direct_candidates - attempts_used,
            )
            sampled_batches = await policy_client.sample_proofs(
                [direct_prompt(theorem, feedback=feedback)],
                n=candidate_limit,
            )
            candidates = single_proof_batch(sampled_batches)
            if not candidates:
                break
            if not self.self_correct:
                verify_item_ids = [
                    attempt_context.direct_verify_item_id(
                        attempts_used + index + 1
                    )
                    for index in range(len(candidates))
                ]
                verify_items = [
                    ExecVerifyItem(
                        item_id=verify_item_id,
                        code=candidate,
                        theorem_name=theorem_name,
                        allowed_axioms=theorem.allowed_axioms,
                    )
                    for verify_item_id, candidate in zip(
                        verify_item_ids,
                        candidates,
                    )
                ]
                try:
                    verification_response = await env_backend.verify(
                        verify_items,
                        env_profile=theorem.env_profile,
                    )
                except asyncio.CancelledError:
                    cancel_report = await cancel_item_ids_best_effort(
                        env_backend,
                        verify_item_ids,
                    )
                    raise SearchCancelledWithDiagnostics(
                        cancel_report.diagnostics()
                    ) from None
                if len(verification_response.items) != len(candidates):
                    return result_with_attempt_context(
                        direct_error_result(
                            theorem,
                            "backend verify result count did not match "
                            "candidates",
                        ),
                        attempt_context,
                    )
                for candidate, verify_item_id, verification in zip(
                    candidates,
                    verify_item_ids,
                    verification_response.items,
                ):
                    attempts_used += 1
                    attempt_feedback = verifier_feedback(
                        verification.status,
                        verification.messages,
                    )
                    direct_attempts.append(
                        _direct_verification_attempt(
                            attempts_used,
                            candidate,
                            verification.status,
                            attempt_feedback,
                            verify_item_id,
                            accepted=verification.status == "accepted",
                        )
                    )
                    if verification.status == "accepted":
                        proof_tree = proof_tree_for_direct_candidate(
                            candidate,
                            verified=True,
                        )
                        if first_accepted_proof_tree is None:
                            first_accepted_proof_tree = proof_tree
                        accepted_proof_trees.append(proof_tree)
                    if verification.status == "cancelled":
                        return result_with_attempt_context(
                            _with_direct_attempts(
                                direct_terminal_result(
                                    theorem,
                                    SearchStatus.CANCELLED,
                                    attempts_used=attempts_used,
                                    verifier_status=verification.status,
                                    messages=verification.messages,
                                ),
                                direct_attempts,
                            ),
                            attempt_context,
                        )
                    if verification.status == "overloaded":
                        return result_with_attempt_context(
                            _with_direct_attempts(
                                direct_terminal_result(
                                    theorem,
                                    SearchStatus.ERROR,
                                    attempts_used=attempts_used,
                                    verifier_status=verification.status,
                                    messages=verification.messages,
                                ),
                                direct_attempts,
                            ),
                            attempt_context,
                        )
                    feedback = attempt_feedback
                break
            for candidate in candidates:
                attempts_used += 1
                verify_item_id = attempt_context.direct_verify_item_id(
                    attempts_used
                )
                try:
                    verification = await env_backend.verify_one(
                        verify_item_id,
                        candidate,
                        theorem_name,
                        allowed_axioms=theorem.allowed_axioms,
                        env_profile=theorem.env_profile,
                    )
                except asyncio.CancelledError:
                    cancel_report = await cancel_item_ids_best_effort(
                        env_backend,
                        [verify_item_id],
                    )
                    raise SearchCancelledWithDiagnostics(
                        cancel_report.diagnostics()
                    ) from None
                attempt_feedback = verifier_feedback(
                    verification.status,
                    verification.messages,
                )
                direct_attempts.append(
                    _direct_verification_attempt(
                        attempts_used,
                        candidate,
                        verification.status,
                        attempt_feedback,
                        verify_item_id,
                        accepted=verification.status == "accepted",
                    )
                )
                if verification.status == "accepted":
                    proof_tree = proof_tree_for_direct_candidate(
                        candidate,
                        verified=True,
                    )
                    if first_accepted_proof_tree is None:
                        first_accepted_proof_tree = proof_tree
                    accepted_proof_trees.append(proof_tree)
                    if self.self_correct:
                        self_correct_turns.append(
                            _self_correct_turn(
                                attempts_used,
                                candidate,
                                verification.status,
                                "",
                                verify_item_id,
                                accepted=True,
                            )
                        )
                        artifacts = _direct_artifacts(
                            direct_attempts,
                            proof_candidates=accepted_proof_trees,
                            self_correct_turns=(
                                self_correct_turns
                                if len(self_correct_turns) > 1
                                else []
                            ),
                        )
                        return result_with_attempt_context(
                            SearchResult(
                                theorem_id=theorem.id,
                                status=SearchStatus.PROVED,
                                proof_tree=proof_tree,
                                training_artifacts=artifacts,
                                search_budget_used=attempts_used,
                                diagnostics={
                                    "verify_attempts": attempts_used
                                },
                            ),
                            attempt_context,
                        )
                if verification.status == "cancelled":
                    return result_with_attempt_context(
                        _with_direct_attempts(
                            direct_terminal_result(
                                theorem,
                                SearchStatus.CANCELLED,
                                attempts_used=attempts_used,
                                verifier_status=verification.status,
                                messages=verification.messages,
                            ),
                            direct_attempts,
                        ),
                        attempt_context,
                    )
                if verification.status == "overloaded":
                    return result_with_attempt_context(
                        _with_direct_attempts(
                            direct_terminal_result(
                                theorem,
                                SearchStatus.ERROR,
                                attempts_used=attempts_used,
                                verifier_status=verification.status,
                                messages=verification.messages,
                            ),
                            direct_attempts,
                        ),
                        attempt_context,
                    )
                feedback = attempt_feedback
                if self.self_correct:
                    self_correct_turns.append(
                        _self_correct_turn(
                            attempts_used,
                            candidate,
                            verification.status,
                            feedback,
                            verify_item_id,
                            accepted=False,
                        )
                    )
            if not self.self_correct:
                break

        if first_accepted_proof_tree is not None:
            artifacts = _direct_artifacts(
                direct_attempts,
                proof_candidates=accepted_proof_trees,
            )
            return result_with_attempt_context(
                SearchResult(
                    theorem_id=theorem.id,
                    status=SearchStatus.PROVED,
                    proof_tree=first_accepted_proof_tree,
                    training_artifacts=artifacts,
                    search_budget_used=attempts_used,
                    diagnostics={"verify_attempts": attempts_used},
                ),
                attempt_context,
            )

        artifacts = None
        if direct_attempts or (self.self_correct and self_correct_turns):
            artifacts = _direct_artifacts(
                direct_attempts,
                self_correct_turns=(
                    self_correct_turns if self.self_correct else []
                ),
            )
        return result_with_attempt_context(
            SearchResult(
                theorem_id=theorem.id,
                status=SearchStatus.EXHAUSTED,
                training_artifacts=artifacts,
                search_budget_used=attempts_used,
                diagnostics={
                    "verify_attempts": attempts_used,
                    "last_feedback": feedback or "",
                },
            ),
            attempt_context,
        )


def _with_direct_attempts(
    result: SearchResult,
    attempts: list[DirectVerificationAttempt],
) -> SearchResult:
    if not attempts:
        return result
    return result.model_copy(
        update={"training_artifacts": _direct_artifacts(attempts)}
    )


def _direct_artifacts(
    attempts: list[DirectVerificationAttempt],
    *,
    proof_candidates: list[ProofTree] | None = None,
    self_correct_turns: list[SelfCorrectTurn] | None = None,
) -> TrainingArtifacts:
    proof_candidate_list = list(proof_candidates or [])
    self_correct_turn_list = list(self_correct_turns or [])
    diagnostics: dict[str, int] = {
        "direct_verification_attempts": len(attempts)
    }
    if proof_candidate_list:
        diagnostics["proof_candidates"] = len(proof_candidate_list)
    if self_correct_turn_list:
        diagnostics["self_correct_turns"] = len(self_correct_turn_list)
    traces = (
        [SelfCorrectTrace(turns=self_correct_turn_list)]
        if self_correct_turn_list
        else []
    )
    return TrainingArtifacts(
        proof_candidates=proof_candidate_list,
        direct_verification_attempts=list(attempts),
        self_correct_traces=traces,
        diagnostics=diagnostics,
    )


def _direct_verification_attempt(
    candidate_index: int,
    proof: str,
    verifier_status: str,
    verifier_feedback: str,
    verify_item_id: str,
    *,
    accepted: bool,
) -> DirectVerificationAttempt:
    return DirectVerificationAttempt(
        candidate_index=candidate_index,
        proof=proof,
        verifier_status=verifier_status,
        verifier_feedback=verifier_feedback,
        verify_item_id=verify_item_id,
        accepted=accepted,
    )


def _self_correct_turn(
    turn_index: int,
    proof: str,
    verifier_status: str,
    verifier_feedback: str,
    verify_item_id: str,
    *,
    accepted: bool,
) -> SelfCorrectTurn:
    return SelfCorrectTurn(
        turn_index=turn_index,
        proof=proof,
        verifier_status=verifier_status,
        verifier_feedback=verifier_feedback,
        verify_item_id=verify_item_id,
        accepted=accepted,
    )


__all__ = [
    "DirectSearchEngine",
]
