"""Concrete AND/OR tree-search engine."""

from __future__ import annotations

from leanfoundry.env_backend import EnvBackend
from leanfoundry.policy import PolicyClient, ValueClient
from leanfoundry.proofsearch._and_or_utils import (
    operational_result,
    verify_extracted_tree,
)
from leanfoundry.proofsearch._backprop import backpropagate_actions
from leanfoundry.proofsearch._budgets import has_tactic_budget
from leanfoundry.proofsearch._common import (
    make_search_id,
    theorem_name_for_verify,
)
from leanfoundry.proofsearch._evaluation import evaluate_new_children
from leanfoundry.proofsearch._expansion import expand_state
from leanfoundry.proofsearch._extract import (
    UnsupportedProofExtraction,
    extract_proof_tree,
)
from leanfoundry.proofsearch._selection import SelectionStrategy
from leanfoundry.proofsearch._tree import StateNodeStatus
from leanfoundry.proofsearch._tree_init import initialize_search_tree
from leanfoundry.proofsearch.base import (
    SearchConfig,
    SearchEngine,
    SearchResult,
    SearchStatus,
)
from leanfoundry.schemas import TheoremSpec


class AndOrSearchEngine(SearchEngine):
    """AND/OR tree search with an injected selection strategy."""

    def __init__(self, selection_strategy: SelectionStrategy) -> None:
        self.selection_strategy = selection_strategy

    async def search(
        self,
        theorem: TheoremSpec,
        *,
        policy_client: PolicyClient,
        value_client: ValueClient | None,
        env_backend: EnvBackend,
        config: SearchConfig,
    ) -> SearchResult:
        """Run AND/OR tree search for one theorem."""

        theorem_name = theorem_name_for_verify(theorem)
        if theorem_name is None:
            return SearchResult(
                theorem_id=theorem.id,
                status=SearchStatus.ERROR,
                diagnostics={
                    "error": "theorem_name is required for verification"
                },
            )

        search_id = make_search_id(theorem, kind="and_or")
        try:
            limits = await env_backend.limits()
            initialized = await initialize_search_tree(
                env_backend,
                theorem,
                search_id=search_id,
            )
            tree = initialized.tree

            while (
                tree.root.status is StateNodeStatus.OPEN
                and has_tactic_budget(config, tree.tactic_calls_made)
            ):
                frontier = self.selection_strategy.select(tree)
                if frontier is None:
                    break
                outcome = await expand_state(
                    tree,
                    frontier,
                    policy_client=policy_client,
                    env_backend=env_backend,
                    config=config,
                    max_tactics_per_step_item=(
                        limits.max_tactics_per_step_item
                    ),
                )
                if outcome.operational_status is not None:
                    return operational_result(
                        theorem,
                        tree.tactic_calls_made,
                        outcome.operational_status,
                        frontier.failure_message,
                    )
                if not outcome.actions and outcome.tactic_calls_used == 0:
                    frontier.failure_message = "no new tactics to try"
                    break
                await evaluate_new_children(
                    outcome.actions,
                    value_client=value_client,
                )
                backpropagate_actions(
                    outcome.actions,
                    update_values=True,
                )

            if tree.root.status is StateNodeStatus.PROVED:
                try:
                    proof_tree = extract_proof_tree(tree, theorem)
                except UnsupportedProofExtraction as error:
                    return SearchResult(
                        theorem_id=theorem.id,
                        status=SearchStatus.ERROR,
                        search_budget_used=tree.tactic_calls_made,
                        diagnostics={"extraction_error": str(error)},
                    )
                return await verify_extracted_tree(
                    theorem,
                    env_backend,
                    search_id,
                    theorem_name,
                    proof_tree,
                    tree.tactic_calls_made,
                )

            return SearchResult(
                theorem_id=theorem.id,
                status=SearchStatus.EXHAUSTED,
                search_budget_used=tree.tactic_calls_made,
                diagnostics={"root_status": tree.root.status},
            )
        finally:
            await env_backend.cleanup([search_id])


__all__ = [
    "AndOrSearchEngine",
]
