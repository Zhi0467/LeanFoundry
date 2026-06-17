"""Trajectory and HER schemas."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel
from leanfoundry.schemas.proof_state import FactorizedProofState


class TacticNode(LeanFoundryModel):
    """Tree projection of the solved slice of a search graph."""

    state: FactorizedProofState
    tactic: str
    children: list[TacticNode] = Field(default_factory=list)
    proved: bool = False
    depth: int = Field(default=0, ge=0)
    total_tactics_tried: int = Field(default=0, ge=0)


class ProofTree(LeanFoundryModel):
    """Canonical proof tree with one root per initial sorry."""

    roots: list[TacticNode] = Field(default_factory=list)
    rendered_lean: str
    verified: bool = False


class TrainingSample(LeanFoundryModel):
    """Verified sample emitted to SFT, EI, or RL training."""

    root_state: FactorizedProofState
    tactic_tree: TacticNode | None = None
    whole_proof: str
    depth: int = Field(ge=0)
    search_budget_used: int = Field(ge=0)
    requires_reverification: bool = True


class TrajectoryRecord(LeanFoundryModel):
    """Replay-buffer trajectory record."""

    id: str
    theorem_id: str
    env_profile: str
    proof_type: str
    whole_proof: str | None = None
    proof_tree: ProofTree | None = None
    search_budget_used: int | None = None
    is_subproof: bool = False
    parent_trajectory_id: str | None = None
    model_version: int
    created_at: str | None = None
