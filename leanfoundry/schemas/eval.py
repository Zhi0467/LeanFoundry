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


class BenchmarkCompatibility(StrEnum):
    """Compatibility of a benchmark split with an env profile."""

    COMPATIBLE = "compatible"
    NEEDS_REVERIFY = "needs_reverify"
    INCOMPATIBLE = "incompatible"


class BenchmarkManifest(LeanFoundryModel):
    """Manifest describing a benchmark split before loading theorem rows."""

    id: str = Field(description="Stable benchmark manifest id.")
    name: str = Field(description="Benchmark family name, e.g. miniF2F.")
    split: str = Field(description="Benchmark split, e.g. train/valid/test.")
    source: str = Field(description="Source repo, dataset, or file URI.")
    row_format: str = Field(
        default="leanfoundry_jsonl",
        min_length=1,
        description=(
            "JSONL row format for theorem loading. The default means each "
            "row is a serialized TheoremSpec; other values require a "
            "benchmark-specific row adapter at load time."
        ),
    )
    env_profile: str = Field(description="Required execution env profile.")
    compatibility: BenchmarkCompatibility = Field(
        description="Whether this benchmark is compatible with env_profile."
    )
    contamination_policy: str = Field(
        description="How overlap with train/eval pools is handled."
    )
    fixed_assignment_id: str = Field(
        description="Stable id for the fixed held-out assignment."
    )
    benchmark_commit: str | None = Field(
        default=None,
        description="Dataset commit or version, if available.",
    )
    theorem_count: int | None = Field(
        default=None,
        ge=0,
        description="Expected theorem count, if known before loading.",
    )
    notes: str | None = Field(
        default=None,
        description="Human-readable caveats for this benchmark split.",
    )


class SamplingConfig(LeanFoundryModel):
    """Sampling configuration recorded in eval manifests."""

    temperature: float = Field(
        default=0.8,
        ge=0,
        description="Temperature used for eval sample generation.",
    )
    top_p: float = Field(
        default=0.95,
        ge=0,
        le=1,
        description="Nucleus sampling cutoff used for eval generation.",
    )
    max_tokens: int = Field(
        default=32768,
        ge=1,
        description="Maximum generated tokens per eval attempt.",
    )


class EvalArtifactManifest(LeanFoundryModel):
    """Manifest describing one reproducible eval run."""

    run_id: str = Field(description="Stable id for this evaluation run.")
    infra_git_sha: str = Field(description="LeanFoundry commit used for eval.")
    training_git_sha: str | None = Field(
        default=None,
        description="Training repo commit, when a training repo is involved.",
    )
    model_checkpoint: str = Field(description="Model checkpoint evaluated.")
    env_profile: str = Field(description="Execution environment profile.")
    benchmark: str = Field(description="Benchmark name and split.")
    benchmark_commit: str | None = Field(
        default=None,
        description="Benchmark dataset commit or version, if known.",
    )
    mode: EvalMode = Field(description="Evaluation mode used for this run.")
    k_values: list[int] = Field(
        default_factory=list,
        description=(
            "Pass@k values for sampling modes (direct, self_correct). "
            "Not populated for search modes."
        ),
    )
    solved_at_budget: dict[int, float] = Field(
        default_factory=dict,
        description=(
            "solved@budget rates keyed by tactic-call budget for "
            "search modes (mcts_state_token). Keys are budgets such as "
            "50, 100, 250, 500, 1000, 2000; values are the fraction of "
            "theorems solved. Not populated for sampling modes."
        ),
    )
    sampling: SamplingConfig | None = Field(
        default=None,
        description="Sampling controls used for generation modes.",
    )
    metrics: dict[str, float | int | str] = Field(
        default_factory=dict,
        description="Scalar evaluation results and throughput metrics.",
    )
