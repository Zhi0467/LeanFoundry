from __future__ import annotations

import json

import pytest

from leanfoundry.env_profiles import header_hash
from leanfoundry.evals import (
    MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT,
    MINIF2F_LEAN4_ROW_FORMAT,
    PROOFNET_LEAN4_ROW_FORMAT,
    PUTNAMBENCH_LEAN4_ROW_FORMAT,
    load_benchmark_jsonl,
    load_benchmark_source,
    write_eval_artifacts,
)
from leanfoundry.proofsearch import SearchResult, SearchStatus
from leanfoundry.schemas import (
    BenchmarkCompatibility,
    BenchmarkManifest,
    EnvProfile,
    EvalArtifactManifest,
    EvalMode,
    TheoremSpec,
)


def _manifest(**updates) -> BenchmarkManifest:
    data = {
        "id": "toy-valid-v1",
        "name": "toy",
        "split": "valid",
        "source": "file://toy.jsonl",
        "env_profile": "env",
        "compatibility": BenchmarkCompatibility.COMPATIBLE,
        "contamination_policy": "eval-only",
        "fixed_assignment_id": "toy-valid-fixed",
        "theorem_count": 1,
    }
    data.update(updates)
    return BenchmarkManifest(**data)


def _theorem(**updates) -> TheoremSpec:
    data = {
        "id": "thm",
        "theorem_name": "thm",
        "lean_statement": "theorem thm : True := by",
        "env_profile": "env",
        "header": "import Mathlib",
        "source": "unit",
    }
    data.update(updates)
    return TheoremSpec(**data)


def _profile(header: str = "import Mathlib") -> EnvProfile:
    return EnvProfile(
        lean_version="4.29.1",
        mathlib_commit="5e932f97",
        header=header,
        header_hash=header_hash(header),
    )


def test_load_benchmark_jsonl_validates_manifest(tmp_path) -> None:
    path = tmp_path / "toy.jsonl"
    path.write_text(f"{_theorem().model_dump_json()}\n")

    theorems = load_benchmark_jsonl(path, _manifest())

    assert [theorem.id for theorem in theorems] == ["thm"]


def test_load_benchmark_source_loads_file_uri(tmp_path) -> None:
    path = tmp_path / "toy.jsonl"
    path.write_text(f"{_theorem().model_dump_json()}\n")

    theorems = load_benchmark_source(
        _manifest(source=path.as_uri()),
    )

    assert [theorem.id for theorem in theorems] == ["thm"]


def test_load_benchmark_source_loads_https_jsonl() -> None:
    fetched_urls = []

    def fetch(url: str) -> str:
        fetched_urls.append(url)
        return f"{_theorem().model_dump_json()}\n"

    theorems = load_benchmark_source(
        _manifest(source="https://bench.example/toy.jsonl"),
        source_fetcher=fetch,
    )

    assert fetched_urls == ["https://bench.example/toy.jsonl"]
    assert [theorem.id for theorem in theorems] == ["thm"]


def test_load_benchmark_source_resolves_huggingface_file_uri() -> None:
    fetched_urls = []

    def fetch(url: str) -> str:
        fetched_urls.append(url)
        return f"{_theorem().model_dump_json()}\n"

    theorems = load_benchmark_source(
        _manifest(
            source="hf://org/repo?path=data/test split.jsonl",
            benchmark_commit="abc123",
        ),
        source_fetcher=fetch,
    )

    assert fetched_urls == [
        "https://huggingface.co/datasets/"
        "org/repo/resolve/abc123/data/test%20split.jsonl"
    ]
    assert [theorem.id for theorem in theorems] == ["thm"]


def test_load_benchmark_source_uses_manifest_row_adapter() -> None:
    def fetch(url: str) -> str:
        assert url == "https://bench.example/custom.jsonl"
        return (
            '{"id":"row-1","name":"toy_thm","formal":"theorem toy_thm : '
            'True := by","profile":"env","imports":"import Mathlib"}\n'
        )

    def adapt(row) -> TheoremSpec:
        return TheoremSpec(
            id=str(row["id"]),
            theorem_name=str(row["name"]),
            lean_statement=str(row["formal"]),
            env_profile=str(row["profile"]),
            header=str(row["imports"]),
            source="custom",
        )

    theorems = load_benchmark_source(
        _manifest(
            source="https://bench.example/custom.jsonl",
            row_format="custom_jsonl",
        ),
        source_fetcher=fetch,
        row_adapters={"custom_jsonl": adapt},
    )

    assert len(theorems) == 1
    assert theorems[0].id == "row-1"
    assert theorems[0].theorem_name == "toy_thm"


