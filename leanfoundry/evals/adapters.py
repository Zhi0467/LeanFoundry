"""Benchmark row adapters for public eval dataset formats."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from leanfoundry.schemas import TheoremSpec


MINIF2F_LEAN4_ROW_FORMAT = "minif2f_lean4_jsonl"
MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT = "matholympiadbench_lean4_jsonl"
PROOFNET_LEAN4_ROW_FORMAT = "proofnet_lean4_jsonl"
PUTNAMBENCH_LEAN4_ROW_FORMAT = "putnambench_lean4_jsonl"


def make_minif2f_lean4_row_adapter(
    *,
    env_profile: str,
    expected_split: str | None = None,
    source: str = "miniF2F",
) -> Callable[[Mapping[str, Any]], TheoremSpec]:
    """Return an adapter for common MiniF2F Lean 4 JSONL rows.

    Expected row fields are ``id`` or ``name``, ``formal_statement``, and
    ``header``. Optional fields include ``split``, ``informal_stmt``,
    ``informal_prefix``, and ``informal_proof``. The manifest owns
    ``env_profile`` because public benchmark rows usually do not pin a
    LeanFoundry environment profile.
    """

    def adapt(row: Mapping[str, Any]) -> TheoremSpec:
        return adapt_minif2f_lean4_row(
            row,
            env_profile=env_profile,
            expected_split=expected_split,
            source=source,
        )

    return adapt


def adapt_minif2f_lean4_row(
    row: Mapping[str, Any],
    *,
    env_profile: str,
    expected_split: str | None = None,
    source: str = "miniF2F",
) -> TheoremSpec:
    """Adapt one MiniF2F Lean 4 JSON object into ``TheoremSpec``."""

    name = _required_any_str(row, ("id", "name"), row_name="MiniF2F")
    split = _optional_str(row, "split")
    if expected_split is not None and split is not None:
        if split != expected_split:
            raise ValueError(
                "MiniF2F split mismatch: "
                f"expected {expected_split!r}, got {split!r}"
            )
    id_parts = [source]
    if split is not None:
        id_parts.append(split)
    id_parts.append(name)
    theorem_source = source if split is None else f"{source}/{split}"
    return TheoremSpec(
        id=":".join(id_parts),
        theorem_name=name,
        lean_statement=_required_str(
            row,
            "formal_statement",
            row_name="MiniF2F",
        ),
        informal_statement=_optional_any_str(
            row,
            ("informal_stmt", "informal_prefix"),
        ),
        env_profile=env_profile,
        header=_required_str(row, "header", row_name="MiniF2F"),
        source=theorem_source,
    )


def make_matholympiadbench_lean4_row_adapter(
    *,
    env_profile: str,
    expected_split: str | None = None,
    source: str = "MathOlympiadBench",
) -> Callable[[Mapping[str, Any]], TheoremSpec]:
    """Return an adapter for MathOlympiadBench Lean 4 JSONL rows.

    Expected row fields are ``name`` or ``problem_id``,
    ``formal_statement``, and ``header``. Optional fields include ``split``,
    ``informal_prefix``, and ``category``. The full formal statement is
    preserved because rows may include declarations before the theorem.
    """

    def adapt(row: Mapping[str, Any]) -> TheoremSpec:
        return adapt_matholympiadbench_lean4_row(
            row,
            env_profile=env_profile,
            expected_split=expected_split,
            source=source,
        )

    return adapt


def adapt_matholympiadbench_lean4_row(
    row: Mapping[str, Any],
    *,
    env_profile: str,
    expected_split: str | None = None,
    source: str = "MathOlympiadBench",
) -> TheoremSpec:
    """Adapt one MathOlympiadBench Lean 4 JSON object into ``TheoremSpec``."""

    name = _required_any_str(
        row,
        ("name", "problem_id"),
        row_name="MathOlympiadBench",
    )
    split = _optional_str(row, "split", row_name="MathOlympiadBench")
    if expected_split is not None and split is not None:
        if split != expected_split:
            raise ValueError(
                "MathOlympiadBench split mismatch: "
                f"expected {expected_split!r}, got {split!r}"
            )
    id_parts = [source]
    if split is not None:
        id_parts.append(split)
    id_parts.append(name)
    theorem_source = source if split is None else f"{source}/{split}"
    return TheoremSpec(
        id=":".join(id_parts),
        theorem_name=name,
        lean_statement=_required_str(
            row,
            "formal_statement",
            row_name="MathOlympiadBench",
        ),
        informal_statement=_optional_str(
            row,
            "informal_prefix",
            row_name="MathOlympiadBench",
        ),
        env_profile=env_profile,
        header=_required_str(
            row,
            "header",
            row_name="MathOlympiadBench",
        ),
        source=theorem_source,
    )


def make_proofnet_lean4_row_adapter(
    *,
    env_profile: str,
    expected_split: str | None = None,
    source: str = "ProofNet",
) -> Callable[[Mapping[str, Any]], TheoremSpec]:
    """Return an adapter for ProofNet Lean 4 JSONL rows.

    Public ProofNet Lean 4 rows store theorem declarations that end at ``:=``.
    This adapter explicitly initializes that placeholder with ``by sorry`` so
    the result is a valid Lean theorem block for benchmark loading.
    """

    def adapt(row: Mapping[str, Any]) -> TheoremSpec:
        return adapt_proofnet_lean4_row(
            row,
            env_profile=env_profile,
            expected_split=expected_split,
            source=source,
        )

    return adapt


def adapt_proofnet_lean4_row(
    row: Mapping[str, Any],
    *,
    env_profile: str,
    expected_split: str | None = None,
    source: str = "ProofNet",
) -> TheoremSpec:
    """Adapt one ProofNet Lean 4 JSON object into ``TheoremSpec``."""

    name = _required_str(row, "name", row_name="ProofNet")
    split = _optional_str(row, "split", row_name="ProofNet")
    if expected_split is not None and split is not None:
        if split != expected_split:
            raise ValueError(
                "ProofNet split mismatch: "
                f"expected {expected_split!r}, got {split!r}"
            )
    id_parts = [source]
    if split is not None:
        id_parts.append(split)
    id_parts.append(name)
    theorem_source = source if split is None else f"{source}/{split}"
    return TheoremSpec(
        id=":".join(id_parts),
        theorem_name=name,
        lean_statement=_proofnet_statement_with_sorry(
            _required_str(
                row,
                "formal_statement",
                row_name="ProofNet",
            )
        ),
        informal_statement=_optional_str(
            row,
            "informal_prefix",
            row_name="ProofNet",
        ),
        env_profile=env_profile,
        header=_required_str(row, "header", row_name="ProofNet"),
        source=theorem_source,
    )


def make_putnambench_lean4_row_adapter(
    *,
    env_profile: str,
    header: str,
    expected_split: str | None = None,
    source: str = "PutnamBench",
) -> Callable[[Mapping[str, Any]], TheoremSpec]:
    """Return an adapter for PutnamBench Lean 4 JSONL rows.

    The public Hugging Face mirror stores rows with ``problem_name``,
    ``formal_statement``, optional informal text, tags, and ``split``. It does
    not include a Lean header per row, so callers must supply the header from
    the benchmark's registered ``EnvProfile``.
    """

    if not header.strip():
        raise ValueError("PutnamBench adapter requires a non-empty header")

    def adapt(row: Mapping[str, Any]) -> TheoremSpec:
        return adapt_putnambench_lean4_row(
            row,
            env_profile=env_profile,
            header=header,
            expected_split=expected_split,
            source=source,
        )

    return adapt


def adapt_putnambench_lean4_row(
    row: Mapping[str, Any],
    *,
    env_profile: str,
    header: str,
    expected_split: str | None = None,
    source: str = "PutnamBench",
) -> TheoremSpec:
    """Adapt one PutnamBench Lean 4 JSON object into ``TheoremSpec``."""

    if not header.strip():
        raise ValueError("PutnamBench row adapter requires a non-empty header")
    name = _required_str(row, "problem_name", row_name="PutnamBench")
    split = _optional_str(row, "split", row_name="PutnamBench")
    if expected_split is not None and split is not None:
        if split != expected_split:
            raise ValueError(
                "PutnamBench split mismatch: "
                f"expected {expected_split!r}, got {split!r}"
            )
    id_parts = [source]
    if split is not None:
        id_parts.append(split)
    id_parts.append(name)
    theorem_source = source if split is None else f"{source}/{split}"
    return TheoremSpec(
        id=":".join(id_parts),
        theorem_name=name,
        lean_statement=_required_str(
            row,
            "formal_statement",
            row_name="PutnamBench",
        ),
        informal_statement=_optional_str(
            row,
            "informal_statement",
            row_name="PutnamBench",
        ),
        env_profile=env_profile,
        header=header,
        source=theorem_source,
    )


def _required_any_str(
    row: Mapping[str, Any],
    fields: tuple[str, ...],
    *,
    row_name: str,
) -> str:
    for field in fields:
        value = _optional_str(row, field, row_name=row_name)
        if value is not None and value.strip():
            return value
    raise ValueError(
        f"{row_name} row requires one non-empty field from "
        f"{', '.join(repr(field) for field in fields)}"
    )


def _required_str(
    row: Mapping[str, Any],
    field: str,
    *,
    row_name: str,
) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{row_name} row requires non-empty {field!r}")
    return value


def _optional_any_str(
    row: Mapping[str, Any],
    fields: tuple[str, ...],
) -> str | None:
    for field in fields:
        value = _optional_str(row, field, row_name="MiniF2F")
        if value is not None:
            return value
    return None


def _optional_str(
    row: Mapping[str, Any],
    field: str,
    *,
    row_name: str = "MiniF2F",
) -> str | None:
    value = row.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{row_name} row {field!r} must be a string")
    return value


def _proofnet_statement_with_sorry(formal_statement: str) -> str:
    stripped = formal_statement.rstrip()
    if not stripped.endswith(":="):
        raise ValueError("ProofNet formal_statement must end with ':='")
    return f"{stripped} by\n  sorry"


__all__ = [
    "MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT",
    "MINIF2F_LEAN4_ROW_FORMAT",
    "PROOFNET_LEAN4_ROW_FORMAT",
    "PUTNAMBENCH_LEAN4_ROW_FORMAT",
    "adapt_matholympiadbench_lean4_row",
    "adapt_minif2f_lean4_row",
    "adapt_proofnet_lean4_row",
    "adapt_putnambench_lean4_row",
    "make_matholympiadbench_lean4_row_adapter",
    "make_minif2f_lean4_row_adapter",
    "make_proofnet_lean4_row_adapter",
    "make_putnambench_lean4_row_adapter",
]
