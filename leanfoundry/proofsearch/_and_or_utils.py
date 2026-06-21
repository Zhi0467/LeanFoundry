"""Private result helpers for the AND/OR tree engine."""

from __future__ import annotations

from leanfoundry.env_backend import EnvBackend
from leanfoundry.proofsearch._common import verifier_feedback
from leanfoundry.proofsearch.base import SearchResult, SearchStatus
from leanfoundry.schemas import ProofTree, TheoremSpec


async def verify_extracted_tree(
    theorem: TheoremSpec,
    env_backend: EnvBackend,
    search_id: str,
    theorem_name: str,
    proof_tree: ProofTree,
    tactic_calls_made: int,
) -> SearchResult:
    """Run final verification and build the top-level search result."""

    verification = await env_backend.verify_one(
        search_id,
        proof_tree.rendered_lean,
        theorem_name,
        allowed_axioms=theorem.allowed_axioms,
        env_profile=theorem.env_profile,
    )
    verified_tree = proof_tree.model_copy(
        update={"verified": verification.status == "accepted"}
    )
    if verification.status == "accepted":
        return SearchResult(
            theorem_id=theorem.id,
            status=SearchStatus.PROVED,
            proof_tree=verified_tree,
            search_budget_used=tactic_calls_made,
            diagnostics={"verifier_status": verification.status},
        )
    status = (
        SearchStatus.CANCELLED
        if verification.status == "cancelled"
        else SearchStatus.ERROR
    )
    return SearchResult(
        theorem_id=theorem.id,
        status=status,
        proof_tree=verified_tree,
        search_budget_used=tactic_calls_made,
        diagnostics={
            "verifier_status": verification.status,
            "verifier_feedback": verifier_feedback(
                verification.status,
                verification.messages,
            ),
        },
    )


def operational_result(
    theorem: TheoremSpec,
    tactic_calls_made: int,
    operational_status: str,
    failure_message: str | None,
) -> SearchResult:
    """Build a non-budget operational failure result."""

    status = (
        SearchStatus.CANCELLED
        if operational_status == "cancelled"
        else SearchStatus.ERROR
    )
    return SearchResult(
        theorem_id=theorem.id,
        status=status,
        search_budget_used=tactic_calls_made,
        diagnostics={
            "operational_status": operational_status,
            "failure_message": failure_message or "",
        },
    )


__all__ = [
    "operational_result",
    "verify_extracted_tree",
]
