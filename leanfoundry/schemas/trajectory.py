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


class SelfCorrectTurn(LeanFoundryModel):
    """One whole-proof attempt in a self-correction trace."""

    turn_index: int = Field(
        ge=1,
        description="One-based proof attempt index inside this trace.",
    )
    proof: str = Field(description="Model-produced Lean proof text.")
    verifier_status: str = Field(description="Verifier status for this proof.")
    verifier_feedback: str = Field(
        default="",
        description="Rendered verifier feedback shown to the next turn.",
    )
    verify_item_id: str = Field(description="Backend verifier item id.")
    accepted: bool = Field(
        default=False,
        description="Whether this turn passed final verification.",
    )


class SelfCorrectTrace(LeanFoundryModel):
    """Failed-proof / feedback / correction artifact for self-correct data."""

    turns: list[SelfCorrectTurn] = Field(
        default_factory=list,
        description="Ordered proof attempts and verifier feedback.",
    )


class DirectVerificationAttempt(LeanFoundryModel):
    """One direct whole-proof candidate verification attempt."""

    candidate_index: int = Field(
        ge=1,
        description="One-based direct candidate index in this search attempt.",
    )
    proof: str = Field(description="Model-produced Lean proof text.")
    verifier_status: str = Field(
        description="Verifier status returned for this candidate."
    )
    verifier_feedback: str = Field(
        default="",
        description="Rendered verifier feedback for this candidate.",
    )
    verify_item_id: str = Field(description="Backend verifier item id.")
    accepted: bool = Field(
        default=False,
        description="Whether this candidate passed final verification.",
    )


class NegationTacticAttempt(LeanFoundryModel):
    """One tactic tried while proving a synthetic negated theorem."""

    tactic: str = Field(description="Tactic attempted on the negation goal.")
    status: str = Field(description="Backend step status for this tactic.")
    messages: list[str] = Field(
        default_factory=list,
        description="Rendered backend messages for this tactic.",
    )


class NegationAttempt(LeanFoundryModel):
    """Synthetic negation proof attempt used to disprove a state."""

    source_node_id: str = Field(
        description="Runtime state node whose negation was checked."
    )
    source_state: FactorizedProofState = Field(
        description="Original state checked for semantic disproof."
    )
    negated_target: str = Field(description="Lean target wrapped in negation.")
    rendered_lean: str | None = Field(
        default=None,
        description="Synthetic negated theorem submitted to the backend.",
    )
    theorem_name: str | None = Field(
        default=None,
        description="Synthetic negated theorem name, when rendered.",
    )
    negation_state: FactorizedProofState | None = Field(
        default=None,
        description="Backend state for the synthetic negation theorem.",
    )
    step_item_id: str | None = Field(
        default=None,
        description="Backend step item id used for negation tactics.",
    )
    status: str = Field(
        description="Attempt outcome, e.g. proved/not_proved/unsupported."
    )
    tactic_attempts: list[NegationTacticAttempt] = Field(
        default_factory=list,
        description="Tactics tried on the synthetic negation goal.",
    )
    tactic_calls_used: int = Field(
        default=0,
        ge=0,
        description="Lean tactic attempts charged for this negation check.",
    )
    proved: bool = Field(
        default=False,
        description="Whether the synthetic negation closed.",
    )
    proved_tactic: str | None = Field(
        default=None,
        description="Tactic that proved the negation, if any.",
    )
    operational_status: str | None = Field(
        default=None,
        description="Operational backend status if the check aborted search.",
    )


class PolicyExample(LeanFoundryModel):
    """Positive tactic-policy example extracted from search data."""

    state: FactorizedProofState = Field(
        description="Proof state where the tactic was selected."
    )
    proof_prefix: str = Field(
        default="",
        description=(
            "Root-to-state tactic prefix kept as provenance or optional "
            "prompt context. Empty for a real initial state."
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
    direct_verification_attempts: list[DirectVerificationAttempt] = Field(
        default_factory=list,
        description=(
            "All verifier attempts for direct/self-correct whole-proof "
            "candidates. Kept for eval provenance, not as a training row."
        ),
    )
    negation_attempts: list[NegationAttempt] = Field(
        default_factory=list,
        description=(
            "Synthetic negation proof attempts used for DISPROVED labels. "
            "Kept for diagnostics/audit, not as policy positives."
        ),
    )
    self_correct_traces: list[SelfCorrectTrace] = Field(
        default_factory=list,
        description="Whole-proof self-correction traces, if any.",
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
