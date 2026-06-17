"""Proof-state schemas used by search and value models."""

from __future__ import annotations

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel


class LocalContextEntry(LeanFoundryModel):
    """One expression in a goal's local context."""

    name: str | None = None
    type: str
    value: str | None = None


class LocalContext(LeanFoundryModel):
    """Local context associated with one factorized goal component."""

    entries: list[LocalContextEntry] = Field(default_factory=list)


class GoalComponent(LeanFoundryModel):
    """One factorized goal component."""

    component_id: str
    target: str
    pretty: str
    hypotheses: list[LocalContextEntry] = Field(default_factory=list)
    name: str | None = None
    sibling_dependencies: list[str] = Field(default_factory=list)


class FactorizedProofState(LeanFoundryModel):
    """LeanTree-inspired proof-state representation owned by LeanFoundry."""

    env_profile: str
    theorem_header_options_hash: str
    goal_components: list[GoalComponent] = Field(default_factory=list)
    local_context_by_component: dict[str, LocalContext] = Field(
        default_factory=dict,
    )
    metavariable_coupling_groups: list[list[str]] = Field(default_factory=list)
    tactic_history_hash: str
    pretty_state: str
    state_token: str | None = None
    serialized_lean_state: bytes | None = None
