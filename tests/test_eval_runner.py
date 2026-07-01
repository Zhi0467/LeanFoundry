from __future__ import annotations

import asyncio

import pytest

from leanfoundry.env_backend import EnvBackendConfig
from leanfoundry.env_profiles import header_hash
from leanfoundry.evals import FixedModelEvalRunner
from leanfoundry.proofsearch import SearchAlgorithm, SearchConfig
from leanfoundry.proofsearch import SearchResult, SearchStatus
from leanfoundry.schemas import (
    BenchmarkCompatibility,
    BenchmarkManifest,
    DirectVerificationAttempt,
    EnvProfile,
    EvalMode,
    TheoremSpec,
    TrainingArtifacts,
)


class FakeEnvBackend:
    def __init__(self, env_profile: str = "env") -> None:
        self.config = EnvBackendConfig(
            api_url="http://lean",
            env_profile=env_profile,
        )


class FakePolicy:
    pass


def _theorem(identifier: str = "t") -> TheoremSpec:
    return TheoremSpec(
        id=identifier,
        theorem_name=identifier,
        lean_statement=f"theorem {identifier} : True := by",
        env_profile="env",
        header="import Mathlib",
        source="unit",
    )


def _benchmark_manifest() -> BenchmarkManifest:
    return BenchmarkManifest(
        id="toy-valid-v1",
        name="toy",
        split="valid",
        source="file://toy.jsonl",
        env_profile="env",
        compatibility=BenchmarkCompatibility.COMPATIBLE,
        contamination_policy="eval-only",
        fixed_assignment_id="toy-valid-fixed",
        benchmark_commit="bench-sha",
        theorem_count=1,
    )


def _profile(header: str = "import Mathlib") -> EnvProfile:
    return EnvProfile(
        lean_version="4.29.1",
        mathlib_commit="5e932f97",
        header=header,
        header_hash=header_hash(header),
    )


def test_fixed_eval_runner_reports_pass_at_k(monkeypatch) -> None:
    captured = {}

    async def fake_run_search_batch(theorems, **kwargs):
        captured["config"] = kwargs["config"]
        return [
            SearchResult(
                status=SearchStatus.PROVED,
                diagnostics={"verify_attempts": 4},
                search_budget_used=4,
                training_artifacts=TrainingArtifacts(
                    direct_verification_attempts=[
                        DirectVerificationAttempt(
                            candidate_index=1,
                            proof="bad",
                            verifier_status="rejected",
                            verifier_feedback="rejected",
                            verify_item_id="verify:1",
                        ),
                        DirectVerificationAttempt(
                            candidate_index=2,
                            proof="good",
                            verifier_status="accepted",
                            verify_item_id="verify:2",
                            accepted=True,
                        ),
                        DirectVerificationAttempt(
                            candidate_index=3,
                            proof="also bad",
                            verifier_status="rejected",
                            verifier_feedback="rejected",
                            verify_item_id="verify:3",
                        ),
                        DirectVerificationAttempt(
                            candidate_index=4,
                            proof="still bad",
                            verifier_status="rejected",
                            verifier_feedback="rejected",
                            verify_item_id="verify:4",
                        ),
                    ]
                ),
            ),
            SearchResult(
                status=SearchStatus.EXHAUSTED,
                diagnostics={"verify_attempts": 4},
                search_budget_used=4,
            ),
        ]

    monkeypatch.setattr(
        "leanfoundry.evals.runner.run_search_batch",
        fake_run_search_batch,
    )
    runner = FixedModelEvalRunner(
        run_id="eval-1",
        infra_git_sha="sha",
        model_checkpoint="ckpt",
        benchmark_name="toy",
        k_values=(1, 2, 4),
    )

    manifest = asyncio.run(
        runner.run(
            benchmark=[_theorem("a"), _theorem("b")],
            policy_client=FakePolicy(),
            env_backend=FakeEnvBackend(),
            search_config=SearchConfig(algorithm=SearchAlgorithm.DIRECT),
        )
    )

    assert manifest.mode is EvalMode.DIRECT
    assert manifest.k_values == [1, 2, 4]
    assert captured["config"].max_direct_candidates == 4
    assert manifest.metrics["pass_at_1"] == 0.0
    assert manifest.metrics["pass_at_2"] == 0.5
    assert manifest.metrics["pass_at_4"] == 0.5
    assert manifest.metrics["direct_verification_attempts"] == 4
    assert manifest.metrics["status_proved"] == 1
    assert manifest.metrics["status_exhausted"] == 1