def test_load_benchmark_source_uses_builtin_minif2f_adapter() -> None:
    def fetch(url: str) -> str:
        assert url == "https://bench.example/minif2f.jsonl"
        return (
            '{"id":"algebra_2varlineareq_xpeeq7_2xpeeq3_eeq11_xeqn4",'
            '"split":"test",'
            '"informal_stmt":"Solve a linear equation.",'
            '"formal_statement":"theorem '
            'algebra_2varlineareq_xpeeq7_2xpeeq3_eeq11_xeqn4 : '
            'True := sorry",'
            '"header":"import Mathlib"}\n'
        )

    theorems = load_benchmark_source(
        _manifest(
            source="https://bench.example/minif2f.jsonl",
            name="miniF2F",
            split="test",
            row_format=MINIF2F_LEAN4_ROW_FORMAT,
        ),
        source_fetcher=fetch,
    )

    assert len(theorems) == 1
    assert theorems[0].id == (
        "miniF2F:test:algebra_2varlineareq_xpeeq7_2xpeeq3_eeq11_xeqn4"
    )
    assert theorems[0].theorem_name == (
        "algebra_2varlineareq_xpeeq7_2xpeeq3_eeq11_xeqn4"
    )
    assert theorems[0].env_profile == "env"
    assert theorems[0].source == "miniF2F/test"
    assert theorems[0].informal_statement == "Solve a linear equation."


def test_load_benchmark_source_rejects_minif2f_split_mismatch() -> None:
    with pytest.raises(ValueError, match="invalid theorem JSONL"):
        load_benchmark_source(
            _manifest(
                source="https://bench.example/minif2f.jsonl",
                split="valid",
                row_format=MINIF2F_LEAN4_ROW_FORMAT,
            ),
            source_fetcher=lambda _url: (
                '{"id":"thm","split":"test","formal_statement":'
                '"theorem thm : True := sorry","header":"import Mathlib"}\n'
            ),
        )


def test_load_benchmark_source_allows_minif2f_adapter_override() -> None:
    def adapt(row) -> TheoremSpec:
        return _theorem(id=str(row["name"]), source="override")

    theorems = load_benchmark_source(
        _manifest(
            source="https://bench.example/minif2f.jsonl",
            row_format=MINIF2F_LEAN4_ROW_FORMAT,
        ),
        source_fetcher=lambda _url: '{"name":"custom"}\n',
        row_adapters={MINIF2F_LEAN4_ROW_FORMAT: adapt},
    )

    assert theorems[0].id == "custom"
    assert theorems[0].source == "override"


def test_load_benchmark_source_uses_builtin_matholympiadbench_adapter(
) -> None:
    def fetch(url: str) -> str:
        assert url == "https://bench.example/mobench.jsonl"
        return (
            '{"name":"Imo2006P3",'
            '"problem_id":"Imo2006P3",'
            '"formal_statement":"noncomputable abbrev solution : '
            'Nat := 0\\n\\ntheorem imo2006_p3 : True := by sorry",'
            '"header":"import Mathlib\\nimport Aesop\\n",'
            '"informal_prefix":"/-! IMO 2006, Problem 3 -/",'
            '"tags":["algebra"],'
            '"split":"test",'
            '"category":"algebra"}\n'
        )

    theorems = load_benchmark_source(
        _manifest(
            source="https://bench.example/mobench.jsonl",
            name="MathOlympiadBench",
            split="test",
            row_format=MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT,
        ),
        source_fetcher=fetch,
    )

    assert len(theorems) == 1
    theorem = theorems[0]
    assert theorem.id == "MathOlympiadBench:test:Imo2006P3"
    assert theorem.theorem_name == "Imo2006P3"
    assert theorem.env_profile == "env"
    assert theorem.header == "import Mathlib\nimport Aesop\n"
    assert theorem.source == "MathOlympiadBench/test"
    assert theorem.informal_statement == "/-! IMO 2006, Problem 3 -/"
    assert theorem.lean_statement.startswith("noncomputable abbrev solution")


