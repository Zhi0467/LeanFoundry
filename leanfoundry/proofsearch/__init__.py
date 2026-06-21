"""Proof-search contracts."""

from leanfoundry.proofsearch.base import (
    SearchAlgorithm,
    SearchAttemptContext,
    SearchConfig,
    SearchEngine,
    SearchResult,
    SearchStatus,
)
from leanfoundry.proofsearch.driver import run_search_batch
from leanfoundry.proofsearch.factory import build_engine
from leanfoundry.proofsearch.extraction import (
    ExtractionContext,
    extract_training_artifacts,
    extraction_context_for_theorem,
)
from leanfoundry.proofsearch.provenance import should_try_negation

__all__ = [
    "ExtractionContext",
    "SearchAlgorithm",
    "SearchAttemptContext",
    "SearchConfig",
    "SearchEngine",
    "SearchResult",
    "SearchStatus",
    "build_engine",
    "extract_training_artifacts",
    "extraction_context_for_theorem",
    "run_search_batch",
    "should_try_negation",
]
