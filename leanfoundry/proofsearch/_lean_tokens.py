"""Small Lean token scanner used by proof-search safeguards."""

from __future__ import annotations

FORBIDDEN_PROOF_PLACEHOLDER_TOKENS = frozenset({"admit", "sorry"})


def find_forbidden_proof_placeholder_token(code: str) -> str | None:
    """Return the first forbidden proof-placeholder token in Lean code."""

    match = find_lean_token(code, FORBIDDEN_PROOF_PLACEHOLDER_TOKENS)
    if match is None:
        return None
    token, _position = match
    return token


def find_lean_token(
    code: str,
    tokens: frozenset[str],
) -> tuple[str, int] | None:
    """Find the first exact Lean token, ignoring comments and strings."""

    index = 0
    block_comment_depth = 0
    in_string = False
    in_interpolated_string = False
    in_line_comment = False
    ordered_tokens = sorted(tokens, key=len, reverse=True)

    while index < len(code):
        character = code[index]
        next_character = code[index + 1] if index + 1 < len(code) else ""

        if in_line_comment:
            if character == "\n":
                in_line_comment = False
            index += 1
            continue

        if in_string:
            if in_interpolated_string:
                match = _match_token_at(code, index, ordered_tokens)
                if match is not None:
                    return match
            if character == "\\":
                index += 2
                continue
            if character == "\"":
                in_string = False
                in_interpolated_string = False
            index += 1
            continue

        if block_comment_depth:
            if character == "/" and next_character == "-":
                block_comment_depth += 1
                index += 2
                continue
            if character == "-" and next_character == "/":
                block_comment_depth -= 1
                index += 2
                continue
            index += 1
            continue

        if character == "-" and next_character == "-":
            in_line_comment = True
            index += 2
            continue
        if character == "/" and next_character == "-":
            block_comment_depth = 1
            index += 2
            continue
        if character == "\"":
            in_string = True
            in_interpolated_string = (
                index >= 2 and code[index - 2:index] == "s!"
            )
            index += 1
            continue

        match = _match_token_at(code, index, ordered_tokens)
        if match is not None:
            return match
        index += 1
    return None


def _match_token_at(
    code: str,
    index: int,
    ordered_tokens: list[str],
) -> tuple[str, int] | None:
    for token in ordered_tokens:
        end = index + len(token)
        if code.startswith(token, index) and _is_token_boundary(
            code,
            index,
            end,
        ):
            return token, index
    return None


def _is_token_boundary(code: str, start: int, end: int) -> bool:
    before = code[start - 1] if start > 0 else ""
    after = code[end] if end < len(code) else ""
    return not _is_identifier_character(
        before
    ) and not _is_identifier_character(after)


def _is_identifier_character(character: str) -> bool:
    return character.isalnum() or character in {"_", "'", "."}


__all__ = [
    "FORBIDDEN_PROOF_PLACEHOLDER_TOKENS",
    "find_forbidden_proof_placeholder_token",
    "find_lean_token",
]