def test_load_benchmark_source_rejects_matholympiadbench_split_mismatch(
) -> None:
    with pytest.raises(ValueError, match="invalid theorem JSONL"):
        load_benchmark_source(
            _manifest(
                source="https://bench.example/mobench.jsonl",
                name="MathOlympiadBench",
                split="valid",
                row_format=MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT,
            ),
            source_fetcher=lambda _url: (
                '{"name":"Imo2006P3","formal_statement":'
                '"theorem imo2006_p3 : True := by sorry",'
                '"header":"import Mathlib","split":"test"}\n'
            ),
        )


def test_load_benchmark_source_uses_builtin_proofnet_adapter() -> None:
    def fetch(url: str) -> str:
        assert url == "https://bench.example/proofnet/test.jsonl"
        return (
            '{"name":"exercise_1_13b",'
            '"split":"test",'
            '"informal_prefix":"/-- If Im(f) is constant, f is constant. -/",'
            '"formal_statement":"theorem exercise_1_13b {f : ℂ → ℂ} '
            '(Ω : Set ℂ) (a b : Ω) (h : IsOpen Ω) :\\n  f a = f b :=",'
            '"goal":"⊢ f ↑a = f ↑b",'
            '"header":"import Mathlib\\n\\nopen Complex\\n"}\n'
        )

    theorems = load_benchmark_source(
        _manifest(
            source="https://bench.example/proofnet/test.jsonl",
            name="ProofNet",
            split="test",
            row_format=PROOFNET_LEAN4_ROW_FORMAT,
        ),
        source_fetcher=fetch,
    )

    assert len(theorems) == 1
    theorem = theorems[0]
    assert theorem.id == "ProofNet:test:exercise_1_13b"
    assert theorem.theorem_name == "exercise_1_13b"
    assert theorem.env_profile == "env"
    assert theorem.header == "import Mathlib\n\nopen Complex\n"
    assert theorem.source == "ProofNet/test"
    assert theorem.informal_statement == (
        "/-- If Im(f) is constant, f is constant. -/"
    )
    assert theorem.lean_statement.endswith(":= by\n  sorry")


def test_load_benchmark_source_rejects_proofnet_non_placeholder_statement(
) -> None:
    with pytest.raises(ValueError, match="invalid theorem JSONL"):
        load_benchmark_source(
            _manifest(
                source="https://bench.example/proofnet/test.jsonl",
                name="ProofNet",
                split="test",
                row_format=PROOFNET_LEAN4_ROW_FORMAT,
            ),
            source_fetcher=lambda _url: (
                '{"name":"exercise_1_13b","split":"test",'
                '"formal_statement":"theorem exercise_1_13b : True := '
                'by trivial",'
                '"header":"import Mathlib"}\n'
            ),
        )


def test_load_benchmark_source_rejects_proofnet_split_mismatch() -> None:
    with pytest.raises(ValueError, match="invalid theorem JSONL"):
        load_benchmark_source(
            _manifest(
                source="https://bench.example/proofnet/test.jsonl",
                name="ProofNet",
                split="valid",
                row_format=PROOFNET_LEAN4_ROW_FORMAT,
            ),
            source_fetcher=lambda _url: (
                '{"name":"exercise_1_13b","split":"test",'
                '"formal_statement":"theorem exercise_1_13b : True :=",'
                '"header":"import Mathlib"}\n'
            ),
        )


def test_load_benchmark_source_uses_builtin_putnambench_adapter() -> None:
    def fetch(url: str) -> str:
        assert url == "https://bench.example/putnam.jsonl"
        return (
            '{"problem_name":"putnam_1962_a2",'
            '"formal_statement":"abbrev putnam_1962_a2_solution : '
            'Set Nat := sorry\\n'
            'theorem putnam_1962_a2 : True := sorry",'
            '"informal_statement":"Find every real-valued function.",'
            '"informal_solution":"None.",'
            '"tags":["analysis"],'
            '"split":"test"}\n'
        )

    theorems = load_benchmark_source(
        _manifest(
            source="https://bench.example/putnam.jsonl",
            name="PutnamBench",
            split="test",
            row_format=PUTNAMBENCH_LEAN4_ROW_FORMAT,
        ),
        profiles={"env": _profile()},
        source_fetcher=fetch,
    )

    assert len(theorems) == 1
    theorem = theorems[0]
    assert theorem.id == "PutnamBench:test:putnam_1962_a2"
    assert theorem.theorem_name == "putnam_1962_a2"
    assert theorem.env_profile == "env"
    assert theorem.header == "import Mathlib"
    assert theorem.source == "PutnamBench/test"
    assert theorem.informal_statement == "Find every real-valued function."
    assert theorem.lean_statement.startswith(
        "abbrev putnam_1962_a2_solution"
    )


