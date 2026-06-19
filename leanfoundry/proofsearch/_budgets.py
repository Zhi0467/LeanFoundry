"""Private tactic-call budget helpers."""

from __future__ import annotations

from collections.abc import Sequence, Sized

from leanfoundry.proofsearch.base import SearchConfig


def remaining_tactic_calls(
    config: SearchConfig,
    tactic_calls_used: int,
) -> int:
    """Return remaining Lean tactic attempts under the search config."""

    if tactic_calls_used < 0:
        raise ValueError("tactic_calls_used must be non-negative")
    return max(0, config.max_tactic_calls - tactic_calls_used)


def has_tactic_budget(
    config: SearchConfig,
    tactic_calls_used: int,
) -> bool:
    """Return whether at least one more tactic can be executed."""

    return remaining_tactic_calls(config, tactic_calls_used) > 0


def count_tactic_attempts(executed_results: Sized) -> int:
    """Count executed tactic attempts.

    The budget unit is one tactic string that Lean actually ran. Callers pass
    every backend ``StepResult`` here, including errored attempts and any later
    synthetic actions.
    """

    return len(executed_results)


def truncate_tactics_to_budget(
    tactics: Sequence[str],
    *,
    config: SearchConfig,
    tactic_calls_used: int,
) -> list[str]:
    """Return only the prefix that fits in the remaining tactic budget."""

    remaining = remaining_tactic_calls(config, tactic_calls_used)
    return list(tactics[:remaining])


def charge_tactic_calls(
    *,
    config: SearchConfig,
    tactic_calls_used: int,
    completed_attempts: int,
) -> int:
    """Return the new tactic-call count after completed backend results."""

    if tactic_calls_used < 0:
        raise ValueError("tactic_calls_used must be non-negative")
    if completed_attempts < 0:
        raise ValueError("completed_attempts must be non-negative")
    new_count = tactic_calls_used + completed_attempts
    if new_count > config.max_tactic_calls:
        raise ValueError("completed_attempts exceed max_tactic_calls")
    return new_count


__all__ = [
    "charge_tactic_calls",
    "count_tactic_attempts",
    "has_tactic_budget",
    "remaining_tactic_calls",
    "truncate_tactics_to_budget",
]
