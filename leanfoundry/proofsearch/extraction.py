"""Training-artifact extraction from search attempts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from leanfoundry.proofsearch._tree import (
    ActionNodeStatus,
    SearchTree,
    StateNode,
    StateNodeStatus,
)
from leanfoundry.proofsearch._tree_init import (
    SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
)
from leanfoundry.proofsearch.base import SearchConfig
from leanfoundry.schemas import (
    ExtractionFailure,
    PolicyExample,
    ProofTree,
    TacticNode,
    TheoremSpec,
    TrainingArtifacts,
    ValueLabel,
)


@dataclass(frozen=True, slots=True)
class ExtractionContext:
    """Attempt metadata required to emit training artifacts."""

    theorem_id: str | None
    env_profile: str
    config: SearchConfig
    search_budget_used: int
    model_version: int = 0
    attempt_id: str | None = None
    search_item_id: str | None = None
    verify_item_id: str | None = None
    verification_status: str | None = None

    def with_verification_status(self, status: str) -> ExtractionContext:
        """Return a copy recording final verifier status."""

        return replace(self, verification_status=status)


def extraction_context_for_theorem(
    theorem: TheoremSpec,
    *,
    config: SearchConfig,
    search_budget_used: int,
    model_version: int = 0,
    attempt_id: str | None = None,
    search_item_id: str | None = None,
    verify_item_id: str | None = None,
    verification_status: str | None = None,
) -> ExtractionContext:
    """Build the explicit context passed into extraction helpers."""

    return ExtractionContext(
        theorem_id=theorem.id,
        env_profile=theorem.env_profile,
        config=config,
        search_budget_used=search_budget_used,
        model_version=model_version,
        attempt_id=attempt_id,
        search_item_id=search_item_id,
        verify_item_id=verify_item_id,
        verification_status=verification_status,
    )


def extract_training_artifacts(
    tree: SearchTree,
    context: ExtractionContext,
    *,
    proof_tree: ProofTree | None = None,
) -> TrainingArtifacts:
    """Extract proof, policy, and value artifacts for one search attempt."""

    proof_candidates: list[ProofTree] = []
    policy_examples: list[PolicyExample] = []
    value_labels: list[ValueLabel] = []
    failures: list[ExtractionFailure] = []
    diagnostics = _base_diagnostics(tree, context)
    disproved_value_labels = _disproved_value_labels_from_runtime_tree(
        tree,
        context,
    )

    if tree.root.status is StateNodeStatus.PROVED:
        policy_examples = _policy_examples_from_runtime_tree(tree, context)
        if _should_emit_value_labels(context):
            value_labels = _proved_value_labels_from_runtime_tree(
                tree,
                context,
            )
            value_labels.extend(disproved_value_labels)
        if proof_tree is not None and proof_tree.verified:
            proof_candidates.append(proof_tree)
        elif (
            proof_tree is not None
            and context.verification_status is not None
        ):
            failures.append(
                ExtractionFailure(
                    kind="verification",
                    message=context.verification_status,
                )
            )
    elif tree.root.status is StateNodeStatus.DISPROVED:
        value_labels = disproved_value_labels
    else:
        value_labels = _censored_negative_value_labels(tree, context)
        value_labels.extend(disproved_value_labels)

    diagnostics["proof_candidates"] = len(proof_candidates)
    diagnostics["policy_examples"] = len(policy_examples)
    diagnostics["value_labels"] = len(value_labels)
    diagnostics["extraction_failures"] = len(failures)
    return TrainingArtifacts(
        proof_candidates=proof_candidates,
        policy_examples=policy_examples,
        value_labels=value_labels,
        failures=failures,
        diagnostics=diagnostics,
    )


def artifacts_with_failure(
    artifacts: TrainingArtifacts,
    failure: ExtractionFailure,
) -> TrainingArtifacts:
    """Return artifacts with one additional extraction failure."""

    failures = [*artifacts.failures, failure]
    diagnostics = dict(artifacts.diagnostics)
    diagnostics["extraction_failures"] = len(failures)
    return artifacts.model_copy(
        update={
            "failures": failures,
            "diagnostics": diagnostics,
        }
    )


def extract_tactic_node_from_state(
    state_node: StateNode,
    *,
    depth: int = 0,
) -> TacticNode:
    """Project a solved subtree rooted at an arbitrary runtime state."""

    action = state_node.proved_action()
    if action is None:
        raise ValueError("proved state did not expose a proved action")
    return TacticNode(
        state=state_node.state,
        tactic=action.tactic,
        children=[
            extract_tactic_node_from_state(child, depth=depth + 1)
            for child in action.children
        ],
        proved=action.status is ActionNodeStatus.PROVED,
        depth=depth,
        total_tactics_tried=action.visit_count,
    )


def _base_diagnostics(
    tree: SearchTree,
    context: ExtractionContext,
) -> dict[str, float | int | str]:
    real_initial_states = _real_initial_states(tree)
    proved_action_count = sum(
        _count_proved_actions(state) for state in real_initial_states
    )
    proved_alternative_count = sum(
        _count_proved_alternatives(state) for state in real_initial_states
    )
    return {
        "root_runtime_status": tree.root.status.value,
        "search_budget_used": context.search_budget_used,
        "proved_actions": proved_action_count,
        "proved_alternatives": proved_alternative_count,
    }


def _count_proved_actions(state_node: StateNode) -> int:
    count = sum(
        1
        for action in state_node.actions
        if action.status is ActionNodeStatus.PROVED
    )
    for action in state_node.actions:
        for child in action.children:
            count += _count_proved_actions(child)
    return count


def _count_proved_alternatives(state_node: StateNode) -> int:
    proved_at_state = sum(
        1
        for action in state_node.actions
        if action.status is ActionNodeStatus.PROVED
    )
    count = max(0, proved_at_state - 1)
    for action in state_node.actions:
        for child in action.children:
            count += _count_proved_alternatives(child)
    return count


def _real_initial_states(tree: SearchTree) -> list[StateNode]:
    initialization_action = tree.root.proved_action()
    if initialization_action is not None:
        if (
            initialization_action.tactic
            == SYNTHETIC_INITIALIZATION_ACTION_TACTIC
        ):
            return list(initialization_action.children)
        if initialization_action.children:
            return initialization_action.children
        return [tree.root]
    for action in tree.root.actions:
        if (
            action.tactic == SYNTHETIC_INITIALIZATION_ACTION_TACTIC
            or action.children
        ):
            return list(action.children)
    return [tree.root]


def _iter_real_states(tree: SearchTree) -> list[StateNode]:
    states: list[StateNode] = []
    for initial_state in _real_initial_states(tree):
        states.extend(_iter_state_subtree(initial_state))
    return states


def _iter_state_subtree(state_node: StateNode) -> list[StateNode]:
    states = [state_node]
    for action in state_node.actions:
        for child in action.children:
            states.extend(_iter_state_subtree(child))
    return states


def _policy_examples_from_runtime_tree(
    tree: SearchTree,
    context: ExtractionContext,
) -> list[PolicyExample]:
    examples: list[PolicyExample] = []
    for root in _real_initial_states(tree):
        examples.extend(_policy_examples_from_state_node(root, context))
    return examples


def _policy_examples_from_state_node(
    state_node: StateNode,
    context: ExtractionContext,
) -> list[PolicyExample]:
    action = state_node.proved_action()
    if action is None:
        return []
    examples = [
        PolicyExample(
            state=state_node.state,
            proof_prefix=proof_prefix_for_state(state_node),
            tactic=action.tactic,
            theorem_id=context.theorem_id,
            env_profile=context.env_profile,
            depth=state_node.depth,
            model_version=context.model_version,
        )
    ]
    for child in action.children:
        examples.extend(_policy_examples_from_state_node(child, context))
    return examples


def _proved_value_labels_from_runtime_tree(
    tree: SearchTree,
    context: ExtractionContext,
) -> list[ValueLabel]:
    labels: list[ValueLabel] = []
    for root in _real_initial_states(tree):
        labels.extend(_proved_value_labels_from_state_node(root, context))
    return labels


def _proved_value_labels_from_state_node(
    state_node: StateNode,
    context: ExtractionContext,
) -> list[ValueLabel]:
    action = state_node.proved_action()
    if action is None:
        return []
    labels = [
        _value_label(
            state_node,
            context,
            label=1,
            weight=1.0,
            disproved=False,
        )
    ]
    for child in action.children:
        labels.extend(_proved_value_labels_from_state_node(child, context))
    return labels


def _disproved_value_labels_from_runtime_tree(
    tree: SearchTree,
    context: ExtractionContext,
) -> list[ValueLabel]:
    if not _should_emit_value_labels(context):
        return []
    return [
        _value_label(
            state,
            context,
            label=0,
            weight=1.0,
            disproved=True,
        )
        for state in _iter_real_states(tree)
        if state.status is StateNodeStatus.DISPROVED
    ]


def proof_prefix_for_state(state_node: StateNode) -> str:
    """Return the linear root-to-state tactic prefix for one runtime state."""

    tactics: list[str] = []
    action = state_node.parent_action
    while action is not None:
        if action.tactic != SYNTHETIC_INITIALIZATION_ACTION_TACTIC:
            tactics.append(action.tactic)
        action = action.parent_state.parent_action
    return "\n".join(reversed(tactics))


def _censored_negative_value_labels(
    tree: SearchTree,
    context: ExtractionContext,
) -> list[ValueLabel]:
    if not _should_emit_value_labels(context):
        return []
    labels: list[ValueLabel] = []
    for state in _iter_real_states(tree):
        if state.status is not StateNodeStatus.OPEN:
            continue
        if state.visit_count < context.config.min_censored_negative_effort:
            continue
        labels.append(
            _value_label(
                state,
                context,
                label=0,
                weight=context.config.censored_negative_weight,
                disproved=False,
            )
        )
    return labels


def _value_label(
    node: StateNode | TacticNode,
    context: ExtractionContext,
    *,
    label: Literal[0, 1],
    weight: float,
    disproved: bool,
) -> ValueLabel:
    state = node.state
    depth = node.depth
    if isinstance(node, TacticNode):
        tactics_tried = node.total_tactics_tried
    else:
        tactics_tried = node.visit_count
    return ValueLabel(
        state=state,
        label=label,
        weight=weight,
        disproved=disproved,
        theorem_id=context.theorem_id,
        env_profile=context.env_profile,
        depth=depth,
        tactics_tried_on_subtree=tactics_tried,
        model_version=context.model_version,
    )


def _should_emit_value_labels(context: ExtractionContext) -> bool:
    return context.config.value_mode == "bonded"


__all__ = [
    "ExtractionContext",
    "artifacts_with_failure",
    "extract_tactic_node_from_state",
    "extract_training_artifacts",
    "extraction_context_for_theorem",
    "proof_prefix_for_state",
]
