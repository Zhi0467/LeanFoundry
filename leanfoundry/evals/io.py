"""Benchmark loading and eval artifact file writing."""

from __future__ import annotations

import json
import hashlib
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from leanfoundry.env_profiles import validate_theorem_batch_env_profiles
from leanfoundry.evals.adapters import (
    MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT,
    MINIF2F_LEAN4_ROW_FORMAT,
    PROOFNET_LEAN4_ROW_FORMAT,
    PUTNAMBENCH_LEAN4_ROW_FORMAT,
    make_matholympiadbench_lean4_row_adapter,
    make_minif2f_lean4_row_adapter,
    make_proofnet_lean4_row_adapter,
    make_putnambench_lean4_row_adapter,
)
from leanfoundry.proofsearch import SearchResult
from leanfoundry.schemas import (
    BenchmarkCompatibility,
    BenchmarkManifest,
    EnvProfile,
    EvalArtifactManifest,
    TheoremSpec,
)


@dataclass(frozen=True, slots=True)
class EvalArtifactPaths:
    """Paths and hashes for materialized eval artifacts."""

    manifest_path: Path
    results_path: Path
    benchmark_path: Path
    report_path: Path
    hashes: Mapping[str, str]


SourceFetcher = Callable[[str], str]
BenchmarkRowAdapter = Callable[[Mapping[str, Any]], TheoremSpec]
_LEANFOUNDRY_JSONL = "leanfoundry_jsonl"


def load_benchmark_source(
    manifest: BenchmarkManifest,
    *,
    profiles: Mapping[str, EnvProfile] | None = None,
    source_fetcher: SourceFetcher | None = None,
    row_adapters: Mapping[str, BenchmarkRowAdapter] | None = None,
) -> list[TheoremSpec]:
    """Load theorem specs from ``manifest.source`` and validate them.

    Supported source forms are local paths, ``file://`` URIs, ``http(s)://``
    JSONL URLs, and explicit Hugging Face file URIs:
    ``hf://repo`` or ``hf://org/repo`` with ``?path=...`` and optional
    ``revision=...``. ``manifest.benchmark_commit`` is used as the HF revision
    when the URI does not include one.
    """

    if manifest.compatibility is BenchmarkCompatibility.INCOMPATIBLE:
        raise ValueError("benchmark manifest is marked incompatible")
    text = _read_benchmark_source(
        manifest,
        source_fetcher=source_fetcher or _fetch_url_text,
    )
    theorems = _parse_theorem_jsonl(
        text,
        source_label=manifest.source,
        row_adapter=_row_adapter_for_manifest(
            manifest,
            profiles=profiles,
            row_adapters=row_adapters,
        ),
    )
    validate_benchmark_theorems(theorems, manifest, profiles=profiles)
    return theorems


def load_benchmark_jsonl(
    path: str | Path,
    manifest: BenchmarkManifest,
    *,
    profiles: Mapping[str, EnvProfile] | None = None,
    row_adapters: Mapping[str, BenchmarkRowAdapter] | None = None,
) -> list[TheoremSpec]:
    """Load theorem specs from JSONL and validate against a manifest."""

    if manifest.compatibility is BenchmarkCompatibility.INCOMPATIBLE:
        raise ValueError("benchmark manifest is marked incompatible")
    theorem_path = Path(path)
    theorems = _parse_theorem_jsonl(
        theorem_path.read_text(),
        source_label=str(theorem_path),
        row_adapter=_row_adapter_for_manifest(
            manifest,
            profiles=profiles,
            row_adapters=row_adapters,
        ),
    )
    validate_benchmark_theorems(theorems, manifest, profiles=profiles)
    return theorems


def validate_benchmark_theorems(
    theorems: Sequence[TheoremSpec],
    manifest: BenchmarkManifest,
    *,
    profiles: Mapping[str, EnvProfile] | None = None,
) -> None:
    """Validate loaded theorem rows against benchmark metadata."""

    validate_theorem_batch_env_profiles(
        theorems,
        profiles=profiles,
        backend_env_profile=manifest.env_profile,
    )
    if manifest.theorem_count is not None:
        if len(theorems) != manifest.theorem_count:
            raise ValueError(
                "benchmark theorem_count mismatch: "
                f"expected {manifest.theorem_count}, got {len(theorems)}"
            )


