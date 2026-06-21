"""Direct whole-proof search engines."""

from __future__ import annotations

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.proofsearch._common import (
    make_search_id,
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
from leanfoundry.proofsearch.base import (
    SearchConfig,
    SearchEngine,
    SearchResult,
    SearchStatus,
)
from leanfoundry.schemas import TheoremSpec


class DirectSearchEngine(SearchEngine):
    """Verify whole-proof candidates sampled from the policy client."""

    def __init__(self, *, self_correct: bool = False) -> None:
        self.self_correct = self_correct

    async def search(
        self,
        theorem: TheoremSpec,
        *,
        policy_client: PolicyClient,
        value_client: ValueClient | None,
        env_backend: EnvBackend,
        config: SearchConfig,
    ) -> SearchResult:
        """Run direct whole-proof search for one theorem."""

        theorem_name = theorem_name_for_verify(theorem)
        if theorem_name is None:
            return direct_error_result(
                theorem,
                "theorem_name is required for final verification",
            )

        search_id = make_search_id(theorem, kind="direct")
        attempts_used = 0
        feedback: str | None = None
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
            for candidate in candidates:
                attempts_used += 1
                verification = await env_backend.verify_one(
                    f"{search_id}:{attempts_used}",
                    candidate,
                    theorem_name,
                    allowed_axioms=theorem.allowed_axioms,
                    env_profile=theorem.env_profile,
                )
                if verification.status == "accepted":
                    return SearchResult(
                        theorem_id=theorem.id,
                        status=SearchStatus.PROVED,
                        proof_tree=proof_tree_for_direct_candidate(
                            candidate,
                            verified=True,
                        ),
                        search_budget_used=attempts_used,
                        diagnostics={"verify_attempts": attempts_used},
                    )
                if verification.status == "cancelled":
                    return direct_terminal_result(
                        theorem,
                        SearchStatus.CANCELLED,
                        attempts_used=attempts_used,
                        verifier_status=verification.status,
                        messages=verification.messages,
                    )
                if verification.status == "overloaded":
                    return direct_terminal_result(
                        theorem,
                        SearchStatus.ERROR,
                        attempts_used=attempts_used,
                        verifier_status=verification.status,
                        messages=verification.messages,
                    )
                feedback = verifier_feedback(
                    verification.status,
                    verification.messages,
                )
            if not self.self_correct:
                break

        return SearchResult(
            theorem_id=theorem.id,
            status=SearchStatus.EXHAUSTED,
            search_budget_used=attempts_used,
            diagnostics={
                "verify_attempts": attempts_used,
                "last_feedback": feedback or "",
            },
        )


__all__ = [
    "DirectSearchEngine",
]
