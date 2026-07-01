from __future__ import annotations

import pytest

from leanfoundry.env_profiles import (
    EnvProfileValidationError,
    header_hash,
    validate_theorem_batch_env_profiles,
    validate_theorem_env_profile,
)
from leanfoundry.schemas import EnvProfile, TheoremSpec


def _theorem(**updates) -> TheoremSpec:
    data = {
        "lean_statement": "theorem t : True := by",
        "env_profile": "lean4.29.1_mathlib_5e932f97",
        "header": "import Mathlib",
        "source": "unit",
    }
    data.update(updates)
    return TheoremSpec(**data)


def test_validate_theorem_env_profile_rejects_default_profile() -> None:
    with pytest.raises(EnvProfileValidationError, match="default"):
        validate_theorem_env_profile(_theorem(env_profile="default"))


def test_validate_theorem_env_profile_accepts_matching_registry() -> None:
    profile = EnvProfile(
        lean_version="4.29.1",
        mathlib_commit="5e932f97",
        header="import Mathlib",
        header_hash=header_hash("import Mathlib"),
    )

    validate_theorem_env_profile(
        _theorem(),
        profiles={"lean4.29.1_mathlib_5e932f97": profile},
    )


def test_validate_theorem_env_profile_rejects_header_mismatch() -> None:
    profile = EnvProfile(
        lean_version="4.29.1",
        mathlib_commit="5e932f97",
        header="import Mathlib.Data.Nat.Basic",
        header_hash=header_hash("import Mathlib.Data.Nat.Basic"),
    )

    with pytest.raises(EnvProfileValidationError, match="header"):
        validate_theorem_env_profile(
            _theorem(),
            profiles={"lean4.29.1_mathlib_5e932f97": profile},
        )


def test_validate_theorem_batch_rejects_mixed_profiles() -> None:
    with pytest.raises(EnvProfileValidationError, match="mixed"):
        validate_theorem_batch_env_profiles(
            [
                _theorem(env_profile="env-a"),
                _theorem(env_profile="env-b"),
            ]
        )


def test_validate_theorem_batch_rejects_backend_mismatch() -> None:
    with pytest.raises(EnvProfileValidationError, match="backend"):
        validate_theorem_batch_env_profiles(
            [_theorem(env_profile="env-a")],
            backend_env_profile="env-b",
        )
