"""Private solved-slice extraction from runtime trees."""

from __future__ import annotations

from leanfoundry.proofsearch._tree import (
    ActionNode,
    SearchTree,
    StateNode,
)
from leanfoundry.proofsearch._tree_init import initial_code_for_theorem
from leanfoundry.proofsearch.extraction import extract_tactic_node_from_state
from leanfoundry.schemas import ProofTree, TheoremSpec


class UnsupportedProofExtraction(ValueError):
    """Raised when the solved tree has no sound tactic-script rendering yet."""


def extract_proof_tree(tree: SearchTree, theorem: TheoremSpec) -> ProofTree:
    """Project a proved runtime tree into a durable ``ProofTree``.

    Runtime tree initialization has one synthetic root state and one synthetic
    initialization action above the real backend-created initial states.
    Extraction intentionally skips that synthetic layer. Each ``ProofTree``
    root is built from one real initial state, paired with the proved tactic
    selected at that state.
    """

    synthetic_initialization_action = tree.root.proved_action()
    if synthetic_initialization_action is None:
        raise ValueError("cannot extract proof tree from unproved root")

    roots = [
        extract_tactic_node_from_state(child, depth=0)
        for child in synthetic_initialization_action.children
    ]
    proof_scripts = [
        _render_state_proof(child)
        for child in synthetic_initialization_action.children
    ]
    rendered_lean = _render_lean_with_proofs(theorem, proof_scripts)
    return ProofTree(
        roots=roots,
        rendered_lean=rendered_lean,
        verified=False,
    )


def _render_state_proof(state_node: StateNode) -> str:
    action = state_node.proved_action()
    if action is None:
        raise ValueError("proved state did not expose a proved action")
    return _render_action_proof(action)


def _render_action_proof(action: ActionNode) -> str:
    lines = _strip_blank_edges(action.tactic.splitlines())
    if not action.children:
        return "\n".join(lines)

    if len(action.children) > 1:
        _reject_split_coupled_children(action)

    child_scripts = [_render_state_proof(child) for child in action.children]
    if len(child_scripts) == 1:
        lines.extend(child_scripts[0].splitlines())
        return "\n".join(lines)

    for child_script in child_scripts:
        child_lines = child_script.splitlines()
        if not child_lines:
            continue
        lines.append(f"· {child_lines[0]}")
        lines.extend(f"  {line}" for line in child_lines[1:])
    return "\n".join(lines)


def _render_lean_with_proofs(
    theorem: TheoremSpec,
    proof_scripts: list[str],
) -> str:
    code = initial_code_for_theorem(theorem)

    if not proof_scripts:
        return code

    rendered = code
    for proof_script in proof_scripts:
        rendered, replaced = _replace_first_sorry(rendered, proof_script)
        if not replaced:
            break
    if rendered != code:
        return rendered
    if len(proof_scripts) == 1:
        return _append_single_proof(theorem, proof_scripts[0])
    raise ValueError("initial Lean block has no sorry placeholders")


def _replace_first_sorry(code: str, proof_script: str) -> tuple[str, bool]:
    position = _find_first_sorry_token(code)
    if position is None:
        return code, False

    indent = _line_indent_before(code, position)
    replacement = _indent_script(proof_script, indent)
    rendered = f"{code[:position]}{replacement}{code[position + 5:]}"
    return rendered, True


def _reject_split_coupled_children(action: ActionNode) -> None:
    for child in action.children:
        if child.open_goal_count <= 1:
            continue
        focus = child.focus or tuple(range(child.open_goal_count))
        raise UnsupportedProofExtraction(
            "cannot render a split action whose child owns multiple "
            f"focused goals; action={action.tactic!r}, "
            f"child_node={child.node_id!r}, focus={focus!r}"
        )


def _append_single_proof(theorem: TheoremSpec, proof_script: str) -> str:
    code = theorem.lean_statement.rstrip()
    if theorem.header:
        code = f"{theorem.header.rstrip()}\n\n{code}"
    return f"{code} := by\n{_indent_script(proof_script, '  ')}"


def _line_indent_before(code: str, position: int) -> str:
    line_start = code.rfind("\n", 0, position) + 1
    indent_chars: list[str] = []
    for character in code[line_start:position]:
        if character in {" ", "\t"}:
            indent_chars.append(character)
        else:
            return ""
    return "".join(indent_chars)


def _find_first_sorry_token(code: str) -> int | None:
    index = 0
    block_comment_depth = 0
    in_string = False
    in_line_comment = False

    while index < len(code):
        character = code[index]
        next_character = code[index + 1] if index + 1 < len(code) else ""

        if in_line_comment:
            if character == "\n":
                in_line_comment = False
            index += 1
            continue

        if in_string:
            if character == "\\":
                index += 2
                continue
            if character == "\"":
                in_string = False
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
            index += 1
            continue

        if code.startswith("sorry", index) and _is_token_boundary(
            code,
            index,
            index + 5,
        ):
            return index
        index += 1
    return None


def _is_token_boundary(code: str, start: int, end: int) -> bool:
    before = code[start - 1] if start > 0 else ""
    after = code[end] if end < len(code) else ""
    return not _is_identifier_character(
        before
    ) and not _is_identifier_character(after)


def _is_identifier_character(character: str) -> bool:
    return character.isalnum() or character in {"_", "'", "."}


def _indent_script(proof_script: str, indent: str) -> str:
    lines = proof_script.splitlines() or [""]
    return "\n".join(
        f"{indent}{line}" if index else line
        for index, line in enumerate(lines)
    )


def _strip_blank_edges(lines: list[str]) -> list[str]:
    first = 0
    last = len(lines)
    while first < last and not lines[first].strip():
        first += 1
    while last > first and not lines[last - 1].strip():
        last -= 1
    return lines[first:last]


__all__ = [
    "UnsupportedProofExtraction",
    "extract_proof_tree",
]
