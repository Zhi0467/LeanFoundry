"""Opt-in live Slime/SGLang/Lean rollout smoke test.

This test exercises the real ``leanfoundry.slime.generate_rollout`` path with
the pinned Slime package, a live SGLang router, and a live Kimina Lean backend.
It is intentionally not part of the default hermetic suite. Enable with::

    LEANFOUNDRY_SLIME_E2E=1 \\
    LEANFOUNDRY_SLIME_E2E_LEAN_API_URL=http://localhost:8000 \\
    LEANFOUNDRY_SLIME_E2E_ENV_PROFILE=lean4.29.1_mathlib_... \\
    LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_IP=127.0.0.1 \\
    LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_PORT=30000 \\
    LEANFOUNDRY_SLIME_E2E_HF_CHECKPOINT=/path/to/checkpoint \\
    LEANFOUNDRY_SLIME_E2E_MODES=direct,puct_tree,self_correct \\
    uv run --extra training pytest -m "slime and e2e" \\
      tests/test_slime_live.py

For local adapter e2e without a deployed SGLang router, set
``LEANFOUNDRY_SLIME_E2E_LOCAL_GENERATOR=1``. The test then starts a
deterministic SGLang-compatible ``/generate`` service and creates a temporary
HF tokenizer checkpoint, while still using the real pinned Slime package and
live Lean backend.

This smoke is intentionally stronger than a connectivity check: each enabled
mode must sample, verify, tokenize, and emit at least one trainable row for a
simple theorem. Use a checkpoint/router setup that can solve ``True`` with
``trivial``.
"""

from __future__ import annotations

import asyncio
import importlib
import os
from argparse import Namespace
from typing import Any

import pytest

from slime_live_support import LocalSlimeGenerator
from slime_live_support import start_local_slime_generator

pytest.importorskip("slime")

_LOCAL_GENERATOR_ENABLED = (
    os.environ.get("LEANFOUNDRY_SLIME_E2E_LOCAL_GENERATOR") == "1"
)
_BASE_REQUIRED_ENV = (
    "LEANFOUNDRY_SLIME_E2E_LEAN_API_URL",
    "LEANFOUNDRY_SLIME_E2E_ENV_PROFILE",
)
_REMOTE_REQUIRED_ENV = (
    "LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_IP",
    "LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_PORT",
    "LEANFOUNDRY_SLIME_E2E_HF_CHECKPOINT",
)
_REQUIRED_ENV = (
    _BASE_REQUIRED_ENV
    if _LOCAL_GENERATOR_ENABLED
    else (*_BASE_REQUIRED_ENV, *_REMOTE_REQUIRED_ENV)
)
_MISSING_ENV = [name for name in _REQUIRED_ENV if not os.environ.get(name)]
_LIVE_MODES = tuple(
    mode.strip()
    for mode in os.environ.get(
        "LEANFOUNDRY_SLIME_E2E_MODES",
        "direct,puct_tree,self_correct",
    ).split(",")
    if mode.strip()
)

pytestmark = [
    pytest.mark.slime,
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("LEANFOUNDRY_SLIME_E2E") != "1" or bool(_MISSING_ENV),
        reason=(
            "live Slime/SGLang/Lean smoke disabled; set "
            "LEANFOUNDRY_SLIME_E2E=1 plus "
            f"{', '.join(_REQUIRED_ENV)}"
        ),
    ),
]


class _OneTheoremSource:
    def __init__(
        self,
        *,
        env_profile: str,
        header: str,
        theorem_name: str,
    ) -> None:
        self.env_profile = env_profile
        self.header = header
        self.theorem_name = theorem_name

    def get_samples(self, count: int) -> list[dict[str, Any]]:
        assert count == 1
        return [
            {
                "prompt": (
                    f"theorem {self.theorem_name} : True := by\n  sorry"
                ),
                "metadata": {
                    "id": self.theorem_name.replace("_", "-"),
                    "theorem_name": self.theorem_name,
                    "source": "live-smoke",
                    "env_profile": self.env_profile,
                    "header": self.header,
                },
            }
        ]


