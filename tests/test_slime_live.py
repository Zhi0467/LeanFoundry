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
    uv run --extra training pytest -m "slime and e2e" \\
      tests/test_slime_live.py

The generated proof is allowed to be rejected by Lean; model quality is not the
contract. The smoke fails only if the live rollout plumbing cannot sample,
verify, tokenize, and return a Slime output for one theorem.
"""

from __future__ import annotations

import asyncio
import importlib
import os
from argparse import Namespace
from typing import Any

import pytest

pytest.importorskip("slime")

_REQUIRED_ENV = (
    "LEANFOUNDRY_SLIME_E2E_LEAN_API_URL",
    "LEANFOUNDRY_SLIME_E2E_ENV_PROFILE",
    "LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_IP",
    "LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_PORT",
    "LEANFOUNDRY_SLIME_E2E_HF_CHECKPOINT",
)
_MISSING_ENV = [name for name in _REQUIRED_ENV if not os.environ.get(name)]

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
    def __init__(self, *, env_profile: str, header: str) -> None:
        self.env_profile = env_profile
        self.header = header

    def get_samples(self, count: int) -> list[dict[str, Any]]:
        assert count == 1
        return [
            {
                "prompt": (
                    "theorem lf_slime_live_true : True := by\n"
                    "  sorry"
                ),
                "metadata": {
                    "id": "lf-slime-live-true",
                    "theorem_name": "lf_slime_live_true",
                    "source": "live-smoke",
                    "env_profile": self.env_profile,
                    "header": self.header,
                },
            }
        ]


def test_live_slime_direct_rollout_smoke() -> None:
    rollout_module = importlib.import_module("leanfoundry.slime.rollout")
    _reset_rollout_globals(rollout_module)
    args = _live_args()
    data_source = _OneTheoremSource(
        env_profile=args.lean_env_profile,
        header=os.environ.get(
            "LEANFOUNDRY_SLIME_E2E_HEADER",
            "import Mathlib",
        ),
    )

    try:
        output = asyncio.run(
            rollout_module.async_generate_rollout(
                args,
                1,
                data_source,
                evaluation=False,
            )
        )
    finally:
        _close_env(rollout_module)
        _reset_rollout_globals(rollout_module)

    metrics = output.metrics
    assert metrics["lf_results"] == 1
    assert "lf_rows" in metrics
    assert metrics.get("lf_status_error", 0) == 0
    assert metrics.get("lf_status_cancelled", 0) == 0
    assert isinstance(output.samples, list)


def _live_args() -> Namespace:
    return Namespace(
        lean_api_url=os.environ[
            "LEANFOUNDRY_SLIME_E2E_LEAN_API_URL"
        ],
        lean_api_key=os.environ.get("LEANFOUNDRY_SLIME_E2E_LEAN_API_KEY"),
        lean_env_profile=os.environ[
            "LEANFOUNDRY_SLIME_E2E_ENV_PROFILE"
        ],
        sglang_router_ip=os.environ[
            "LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_IP"
        ],
        sglang_router_port=int(
            os.environ["LEANFOUNDRY_SLIME_E2E_SGLANG_ROUTER_PORT"]
        ),
        hf_checkpoint=os.environ["LEANFOUNDRY_SLIME_E2E_HF_CHECKPOINT"],
        over_sampling_batch_size=1,
        lf_search_algorithm="direct",
        lf_max_direct_candidates=1,
        lf_max_concurrent=1,
        lf_value_mode="unbonded",
        lf_use_value_client=False,
    )


def _close_env(rollout_module: Any) -> None:
    env = getattr(rollout_module, "_ENV", None)
    if env is not None:
        asyncio.run(env.close())


def _reset_rollout_globals(rollout_module: Any) -> None:
    rollout_module._RUNNER = None
    rollout_module._ENV = None
    rollout_module._POLICY = None
    rollout_module._VALUE = None
    rollout_module._VALUE_BUILT = False
