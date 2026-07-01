"""Convert framework-neutral rows into Slime Samples."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from typing import Any

from slime.utils.types import Sample

from leanfoundry.proofsearch.to_rows import TrainingRow, TrainingSegment


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
    response_parts: list[str] = []
    response_ids: list[int] = []
    loss_mask: list[int] = []
    for segment in segments:
        tokens = _encode(tokenizer, segment.text)
        response_parts.append(segment.text)
        response_ids.extend(tokens)
        loss_mask.extend([1 if segment.trainable else 0] * len(tokens))

    sample = Sample(
        rollout_id=rollout_id,
        prompt=row.prompt,
        tokens=[*prompt_ids, *response_ids],
        response="".join(response_parts),
        response_length=len(response_ids),
        label=row.kind,
        reward=row.reward,
        loss_mask=loss_mask,
        metadata={
            **row.meta,
            "rollout_id": rollout_id,
            "group_key": row.group_key,
            "lf_kind": row.kind,
        },
        train_metadata={"lf_kind": row.kind},
        status=Sample.Status.COMPLETED,
    )
    _validate_sample(sample, prompt_token_count=len(prompt_ids))
    return sample


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
