from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from lean_client.exec_models import (
    ExecCreateStatesResponse,
    ExecCreateStatesResult,
    ExecGoalInfo,
    ExecStepBatchResult,
    ExecStepResult,
    ExecVerifyResult,
)

from leanfoundry.env_backend.validation import (
    BackendReplayStep,
    BackendValidationCase,
    validate_backend_case,
)
from leanfoundry.env_backend.validation_cli import async_main
from leanfoundry.schemas import TheoremSpec


class _FakeClock:
    def __init__(self, readings: list[float]) -> None:
        self.readings = readings

    def __call__(self) -> float:
        return self.readings.pop(0)


class _FakeReplayBackend:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config
        self.connected = False
        self.closed = False
        self.step_calls: list[tuple[str, tuple[int, ...] | None, str]] = []
        self.verify_calls: list[tuple[str, str]] = []

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    async def limits(self) -> Any:
        raise NotImplementedError

    async def stats(self) -> Any:
        raise NotImplementedError

    async def cleanup(self, item_ids: list[str]) -> Any:
        raise NotImplementedError

    async def cancel(self, item_ids: list[str]) -> Any:
        raise NotImplementedError

    async def create_states(
        self,
        item_id: str,
        code: str,
        *,
        env_profile: str | None = None,
    ) -> ExecCreateStatesResponse:
        return ExecCreateStatesResponse(
            items=[
                ExecCreateStatesResult(
                    item_id=item_id,
                    status="open",
                    states=[
                        {
                            "state_token": "s0",
                            "goals": [_goal("True ∧ True")],
                        }
                    ],
                )
            ]
        )

    async def step(
        self,
        node_id: str,
        state_token: str,
        tactics: list[str],
        *,
        goal_group: tuple[int, ...] | None = None,
        timeout_ms: int | None = None,
    ) -> ExecStepBatchResult:
        tactic = tactics[0]
        self.step_calls.append((state_token, goal_group, tactic))
        if state_token == "s0" and goal_group is None:
            result = ExecStepResult(
                tactic=tactic,
                status="open",
                state_token="s1",
                goals=[_goal("True"), _goal("True")],
            )
        elif state_token == "s1" and goal_group in {(0,), (1,)}:
            result = ExecStepResult(tactic=tactic, status="complete")
        else:
            result = ExecStepResult(tactic=tactic, status="error")
        return ExecStepBatchResult(node_id=node_id, results=[result])

    async def verify_one(
        self,
        item_id: str,
        code: str,
        theorem_name: str,
        *,
        allowed_axioms: list[str] | None = None,
        env_profile: str | None = None,
    ) -> ExecVerifyResult:
        self.verify_calls.append((item_id, theorem_name))
        return ExecVerifyResult(
            item_id=item_id,
            status="accepted",
            theorem_name=theorem_name,
        )


def _goal(target: str) -> ExecGoalInfo:
    return ExecGoalInfo(target=target, pretty=f"|- {target}")


def _case(
    *,
    expected_targets: list[str] | None = None,
) -> BackendValidationCase:
    return BackendValidationCase(
        case_id="split",
        theorem=TheoremSpec(
            lean_statement="theorem split : True ∧ True := by",
            env_profile="env",
            header="",
            source="unit",
            theorem_name="split",
        ),
        replay=[
            BackendReplayStep(
                tactic="constructor",
                expected_status="open",
                expected_targets=expected_targets or ["True", "True"],
                children=[
                    BackendReplayStep(
                        tactic="trivial",
                        expected_status="complete",
                    ),
                    BackendReplayStep(
                        tactic="trivial",
                        expected_status="complete",
                    ),
                ],
            )
        ],
        final_proof_code=(
            "theorem split : True ∧ True := by\n"
            "  constructor\n"
            "  · trivial\n"
            "  · trivial\n"
        ),
    )


def test_validate_backend_case_replays_split_goal_groups() -> None:
    backend = _FakeReplayBackend()
    clock = _FakeClock(
        [
            0.0,
            0.1,
            0.4,
            0.5,
            0.7,
            0.8,
            1.0,
            1.1,
            1.3,
            1.4,
            1.9,
            2.0,
        ]
    )

    report = asyncio.run(
        validate_backend_case(
            backend,
            _case(),
            monotonic=clock,
        )
    )

    assert report.passed is True
    assert report.replayed_steps == 3
    assert report.verify_status == "accepted"
    assert report.create_latency_seconds == pytest.approx(0.3)
    assert report.replay_latency_seconds == pytest.approx(0.6)
    assert report.verify_latency_seconds == pytest.approx(0.5)
    assert report.total_latency_seconds == pytest.approx(2.0)
    assert backend.step_calls == [
        ("s0", None, "constructor"),
        ("s1", (0,), "trivial"),
        ("s1", (1,), "trivial"),
    ]
    assert backend.verify_calls == [("split:verify", "split")]


def test_validate_backend_case_reports_replay_mismatch() -> None:
    backend = _FakeReplayBackend()

    report = asyncio.run(
        validate_backend_case(
            backend,
            _case(expected_targets=["False"]),
        )
    )

    assert report.passed is False
    assert report.verify_status is None
    assert any("target mismatch" in failure for failure in report.failures)
    assert backend.verify_calls == []


def test_validation_cli_replays_jsonl_cases(
    tmp_path: Path,
    capsys,
) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(f"{_case().model_dump_json()}\n")
    backends: list[_FakeReplayBackend] = []

    def backend_factory(config: Any) -> _FakeReplayBackend:
        backend = _FakeReplayBackend(config)
        backends.append(backend)
        return backend

    exit_code = asyncio.run(
        async_main(
            [
                "--input",
                str(cases_path),
                "--api-url",
                "http://lean.local",
                "--attempt-prefix",
                "validation",
            ],
            backend_factory=backend_factory,
        )
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert captured.err == ""
    assert payload["cases_seen"] == 1
    assert payload["cases_passed"] == 1
    assert payload["cases_failed"] == 0
    assert payload["latency_seconds"]["total"] >= 0
    assert payload["latency_seconds"]["mean_per_case"] >= 0
    assert payload["latency_seconds"]["create_total"] >= 0
    assert payload["latency_seconds"]["replay_total"] >= 0
    assert payload["latency_seconds"]["verify_total"] >= 0
    assert payload["reports"][0]["case_id"] == "split"
    assert payload["reports"][0]["total_latency_seconds"] >= 0
    assert len(backends) == 1
    assert backends[0].connected
    assert backends[0].closed
    assert backends[0].config.api_url == "http://lean.local"
    assert backends[0].config.env_profile == "env"
    assert backends[0].step_calls[0] == ("s0", None, "constructor")
    assert backends[0].verify_calls == [("validation:0:split:verify", "split")]


def test_validation_cli_exits_nonzero_on_failed_report(
    tmp_path: Path,
    capsys,
) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(_case(expected_targets=["False"]).model_dump_json())

    def backend_factory(config: Any) -> _FakeReplayBackend:
        return _FakeReplayBackend(config)

    exit_code = asyncio.run(
        async_main(
            [
                "--input",
                str(cases_path),
                "--api-url",
                "http://lean.local",
                "--env-profile",
                "env",
            ],
            backend_factory=backend_factory,
        )
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["cases_seen"] == 1
    assert payload["cases_passed"] == 0
    assert payload["cases_failed"] == 1
    assert any(
        "target mismatch" in failure
        for failure in payload["reports"][0]["failures"]
    )
