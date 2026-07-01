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
    result_with_attempt_context,
    theorem_name_for_verify,
)
from leanfoundry.proofsearch._evaluation import evaluate_new_children
from leanfoundry.proofsearch._expansion import (
    BackendProtocolError,
    expand_state,
)
from leanfoundry.proofsearch._lifecycle import cleanup_search_state
from leanfoundry.proofsearch._negation import (
    collect_new_negation_attempts,
)
from leanfoundry.proofsearch._extract import (
    UnsupportedProofExtraction,
    extract_proof_tree,
)
from leanfoundry.proofsearch._selection import SelectionStrategy
from leanfoundry.proofsearch._tree import SearchTree, StateNodeStatus
from leanfoundry.proofsearch._tree_init import initialize_search_tree
from leanfoundry.proofsearch.base import (
    SearchAttemptContext,
    SearchConfig,
    SearchEngine,
    SearchResult,
    SearchStatus,
)
from leanfoundry.proofsearch.extraction import (
    artifacts_with_failure,
    extract_training_artifacts,
    extraction_context_for_theorem,
)
from leanfoundry.schemas import (
    ExtractionFailure,
    NegationAttempt,
    TheoremSpec,
    TrainingArtifacts,
)


class AndOrSearchEngine(SearchEngine):
    """AND/OR tree search with an injected selection strategy."""

    def __init__(self, selection_strategy: SelectionStrategy) -> None:
        self.selection_strategy = selection_strategy

    async def search(
        self,
        theorem: TheoremSpec,
        *,
        attempt_context: SearchAttemptContext,
        policy_client: PolicyClient,
        value_client: ValueClient | None,
        env_backend: EnvBackend,
        config: SearchConfig,
    ) -> SearchResult:
        """Run AND/OR tree search for one theorem."""

        theorem_name = theorem_name_for_verify(theorem)
        if theorem_name is None:
            return result_with_attempt_context(
                SearchResult(
                    theorem_id=theorem.id,
                    status=SearchStatus.ERROR,
                    diagnostics={
                        "error": "theorem_name is required for verification"
                    },
                ),
                attempt_context,
            )
        if attempt_context.search_item_id is None:
            return result_with_attempt_context(
                SearchResult(
                    theorem_id=theorem.id,
                    status=SearchStatus.ERROR,
                    diagnostics={
                        "error": "tree search requires search_item_id"
                    },
                ),
                attempt_context,
            )

        search_item_id = attempt_context.search_item_id
        tree: SearchTree | None = None
        cleanup_needed = False
        negation_attempts: list[NegationAttempt] = []

        async def finish(result: SearchResult) -> SearchResult:
            cleanup_report = await cleanup_search_state(
                env_backend,
                attempt_context,
            )
            return result_with_attempt_context(
                result,
                attempt_context,
                diagnostics=cleanup_report.diagnostics(),
            )

        try:
            limits = await env_backend.limits()
            cleanup_needed = True
            initialized = await initialize_search_tree(
                env_backend,
                theorem,
                search_id=search_item_id,
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
                    theorem=theorem,
                    max_tactics_per_step_item=(
                        limits.max_tactics_per_step_item
                    ),
                )
                negation_attempts.extend(outcome.negation_attempts)
                if outcome.operational_status is not None:
                    return await finish(
                        _with_negation_attempts(
                            operational_result(
                                theorem,
                                tree.tactic_calls_made,
                                outcome.operational_status,
                                frontier.failure_message,
                            ),
                            negation_attempts,
                        )
                    )
                if not outcome.made_progress:
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
                negation_attempts.extend(
                    collect_new_negation_attempts(tree)
                )

            if tree.root.status is StateNodeStatus.PROVED:
                proved_context = extraction_context_for_theorem(
                    theorem,
                    config=config,
                    search_budget_used=tree.tactic_calls_made,
                    attempt_id=attempt_context.attempt_id,
                    search_item_id=search_item_id,
                    verify_item_id=attempt_context.verify_item_id,
                )
                try:
                    proof_tree = extract_proof_tree(tree, theorem)
                except (UnsupportedProofExtraction, ValueError) as error:
                    failure_kind = "rendering"
                    artifact_status = "rendering_failed"
                    if isinstance(error, UnsupportedProofExtraction):
                        failure_kind = "unsupported"
                        artifact_status = "unsupported_extraction"
                    artifacts = extract_training_artifacts(
                        tree,
                        proved_context,
                    )
                    artifacts = artifacts_with_failure(
                        artifacts,
                        ExtractionFailure(
                            kind=failure_kind,
                            message=str(error),
                            node_id=(
                                error.node_id
                                if isinstance(
                                    error,
                                    UnsupportedProofExtraction,
                                )
                                else None
                            ),
                        ),
                    )
                    artifacts = _artifacts_with_negation_attempts(
                        artifacts,
                        negation_attempts,
                    )
                    return await finish(
                        SearchResult(
                            theorem_id=theorem.id,
                            status=SearchStatus.ERROR,
                            training_artifacts=artifacts,
                            search_budget_used=tree.tactic_calls_made,
                            diagnostics={
                                "proof_artifact_status": artifact_status,
                                "extraction_error": str(error),
                            },
                        ),
                    )
                verified_result = await verify_extracted_tree(
                    theorem,
                    env_backend,
                    attempt_context.verify_item_id,
                    theorem_name,
                    proof_tree,
                    tree.tactic_calls_made,
                    tree,
                    proved_context,
                )
                return await finish(
                    _with_negation_attempts(
                        verified_result,
                        negation_attempts,
                    )
                )

            if tree.root.status is StateNodeStatus.DISPROVED:
                disproved_context = extraction_context_for_theorem(
                    theorem,
                    config=config,
                    search_budget_used=tree.tactic_calls_made,
                    attempt_id=attempt_context.attempt_id,
                    search_item_id=search_item_id,
                    verify_item_id=attempt_context.verify_item_id,
                )
                artifacts = extract_training_artifacts(
                    tree,
                    disproved_context,
                )
                artifacts = _artifacts_with_negation_attempts(
                    artifacts,
                    negation_attempts,
                )
                return await finish(
                    SearchResult(
                        theorem_id=theorem.id,
                        status=SearchStatus.DISPROVED,
                        training_artifacts=artifacts,
                        search_budget_used=tree.tactic_calls_made,
                        diagnostics={
                            "root_status": tree.root.status.value,
                        },
                    )
                )

            exhausted_context = extraction_context_for_theorem(
                theorem,
                config=config,
                search_budget_used=tree.tactic_calls_made,
                attempt_id=attempt_context.attempt_id,
                search_item_id=search_item_id,
                verify_item_id=attempt_context.verify_item_id,
            )
            artifacts = extract_training_artifacts(
                tree,
                exhausted_context,
            )
            artifacts = _artifacts_with_negation_attempts(
                artifacts,
                negation_attempts,
            )
            return await finish(
                SearchResult(
                    theorem_id=theorem.id,
                    status=SearchStatus.EXHAUSTED,
                    training_artifacts=artifacts,
                    search_budget_used=tree.tactic_calls_made,
                    diagnostics={"root_status": tree.root.status.value},
                )
            )
        except BackendProtocolError as error:
            tactic_calls_made = 0
            if tree is not None:
                tactic_calls_made = tree.tactic_calls_made
            return await finish(
                SearchResult(
                    theorem_id=theorem.id,
                    status=SearchStatus.ERROR,
                    search_budget_used=tactic_calls_made,
                    diagnostics={
                        "operational_status": "backend_protocol_error",
                        "failure_message": str(error),
                    },
                )
            )
        except Exception as error:
            tactic_calls_made = 0
            if tree is not None:
                tactic_calls_made = tree.tactic_calls_made
            error_result = SearchResult(
                theorem_id=theorem.id,
                status=SearchStatus.ERROR,
                search_budget_used=tactic_calls_made,
                diagnostics={
                    "operational_status": "unexpected_error",
                    "failure_message": str(error),
                },
            )
            if cleanup_needed:
                return await finish(error_result)
            return result_with_attempt_context(error_result, attempt_context)


__all__ = [
    "AndOrSearchEngine",
]


def _with_negation_attempts(
    result: SearchResult,
    attempts: list[NegationAttempt],
) -> SearchResult:
    if not attempts:
        return result
    artifacts = result.training_artifacts or TrainingArtifacts()
    return result.model_copy(
        update={
            "training_artifacts": _artifacts_with_negation_attempts(
                artifacts,
                attempts,
            )
        }
    )


def _artifacts_with_negation_attempts(
    artifacts: TrainingArtifacts,
    attempts: list[NegationAttempt],
) -> TrainingArtifacts:
    if not attempts:
        return artifacts
    return artifacts.model_copy(
        update={
            "negation_attempts": [
                *artifacts.negation_attempts,
                *attempts,
            ],
            "diagnostics": {
                **artifacts.diagnostics,
                "negation_attempts": (
                    len(artifacts.negation_attempts) + len(attempts)
                ),
            },
        }
    )
