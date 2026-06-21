"""Training-artifact extraction from search attempts."""

from __future__ import annotations

from dataclasses import dataclass, replace

from leanfoundry.proofsearch._tree import (
    ActionNodeStatus,
    SearchTree,
    StateNode,
    StateNodeStatus,
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

    if tree.root.status is StateNodeStatus.PROVED:
        if (
            context.verification_status == "accepted"
            and proof_tree is not None
        ):
            proof_candidates.append(proof_tree)
            policy_examples = _policy_examples_from_proof_tree(
                proof_tree,
                context,
            )
            if _should_emit_value_labels(context):
                value_labels = _proved_value_labels(proof_tree, context)
        elif context.verification_status is not None:
            failures.append(
                ExtractionFailure(
                    kind="verification",
                    message=context.verification_status,
                )
            )
    elif tree.root.status is StateNodeStatus.DISPROVED:
        if _should_emit_value_labels(context):
            value_labels = [
                _value_label(
                    state,
                    context,
                    label=0,
                    weight=1.0,
                    disproved=True,
                )
                for state in _real_initial_states(tree)
                if state.status is StateNodeStatus.DISPROVED
            ]
    else:
        if _should_emit_censored_negative(context):
            value_labels = [
                _value_label(
                    state,
                    context,
                    label=0,
                    weight=context.config.censored_negative_weight,
                    disproved=False,
                )
                for state in _real_initial_states(tree)
                if state.status is StateNodeStatus.OPEN
            ]

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


def rendering_failure_artifacts(message: str) -> TrainingArtifacts:
    """Return an artifact envelope for a proved tree that did not render."""

    return TrainingArtifacts(
        failures=[
            ExtractionFailure(
                kind="rendering",
                message=message,
            )
        ],
        diagnostics={"extraction_failures": 1},
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
    if initialization_action is None:
        for action in tree.root.actions:
            if action.children:
                return action.children
        return [tree.root]
    if initialization_action.children:
        return initialization_action.children
    return [tree.root]


def _policy_examples_from_proof_tree(
    proof_tree: ProofTree,
    context: ExtractionContext,
) -> list[PolicyExample]:
    examples: list[PolicyExample] = []
    for root in proof_tree.roots:
        examples.extend(_policy_examples_from_tactic_node(root, context))
    return examples


def _policy_examples_from_tactic_node(
    tactic_node: TacticNode,
    context: ExtractionContext,
) -> list[PolicyExample]:
    examples = [
        PolicyExample(
            state=tactic_node.state,
            tactic=tactic_node.tactic,
            theorem_id=context.theorem_id,
            env_profile=context.env_profile,
            depth=tactic_node.depth,
            model_version=context.model_version,
        )
    ]
    for child in tactic_node.children:
        examples.extend(_policy_examples_from_tactic_node(child, context))
    return examples


def _proved_value_labels(
    proof_tree: ProofTree,
    context: ExtractionContext,
) -> list[ValueLabel]:
    labels: list[ValueLabel] = []
    for root in proof_tree.roots:
        labels.extend(_proved_value_labels_from_tactic_node(root, context))
    return labels


def _proved_value_labels_from_tactic_node(
    tactic_node: TacticNode,
    context: ExtractionContext,
) -> list[ValueLabel]:
    labels = [
        _value_label(
            tactic_node,
            context,
            label=1,
            weight=1.0,
            disproved=False,
        )
    ]
    for child in tactic_node.children:
        labels.extend(_proved_value_labels_from_tactic_node(child, context))
    return labels


def _value_label(
    node: StateNode | TacticNode,
    context: ExtractionContext,
    *,
    label: int,
    weight: float,
    disproved: bool,
) -> ValueLabel:
    state = node.state
    depth = node.depth
    tactics_tried = context.search_budget_used
    if isinstance(node, TacticNode):
        tactics_tried = node.total_tactics_tried
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


def _should_emit_censored_negative(context: ExtractionContext) -> bool:
    if not _should_emit_value_labels(context):
        return False
    return (
        context.search_budget_used
        >= context.config.min_censored_negative_effort
    )


def _should_emit_value_labels(context: ExtractionContext) -> bool:
    return context.config.value_mode == "bonded"


__all__ = [
    "ExtractionContext",
    "extract_tactic_node_from_state",
    "extract_training_artifacts",
    "extraction_context_for_theorem",
    "rendering_failure_artifacts",
]
