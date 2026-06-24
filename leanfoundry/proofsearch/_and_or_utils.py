"""Private result helpers for the AND/OR tree engine."""

from __future__ import annotations

from leanfoundry.env_backend import EnvBackend
from leanfoundry.proofsearch._common import verifier_feedback
from leanfoundry.proofsearch._tree import SearchTree
from leanfoundry.proofsearch.base import SearchResult, SearchStatus
from leanfoundry.proofsearch.extraction import (
    ExtractionContext,
    extract_training_artifacts,
)
from leanfoundry.schemas import ProofTree, TheoremSpec


async def verify_extracted_tree(
    theorem: TheoremSpec,
    env_backend: EnvBackend,
    verify_item_id: str,
    theorem_name: str,
    proof_tree: ProofTree,
    tactic_calls_made: int,
    tree: SearchTree,
    extraction_context: ExtractionContext,
) -> SearchResult:
    """Run final verification and build the top-level search result."""

    verification = await env_backend.verify_one(
        verify_item_id,
        proof_tree.rendered_lean,
        theorem_name,
        allowed_axioms=theorem.allowed_axioms,
        env_profile=theorem.env_profile,
    )
    verified_tree = proof_tree.model_copy(
        update={"verified": verification.status == "accepted"}
    )
    artifacts = extract_training_artifacts(
        tree,
        extraction_context.with_verification_status(verification.status),
        proof_tree=verified_tree,
    )
    diagnostics: dict[str, float | int | str] = {
        "verifier_status": verification.status
    }
    if verification.status == "accepted":
        status = SearchStatus.PROVED
    elif verification.status == "cancelled":
        status = SearchStatus.CANCELLED
    else:
        status = SearchStatus.ERROR
    if verification.status != "accepted":
        diagnostics["verifier_feedback"] = verifier_feedback(
            verification.status,
            verification.messages,
        )
    return SearchResult(
        theorem_id=theorem.id,
        status=status,
        proof_tree=verified_tree,
        training_artifacts=artifacts,
        search_budget_used=tactic_calls_made,
        diagnostics=diagnostics,
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
