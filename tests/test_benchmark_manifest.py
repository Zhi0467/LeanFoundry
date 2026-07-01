from __future__ import annotations

import pytest
from pydantic import ValidationError

from leanfoundry.env_profiles import validate_theorem_batch_env_profiles
from leanfoundry.schemas import (
    BenchmarkCompatibility,
    BenchmarkManifest,
    TheoremSpec,
)


def test_benchmark_manifest_records_split_profile_and_policy() -> None:
    manifest = BenchmarkManifest(
        id="miniF2F-test-v1",
        name="miniF2F",
        split="test",
        source="hf://miniF2F",
        env_profile="lean4.29.1_mathlib_5e932f97",
        compatibility=BenchmarkCompatibility.NEEDS_REVERIFY,
        contamination_policy="eval-only; reject theorem/proof overlap",
        fixed_assignment_id="miniF2F-test-2026-06-30",
        benchmark_commit="abc123",
        theorem_count=244,
    )

    assert manifest.split == "test"
    assert manifest.row_format == "leanfoundry_jsonl"
    assert manifest.compatibility is BenchmarkCompatibility.NEEDS_REVERIFY


def test_benchmark_manifest_rejects_negative_theorem_count() -> None:
    with pytest.raises(ValidationError):
        BenchmarkManifest(
            id="bad",
            name="bad",
            split="test",
            source="file://bad",
            env_profile="env",
            compatibility=BenchmarkCompatibility.COMPATIBLE,
            contamination_policy="none",
            fixed_assignment_id="fixed",
            theorem_count=-1,
        )


def test_benchmark_manifest_env_profile_matches_loaded_theorems() -> None:
    manifest = BenchmarkManifest(
        id="toy-test",
        name="toy",
        split="test",
        source="file://toy",
        env_profile="env-a",
        compatibility=BenchmarkCompatibility.COMPATIBLE,
        contamination_policy="fixed heldout",
        fixed_assignment_id="toy-test-fixed",
    )
    theorem = TheoremSpec(
        lean_statement="theorem t : True := by",
        env_profile="env-a",
        header="import Mathlib",
    )

    validate_theorem_batch_env_profiles(
        [theorem],
        backend_env_profile=manifest.env_profile,
    )
