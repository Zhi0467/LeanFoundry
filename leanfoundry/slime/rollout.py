"""Slime rollout entrypoint for LeanFoundry proof search."""

from __future__ import annotations

import asyncio
import importlib
from typing import Any

from slime.rollout.base_types import RolloutFnEvalOutput, RolloutFnTrainOutput

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.proofsearch import SearchAlgorithm, SearchConfig
from leanfoundry.proofsearch import run_search_batch
from leanfoundry.proofsearch.to_rows import TrainingRow, to_training_rows
from leanfoundry.schemas import TheoremSpec
from leanfoundry.slime.runner import SlimeRolloutRunner


_RUNNER: SlimeRolloutRunner | None = None
_ENV: EnvBackend | None = None
_POLICY: PolicyClient | None = None
_VALUE: ValueClient | None = None
_VALUE_BUILT = False


def generate_rollout(
    args: Any,
    rollout_id: int,
    data_source: Any,
    evaluation: bool = False,
) -> RolloutFnTrainOutput | RolloutFnEvalOutput:
    """Synchronous entrypoint loaded by Slime."""

    return _run(
        async_generate_rollout(
            args,
            rollout_id,
            data_source,
            evaluation=evaluation,
        )
    )


async def async_generate_rollout(
    args: Any,
    rollout_id: int,
    data_source: Any,
    evaluation: bool = False,
) -> RolloutFnTrainOutput | RolloutFnEvalOutput:
    """Async implementation for tests and advanced callers."""

    runner, env, policy, value = await _resources(args)
    source_samples = runner.source_samples(data_source, args)
    theorems = runner.theorems_from_source(source_samples, args)
    runner.validate_env_profiles(theorems, args)
    config = runner.search_config(args)
    results = await run_search_batch(
        theorems,
        policy_client=policy,
        value_client=value,
        env_backend=env,
        config=config,
        max_concurrent=getattr(args, "lf_max_concurrent", None),
        replay_store=getattr(args, "replay_store", None),
        model_version=rollout_id,
    )
    rows = _rows_from_results(
        results,
        theorems,
        include_whole_proofs=_include_whole_proof_rows(args, config),
        include_failed_self_correct_negatives=getattr(
            args,
            "lf_include_failed_self_correct_negatives",
            False,
        ),
    )
    metrics = _metrics(results, rows)
    if evaluation:
        return RolloutFnEvalOutput(
            data=_eval_data(results, theorems),
            metrics=metrics,
        )
    return RolloutFnTrainOutput(
        samples=runner.to_samples(rows, rollout_id, args),
        metrics=metrics,
    )


async def _resources(
    args: Any,
) -> tuple[
    SlimeRolloutRunner,
    EnvBackend,
    PolicyClient,
    ValueClient | None,
]:
    global _ENV, _POLICY, _RUNNER, _VALUE, _VALUE_BUILT
    if _RUNNER is None:
        _RUNNER = _build_runner(args)
    if _ENV is None:
        _ENV = _RUNNER.build_env_backend(args)
        await _ENV.connect()
    if _POLICY is None:
        _POLICY = _RUNNER.build_policy_client(args)
    if not _VALUE_BUILT:
        _VALUE = _RUNNER.build_value_client(args)
        _VALUE_BUILT = True
    return _RUNNER, _ENV, _POLICY, _VALUE


def _build_runner(args: Any) -> SlimeRolloutRunner:
    runner_class_path = getattr(args, "lf_runner_class", None)
    if runner_class_path is None:
        return SlimeRolloutRunner()
    module_name, _, class_name = runner_class_path.rpartition(".")
    if not module_name or not class_name:
        raise ValueError("lf_runner_class must be a full import path")
    module = importlib.import_module(module_name)
    runner_class = getattr(module, class_name)
    runner = runner_class()
    if not isinstance(runner, SlimeRolloutRunner):
        raise TypeError("lf_runner_class must subclass SlimeRolloutRunner")
    return runner


def _rows_from_results(
    results: list[Any],
    theorems: list[TheoremSpec],
    *,
    include_whole_proofs: bool = True,
    include_failed_self_correct_negatives: bool = False,
) -> list[TrainingRow]:
    rows: list[TrainingRow] = []
    for result, theorem in zip(results, theorems, strict=True):
        rows.extend(
            to_training_rows(
                result,
                theorem,
                include_whole_proofs=include_whole_proofs,
                include_failed_self_correct_negatives=(
                    include_failed_self_correct_negatives
                ),
            )
        )
    return rows


def _include_whole_proof_rows(args: Any, config: SearchConfig) -> bool:
    if getattr(args, "lf_include_tree_whole_proof_rows", False):
        return True
    return config.algorithm in {
        SearchAlgorithm.DIRECT,
        SearchAlgorithm.SELF_CORRECT,
    }


def _metrics(results: list[Any], rows: list[TrainingRow]) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "lf_results": len(results),
        "lf_rows": len(rows),
    }
    for row in rows:
        key = f"lf_rows_{row.kind}"
        metrics[key] = int(metrics.get(key, 0)) + 1
    for result in results:
        key = f"lf_status_{result.status.value}"
        metrics[key] = int(metrics.get(key, 0)) + 1
    return metrics


def _eval_data(
    results: list[Any],
    theorems: list[TheoremSpec],
) -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = {}
    for result, theorem in zip(results, theorems, strict=True):
        key = theorem.id or theorem.theorem_name or result.attempt_id
        if key is None:
            key = theorem.lean_statement
        data[key] = {
            "status": result.status.value,
            "search_budget_used": result.search_budget_used,
            "diagnostics": result.diagnostics,
        }
    return data


def _run(awaitable: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError(
        "generate_rollout cannot run inside an existing event loop; "
        "call async_generate_rollout instead"
    )


__all__ = ["async_generate_rollout", "generate_rollout"]
