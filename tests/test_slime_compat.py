"""Slime API-compatibility tests.

These guard the narrow Slime surface the LeanFoundry rollout adapter
(`leanfoundry/slime/`, future slice) depends on, so a Slime version bump that
renames or reshapes that surface fails loudly here instead of silently
corrupting training data.

They require the `[training]` extra and a CUDA/Linux box; the default hermetic
suite skips them via ``importorskip``. Run them when bumping the pinned Slime
commit in ``[tool.uv.sources]``::

    uv run --extra training pytest -m slime tests/test_slime_compat.py

Every assertion below is grounded in the pinned commit
``a897e1f40357fdf3b148f1eb4ce26e1aeccfcd2c`` (``slime/utils/types.py``). The
runtime ``data_buffer`` / ``args`` surfaces are exercised by the adapter's own
tests once that slice lands; here we pin only the ``Sample`` data contract,
which is what serializes our search trajectories into the trainer.
"""

from __future__ import annotations

import dataclasses
import inspect
import sys
import types
from argparse import Namespace
from typing import Any

import pytest

pytest.importorskip("slime")

pytestmark = pytest.mark.slime

# Sample fields the adapter reads or writes when converting a search attempt
# into trainer rows: prompt/response/tokens carry the text and ids, reward and
# label carry the verified outcome, loss_mask marks trainable spans (tactic
# spans for tree/trajectory samples), status reports rollout completion, and
# metadata carries our provenance (theorem id, rollout id).
_REQUIRED_SAMPLE_FIELDS = frozenset(
    {
        "prompt",
        "tokens",
        "response",
        "response_length",
        "reward",
        "label",
        "loss_mask",
        "status",
        "metadata",
    }
)


def _sample_type():
    from slime.utils.types import Sample

    return Sample


def test_sample_importable_and_is_dataclass():
    sample_type = _sample_type()
    assert dataclasses.is_dataclass(sample_type)


def test_sample_has_required_fields():
    sample_type = _sample_type()
    present = {field.name for field in dataclasses.fields(sample_type)}
    missing = _REQUIRED_SAMPLE_FIELDS - present
    assert not missing, f"Slime Sample dropped fields we rely on: {missing}"


def test_append_response_tokens_supports_trainable_spans():
    """Self-correct samples need per-span loss masking."""

    sample_type = _sample_type()
    append = getattr(sample_type, "append_response_tokens", None)
    assert append is not None, "Sample.append_response_tokens was removed"

    parameter = inspect.signature(append).parameters.get("trainable")
    assert parameter is not None, "append_response_tokens lost `trainable`"
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_append_response_tokens_requires_trainable_log_probs():
    """LeanFoundry's verified-row fallback exists for this Slime contract."""

    sample_type = _sample_type()
    sample = sample_type(prompt="P:", tokens=[1, 2])

    sample.append_response_tokens(
        tokens=[3, 4],
        log_probs=[-0.1, -0.2],
        trainable=True,
        text="ok",
        update_terminal_info=False,
    )
    sample.append_response_tokens(
        tokens=[5],
        trainable=False,
        text="!",
        update_terminal_info=False,
    )

    assert sample.tokens == [1, 2, 3, 4, 5]
    assert sample.response == "ok!"
    assert sample.response_length == 3
    assert sample.loss_mask == [1, 1, 0]
    assert sample.rollout_log_probs == [-0.1, -0.2, 0.0]

    with pytest.raises(ValueError, match="rollout log probabilities"):
        sample_type(prompt="P:", tokens=[1, 2]).append_response_tokens(
            tokens=[3],
            trainable=True,
            text="x",
            update_terminal_info=False,
        )


def test_tree_tactic_fanout_rollout_ids_schedule_as_two_rollouts():
    """Tree EI rows must schedule by theorem search, not Slime step id."""

    from slime.utils.dp_schedule import build_dp_schedule

    output = _tree_tactic_output()
    samples = _flatten(output)

    assert [sample.rollout_id for sample in samples] == [0, 0, 2]
    partitions, _micro_batches, _num_microbatches, global_batch_sizes = (
        build_dp_schedule(
            Namespace(
                use_dynamic_batch_size=False,
                micro_batch_size=1,
                balance_data=False,
                balance_by_flops=False,
            ),
            {
                "dp_size": 1,
                "cp_size": 1,
                "vpp_size": 1,
                "microbatch_group_size_per_vp_stage": 1,
            },
            [len(sample.tokens) for sample in samples],
            global_batch_size=2,
            rollout_indices=[sample.rollout_id for sample in samples],
        )
    )

    assert partitions == [[0, 1, 2]]
    assert global_batch_sizes == [2]


