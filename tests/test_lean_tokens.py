from __future__ import annotations

import pytest

from leanfoundry.proofsearch._lean_tokens import (
    find_forbidden_proof_placeholder_token,
    find_lean_token,
)


FORBIDDEN_TOKENS = frozenset({"admit", "sorry"})


def test_find_lean_token_returns_first_token_and_position() -> None:
    code = "exact trivial\nadmit\nsorry\n"

    assert find_lean_token(code, FORBIDDEN_TOKENS) == (
        "admit",
        code.index("admit"),
    )


def test_find_lean_token_requires_identifier_boundaries() -> None:
    code = (
        "have sorryful := True\n"
        "have _sorry := True\n"
        "have h := foo.sorry\n"
        "have h' := sorry'\n"
        "have admitter := True\n"
        "trivial\n"
    )

    assert find_lean_token(code, FORBIDDEN_TOKENS) is None


def test_find_lean_token_rejects_identifier_prefix_at_index_one() -> None:
    assert find_lean_token("_sorry", FORBIDDEN_TOKENS) is None
    assert find_lean_token("xsorry", FORBIDDEN_TOKENS) is None


def test_find_lean_token_ignores_line_and_nested_block_comments() -> None:
    code = (
        "-- admit in a line comment\n"
        "/- sorry in a block /- admit nested -/ sorry still comment -/\n"
        "exact sorry"
    )

    assert find_lean_token(code, FORBIDDEN_TOKENS) == (
        "sorry",
        code.rindex("sorry"),
    )


def test_find_lean_token_handles_comments_adjacent_to_tokens() -> None:
    line_comment_code = "--\nsorry"
    empty_block_code = "/--/sorry"
    block_close_code = "/-x-/sorry"
    nested_block_code = "/- /--/ -/sorry"

    assert find_lean_token(line_comment_code, FORBIDDEN_TOKENS) == (
        "sorry",
        line_comment_code.index("sorry"),
    )
    assert find_lean_token(empty_block_code, FORBIDDEN_TOKENS) == (
        "sorry",
        empty_block_code.index("sorry"),
    )
    assert find_lean_token(block_close_code, FORBIDDEN_TOKENS) == (
        "sorry",
        block_close_code.index("sorry"),
    )
    assert find_lean_token(nested_block_code, FORBIDDEN_TOKENS) == (
        "sorry",
        nested_block_code.index("sorry"),
    )


def test_find_lean_token_does_not_treat_single_minus_as_comment() -> None:
    code = "- sorry"

    assert find_lean_token(code, FORBIDDEN_TOKENS) == (
        "sorry",
        code.index("sorry"),
    )


def test_find_lean_token_ignores_regular_strings_and_escaped_quotes() -> None:
    code = (
        'have text := "not code \\" admit \\" sorry"\n'
        "exact sorry"
    )

    assert find_lean_token(code, FORBIDDEN_TOKENS) == (
        "sorry",
        code.rindex("sorry"),
    )


def test_find_lean_token_handles_escaped_quote_before_string_close() -> None:
    code = 'have text := "escaped quote \\""\nexact sorry'

    assert find_lean_token(code, FORBIDDEN_TOKENS) == (
        "sorry",
        code.index("sorry"),
    )


def test_find_lean_token_fails_closed_inside_interpolated_strings() -> None:
    code = 'have text := s!"literal sorry"\ntrivial'

    assert find_lean_token(code, FORBIDDEN_TOKENS) == (
        "sorry",
        code.index("sorry"),
    )


def test_find_lean_token_fails_closed_for_initial_interpolation() -> None:
    code = 's!"sorry"'

    assert find_lean_token(code, FORBIDDEN_TOKENS) == (
        "sorry",
        code.index("sorry"),
    )


def test_find_lean_token_prefers_longest_token_at_same_position() -> None:
    assert find_lean_token("<=", frozenset({"<", "<="})) == ("<=", 0)


@pytest.mark.parametrize(
    ("code", "expected_token"),
    [
        ("exact admit", "admit"),
        ("exact sorry", "sorry"),
        ("have sorryful := True\ntrivial", None),
    ],
)
def test_find_forbidden_proof_placeholder_token(
    code: str,
    expected_token: str | None,
) -> None:
    assert find_forbidden_proof_placeholder_token(code) == expected_token
