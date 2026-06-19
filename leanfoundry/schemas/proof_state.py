"""Proof-state schemas used by search and value models."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel


class LocalContextEntry(LeanFoundryModel):
    """One hypothesis or local definition in a goal's local context."""

    name: str | None = Field(
        default=None,
        description="Local variable or hypothesis name as shown by Lean.",
    )
    type: str = Field(description="Lean expression type for this entry.")
    value: str | None = Field(
        default=None,
        description="Value for let-bindings; absent for ordinary hypotheses.",
    )


class GoalComponent(LeanFoundryModel):
    """One open goal in a proof state.

    Goals are referenced by their position in the owning state's
    ``goal_components`` list; they carry no separate id.
    """

    target: str = Field(description="Lean target expression to prove.")
    pretty: str = Field(description="Prompt-facing rendering of this goal.")
    hypotheses: list[LocalContextEntry] = Field(
        default_factory=list,
        description="Local hypotheses visible to this goal.",
    )
    name: str | None = Field(
        default=None,
        description="Lean goal name, such as a case label, when available.",
    )


class FactorizedProofState(LeanFoundryModel):
    """A tree-search node: the open goals plus the token to resume them.

    v0 search is AND/OR tree search, so this stores only what the search and
    the policy/value models read: the open goals and the backend token. It
    does not store how the node was assembled. Metavariable coupling between
    goals is read from the backend response at expansion time to decide goal
    bundling, then discarded. There is no state-identity fingerprint because
    states reached by different paths are not merged. See design doc §3.1.
    """

    env_profile: str = Field(
        description="Pinned Lean/Mathlib environment for this proof state."
    )
    goal_components: list[GoalComponent] = Field(
        default_factory=list,
        description="Open goals in this state, in Lean's order.",
    )
    pretty_state: str = Field(
        description="Full proof-state rendering for prompts and diagnostics."
    )
    state_token: str | None = Field(
        default=None,
        description="Opaque backend token used to resume this state.",
    )
    serialized_lean_state: bytes | None = Field(
        default=None,
        description=(
            "Optional materialized Lean state blob. Normal search uses "
            "state_token (the backend keeps the blob); this is the escape "
            "hatch for multi-node/content-addressed backends per design §2.3."
        ),
    )