def test_load_benchmark_source_requires_putnambench_profile_header() -> None:
    with pytest.raises(ValueError, match="EnvProfile registry"):
        load_benchmark_source(
            _manifest(
                source="https://bench.example/putnam.jsonl",
                name="PutnamBench",
                split="test",
                row_format=PUTNAMBENCH_LEAN4_ROW_FORMAT,
            ),
            source_fetcher=lambda _url: (
                '{"problem_name":"putnam_1962_a1","formal_statement":'
                '"theorem putnam_1962_a1 : True := sorry",'
                '"split":"test"}\n'
            ),
        )


def test_load_benchmark_source_rejects_putnambench_split_mismatch() -> None:
    with pytest.raises(ValueError, match="invalid theorem JSONL"):
        load_benchmark_source(
            _manifest(
                source="https://bench.example/putnam.jsonl",
                name="PutnamBench",
                split="valid",
                row_format=PUTNAMBENCH_LEAN4_ROW_FORMAT,
            ),
            profiles={"env": _profile()},
            source_fetcher=lambda _url: (
                '{"problem_name":"putnam_1962_a1","formal_statement":'
                '"theorem putnam_1962_a1 : True := sorry",'
                '"split":"test"}\n'
            ),
        )


def test_load_benchmark_source_rejects_missing_row_adapter() -> None:
    with pytest.raises(ValueError, match="row_format"):
        load_benchmark_source(
            _manifest(
                source="https://bench.example/custom.jsonl",
                row_format="custom_jsonl",
            ),
            source_fetcher=lambda _url: "{}\n",
        )


def test_load_benchmark_source_rejects_implicit_hf_path() -> None:
    with pytest.raises(ValueError, match="path query"):
        load_benchmark_source(_manifest(source="hf://org/repo/data.jsonl"))


def test_load_benchmark_jsonl_rejects_manifest_mismatch(tmp_path) -> None:
    path = tmp_path / "toy.jsonl"
    path.write_text(f"{_theorem(env_profile='other').model_dump_json()}\n")

    with pytest.raises(ValueError, match="backend"):
        load_benchmark_jsonl(path, _manifest())


def test_load_benchmark_jsonl_validates_profile_registry(tmp_path) -> None:
    path = tmp_path / "toy.jsonl"
    path.write_text(f"{_theorem().model_dump_json()}\n")

    with pytest.raises(ValueError, match="header"):
        load_benchmark_jsonl(
            path,
            _manifest(),
            profiles={"env": _profile(header="import Mathlib.Data.Nat.Basic")},
        )


def test_load_benchmark_jsonl_rejects_incompatible_manifest(tmp_path) -> None:
    path = tmp_path / "toy.jsonl"
    path.write_text(f"{_theorem().model_dump_json()}\n")

    with pytest.raises(ValueError, match="incompatible"):
        load_benchmark_jsonl(
            path,
            _manifest(compatibility=BenchmarkCompatibility.INCOMPATIBLE),
        )


def test_write_eval_artifacts_materializes_hashes_and_report(tmp_path) -> None:
    manifest = EvalArtifactManifest(
        run_id="eval-1",
        infra_git_sha="infra",
        model_checkpoint="ckpt",
        env_profile="env",
        benchmark="toy:valid",
        mode=EvalMode.STATE_TOKEN_SEARCH,
        metrics={"proved_rate": 1.0},
    )

    paths = write_eval_artifacts(
        tmp_path,
        manifest=manifest,
        results=[SearchResult(status=SearchStatus.PROVED)],
        theorems=[_theorem()],
    )

    written_manifest = json.loads(paths.manifest_path.read_text())
    assert paths.results_path.read_text().count("\n") == 1
    assert paths.benchmark_path.read_text().count("\n") == 1
    assert "# Eval eval-1" in paths.report_path.read_text()
    assert set(paths.hashes) == {
        "benchmark_sha256",
        "report_sha256",
        "results_sha256",
    }
    assert written_manifest["metrics"]["results_sha256"] == (
        paths.hashes["results_sha256"]
    )