@pytest.mark.parametrize("mode", _LIVE_MODES)
def test_live_slime_rollout_smoke(
    mode: str,
    local_generator: LocalSlimeGenerator | None,
) -> None:
    rollout_module = importlib.import_module("leanfoundry.slime.rollout")
    _reset_rollout_globals(rollout_module)
    args = _live_args(mode, local_generator)
    data_source = _OneTheoremSource(
        env_profile=args.lean_env_profile,
        header=os.environ.get(
            "LEANFOUNDRY_SLIME_E2E_HEADER",
            "import Mathlib",
        ),
        theorem_name=f"lf_slime_live_{_safe_mode_name(mode)}",
    )

    output = asyncio.run(
        _run_live_rollout(
            rollout_module,
            args,
            data_source,
        )
    )

    metrics = output.metrics
    assert metrics["lf_results"] == 1
    assert metrics["lf_rows"] > 0, metrics
    assert metrics.get("lf_status_error", 0) == 0, metrics
    assert metrics.get("lf_status_cancelled", 0) == 0, metrics
    assert isinstance(output.samples, list)
    assert sum(len(group) for group in output.samples) > 0, metrics


@pytest.fixture()
def local_generator(tmp_path) -> LocalSlimeGenerator | None:
    if not _LOCAL_GENERATOR_ENABLED:
        yield None
        return
    generator = start_local_slime_generator(tmp_path)
    try:
        yield generator
    finally:
        generator.stop()


def _live_args(
    mode: str,
    local_generator: LocalSlimeGenerator | None,
) -> Namespace:
    normalized_mode = _normalize_mode(mode)
    max_direct_candidates = 2 if normalized_mode == "self_correct" else 1
    if local_generator is None:
        sglang_router_ip = os.environ[
            "LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_IP"
        ]
        sglang_router_port = int(
            os.environ["LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_PORT"]
        )
        hf_checkpoint = os.environ["LEANFOUNDRY_SLIME_E2E_HF_CHECKPOINT"]
    else:
        sglang_router_ip = local_generator.host
        sglang_router_port = local_generator.port
        hf_checkpoint = str(local_generator.checkpoint_path)
    args = Namespace(
        lean_api_url=os.environ[
            "LEANFOUNDRY_SLIME_E2E_LEAN_API_URL"
        ],
        lean_api_key=os.environ.get("LEANFOUNDRY_SLIME_E2E_LEAN_API_KEY"),
        lean_env_profile=os.environ[
            "LEANFOUNDRY_SLIME_E2E_ENV_PROFILE"
        ],
        lean_timeout_ms=600000,
        lean_acquire_timeout_ms=600000,
        lean_step_timeout_ms=600000,
        lean_http_timeout_seconds=600,
        sglang_router_ip=sglang_router_ip,
        sglang_router_port=sglang_router_port,
        hf_checkpoint=hf_checkpoint,
        over_sampling_batch_size=1,
        lf_search_algorithm=normalized_mode,
        lf_max_direct_candidates=max_direct_candidates,
        lf_direct_candidates_per_round=1,
        lf_max_tactic_calls=2,
        lf_tactics_per_expansion=1,
        lf_max_concurrent=1,
        lf_value_mode="unbonded",
        lf_use_value_client=False,
    )
    return args


def _normalize_mode(mode: str) -> str:
    if mode == "tree":
        return "puct_tree"
    return mode


def _safe_mode_name(mode: str) -> str:
    return _normalize_mode(mode).replace("-", "_")


async def _run_live_rollout(
    rollout_module: Any,
    args: Namespace,
    data_source: Any,
) -> Any:
    try:
        return await rollout_module.async_generate_rollout(
            args,
            1,
            data_source,
            evaluation=False,
        )
    finally:
        await _close_env(rollout_module)
        _reset_rollout_globals(rollout_module)


async def _close_env(rollout_module: Any) -> None:
    env = getattr(rollout_module, "_ENV", None)
    if env is not None:
        await env.close()


def _reset_rollout_globals(rollout_module: Any) -> None:
    rollout_module._RUNNER = None
    rollout_module._ENV = None
    rollout_module._POLICY = None
    rollout_module._VALUE = None
    rollout_module._VALUE_BUILT = False