def test_fixed_eval_runner_reports_self_correct_pass_at_k(monkeypatch) -> None:
    captured = {}

    async def fake_run_search_batch(theorems, **kwargs):
        captured["config"] = kwargs["config"]
        return [
            SearchResult(
                status=SearchStatus.PROVED,
                search_budget_used=3,
                training_artifacts=TrainingArtifacts(
                    direct_verification_attempts=[
                        DirectVerificationAttempt(
                            candidate_index=1,
                            proof="bad",
                            verifier_status="rejected",
                            verifier_feedback="rejected",
                            verify_item_id="verify:1",
                        ),
                        DirectVerificationAttempt(
                            candidate_index=2,
                            proof="still bad",
                            verifier_status="rejected",
                            verifier_feedback="rejected",
                            verify_item_id="verify:2",
                        ),
                        DirectVerificationAttempt(
                            candidate_index=3,
                            proof="good",
                            verifier_status="accepted",
                            verify_item_id="verify:3",
                            accepted=True,
                        ),
                    ]
                ),
            ),
            SearchResult(
                status=SearchStatus.EXHAUSTED,
                search_budget_used=3,
                training_artifacts=TrainingArtifacts(
                    direct_verification_attempts=[
                        DirectVerificationAttempt(
                            candidate_index=1,
                            proof="bad",
                            verifier_status="rejected",
                            verifier_feedback="rejected",
                            verify_item_id="other:1",
                        )
                    ]
                ),
            ),
        ]

    monkeypatch.setattr(
        "leanfoundry.evals.runner.run_search_batch",
        fake_run_search_batch,
    )
    runner = FixedModelEvalRunner(
        run_id="eval-1",
        infra_git_sha="sha",
        model_checkpoint="ckpt",
        benchmark_name="toy",
        k_values=(1, 2, 3),
    )

    manifest = asyncio.run(
        runner.run(
            benchmark=[_theorem("a"), _theorem("b")],
            policy_client=FakePolicy(),
            env_backend=FakeEnvBackend(),
            search_config=SearchConfig(
                algorithm=SearchAlgorithm.SELF_CORRECT,
            ),
        )
    )

    assert manifest.mode is EvalMode.SELF_CORRECT
    assert manifest.k_values == [1, 2, 3]
    assert captured["config"].max_direct_candidates == 3
    assert manifest.metrics["pass_at_1"] == 0.0
    assert manifest.metrics["pass_at_2"] == 0.0
    assert manifest.metrics["pass_at_3"] == 0.5
    assert manifest.metrics["direct_verification_attempts"] == 4


@pytest.mark.parametrize(
    "algorithm",
    [
        SearchAlgorithm.PUCT_TREE,
        SearchAlgorithm.BEST_FIRST,
        SearchAlgorithm.AND_OR_TREE,
    ],
)
def test_fixed_eval_runner_reports_solved_at_budget(
    monkeypatch,
    algorithm: SearchAlgorithm,
) -> None:
    async def fake_run_search_batch(theorems, **kwargs):
        return [
            SearchResult(status=SearchStatus.PROVED),
            SearchResult(status=SearchStatus.ERROR),
        ]

    monkeypatch.setattr(
        "leanfoundry.evals.runner.run_search_batch",
        fake_run_search_batch,
    )
    runner = FixedModelEvalRunner(
        run_id="eval-1",
        infra_git_sha="sha",
        model_checkpoint="ckpt",
        benchmark_name="toy",
    )

    manifest = asyncio.run(
        runner.run(
            benchmark=[_theorem("a"), _theorem("b")],
            policy_client=FakePolicy(),
            env_backend=FakeEnvBackend(),
            search_config=SearchConfig(
                algorithm=algorithm,
                max_tactic_calls=250,
            ),
        )
    )

    assert manifest.mode is EvalMode.STATE_TOKEN_SEARCH
    assert manifest.solved_at_budget == {250: 0.5}
    assert manifest.metrics["proved_rate"] == 0.5


def test_fixed_eval_runner_rejects_mismatched_env_profile() -> None:
    runner = FixedModelEvalRunner(
        run_id="eval-1",
        infra_git_sha="sha",
        model_checkpoint="ckpt",
        benchmark_name="toy",
    )

    with pytest.raises(ValueError, match="backend"):
        asyncio.run(
            runner.run(
                benchmark=[_theorem("a")],
                policy_client=FakePolicy(),
                env_backend=FakeEnvBackend(env_profile="other-env"),
                search_config=SearchConfig(),
            )
        )


def test_fixed_eval_runner_validates_env_profile_registry() -> None:
    runner = FixedModelEvalRunner(
        run_id="eval-1",
        infra_git_sha="sha",
        model_checkpoint="ckpt",
        benchmark_name="toy",
    )

    with pytest.raises(ValueError, match="header"):
        asyncio.run(
            runner.run(
                benchmark=[_theorem("a")],
                policy_client=FakePolicy(),
                env_backend=FakeEnvBackend(),
                search_config=SearchConfig(),
                env_profiles={
                    "env": _profile("import Mathlib.Data.Nat.Basic")
                },
            )
        )


def test_fixed_eval_runner_writes_manifest_backed_artifacts(
    monkeypatch,
    tmp_path,
) -> None:
    async def fake_run_search_batch(theorems, **kwargs):
        return [SearchResult(status=SearchStatus.PROVED)]

    monkeypatch.setattr(
        "leanfoundry.evals.runner.run_search_batch",
        fake_run_search_batch,
    )
    runner = FixedModelEvalRunner(
        run_id="eval-1",
        infra_git_sha="sha",
        model_checkpoint="ckpt",
        benchmark_name="unused",
    )

    manifest = asyncio.run(
        runner.run(
            benchmark=[_theorem("a")],
            policy_client=FakePolicy(),
            env_backend=FakeEnvBackend(),
            search_config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=25,
            ),
            benchmark_manifest=_benchmark_manifest(),
            artifact_dir=tmp_path,
        )
    )

    assert manifest.benchmark == "toy:valid"
    assert manifest.benchmark_commit == "bench-sha"
    assert manifest.metrics["artifact_dir"] == str(tmp_path)
    assert "results_sha256" in manifest.metrics
    assert (tmp_path / "eval_manifest.json").exists()
    assert (tmp_path / "results.jsonl").exists()
    assert (tmp_path / "benchmark.jsonl").exists()
    assert (tmp_path / "report.md").exists()
