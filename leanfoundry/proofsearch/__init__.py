"""Proof-search contracts."""

from leanfoundry.proofsearch.base import (
    SearchAlgorithm,
    SearchConfig,
    SearchEngine,
    SearchResult,
    SearchStatus,
)
from leanfoundry.proofsearch.driver import run_search_batch
from leanfoundry.proofsearch.factory import build_engine
from leanfoundry.proofsearch.provenance import should_try_negation

__all__ = [
    "SearchAlgorithm",
    "SearchConfig",
    "SearchEngine",
    "SearchResult",
    "SearchStatus",
    "build_engine",
    "run_search_batch",
    "should_try_negation",
]
