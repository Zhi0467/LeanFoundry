"""Trajectory and HER schemas."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel
from leanfoundry.schemas.proof_state import FactorizedProofState


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
    """Verified sample emitted to SFT, EI, or RL training."""

    root_state: FactorizedProofState = Field(
        description="State used as the training sample root."
    )
    tactic_tree: TacticNode | None = Field(
        default=None,
        description="Tree proof for tactic training or HER, when available.",
    )
    whole_proof: str = Field(description="Complete Lean proof text.")
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
