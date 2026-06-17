"""Public model client protocols."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from leanfoundry.schemas import FactorizedProofState
from leanfoundry.schemas._base import LeanFoundryModel


class PolicySamplingParams(LeanFoundryModel):
    """Sampling controls passed through to policy endpoints."""

    temperature: float = 0.8
    top_p: float | None = 0.95
    max_tokens: int | None = None
    extra: Mapping[str, Any] | None = None


class PolicyClient(Protocol):
    """Model-agnostic policy endpoint used by search and rollouts."""

    async def sample_tactics(
        self,
        states: Sequence[FactorizedProofState],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
    ) -> list[list[str]]:
        """Return n tactic candidates for each proof state."""

    async def sample_proofs(
        self,
        prompts: Sequence[str],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
    ) -> list[list[str]]:
        """Return n whole-proof or informal-reasoning candidates per prompt."""


class ValueClient(Protocol):
    """Separate value endpoint used by search selection."""

    async def estimate(
        self,
        states: Sequence[FactorizedProofState],
    ) -> list[float]:
        """Score each state in [0, 1]."""
