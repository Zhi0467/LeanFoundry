"""Public model client protocols."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import Field

from leanfoundry.schemas import FactorizedProofState
from leanfoundry.schemas._base import LeanFoundryModel


class PolicySamplingParams(LeanFoundryModel):
    """Sampling controls passed through to policy endpoints."""

    temperature: float = Field(
        default=0.8,
        ge=0,
        description="Sampling temperature for tactic or proof generation.",
    )
    top_p: float | None = Field(
        default=0.95,
        ge=0,
        le=1,
        description="Nucleus sampling cutoff; None leaves endpoint default.",
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Maximum generated tokens; None leaves endpoint default.",
    )
    extra: Mapping[str, Any] | None = Field(
        default=None,
        description="Provider-specific sampling options passed through.",
    )


class PolicyContext(LeanFoundryModel):
    """Inference-only context for tactic sampling."""

    proof_prefix: str = Field(
        default="",
        description=(
            "Root-to-state tactic history, including comments. This is prompt "
            "context only, not a separate training target."
        ),
    )


class PolicyClient(Protocol):
    """Model-agnostic policy endpoint used by search and rollouts."""

    async def sample_tactics(
        self,
        states: Sequence[FactorizedProofState],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
        context: Sequence[PolicyContext] | None = None,
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
