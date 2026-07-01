"""Convert framework-neutral rows into Slime Samples."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from collections.abc import Sequence
from typing import Any

from slime.utils.types import Sample

from leanfoundry.proofsearch.to_rows import TrainingRow, TrainingSegment

_SLIME_RESPONSE_LOG_PROBS_KEY = "slime_response_log_probs"
_SLIME_RESPONSE_META_INFO_KEY = "slime_response_meta_info"
_SLIME_UPDATE_TERMINAL_INFO_KEY = "slime_update_terminal_info"
_INTERNAL_METADATA_KEYS = frozenset(
    {
        _SLIME_RESPONSE_LOG_PROBS_KEY,
        _SLIME_RESPONSE_META_INFO_KEY,
        _SLIME_UPDATE_TERMINAL_INFO_KEY,
    }
)


def to_samples(
    rows: Iterable[TrainingRow],
    *,
    rollout_id: int,
    tokenizer: Any,
    args: Any = None,
) -> list[list[Sample]]:
    """Convert training rows to Slime sample groups."""

    groups: OrderedDict[str, list[Sample]] = OrderedDict()
    for row in rows:
        groups.setdefault(row.group_key, []).append(
            sample_from_row(
                row,
                rollout_id=rollout_id,
                tokenizer=tokenizer,
                args=args,
            )
        )
    for group_index, group in enumerate(groups.values()):
        for index, sample in enumerate(group):
            sample.group_index = group_index
            sample.index = index
    return list(groups.values())


def sample_from_row(
    row: TrainingRow,
    *,
    rollout_id: int,
    tokenizer: Any,
    args: Any = None,
) -> Sample:
    """Build one Slime Sample with aligned tokens and loss mask."""

    prompt_ids = _encode(tokenizer, row.prompt)
    segments = row.segments or (TrainingSegment(row.response, True),)
    segment_tokens = [_encode(tokenizer, segment.text) for segment in segments]
    rollout_log_probs = _optional_float_list(
        row.meta.get(_SLIME_RESPONSE_LOG_PROBS_KEY)
    )
    token_source = (
        "slime_append_response_tokens"
        if rollout_log_probs is not None
        else "leanfoundry_verified_without_rollout_logprobs"
    )

    sample = Sample(
        rollout_id=rollout_id,
        prompt=row.prompt,
        tokens=list(prompt_ids),
        label=row.kind,
        reward=row.reward,
        metadata={
            **_public_metadata(row.meta),
            "rollout_id": rollout_id,
            "group_key": row.group_key,
            "lf_kind": row.kind,
            "lf_trainable_token_source": token_source,
        },
        train_metadata={"lf_kind": row.kind},
        status=Sample.Status.COMPLETED,
    )
    if rollout_log_probs is None:
        _append_verified_segments(sample, segments, segment_tokens)
    else:
        _append_slime_segments(
            sample,
            segments,
            segment_tokens,
            rollout_log_probs=rollout_log_probs,
            args=args,
            meta_info=_optional_dict(
                row.meta.get(_SLIME_RESPONSE_META_INFO_KEY)
            ),
            update_terminal_info=bool(
                row.meta.get(_SLIME_UPDATE_TERMINAL_INFO_KEY, False)
            ),
        )
    _validate_sample(sample, prompt_token_count=len(prompt_ids))
    return sample


def _append_verified_segments(
    sample: Sample,
    segments: tuple[TrainingSegment, ...],
    segment_tokens: list[list[int]],
) -> None:
    """Append verified rows that do not carry rollout log probabilities."""

    for segment, tokens in zip(segments, segment_tokens, strict=True):
        _append_without_rollout_metadata(
            sample,
            tokens=tokens,
            text=segment.text,
            trainable=segment.trainable,
        )


def _append_slime_segments(
    sample: Sample,
    segments: tuple[TrainingSegment, ...],
    segment_tokens: list[list[int]],
    *,
    rollout_log_probs: list[float],
    args: Any,
    meta_info: dict[str, Any] | None,
    update_terminal_info: bool,
) -> None:
    """Append generated rows through Slime's native metadata path."""

    trainable_token_count = sum(
        len(tokens)
        for segment, tokens in zip(segments, segment_tokens, strict=True)
        if segment.trainable
    )
    if len(rollout_log_probs) != trainable_token_count:
        raise ValueError(
            "slime_response_log_probs length must equal trainable token count"
        )

    offset = 0
    last_index = len(segments) - 1
    for index, (segment, tokens) in enumerate(
        zip(segments, segment_tokens, strict=True)
    ):
        log_probs = None
        if segment.trainable:
            next_offset = offset + len(tokens)
            log_probs = rollout_log_probs[offset:next_offset]
            offset = next_offset
        sample.append_response_tokens(
            args,
            tokens=tokens,
            log_probs=log_probs,
            trainable=segment.trainable,
            text=segment.text,
            meta_info=meta_info if index == last_index else None,
            update_terminal_info=update_terminal_info,
        )


def _append_without_rollout_metadata(
    sample: Sample,
    *,
    tokens: list[int],
    text: str,
    trainable: bool,
) -> None:
    if text:
        sample.response += text
    if not tokens:
        return
    sample.tokens += tokens
    sample.response_length += len(tokens)
    if sample.loss_mask is None:
        sample.loss_mask = []
    sample.loss_mask += [1 if trainable else 0] * len(tokens)


def _public_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in metadata.items()
        if key not in _INTERNAL_METADATA_KEYS
    }


def _optional_float_list(value: object) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("slime_response_log_probs must be a sequence")
    return [float(item) for item in value]


def _optional_dict(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("slime_response_meta_info must be a dict")
    return dict(value)


def _encode(tokenizer: Any, text: str) -> list[int]:
    if hasattr(tokenizer, "encode"):
        try:
            tokens = tokenizer.encode(text, add_special_tokens=False)
        except TypeError:
            tokens = tokenizer.encode(text)
    elif callable(tokenizer):
        tokens = tokenizer(text)
    else:
        raise TypeError("tokenizer must expose encode(text) or be callable")
    return [int(token) for token in tokens]


def _validate_sample(sample: Sample, *, prompt_token_count: int) -> None:
    if sample.loss_mask is None:
        raise ValueError("sample loss_mask must be set")
    if len(sample.loss_mask) != sample.response_length:
        raise ValueError("loss_mask length must equal response_length")
    if len(sample.tokens) != prompt_token_count + sample.response_length:
        raise ValueError("tokens must be prompt tokens followed by response")


__all__ = ["sample_from_row", "to_samples"]