def test_tree_tactic_fanout_reaches_train_rollout_data(monkeypatch):
    """Exercise Slime's train-data split, not only its public scheduler."""

    pytest.importorskip("megatron")
    _stub_sglang_constants(monkeypatch)

    from slime.backends.megatron_utils import data as train_data_module
    from slime.ray import rollout as rollout_module
    from slime.ray.rollout import RolloutManager
    from slime.utils import data as slime_data_module

    samples = _flatten(_tree_tactic_output())
    args = _rollout_manager_args()
    rollout_manager_class = RolloutManager.__ray_actor_class__
    manager = rollout_manager_class.__new__(rollout_manager_class)
    manager.args = args
    manager.custom_convert_samples_to_train_data_func = None
    manager.custom_reward_post_process_func = None
    manager.train_parallel_config = {
        "dp_size": 1,
        "cp_size": 1,
        "vpp_size": 1,
        "microbatch_group_size_per_vp_stage": 1,
    }
    monkeypatch.setattr(
        rollout_module.ray,
        "put",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        slime_data_module.ray,
        "get",
        lambda value: value,
    )
    monkeypatch.setattr(
        train_data_module.mpu,
        "get_virtual_pipeline_model_parallel_world_size",
        lambda: None,
    )

    train_data = manager._convert_samples_to_train_data(samples)
    rollout_data_refs = manager._split_train_data_by_dp(train_data)
    rollout_data = slime_data_module.process_rollout_data(
        args,
        rollout_data_refs,
        dp_rank=0,
        dp_size=1,
    )

    assert rollout_data["rollout_ids"] == [0, 0, 2]
    assert rollout_data["sample_indices"] == [0, 1, 2]
    assert rollout_data["global_batch_sizes"] == [2]
    assert rollout_data["num_microbatches"] == [3]
    assert rollout_data["micro_batch_indices"] == [[0], [1], [2]]
    assert rollout_data["total_lengths"] == [
        len(sample.tokens) for sample in samples
    ]
    assert rollout_data["rollout_mask_sums"].tolist() == [11.0, 11.0, 5.0]
    assert rollout_data["loss_masks"][0].tolist() == [1, 1, 1, 1]

    (iterator,) = train_data_module.get_data_iterator(rollout_data)
    first_batch = iterator.get_next(
        [
            "tokens",
            "loss_masks",
            "rollout_ids",
            "rollout_mask_sums",
        ]
    )
    assert first_batch["rollout_ids"] == [0]
    assert first_batch["rollout_mask_sums"][0].item() == 11.0
    assert first_batch["loss_masks"][0].tolist() == [1, 1, 1, 1]


def _tree_tactic_output() -> list[Any]:
    from leanfoundry.proofsearch.to_rows import TrainingRow
    from leanfoundry.proofsearch.to_rows import TrainingSegment

    sys.modules.pop("leanfoundry.slime.samples", None)
    from leanfoundry.slime.samples import to_samples

    class Tokenizer:
        def encode(self, text, add_special_tokens=False):
            return [ord(char) for char in text]

    return to_samples(
        [
            TrainingRow(
                kind="tactic",
                prompt="S1:",
                response="simp",
                reward=1.0,
                group_key="theorem-1",
                meta={"env_profile": "mathlib"},
                segments=(TrainingSegment("simp", True),),
            ),
            TrainingRow(
                kind="tactic",
                prompt="S2:",
                response="trivial",
                reward=1.0,
                group_key="theorem-1",
                meta={"env_profile": "mathlib"},
                segments=(TrainingSegment("trivial", True),),
            ),
            TrainingRow(
                kind="tactic",
                prompt="S3:",
                response="aesop",
                reward=1.0,
                group_key="theorem-2",
                meta={"env_profile": "mathlib"},
                segments=(TrainingSegment("aesop", True),),
            ),
        ],
        rollout_id=11,
        tokenizer=Tokenizer(),
    )


def _rollout_manager_args() -> Namespace:
    return Namespace(
        advantage_estimator="grpo",
        rewards_normalization=False,
        use_dynamic_batch_size=False,
        micro_batch_size=1,
        balance_data=False,
        balance_by_flops=False,
        global_batch_size=2,
        rollout_data_transport="object-store",
        reward_key=None,
    )


def _stub_sglang_constants(monkeypatch) -> None:
    # Slime imports SGLang launch types at module import time. This test only
    # exercises RolloutManager's train-data conversion/split methods; real
    # SGLang serving is covered by tests/test_slime_tree_ei_live.py.
    sglang_module = types.ModuleType("sglang")
    srt_module = types.ModuleType("sglang.srt")
    srt_module.__path__ = []
    constants_module = types.ModuleType("sglang.srt.constants")
    server_args_module = types.ModuleType("sglang.srt.server_args")
    utils_module = types.ModuleType("sglang.srt.utils")

    class ServerArgs:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def url(self):
            host = getattr(self, "host", "127.0.0.1")
            port = getattr(self, "port", 30000)
            return f"http://{host}:{port}"

    constants_module.GPU_MEMORY_TYPE_CUDA_GRAPH = "cuda_graph"
    constants_module.GPU_MEMORY_TYPE_KV_CACHE = "kv_cache"
    constants_module.GPU_MEMORY_TYPE_WEIGHTS = "weights"
    server_args_module.ServerArgs = ServerArgs
    utils_module.kill_process_tree = lambda _pid: None
    monkeypatch.setitem(sys.modules, "sglang", sglang_module)
    monkeypatch.setitem(sys.modules, "sglang.srt", srt_module)
    monkeypatch.setitem(sys.modules, "sglang.srt.constants", constants_module)
    monkeypatch.setitem(
        sys.modules,
        "sglang.srt.server_args",
        server_args_module,
    )
    monkeypatch.setitem(sys.modules, "sglang.srt.utils", utils_module)


def _flatten(node):
    if isinstance(node, list):
        flattened = []
        for item in node:
            flattened.extend(_flatten(item))
        return flattened
    return [node]
