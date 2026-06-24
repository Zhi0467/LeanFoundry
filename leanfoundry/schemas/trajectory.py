"""Trajectory and HER schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel
from leanfoundry.schemas.proof_state import FactorizedProofState
from leanfoundry.schemas.value import ValueLabel


class TacticNode(LeanFoundryModel):
    """Tree projection of the solved slice of a search graph."""

    state: FactorizedProofState = Field(
        description="Proof state where this tactic was chosen."
    )
    tactic: str = Field(
        description="Full model action text, including inline comments."
    )
    children: list[TacticNode] = Field(
        default_factory=list,
        description="AND-children produced by this tactic.",
    )
    proved: bool = Field(
        default=False,
        description="Whether the subtree rooted at this node is closed.",
    )
    depth: int = Field(
        default=0,
        ge=0,
        description="Depth of this node in the rendered proof tree.",
    )
    total_tactics_tried: int = Field(
        default=0,
        ge=0,
        description="Search effort spent on the subtree rooted here.",
    )


class ProofTree(LeanFoundryModel):
    """Solved proof forest below the synthetic initialization layer."""

    roots: list[TacticNode] = Field(
        default_factory=list,
        description=(
            "One solved initial backend state per root. Each root stores that "
            "state plus the proved tactic selected at the state."
        ),
    )
    rendered_lean: str = Field(
        description="Lean proof text reconstructed from tactic history."
    )
    verified: bool = Field(
        default=False,
        description="Whether rendered_lean passed final verification.",
    )


class TrainingSample(LeanFoundryModel):
    """Sample emitted to SFT, EI, or RL training."""

    root_state: FactorizedProofState = Field(
        description="State used as the training sample root."
    )
    tactic_tree: TacticNode | None = Field(
        default=None,
        description="Tree proof for tactic training or HER, when available.",
    )
    whole_proof: str | None = Field(
        default=None,
        description="Complete Lean proof text, when available.",
    )
    depth: int = Field(
        ge=0,
        description="Proof depth for this sample.",
    )
    search_budget_used: int = Field(
        ge=0,
        description="Tactic attempts spent before discovering this proof.",
    )
    requires_reverification: bool = Field(
        default=True,
        description="Whether the sample must pass /exec/verify before use.",
    )


class PolicyExample(LeanFoundryModel):
    """Positive tactic-policy example extracted from search data."""

    state: FactorizedProofState = Field(
        description="Proof state where the tactic was selected."
    )
    proof_prefix: str = Field(
        default="",
        description=(
            "Root-to-state tactic prefix for history-conditional training. "
            "Empty for a real initial state."
        ),
    )
    tactic: str = Field(description="Proved tactic text.")
    theorem_id: str | None = Field(
        default=None,
        description="Source theorem id for this example, if available.",
    )
    env_profile: str = Field(
        description="Pinned Lean/Mathlib environment for this state."
    )
    depth: int = Field(
        ge=0,
        description="Depth of the state in the extracted proof tree.",
    )
    model_version: int | None = Field(
        default=None,
        description="Policy model iteration that produced this tactic.",
    )


class ExtractionFailure(LeanFoundryModel):
    """Non-search failure encountered while building training artifacts."""

    kind: Literal["rendering", "verification", "unsupported"] = Field(
        description="Failure class for extraction accounting."
    )
    message: str = Field(description="Human-readable failure detail.")
    node_id: str | None = Field(
        default=None,
        description="Runtime node id when the failure localizes to one node.",
    )


class TrainingArtifacts(LeanFoundryModel):
    """Training-data artifacts emitted by one search attempt."""

    proof_candidates: list[ProofTree] = Field(
        default_factory=list,
        description="Rendered proof candidates and verifier status.",
    )
    policy_examples: list[PolicyExample] = Field(
        default_factory=list,
        description="Positive policy examples grounded by accepted steps.",
    )
    value_labels: list[ValueLabel] = Field(
        default_factory=list,
        description="Bonded value labels extracted from the search tree.",
    )
    failures: list[ExtractionFailure] = Field(
        default_factory=list,
        description="Rendering, verification, or unsupported extraction gaps.",
    )
    diagnostics: dict[str, float | int | str] = Field(
        default_factory=dict,
        description="Small scalar extraction counters.",
    )


class TrajectoryRecord(LeanFoundryModel):
    """Replay-buffer trajectory record."""

    id: str = Field(description="Durable trajectory id.")
    theorem_id: str = Field(description="Theorem this trajectory attempts.")
    env_profile: str = Field(description="Execution environment profile.")
    proof_type: str = Field(description="Trajectory family, e.g. mcts_search.")
    whole_proof: str | None = Field(
        default=None,
        description="Final verified proof text, if one was found.",
    )
    proof_tree: ProofTree | None = Field(
        default=None,
        description="Serialized solved proof tree, not the live search graph.",
    )
    search_budget_used: int | None = Field(
        default=None,
        description="Tactic attempts consumed by this trajectory.",
    )
    is_subproof: bool = Field(
        default=False,
        description="True when this trajectory was emitted by HER.",
    )
    parent_trajectory_id: str | None = Field(
        default=None,
        description="Parent trajectory id for HER subproofs.",
    )
    model_version: int = Field(description="Model iteration that ran search.")
    created_at: str | None = Field(
        default=None,
        description="Storage timestamp, if assigned by the store.",
    )
