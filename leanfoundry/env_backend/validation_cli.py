"""CLI for replaying backend validation cases against a live EnvBackend."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Callable, Sequence
from pathlib import Path

from leanfoundry.env_backend import EnvBackend, EnvBackendConfig
from leanfoundry.env_backend import make_env_backend
from leanfoundry.env_backend.validation import (
    BackendValidationCase,
    BackendValidationReport,
    validate_backend_case,
)


BackendFactory = Callable[[EnvBackendConfig], EnvBackend]


async def async_main(
    argv: Sequence[str] | None = None,
    *,
    backend_factory: BackendFactory = make_env_backend,
) -> int:
    """Run backend validation cases from parsed CLI arguments."""

    args = _parse_args(argv)
    cases = _load_cases(args.input)
    env_profile = _resolve_env_profile(cases, args.env_profile)
    backend = backend_factory(_env_backend_config(args, env_profile))
    reports: list[BackendValidationReport] = []

    try:
        await backend.connect()
        for index, case in enumerate(cases):
            reports.append(
                await validate_backend_case(
                    backend,
                    case,
                    attempt_id=_attempt_id(args.attempt_prefix, case, index),
                )
            )
    finally:
        await backend.close()

    print(json.dumps(_summary_payload(args.input, reports), sort_keys=True))
    if any(not report.passed for report in reports):
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entrypoint."""

    return asyncio.run(async_main(argv))


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay known tactic trajectories through /exec/create_states, "
            "/exec/step_batch, and /exec/verify."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument(
        "--env-profile",
        help=(
            "Expected env profile for every case. If omitted, the profile is "
            "derived from the input and mixed-profile inputs are rejected."
        ),
    )
    parser.add_argument("--api-key")
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--acquire-timeout-ms", type=int)
    parser.add_argument("--step-timeout-ms", type=int)
    parser.add_argument("--http-timeout-seconds", type=int, default=60)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-overloaded-retries", type=int, default=0)
    parser.add_argument("--overload-backoff-seconds", type=float, default=0.0)
    parser.add_argument(
        "--attempt-prefix",
        help="Optional prefix for backend item ids emitted during validation.",
    )
    return parser.parse_args(argv)


def _load_cases(path: Path) -> list[BackendValidationCase]:
    if path.suffix == ".jsonl":
        return _load_jsonl_cases(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        cases = [
            BackendValidationCase.model_validate(item) for item in payload
        ]
    elif isinstance(payload, dict) and "cases" in payload:
        cases = [
            BackendValidationCase.model_validate(item)
            for item in payload["cases"]
        ]
    elif isinstance(payload, dict):
        cases = [BackendValidationCase.model_validate(payload)]
    else:
        raise ValueError("validation input must be a JSON object or list")

    return _require_cases(cases, path)


def _load_jsonl_cases(path: Path) -> list[BackendValidationCase]:
    cases: list[BackendValidationCase] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            cases.append(BackendValidationCase.model_validate_json(stripped))
        except ValueError as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid validation case"
            ) from exc
    return _require_cases(cases, path)


def _require_cases(
    cases: list[BackendValidationCase],
    path: Path,
) -> list[BackendValidationCase]:
    if not cases:
        raise ValueError(f"{path} did not contain validation cases")
    return cases


def _resolve_env_profile(
    cases: list[BackendValidationCase],
    override: str | None,
) -> str:
    profiles = {case.theorem.env_profile for case in cases}
    if override is not None:
        if profiles != {override}:
            raise ValueError(
                "validation input env_profile values do not match "
                f"--env-profile={override!r}: {sorted(profiles)}"
            )
        return override
    if len(profiles) != 1:
        raise ValueError(
            "validation input must use one env_profile unless an explicit "
            f"--env-profile is supplied: {sorted(profiles)}"
        )
    return next(iter(profiles))


def _env_backend_config(
    args: argparse.Namespace,
    env_profile: str,
) -> EnvBackendConfig:
    return EnvBackendConfig(
        api_url=args.api_url,
        env_profile=env_profile,
        api_key=args.api_key,
        timeout_ms=args.timeout_ms,
        acquire_timeout_ms=args.acquire_timeout_ms,
        step_timeout_ms=args.step_timeout_ms,
        http_timeout_seconds=args.http_timeout_seconds,
        retries=args.retries,
        max_overloaded_retries=args.max_overloaded_retries,
        overload_backoff_seconds=args.overload_backoff_seconds,
    )


def _attempt_id(
    prefix: str | None,
    case: BackendValidationCase,
    index: int,
) -> str | None:
    if prefix is None:
        return None
    return f"{prefix}:{index}:{case.case_id}"


def _summary_payload(
    input_path: Path,
    reports: list[BackendValidationReport],
) -> dict[str, object]:
    passed = sum(1 for report in reports if report.passed)
    latency = _latency_summary(reports)
    return {
        "input": str(input_path),
        "cases_seen": len(reports),
        "cases_passed": passed,
        "cases_failed": len(reports) - passed,
        "latency_seconds": latency,
        "reports": [
            report.model_dump(mode="json") for report in reports
        ],
    }


def _latency_summary(
    reports: list[BackendValidationReport],
) -> dict[str, float]:
    case_count = len(reports)
    total = sum(report.total_latency_seconds for report in reports)
    create_total = sum(
        report.create_latency_seconds or 0.0 for report in reports
    )
    replay_total = sum(report.replay_latency_seconds for report in reports)
    verify_total = sum(
        report.verify_latency_seconds or 0.0 for report in reports
    )
    mean = total / case_count if case_count else 0.0
    return {
        "total": total,
        "mean_per_case": mean,
        "create_total": create_total,
        "replay_total": replay_total,
        "verify_total": verify_total,
    }


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["async_main", "main"]
