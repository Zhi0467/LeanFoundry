"""Opt-in live tree-search EI smoke with real SGLang and Lean.

Enable with::

    LEANFOUNDRY_SLIME_TREE_EI_E2E=1 \\
    LEANFOUNDRY_SLIME_E2E_LEAN_API_URL=http://127.0.0.1:8000 \\
    LEANFOUNDRY_SLIME_E2E_ENV_PROFILE=mathlib \\
    LEANFOUNDRY_SGLANG_PYTHON=.venv-sglang/bin/python \\
    uv run --extra training pytest -q -m "slime and e2e" \\
      tests/test_slime_tree_ei_live.py

This is intentionally a tiny Expert Iteration loop, not a full Slime trainer:
tree search uses a real SGLang `/generate` server and a live Lean backend, then
one local optimizer step consumes the emitted Slime Sample
``tokens/response_length/loss_mask`` contract.
"""

from __future__ import annotations

import asyncio
import importlib
import os
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from slime_live_support import RealSGLangServer, start_real_sglang_server

pytest.importorskip("slime")

_REQUIRED_ENV = (
    "LEANFOUNDRY_SLIME_E2E_LEAN_API_URL",
    "LEANFOUNDRY_SLIME_E2E_ENV_PROFILE",
    "LEANFOUNDRY_SGLANG_PYTHON",
)
_MISSING_ENV = [name for name in _REQUIRED_ENV if not os.environ.get(name)]

pytestmark = [
    pytest.mark.slime,
    pytest.mark.e2e,
    pytest.mark.skipif(
        (
            os.environ.get("LEANFOUNDRY_SLIME_TREE_EI_E2E") != "1"
            or bool(_MISSING_ENV)
        ),
        reason=(
            "live tree EI smoke disabled; set "
            "LEANFOUNDRY_SLIME_TREE_EI_E2E=1 plus "
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
                    "theorem lf_slime_tree_ei_true : True := by\n  sorry"
                ),
                "metadata": {
                    "id": "lf-slime-tree-ei-true",
                    "theorem_name": "lf_slime_tree_ei_true",
                    "source": "live-tree-ei-smoke",
                    "env_profile": self.env_profile,
                    "header": self.header,
                },
            }
        ]


def test_live_tree_search_ei_training_step(
    tmp_path: Path,
    real_sglang_server: RealSGLangServer,
) -> None:
    rollout_module = importlib.import_module("leanfoundry.slime.rollout")
    _reset_rollout_globals(rollout_module)
    args = _live_tree_args(real_sglang_server)
    data_source = _OneTheoremSource(
        env_profile=args.lean_env_profile,
        header=os.environ.get(
            "LEANFOUNDRY_SLIME_E2E_HEADER",
            "import Mathlib",
        ),
    )

    output = asyncio.run(_run_live_rollout(rollout_module, args, data_source))

    metrics = output.metrics
    assert metrics["lf_results"] == 1
    assert metrics["lf_rows"] > 0, metrics
    assert metrics["lf_rows_tactic"] > 0, metrics
    assert metrics.get("lf_status_error", 0) == 0, metrics
    assert isinstance(output.samples, list)
    assert isinstance(output.samples[0][0], list)
    samples = _flatten_samples(output.samples)
    assert samples, metrics
    first = samples[0]
    assert first.metadata["lf_kind"] == "tactic"
    assert first.metadata["rollout_id"] == first.rollout_id
    assert first.metadata["slime_rollout_id"] == 1
    assert first.response.strip() == "trivial"
    assert first.response_length > 0
    assert first.loss_mask == [1] * first.response_length
    assert len(first.tokens) > first.response_length

    loss = _run_optimizer_step(
        checkpoint_path=real_sglang_server.checkpoint_path,
        samples=samples,
        output_dir=tmp_path / "trained",
    )

    assert loss > 0.0


@pytest.fixture()
def real_sglang_server(tmp_path: Path) -> RealSGLangServer:
    server = start_real_sglang_server(
        tmp_path,
        python_path=os.environ["LEANFOUNDRY_SGLANG_PYTHON"],
        cuda_visible_devices=os.environ.get(
            "LEANFOUNDRY_TREE_EI_E2E_CUDA_VISIBLE_DEVICES",
            "0",
        ),
    )
    try:
        yield server
    finally:
        server.stop()


def _live_tree_args(server: RealSGLangServer) -> Namespace:
    return Namespace(
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
        sglang_router_ip=server.host,
        sglang_router_port=server.port,
        hf_checkpoint=str(server.checkpoint_path),
        over_sampling_batch_size=1,
        lf_search_algorithm="puct_tree",
        lf_max_tactic_calls=2,
        lf_tactics_per_expansion=1,
        lf_max_concurrent=1,
        lf_value_mode="unbonded",
        lf_use_value_client=False,
        lf_tactic_temperature=0.0,
        lf_tactic_top_p=1.0,
        lf_tactic_max_new_tokens=1,
        lf_tactic_logit_bias={"0": 100.0},
    )


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


def _flatten_samples(node: Any) -> list[Any]:
    if isinstance(node, list):
        flattened: list[Any] = []
        for item in node:
            flattened.extend(_flatten_samples(item))
        return flattened
    return [node]


def _run_optimizer_step(
    *,
    checkpoint_path: Path,
    samples: list[Any],
    output_dir: Path,
) -> float:
    import torch
    import torch.nn.functional as functional
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(checkpoint_path)
    model.train()
    optimizer = torch.optim.SGD(model.parameters(), lr=1e-2)
    before = [
        parameter.detach().clone()
        for parameter in model.parameters()
        if parameter.requires_grad
    ]

    losses = []
    for sample in samples:
        input_ids = torch.tensor([sample.tokens], dtype=torch.long)
        logits = model(input_ids=input_ids).logits[:, :-1, :]
        labels = input_ids[:, 1:]
        loss_mask = _response_loss_mask(sample, labels.shape[1], torch)
        token_loss = functional.cross_entropy(
            logits.reshape(-1, logits.shape[-1]),
            labels.reshape(-1),
            reduction="none",
        ).reshape_as(loss_mask)
        losses.append((token_loss * loss_mask).sum() / loss_mask.sum())

    loss = torch.stack(losses).mean()
    assert torch.isfinite(loss)
    loss.backward()
    optimizer.step()
    optimizer.zero_grad(set_to_none=True)
    model.save_pretrained(output_dir, safe_serialization=True)

    after = [
        parameter.detach()
        for parameter in model.parameters()
        if parameter.requires_grad
    ]
    assert any(
        torch.any((after_item - before_item).abs() > 0).item()
        for before_item, after_item in zip(before, after, strict=True)
    )
    return float(loss.item())


def _response_loss_mask(
    sample: Any,
    label_count: int,
    torch_module: Any,
) -> Any:
    mask = torch_module.zeros((1, label_count), dtype=torch_module.float32)
    response_start = len(sample.tokens) - sample.response_length
    for offset, trainable in enumerate(sample.loss_mask):
        token_index = response_start + offset
        if token_index > 0:
            mask[0, token_index - 1] = float(trainable)
    assert mask.sum().item() > 0
    return mask
