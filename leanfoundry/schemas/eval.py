"""Evaluation artifact schemas."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel


class EvalMode(StrEnum):
    """Evaluation modes owned by the infrastructure repo."""

    DIRECT = "direct"
    SELF_CORRECT = "self_correct"
    STATE_TOKEN_SEARCH = "mcts_state_token"


class SamplingConfig(LeanFoundryModel):
    """Sampling configuration recorded in eval manifests."""

    temperature: float = 0.8
    top_p: float = 0.95
    max_tokens: int = Field(default=32768, ge=1)


class EvalArtifactManifest(LeanFoundryModel):
    """Manifest describing one reproducible eval run."""

    run_id: str
    infra_git_sha: str
    training_git_sha: str | None = None
    model_checkpoint: str
    env_profile: str
    benchmark: str
    benchmark_commit: str | None = None
    mode: EvalMode
    k_values: list[int] = Field(default_factory=list)
    sampling: SamplingConfig | None = None
    metrics: dict[str, float | int | str] = Field(default_factory=dict)
