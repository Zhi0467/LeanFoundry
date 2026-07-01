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
