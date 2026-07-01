"""Argparse provider for LeanFoundry's Slime rollout adapter."""

from __future__ import annotations

import argparse

from leanfoundry.proofsearch import SearchAlgorithm


def add_leanfoundry_arguments(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    """Register LeanFoundry-owned arguments for Slime's parser hook.

    Slime already owns generic training, checkpoint, rollout-batch, and SGLang
    router flags. This hook registers only the ``lean_*`` and ``lf_*`` fields
    consumed by ``leanfoundry.slime.generate_rollout``.
    """

    _add_lean_backend_arguments(parser)
    _add_search_arguments(parser)
    _add_sampling_arguments(parser, prefix="lf-tactic")
    _add_sampling_arguments(parser, prefix="lf-proof")
    _add_value_arguments(parser)
    return parser


def _add_lean_backend_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lean-api-url", type=str, default=None)
    parser.add_argument("--lean-api-key", type=str, default=None)
    parser.add_argument("--lean-env-profile", type=str, default=None)
    parser.add_argument("--lean-timeout-ms", type=int, default=5000)
    parser.add_argument("--lean-acquire-timeout-ms", type=int, default=None)
    parser.add_argument("--lean-step-timeout-ms", type=int, default=None)
    parser.add_argument("--lean-http-timeout-seconds", type=int, default=60)
    parser.add_argument("--lean-retries", type=int, default=3)
    parser.add_argument("--lean-max-overloaded-retries", type=int, default=0)
    parser.add_argument(
        "--lean-overload-backoff-seconds",
        type=float,
        default=0.0,
    )


def _add_search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lf-runner-class", type=str, default=None)
    parser.add_argument("--lf-max-concurrent", type=int, default=None)
    parser.add_argument(
        "--lf-search-algorithm",
        type=str,
        choices=[algorithm.value for algorithm in SearchAlgorithm],
        default=SearchAlgorithm.PUCT_TREE.value,
    )
    parser.add_argument("--lf-max-tactic-calls", type=int, default=100)
    parser.add_argument("--lf-max-direct-candidates", type=int, default=64)
    parser.add_argument("--lf-tactics-per-expansion", type=int, default=8)
    parser.add_argument(
        "--lf-puct-exploration-weight",
        type=float,
        default=1.0,
    )
    parser.add_argument(
        "--lf-best-first-missing-value-score",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--lf-direct-candidates-per-round",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--lf-censored-negative-weight",
        type=float,
        default=0.25,
    )
    parser.add_argument(
        "--lf-min-censored-negative-effort",
        type=int,
        default=50,
    )
    _add_boolean_argument(parser, "--lf-try-negation", default=False)
    _add_boolean_argument(
        parser,
        "--lf-allow-mixed-env-profiles",
        default=False,
    )
    _add_boolean_argument(
        parser,
        "--lf-include-failed-self-correct-negatives",
        default=False,
    )
    _add_boolean_argument(
        parser,
        "--lf-include-tree-whole-proof-rows",
        default=False,
    )


def _add_sampling_arguments(
    parser: argparse.ArgumentParser,
    *,
    prefix: str,
) -> None:
    parser.add_argument(f"--{prefix}-temperature", type=float, default=None)
    parser.add_argument(f"--{prefix}-top-p", type=float, default=None)
    parser.add_argument(f"--{prefix}-top-k", type=int, default=None)
    parser.add_argument(f"--{prefix}-min-p", type=float, default=None)
    parser.add_argument(f"--{prefix}-max-new-tokens", type=int, default=None)
    parser.add_argument(f"--{prefix}-max-tokens", type=int, default=None)
    parser.add_argument(f"--{prefix}-regex", type=str, default=None)
    parser.add_argument(f"--{prefix}-stop", type=str, default=None)
    parser.add_argument(f"--{prefix}-stop-token-ids", type=str, default=None)
    parser.add_argument(f"--{prefix}-logit-bias", type=str, default=None)
    parser.add_argument(
        f"--{prefix}-extra-sampling-params",
        type=str,
        default=None,
    )


def _add_value_arguments(parser: argparse.ArgumentParser) -> None:
    _add_boolean_argument(parser, "--lf-use-value-client", default=False)
    parser.add_argument(
        "--lf-value-mode",
        type=str,
        choices=["bonded", "unbonded"],
        default="unbonded",
    )
    parser.add_argument("--lf-value-base-url", type=str, default=None)
    parser.add_argument(
        "--lf-value-generate-path",
        type=str,
        default="/generate",
    )
    parser.add_argument(
        "--lf-value-output-mode",
        type=str,
        choices=["numeric_head", "natural_language"],
        default="natural_language",
    )
    parser.add_argument("--lf-value-budget-tokens", type=int, default=256)


def _add_boolean_argument(
    parser: argparse.ArgumentParser,
    name: str,
    *,
    default: bool,
) -> None:
    parser.add_argument(
        name,
        action=argparse.BooleanOptionalAction,
        default=default,
    )


__all__ = ["add_leanfoundry_arguments"]
