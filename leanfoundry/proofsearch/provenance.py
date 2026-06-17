"""Public provenance gates for search behavior."""

from __future__ import annotations

from collections.abc import Collection

from leanfoundry.proofsearch._provenance import DEFAULT_NEGATION_SOURCES
from leanfoundry.schemas import TheoremSpec


def should_try_negation(
    spec: TheoremSpec,
    *,
    enabled_sources: Collection[str] = DEFAULT_NEGATION_SOURCES,
) -> bool:
    """Return whether negation pruning should be enabled for a theorem."""

    normalized_sources = {source.lower() for source in enabled_sources}
    return spec.source.lower() in normalized_sources