def write_eval_artifacts(
    output_dir: str | Path,
    *,
    manifest: EvalArtifactManifest,
    results: Sequence[SearchResult],
    theorems: Sequence[TheoremSpec],
) -> EvalArtifactPaths:
    """Write manifest, per-theorem results, benchmark copy, and report."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "eval_manifest.json"
    results_path = directory / "results.jsonl"
    benchmark_path = directory / "benchmark.jsonl"
    report_path = directory / "report.md"

    _write_text(
        results_path,
        "".join(f"{result.model_dump_json()}\n" for result in results),
    )
    _write_text(
        benchmark_path,
        "".join(f"{theorem.model_dump_json()}\n" for theorem in theorems),
    )
    _write_text(report_path, render_eval_report(manifest))
    hashes = {
        "results_sha256": _sha256_file(results_path),
        "benchmark_sha256": _sha256_file(benchmark_path),
        "report_sha256": _sha256_file(report_path),
    }
    manifest_with_hashes = manifest.model_copy(
        update={"metrics": {**manifest.metrics, **hashes}}
    )
    _write_text(
        manifest_path,
        f"{manifest_with_hashes.model_dump_json(indent=2)}\n",
    )
    return EvalArtifactPaths(
        manifest_path=manifest_path,
        results_path=results_path,
        benchmark_path=benchmark_path,
        report_path=report_path,
        hashes=hashes,
    )


def render_eval_report(manifest: EvalArtifactManifest) -> str:
    """Render a compact markdown report from an eval manifest."""

    lines = [
        f"# Eval {manifest.run_id}",
        "",
        f"- Benchmark: {manifest.benchmark}",
        f"- Mode: {manifest.mode.value}",
        f"- Model: {manifest.model_checkpoint}",
        f"- Env profile: {manifest.env_profile}",
    ]
    if manifest.benchmark_commit:
        lines.append(f"- Benchmark commit: {manifest.benchmark_commit}")
    lines.extend(["", "## Metrics", ""])
    for key in sorted(manifest.metrics):
        lines.append(f"- `{key}`: {manifest.metrics[key]}")
    if manifest.solved_at_budget:
        lines.extend(["", "## Solved At Budget", ""])
        for budget, value in sorted(manifest.solved_at_budget.items()):
            lines.append(f"- `{budget}`: {value}")
    if manifest.k_values:
        lines.extend(["", "## Pass@k", ""])
        for k in manifest.k_values:
            key = f"pass_at_{k}"
            if key in manifest.metrics:
                lines.append(f"- `{key}`: {manifest.metrics[key]}")
    return "\n".join(lines) + "\n"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text)


def _read_benchmark_source(
    manifest: BenchmarkManifest,
    *,
    source_fetcher: SourceFetcher,
) -> str:
    source = manifest.source
    parsed = urllib.parse.urlparse(source)
    if not parsed.scheme:
        return Path(source).read_text()
    if parsed.scheme == "file":
        return _path_from_file_uri(parsed).read_text()
    if parsed.scheme in {"http", "https"}:
        return source_fetcher(source)
    if parsed.scheme == "hf":
        return source_fetcher(_hf_resolved_url(parsed, manifest))
    raise ValueError(f"unsupported benchmark source scheme: {parsed.scheme}")


def _path_from_file_uri(parsed: urllib.parse.ParseResult) -> Path:
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        return Path(f"//{parsed.netloc}{urllib.parse.unquote(parsed.path)}")
    return Path(urllib.parse.unquote(parsed.path))


def _hf_resolved_url(
    parsed: urllib.parse.ParseResult,
    manifest: BenchmarkManifest,
) -> str:
    repo_id = _hf_repo_id(parsed)
    query = urllib.parse.parse_qs(parsed.query)
    paths = query.get("path", [])
    if len(paths) != 1 or not paths[0]:
        raise ValueError("hf benchmark source requires exactly one path query")
    revisions = query.get("revision", [])
    if len(revisions) > 1:
        raise ValueError("hf benchmark source has multiple revisions")
    revision = (
        revisions[0]
        if revisions
        else manifest.benchmark_commit or "main"
    )
    file_path = paths[0].lstrip("/")
    encoded_repo = "/".join(
        urllib.parse.quote(part, safe="")
        for part in repo_id.split("/")
    )
    encoded_revision = urllib.parse.quote(revision, safe="")
    encoded_file_path = "/".join(
        urllib.parse.quote(part, safe="")
        for part in file_path.split("/")
    )
    return (
        "https://huggingface.co/datasets/"
        f"{encoded_repo}/resolve/{encoded_revision}/{encoded_file_path}"
    )


def _hf_repo_id(parsed: urllib.parse.ParseResult) -> str:
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc:
        parts.insert(0, parsed.netloc)
    repo_id = "/".join(parts)
    if not repo_id:
        raise ValueError("hf benchmark source requires a repository id")
    return repo_id


def _fetch_url_text(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def _row_adapter_for_manifest(
    manifest: BenchmarkManifest,
    *,
    profiles: Mapping[str, EnvProfile] | None,
    row_adapters: Mapping[str, BenchmarkRowAdapter] | None,
) -> BenchmarkRowAdapter | None:
    if manifest.row_format == _LEANFOUNDRY_JSONL:
        return None
    if row_adapters is not None and manifest.row_format in row_adapters:
        return row_adapters[manifest.row_format]
    if manifest.row_format == MINIF2F_LEAN4_ROW_FORMAT:
        return make_minif2f_lean4_row_adapter(
            env_profile=manifest.env_profile,
            expected_split=manifest.split,
        )
    if manifest.row_format == MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT:
        return make_matholympiadbench_lean4_row_adapter(
            env_profile=manifest.env_profile,
            expected_split=manifest.split,
        )
    if manifest.row_format == PROOFNET_LEAN4_ROW_FORMAT:
        return make_proofnet_lean4_row_adapter(
            env_profile=manifest.env_profile,
            expected_split=manifest.split,
        )
    if manifest.row_format == PUTNAMBENCH_LEAN4_ROW_FORMAT:
        return make_putnambench_lean4_row_adapter(
            env_profile=manifest.env_profile,
            header=_header_from_profile(manifest, profiles),
            expected_split=manifest.split,
        )
    if row_adapters is None or manifest.row_format not in row_adapters:
        raise ValueError(
            "no benchmark row adapter registered for row_format "
            f"{manifest.row_format!r}"
        )
    return row_adapters[manifest.row_format]


def _header_from_profile(
    manifest: BenchmarkManifest,
    profiles: Mapping[str, EnvProfile] | None,
) -> str:
    if profiles is None or manifest.env_profile not in profiles:
        raise ValueError(
            "putnambench_lean4_jsonl requires an EnvProfile registry entry "
            f"for env_profile {manifest.env_profile!r}"
        )
    return profiles[manifest.env_profile].header


def _parse_theorem_jsonl(
    text: str,
    *,
    source_label: str,
    row_adapter: BenchmarkRowAdapter | None,
) -> list[TheoremSpec]:
    theorems: list[TheoremSpec] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            if row_adapter is None:
                theorem = TheoremSpec.model_validate_json(line)
            else:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("adapted benchmark row must be an object")
                theorem = row_adapter(row)
            theorems.append(theorem)
        except Exception as error:
            raise ValueError(
                f"invalid theorem JSONL in {source_label} at line "
                f"{line_number}"
            ) from error
    return theorems


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "BenchmarkRowAdapter",
    "EvalArtifactPaths",
    "load_benchmark_source",
    "load_benchmark_jsonl",
    "render_eval_report",
    "validate_benchmark_theorems",
    "write_eval_artifacts",
]
