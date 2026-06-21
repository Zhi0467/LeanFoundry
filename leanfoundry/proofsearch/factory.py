"""Public search-engine factory."""

from __future__ import annotations

from leanfoundry.proofsearch._selection import (
    BestFirstSelection,
    PuctSelection,
)
from leanfoundry.proofsearch.and_or import AndOrSearchEngine
from leanfoundry.proofsearch.base import (
    SearchAlgorithm,
    SearchConfig,
    SearchEngine,
)
from leanfoundry.proofsearch.direct import DirectSearchEngine


def build_engine(config: SearchConfig) -> SearchEngine:
    """Build the search engine selected by ``config.algorithm``."""

    if config.algorithm is SearchAlgorithm.DIRECT:
        return DirectSearchEngine()
    if config.algorithm is SearchAlgorithm.SELF_CORRECT:
        return DirectSearchEngine(self_correct=True)
    if config.algorithm in {
        SearchAlgorithm.PUCT_TREE,
        SearchAlgorithm.AND_OR_TREE,
    }:
        # AND_OR_TREE is the generic tree-shape alias for now; PUCT is the
        # default selection peg until the alias gets its own config surface.
        return AndOrSearchEngine(
            PuctSelection(
                c_explore=config.puct_exploration_weight,
            )
        )
    if config.algorithm is SearchAlgorithm.BEST_FIRST:
        return AndOrSearchEngine(
            BestFirstSelection(
                missing_value_score=config.best_first_missing_value_score,
            )
        )
    raise NotImplementedError(
        f"search algorithm is not implemented: {config.algorithm}"
    )


__all__ = [
    "build_engine",
]
