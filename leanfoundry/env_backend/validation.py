"""Validation harness for replaying known tactic trajectories."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from lean_client.exec_models import ExecGoalInfo, ExecStateInfo
from pydantic import Field

from leanfoundry.env_backend.base import EnvBackend
from leanfoundry.proofsearch._common import verifier_feedback
from leanfoundry.proofsearch._expansion import (
    goal_info_to_component,
    proof_states_from_goals,
)
from leanfoundry.proofsearch._tree_init import initial_code_for_theorem
from leanfoundry.schemas import FactorizedProofState, TheoremSpec
from leanfoundry.schemas._base import LeanFoundryModel


StepStatus = Literal[
    "open",
    "complete",
    "error",
    "invalid_state_token",
    "overloaded",
    "cancelled",
]
VerifyStatus = Literal[
    "accepted",
    "rejected",
    "error",
    "overloaded",
    "cancelled",
]


class BackendReplayStep(LeanFoundryModel):
    """One expected tactic step in a backend replay trajectory."""

    tactic: str = Field(description="Tactic to replay at this proof state.")
    expected_status: StepStatus | None = Field(
        default=None,
        description="Expected backend step status, if the fixture asserts it.",
    )
    expected_targets: list[str] | None = Field(
        default=None,
        description="Expected post-step goal targets, in backend order.",
    )
    children: list["BackendReplayStep"] = Field(
        default_factory=list,
        description=(
            "Replay steps for the focused child states produced by this "
            "tactic. Child order follows LeanFoundry's goal-coupling split."
        ),
    )


class BackendValidationCase(LeanFoundryModel):
    """A known theorem trajectory used to validate an EnvBackend."""

    case_id: str = Field(description="Stable id for diagnostics.")
    theorem: TheoremSpec = Field(description="The theorem to initialize.")
    replay: list[BackendReplayStep] = Field(
        default_factory=list,
        description="Replay roots, one per initial backend proof state.",
    )
    final_proof_code: str = Field(
        min_length=1,
        description="Complete Lean proof code sent to /exec/verify.",
    )
    theorem_name: str | None = Field(
        default=None,
        description=(
            "The theorem name for /exec/verify. Defaults to "
            "theorem.theorem_name."
        ),
    )
    expected_verify_status: VerifyStatus = Field(
        default="accepted",
        description="Expected final /exec/verify status.",
    )


class BackendValidationReport(LeanFoundryModel):
    """Result of replaying one backend validation case."""

    case_id: str
    passed: bool
    create_status: StepStatus | None = None
    replayed_steps: int = 0
    verify_status: VerifyStatus | None = None
    create_latency_seconds: float | None = Field(default=None, ge=0)
    replay_latency_seconds: float = Field(default=0.0, ge=0)
    verify_latency_seconds: float | None = Field(default=None, ge=0)
    total_latency_seconds: float = Field(default=0.0, ge=0)
    failures: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _ReplayState:
    state_token: str
    goals: list[ExecGoalInfo]
    focus: tuple[int, ...] | None = None


@dataclass(slots=True)
class _ReplayCounter:
    step_count: int = 0
    step_latency_seconds: float = 0.0


async def validate_backend_case(
    env_backend: EnvBackend,
    case: BackendValidationCase,
    *,
    attempt_id: str | None = None,
    monotonic: Callable[[], float] | None = None,
) -> BackendValidationReport:
    """Replay one known trajectory and verify the final proof artifact."""

    clock = monotonic or time.perf_counter
    started_at = clock()
    item_id = attempt_id or case.case_id
    failures: list[str] = []
    create_started_at = clock()
    create_response = await env_backend.create_states(
        f"{item_id}:create",
        initial_code_for_theorem(case.theorem),
        env_profile=case.theorem.env_profile,
    )
    create_latency_seconds = _elapsed_seconds(clock, create_started_at)
    if len(create_response.items) != 1:
        return _report(
            case,
            create_latency_seconds=create_latency_seconds,
            total_latency_seconds=_elapsed_seconds(clock, started_at),
            failures=[
                "create_states returned "
                f"{len(create_response.items)} items; expected 1"
            ],
        )
    create_item = create_response.items[0]
    create_status = create_item.status
    if create_status not in {"open", "complete"}:
        return _report(
            case,
            create_status=create_status,
            create_latency_seconds=create_latency_seconds,
            total_latency_seconds=_elapsed_seconds(clock, started_at),
            failures=[
                "create_states failed: "
                f"{verifier_feedback(create_status, create_item.messages)}"
            ],
        )

    if len(create_item.states) != len(case.replay):
        failures.append(
            "initial state count mismatch: "
            f"expected {len(case.replay)}, got {len(create_item.states)}"
        )
    counter = _ReplayCounter()
    for state_info, replay in zip(create_item.states, case.replay):
        await _replay_step(
            env_backend,
            case=case,
            item_id=item_id,
            replay_state=_state_info_to_replay_state(state_info),
            replay_step=replay,
            counter=counter,
            failures=failures,
            monotonic=clock,
        )

    verify_status: VerifyStatus | None = None
    verify_latency_seconds: float | None = None
    if not failures:
        theorem_name = case.theorem_name or case.theorem.theorem_name
        if theorem_name is None:
            failures.append("theorem_name is required for /exec/verify")
        else:
            verify_started_at = clock()
            verify_result = await env_backend.verify_one(
                f"{item_id}:verify",
                case.final_proof_code,
                theorem_name,
                allowed_axioms=case.theorem.allowed_axioms,
                env_profile=case.theorem.env_profile,
            )
            verify_latency_seconds = _elapsed_seconds(
                clock,
                verify_started_at,
            )
            verify_status = verify_result.status
            if verify_status != case.expected_verify_status:
                failures.append(
                    "verify status mismatch: expected "
                    f"{case.expected_verify_status}, got {verify_status}"
                )

    return _report(
        case,
        create_status=create_status,
        replayed_steps=counter.step_count,
        verify_status=verify_status,
        create_latency_seconds=create_latency_seconds,
        replay_latency_seconds=counter.step_latency_seconds,
        verify_latency_seconds=verify_latency_seconds,
        total_latency_seconds=_elapsed_seconds(clock, started_at),
        failures=failures,
    )


async def _replay_step(
    env_backend: EnvBackend,
    *,
    case: BackendValidationCase,
    item_id: str,
    replay_state: _ReplayState,
    replay_step: BackendReplayStep,
    counter: _ReplayCounter,
    failures: list[str],
    monotonic: Callable[[], float],
) -> None:
    counter.step_count += 1
    node_id = f"{item_id}:step:{counter.step_count}"
    step_started_at = monotonic()
    result_batch = await env_backend.step(
        node_id,
        replay_state.state_token,
        [replay_step.tactic],
        goal_group=replay_state.focus,
    )
    counter.step_latency_seconds += _elapsed_seconds(
        monotonic,
        step_started_at,
    )
    if len(result_batch.results) != 1:
        failures.append(
            f"{node_id}: step returned {len(result_batch.results)} "
            "results; expected 1"
        )
        return

    result = result_batch.results[0]
    if result.tactic != replay_step.tactic:
        failures.append(
            f"{node_id}: tactic echo mismatch: expected "
            f"{replay_step.tactic!r}, got {result.tactic!r}"
        )
    if (
        replay_step.expected_status is not None
        and result.status != replay_step.expected_status
    ):
        failures.append(
            f"{node_id}: status mismatch: expected "
            f"{replay_step.expected_status}, got {result.status}"
        )
    if replay_step.expected_targets is not None:
        actual_targets = [goal.target for goal in result.goals]
        if actual_targets != replay_step.expected_targets:
            failures.append(
                f"{node_id}: target mismatch: expected "
                f"{replay_step.expected_targets}, got {actual_targets}"
            )

    if result.status == "complete":
        if replay_step.children:
            failures.append(f"{node_id}: complete step has replay children")
        return
    if result.status != "open":
        if replay_step.children:
            failures.append(
                f"{node_id}: non-open status {result.status} "
                "cannot replay children"
            )
        return
    if result.state_token is None:
        failures.append(f"{node_id}: open step did not return a state_token")
        return

    child_states = _child_replay_states(
        case.theorem,
        replay_state,
        state_token=result.state_token,
        goals=result.goals,
    )
    if len(child_states) != len(replay_step.children):
        failures.append(
            f"{node_id}: child count mismatch: expected "
            f"{len(replay_step.children)}, got {len(child_states)}"
        )
        return
    for child_state, child_step in zip(child_states, replay_step.children):
        await _replay_step(
            env_backend,
            case=case,
            item_id=item_id,
            replay_state=child_state,
            replay_step=child_step,
            counter=counter,
            failures=failures,
            monotonic=monotonic,
        )


def _state_info_to_replay_state(state_info: ExecStateInfo) -> _ReplayState:
    return _ReplayState(
        state_token=state_info.state_token,
        goals=state_info.goals,
    )


def _child_replay_states(
    theorem: TheoremSpec,
    parent: _ReplayState,
    *,
    state_token: str,
    goals: list[ExecGoalInfo],
) -> list[_ReplayState]:
    parent_state = FactorizedProofState(
        env_profile=theorem.env_profile,
        goal_components=[
            goal_info_to_component(goal_info) for goal_info in parent.goals
        ],
        pretty_state="\n\n".join(goal.pretty for goal in parent.goals),
        state_token=parent.state_token,
    )
    return [
        _ReplayState(
            state_token=child.state.state_token or state_token,
            goals=goals_for_targets(goals, child.focus),
            focus=child.focus,
        )
        for child in proof_states_from_goals(
            parent_state,
            state_token=state_token,
            goals=goals,
        )
    ]


def goals_for_targets(
    goals: list[ExecGoalInfo],
    focus: tuple[int, ...] | None,
) -> list[ExecGoalInfo]:
    """Return the backend goals visible to a replay child."""

    if focus is None:
        return list(goals)
    return [goals[index] for index in focus]


def _report(
    case: BackendValidationCase,
    *,
    create_status: StepStatus | None = None,
    replayed_steps: int = 0,
    verify_status: VerifyStatus | None = None,
    create_latency_seconds: float | None = None,
    replay_latency_seconds: float = 0.0,
    verify_latency_seconds: float | None = None,
    total_latency_seconds: float = 0.0,
    failures: list[str] | None = None,
) -> BackendValidationReport:
    actual_failures = list(failures or [])
    return BackendValidationReport(
        case_id=case.case_id,
        passed=not actual_failures,
        create_status=create_status,
        replayed_steps=replayed_steps,
        verify_status=verify_status,
        create_latency_seconds=create_latency_seconds,
        replay_latency_seconds=replay_latency_seconds,
        verify_latency_seconds=verify_latency_seconds,
        total_latency_seconds=total_latency_seconds,
        failures=actual_failures,
    )


def _elapsed_seconds(
    monotonic: Callable[[], float],
    started_at: float,
) -> float:
    return max(0.0, monotonic() - started_at)


__all__ = [
    "BackendReplayStep",
    "BackendValidationCase",
    "BackendValidationReport",
    "validate_backend_case",
]
