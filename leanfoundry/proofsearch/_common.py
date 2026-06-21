"""Private helpers shared by search-engine implementations."""

from __future__ import annotations

import re
from uuid import uuid4

from lean_client.exec_models import ExecMessage

from leanfoundry.proofsearch.base import SearchAttemptContext, SearchResult
from leanfoundry.schemas import TheoremSpec

_THEOREM_NAME_RE = re.compile(
    r"\b(?:theorem|lemma|def)\s+([A-Za-z_][A-Za-z0-9_'.]*)"
)


def make_attempt_id(theorem: TheoremSpec, *, kind: str) -> str:
    """Return a runner-owned id for one theorem attempt."""

    stable_part = theorem.id or theorem.theorem_name or "anonymous"
    safe_part = re.sub(r"[^A-Za-z0-9_.:-]+", "_", stable_part).strip("_")
    if not safe_part:
        safe_part = "anonymous"
    return f"{safe_part}:{kind}:{uuid4().hex}"


def make_attempt_context(
    theorem: TheoremSpec,
    *,
    kind: str,
    uses_search_state: bool,
    cleanup_max_attempts: int = 3,
    cleanup_backoff_seconds: float = 0.0,
) -> SearchAttemptContext:
    """Allocate backend lifecycle ids for one theorem attempt."""

    attempt_id = make_attempt_id(theorem, kind=kind)
    return SearchAttemptContext(
        attempt_id=attempt_id,
        search_item_id=(
            f"{attempt_id}:search" if uses_search_state else None
        ),
        verify_item_id=f"{attempt_id}:verify",
        cleanup_max_attempts=cleanup_max_attempts,
        cleanup_backoff_seconds=cleanup_backoff_seconds,
    )


def result_with_attempt_context(
    result: SearchResult,
    context: SearchAttemptContext,
    *,
    diagnostics: dict[str, float | int | str] | None = None,
) -> SearchResult:
    """Attach runner-owned attempt identity to a search result."""

    merged_diagnostics = dict(result.diagnostics)
    if diagnostics:
        merged_diagnostics.update(diagnostics)
    return result.model_copy(
        update={
            "attempt_id": context.attempt_id,
            "search_item_id": context.search_item_id,
            "verify_item_id": context.verify_item_id,
            "diagnostics": merged_diagnostics,
        }
    )


def theorem_name_for_verify(theorem: TheoremSpec) -> str | None:
    """Return the theorem name required by ``/exec/verify``."""

    if theorem.theorem_name:
        return theorem.theorem_name
    match = _THEOREM_NAME_RE.search(theorem.lean_statement)
    if match is not None:
        return match.group(1)
    if theorem.initial_lean_block is not None:
        match = _THEOREM_NAME_RE.search(theorem.initial_lean_block)
        if match is not None:
            return match.group(1)
    return None


def verifier_feedback(
    status: str,
    messages: list[ExecMessage],
) -> str:
    """Render verifier status/messages for diagnostics or self-correction."""

    rendered_messages = "\n".join(
        f"{message.severity}: {message.data}" for message in messages
    )
    if not rendered_messages:
        return status
    return f"{status}\n{rendered_messages}"


__all__ = [
    "make_attempt_context",
    "make_attempt_id",
    "result_with_attempt_context",
    "theorem_name_for_verify",
    "verifier_feedback",
]
