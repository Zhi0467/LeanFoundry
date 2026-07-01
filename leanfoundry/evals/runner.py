"""Concrete fixed-model evaluation runner."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from leanfoundry.env_backend import EnvBackend
from leanfoundry.env_profiles import validate_theorem_batch_env_profiles
from leanfoundry.evals.io import (
    validate_benchmark_theorems,
    write_eval_artifacts,
)
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.proofsearch import (
    SearchAlgorithm,
    SearchConfig,
    SearchResult,
    SearchStatus,
    run_search_batch,
)
from leanfoundry.schemas import (
    BenchmarkManifest,
    EnvProfile,
    EvalArtifactManifest,
    EvalMode,
    TheoremSpec,
)


@dataclass(frozen=True, slots=True)
class FixedModelEvalRunner:
    """Run one fixed benchmark against one fixed model/search config."""

    run_id: str
    infra_git_sha: str
    model_checkpoint: str
    benchmark_name: str
    benchmark_commit: str | None = None
    training_git_sha: str | None = None
    max_concurrent: int | None = None
    k_values: tuple[int, ...] = (1, 2, 4, 8, 16, 32)

    async def run(
        self,
        *,
        benchmark: Sequence[TheoremSpec],
        policy_client: PolicyClient,
        env_backend: EnvBackend,
        search_config: SearchConfig,
        value_client: ValueClient | None = None,
        benchmark_manifest: BenchmarkManifest | None = None,
        env_profiles: Mapping[str, EnvProfile] | None = None,
        artifact_dir: str | Path | None = None,
    ) -> EvalArtifactManifest:
        """Run eval and return a reproducible manifest."""

        theorems = list(benchmark)
        if benchmark_manifest is not None:
            validate_benchmark_theorems(
                theorems,
                benchmark_manifest,
                profiles=env_profiles,
            )
        backend_profile = getattr(
            getattr(env_backend, "config", None),
            "env_profile",
            None,
        )
        validate_theorem_batch_env_profiles(
            theorems,
            profiles=env_profiles,
            backend_env_profile=backend_profile,
        )
        config = _eval_search_config(search_config, self.k_values)
        started = time.perf_counter()
        results = await run_search_batch(
            theorems,
            policy_client=policy_client,
            value_client=value_client,
            env_backend=env_backend,
            config=config,
            max_concurrent=self.max_concurrent,
        )
        elapsed_seconds = time.perf_counter() - started
        manifest = self._manifest(
            results,
            theorems,
            config,
            elapsed_seconds=elapsed_seconds,
            benchmark_manifest=benchmark_manifest,
        )
        if artifact_dir is not None:
            manifest = manifest.model_copy(
                update={
                    "metrics": {
                        **manifest.metrics,
                        "artifact_dir": str(Path(artifact_dir)),
                    }
                }
            )
            paths = write_eval_artifacts(
                artifact_dir,
                manifest=manifest,
                results=results,
                theorems=theorems,
            )
            manifest = manifest.model_copy(
                update={"metrics": {**manifest.metrics, **paths.hashes}}
            )
        return manifest

    def _manifest(
        self,
        results: list[SearchResult],
        theorems: list[TheoremSpec],
        config: SearchConfig,
        *,
        elapsed_seconds: float,
        benchmark_manifest: BenchmarkManifest | None = None,
    ) -> EvalArtifactManifest:
        env_profile = theorems[0].env_profile if theorems else "unknown"
        benchmark_name = self.benchmark_name
        benchmark_commit = self.benchmark_commit
        if benchmark_manifest is not None:
            env_profile = benchmark_manifest.env_profile
            benchmark_name = (
                f"{benchmark_manifest.name}:{benchmark_manifest.split}"
            )
            benchmark_commit = benchmark_manifest.benchmark_commit
        mode = _eval_mode(config.algorithm)
        metrics = _result_metrics(results, elapsed_seconds=elapsed_seconds)
        k_values: list[int] = []
        solved_at_budget: dict[int, float] = {}
        if mode in {EvalMode.DIRECT, EvalMode.SELF_CORRECT}:
            k_values = [
                k for k in self.k_values if k <= config.max_direct_candidates
            ]
            metrics.update(_pass_at_k_metrics(results, k_values))
        else:
            solved_at_budget = {
                config.max_tactic_calls: _proved_rate(results)
            }
        return EvalArtifactManifest(
            run_id=self.run_id,
            infra_git_sha=self.infra_git_sha,
            training_git_sha=self.training_git_sha,
            model_checkpoint=self.model_checkpoint,
            env_profile=env_profile,
            benchmark=benchmark_name,
            benchmark_commit=benchmark_commit,
            mode=mode,
            k_values=k_values,
            solved_at_budget=solved_at_budget,
            sampling=None,
            metrics=metrics,
        )


def _eval_search_config(
    config: SearchConfig,
    k_values: tuple[int, ...],
) -> SearchConfig:
    if config.algorithm not in {
        SearchAlgorithm.DIRECT,
        SearchAlgorithm.SELF_CORRECT,
    }:
        return config
    max_k = max(k_values) if k_values else config.max_direct_candidates
    return config.model_copy(update={"max_direct_candidates": max_k})


def _eval_mode(algorithm: SearchAlgorithm) -> EvalMode:
    if algorithm is SearchAlgorithm.DIRECT:
        return EvalMode.DIRECT
    if algorithm is SearchAlgorithm.SELF_CORRECT:
        return EvalMode.SELF_CORRECT
    return EvalMode.STATE_TOKEN_SEARCH


def _result_metrics(
    results: list[SearchResult],
    *,
    elapsed_seconds: float,
) -> dict[str, float | int | str]:
    metrics: dict[str, float | int | str] = {
        "theorem_count": len(results),
        "elapsed_seconds": elapsed_seconds,
        "theorems_per_second": (
            len(results) / elapsed_seconds if elapsed_seconds > 0 else 0.0
        ),
    }
    for status in SearchStatus:
        metrics[f"status_{status.value}"] = sum(
            1 for result in results if result.status is status
        )
    direct_attempt_count = sum(
        len(result.training_artifacts.direct_verification_attempts)
        for result in results
        if result.training_artifacts is not None
    )
    if direct_attempt_count:
        metrics["direct_verification_attempts"] = direct_attempt_count
    metrics["proved_rate"] = _proved_rate(results)
    return metrics


def _pass_at_k_metrics(
    results: list[SearchResult],
    k_values: list[int],
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for k in k_values:
        if not results:
            metrics[f"pass_at_{k}"] = 0.0
            continue
        successes = sum(1 for result in results if _proved_by_k(result, k))
        metrics[f"pass_at_{k}"] = successes / len(results)
    return metrics


def _proved_by_k(result: SearchResult, k: int) -> bool:
    if result.status is not SearchStatus.PROVED:
        return False
    if result.training_artifacts is not None:
        direct_attempts = (
            result.training_artifacts.direct_verification_attempts
        )
        if direct_attempts:
            return any(
                attempt.accepted and attempt.candidate_index <= k
                for attempt in direct_attempts
            )
    attempts = result.diagnostics.get("verify_attempts")
    if isinstance(attempts, int | float):
        return int(attempts) <= k
    return result.search_budget_used <= k


def _proved_rate(results: list[SearchResult]) -> float:
    if not results:
        return 0.0
    return (
        sum(1 for result in results if result.status is SearchStatus.PROVED)
        / len(results)
    )


__all__ = ["FixedModelEvalRunner"]
