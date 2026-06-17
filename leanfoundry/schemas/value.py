"""Value-label schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from leanfoundry.schemas._base import LeanFoundryModel
from leanfoundry.schemas.proof_state import FactorizedProofState


class ValueLabel(LeanFoundryModel):
    """Supervised value label extracted from search traces."""

    state: FactorizedProofState
    label: Literal[0, 1]
    weight: float = Field(default=1.0, ge=0)
    disproved: bool = False
    theorem_id: str | None = None
    env_profile: str
    proof_state_hash: str | None = None
    depth: int | None = Field(default=None, ge=0)
    tactics_tried_on_subtree: int | None = Field(default=None, ge=0)
    model_version: int
