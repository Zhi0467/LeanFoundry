"""Private helpers shared by search-engine implementations."""

from __future__ import annotations

import re
from uuid import uuid4

from lean_client.exec_models import ExecMessage

from leanfoundry.schemas import TheoremSpec

_THEOREM_NAME_RE = re.compile(
    r"\b(?:theorem|lemma|def)\s+([A-Za-z_][A-Za-z0-9_'.]*)"
)


def make_search_id(theorem: TheoremSpec, *, kind: str) -> str:
    """Return a backend item id that is unique across concurrent searches."""

    stable_part = theorem.id or theorem.theorem_name or "anonymous"
    safe_part = re.sub(r"[^A-Za-z0-9_.:-]+", "_", stable_part).strip("_")
    if not safe_part:
        safe_part = "anonymous"
    return f"{safe_part}:{kind}:{uuid4().hex}"


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
    "make_search_id",
    "theorem_name_for_verify",
    "verifier_feedback",
]
