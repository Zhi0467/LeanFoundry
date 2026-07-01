"""Environment-profile validation helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

from leanfoundry.schemas import EnvProfile, TheoremSpec


DEFAULT_ENV_PROFILE = "default"


class EnvProfileValidationError(ValueError):
    """Raised when theorem data is not tied to a pinned environment."""


def header_hash(header: str) -> str:
    """Return the canonical hash for Lean header text."""

    return hashlib.sha256(header.encode("utf-8")).hexdigest()


def require_pinned_env_profile(
    env_profile: str,
    *,
    allow_default: bool = False,
) -> None:
    """Reject empty/default profiles at training-data ingress."""

    if not env_profile:
        raise EnvProfileValidationError("env_profile must be non-empty")
    if env_profile == DEFAULT_ENV_PROFILE and not allow_default:
        raise EnvProfileValidationError("default env_profile is not allowed")


def validate_theorem_env_profile(
    theorem: TheoremSpec,
    *,
    profiles: Mapping[str, EnvProfile] | None = None,
    allow_default: bool = False,
) -> None:
    """Validate one theorem against optional profile metadata."""

    require_pinned_env_profile(
        theorem.env_profile,
        allow_default=allow_default,
    )
    if profiles is None:
        return
    profile = profiles.get(theorem.env_profile)
    if profile is None:
        raise EnvProfileValidationError(
            f"unknown env_profile: {theorem.env_profile}"
        )
    expected_hash = header_hash(profile.header)
    if profile.header_hash != expected_hash:
        raise EnvProfileValidationError(
            f"EnvProfile {theorem.env_profile} has stale header_hash"
        )
    if theorem.header != profile.header:
        raise EnvProfileValidationError(
            f"theorem header does not match env_profile {theorem.env_profile}"
        )


def validate_theorem_batch_env_profiles(
    theorems: Sequence[TheoremSpec],
    *,
    profiles: Mapping[str, EnvProfile] | None = None,
    backend_env_profile: str | None = None,
    allow_default: bool = False,
    allow_mixed: bool = False,
) -> None:
    """Validate a batch of theorem specs for one training/eval run."""

    for theorem in theorems:
        validate_theorem_env_profile(
            theorem,
            profiles=profiles,
            allow_default=allow_default,
        )
    profile_names = {theorem.env_profile for theorem in theorems}
    if len(profile_names) > 1 and not allow_mixed:
        raise EnvProfileValidationError(
            "mixed env_profile batches require explicit routing"
        )
    if backend_env_profile and backend_env_profile != DEFAULT_ENV_PROFILE:
        if profile_names and profile_names != {backend_env_profile}:
            raise EnvProfileValidationError(
                "theorem env_profile disagrees with backend env_profile"
            )


__all__ = [
    "DEFAULT_ENV_PROFILE",
    "EnvProfileValidationError",
    "header_hash",
    "require_pinned_env_profile",
    "validate_theorem_batch_env_profiles",
    "validate_theorem_env_profile",
]
