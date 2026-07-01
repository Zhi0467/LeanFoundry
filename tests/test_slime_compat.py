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
from argparse import Namespace

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

    from leanfoundry.proofsearch.to_rows import TrainingRow
    from leanfoundry.proofsearch.to_rows import TrainingSegment
    from leanfoundry.slime.samples import to_samples

    class Tokenizer:
        def encode(self, text, add_special_tokens=False):
            return [ord(char) for char in text]

    output = to_samples(
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


def _flatten(node):
    if isinstance(node, list):
        flattened = []
        for item in node:
            flattened.extend(_flatten(item))
        return flattened
    return [node]
