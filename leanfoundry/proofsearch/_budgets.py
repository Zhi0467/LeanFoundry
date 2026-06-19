"""Private tactic-call budget helpers."""

from __future__ import annotations

from collections.abc import Iterable

from lean_client.exec_models import ExecStepResult

from leanfoundry.proofsearch.base import SearchConfig

EXECUTED_STEP_STATUSES = frozenset({"open", "complete", "error"})


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


def count_tactic_attempts(step_results: Iterable[ExecStepResult]) -> int:
    """Count executed tactic attempts.

    The budget unit is one tactic string that Lean actually ran. Callers pass
    backend ``StepResult`` objects here; errored tactics count because Lean ran
    them, while overload/cancel/token failures do not.
    """

    return sum(1 for result in step_results if step_result_ran_lean(result))


def step_result_ran_lean(step_result: ExecStepResult) -> bool:
    """Return whether a backend step result consumed a Lean tactic attempt."""

    return step_result.status in EXECUTED_STEP_STATUSES


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
    "step_result_ran_lean",
]
