"""Private helpers for direct search."""

from __future__ import annotations

from lean_client.exec_models import ExecMessage

from leanfoundry.proofsearch._common import verifier_feedback
from leanfoundry.proofsearch.base import SearchResult, SearchStatus
from leanfoundry.schemas import ProofTree, TheoremSpec


def direct_prompt(theorem: TheoremSpec, *, feedback: str | None = None) -> str:
    """Build the prompt string passed through to ``sample_proofs``."""

    parts = [
        theorem.header.strip(),
        theorem.initial_lean_block or theorem.lean_statement,
    ]
    if theorem.informal_statement is not None:
        parts.append(theorem.informal_statement)
    if feedback:
        parts.append("Previous verifier feedback:")
        parts.append(feedback)
    return "\n\n".join(part for part in parts if part)


def proof_tree_for_direct_candidate(
    candidate: str,
    *,
    verified: bool,
) -> ProofTree:
    """Wrap a verified whole-proof candidate as a proof-tree projection."""

    return ProofTree(roots=[], rendered_lean=candidate, verified=verified)


def single_proof_batch(sampled_batches: list[list[str]]) -> list[str]:
    """Return the only proof batch from a single-prompt policy call."""

    if len(sampled_batches) != 1:
        raise ValueError("policy_client must return one proof batch")
    return sampled_batches[0]


def direct_terminal_result(
    theorem: TheoremSpec,
    status: SearchStatus,
    *,
    attempts_used: int,
    verifier_status: str,
    messages: list[ExecMessage],
) -> SearchResult:
    """Build a direct-search terminal result from verifier output."""

    return SearchResult(
        theorem_id=theorem.id,
        status=status,
        search_budget_used=attempts_used,
        diagnostics={
            "verify_attempts": attempts_used,
            "verifier_status": verifier_status,
            "verifier_feedback": verifier_feedback(verifier_status, messages),
        },
    )


def direct_error_result(theorem: TheoremSpec, message: str) -> SearchResult:
    """Build a direct-search configuration error result."""

    return SearchResult(
        theorem_id=theorem.id,
        status=SearchStatus.ERROR,
        diagnostics={"error": message},
    )
