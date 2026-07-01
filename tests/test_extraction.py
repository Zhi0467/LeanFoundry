from __future__ import annotations

from leanfoundry.proofsearch._extract import extract_proof_tree
from leanfoundry.proofsearch import SearchConfig
from leanfoundry.proofsearch._tree import SearchTree, StateNode
from leanfoundry.proofsearch._tree_init import (
    SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
)
from leanfoundry.proofsearch.extraction import (
    extract_tactic_node_from_state,
    extract_training_artifacts,
    extraction_context_for_theorem,
)
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
    ProofTree,
    TheoremSpec,
)


def make_state(token: str = "state-token") -> FactorizedProofState:
    return FactorizedProofState(
        env_profile="test-env",
        goal_components=[GoalComponent(target="True", pretty="|- True")],
        pretty_state="|- True",
        state_token=token,
    )


def make_state_with_targets(
    token: str,
    targets: list[str],
) -> FactorizedProofState:
    components = [
        GoalComponent(target=target, pretty=f"|- {target}")
        for target in targets
    ]
    return FactorizedProofState(
        env_profile="test-env",
        goal_components=components,
        pretty_state="\n\n".join(component.pretty for component in components),
        state_token=token,
    )


def make_solved_tree() -> tuple[SearchTree, StateNode]:
    synthetic_root_state = FactorizedProofState(
        env_profile="test-env",
        goal_components=[],
        pretty_state="theorem t : True := by\n  sorry",
        state_token=None,
    )
    tree = SearchTree.create("search", synthetic_root_state)
    initialization_action = tree.add_action(
        tree.root,
        SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
        prior=1.0,
    )
    initial_state = tree.add_child_state(initialization_action, make_state())
    proved_action = tree.add_action(initial_state, "trivial", prior=1.0)
    tree.mark_action_proved(proved_action)
    return tree, initial_state


def test_extract_tactic_node_projects_arbitrary_solved_state() -> None:
    _tree, initial_state = make_solved_tree()

    tactic_node = extract_tactic_node_from_state(initial_state)

    assert tactic_node.tactic == "trivial"
    assert tactic_node.state.state_token == "state-token"
    assert tactic_node.proved


def test_extract_proof_tree_replaces_only_real_sorry_tokens() -> None:
    tree, _initial_state = make_solved_tree()
    theorem = TheoremSpec(
        lean_statement="theorem t : True := by\n  sorry",
        initial_lean_block=(
            "theorem t : True := by\n"
            "  -- this comment says sorry\n"
            "  have message : String := \"sorry\"\n"
            "  /- nested sorry /- inner sorry -/ still comment -/\n"
            "  sorry\n"
        ),
        env_profile="test-env",
        header="",
        source="test",
        theorem_name="t",
    )

    proof_tree = extract_proof_tree(tree, theorem)

    assert proof_tree.rendered_lean == (
        "theorem t : True := by\n"
        "  -- this comment says sorry\n"
        "  have message : String := \"sorry\"\n"
        "  /- nested sorry /- inner sorry -/ still comment -/\n"
        "  trivial\n"
    )


def test_training_artifacts_include_internal_disproved_labels() -> None:
    tree, initial_state = make_solved_tree()
    split_action = tree.add_action(initial_state, "constructor", prior=0.5)
    left = tree.add_child_state(split_action, make_state("left"))
    tree.add_child_state(split_action, make_state("right"))
    tree.mark_state_disproved(left, message="negation proof")

    theorem = TheoremSpec(
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="test-env",
        header="",
        source="test",
        theorem_name="t",
    )
    context = extraction_context_for_theorem(
        theorem,
        config=SearchConfig(
            value_mode="bonded",
            min_censored_negative_effort=999,
        ),
        search_budget_used=3,
    )

    artifacts = extract_training_artifacts(tree, context)

    disproved_labels = [
        label for label in artifacts.value_labels if label.disproved
    ]
    assert len(disproved_labels) == 1
    label = disproved_labels[0]
    assert label.label == 0
    assert label.weight == 1.0
    assert label.state.state_token == "left"


def test_training_artifacts_emit_proved_internal_step_under_open_root(
) -> None:
    synthetic_root_state = FactorizedProofState(
        env_profile="test-env",
        goal_components=[],
        pretty_state="theorem t : True := by\n  sorry",
        state_token=None,
    )
    tree = SearchTree.create("search", synthetic_root_state)
    initialization_action = tree.add_action(
        tree.root,
        SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
        prior=1.0,
    )
    initial_state = tree.add_child_state(
        initialization_action,
        make_state("initial"),
    )
    split_action = tree.add_action(initial_state, "constructor", prior=0.5)
    left = tree.add_child_state(split_action, make_state("left"))
    tree.add_child_state(split_action, make_state("right"))
    left_action = tree.add_action(left, "left_proof", prior=1.0)
    tree.mark_action_proved(left_action)

    theorem = TheoremSpec(
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="test-env",
        header="",
        source="test",
        theorem_name="t",
    )
    context = extraction_context_for_theorem(
        theorem,
        config=SearchConfig(
            value_mode="bonded",
            min_censored_negative_effort=999,
        ),
        search_budget_used=3,
    )

    artifacts = extract_training_artifacts(tree, context)

    observed = [
        (example.state.state_token, example.tactic)
        for example in artifacts.policy_examples
    ]
    assert ("left", "left_proof") in observed
    labels = {
        label.state.state_token: label
        for label in artifacts.value_labels
        if label.label == 1
    }
    assert labels["left"].weight == 1.0
    assert artifacts.diagnostics["step_her_multiplier"] == len(
        artifacts.policy_examples
    )


def test_training_artifacts_emit_multiple_proved_actions_for_one_state(
) -> None:
    tree, initial_state = make_solved_tree()
    alternate_action = tree.add_action(
        initial_state,
        "exact True.intro",
        prior=0.5,
    )
    tree.mark_action_proved(alternate_action)

    theorem = TheoremSpec(
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="test-env",
        header="",
        source="test",
        theorem_name="t",
    )
    context = extraction_context_for_theorem(
        theorem,
        config=SearchConfig(),
        search_budget_used=2,
    )

    artifacts = extract_training_artifacts(tree, context)

    tactics = sorted(
        example.tactic for example in artifacts.policy_examples
    )
    assert tactics == ["exact True.intro", "trivial"]


def test_training_artifacts_report_path_b_render_diagnostics() -> None:
    tree, _initial_state = make_solved_tree()
    theorem = TheoremSpec(
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="test-env",
        header="",
        source="test",
        theorem_name="t",
    )
    context = extraction_context_for_theorem(
        theorem,
        config=SearchConfig(),
        search_budget_used=1,
    )
    proof_tree = ProofTree(
        roots=[],
        rendered_lean="theorem t : True := by\n  trivial",
        verified=True,
    )

    artifacts = extract_training_artifacts(
        tree,
        context,
        proof_tree=proof_tree,
    )

    assert artifacts.diagnostics["path_b_render_candidates"] == 1
    assert artifacts.diagnostics["path_b_renderable_candidates"] == 1
    assert artifacts.diagnostics["path_b_unsupported_candidates"] == 0
    assert artifacts.diagnostics["path_b_verified_candidates"] == 1


def test_training_artifacts_count_unsupported_path_b_subtrees() -> None:
    tree, initial_state = make_solved_tree()
    split_action = tree.add_action(initial_state, "constructor", prior=0.5)
    coupled_child = tree.add_child_state(
        split_action,
        make_state_with_targets("coupled", ["A", "B"]),
    )
    other_child = tree.add_child_state(
        split_action,
        make_state_with_targets("other", ["C"]),
    )
    coupled_proof = tree.add_action(
        coupled_child,
        "all_goals trivial",
        prior=1.0,
    )
    other_proof = tree.add_action(other_child, "trivial", prior=1.0)
    tree.mark_action_proved(coupled_proof)
    tree.mark_action_proved(other_proof)

    theorem = TheoremSpec(
        lean_statement="theorem t : True := by\n  sorry",
        env_profile="test-env",
        header="",
        source="test",
        theorem_name="t",
    )
    context = extraction_context_for_theorem(
        theorem,
        config=SearchConfig(),
        search_budget_used=3,
    )

    artifacts = extract_training_artifacts(tree, context)

    assert artifacts.diagnostics["path_b_render_candidates"] == 4
    assert artifacts.diagnostics["path_b_renderable_candidates"] == 3
    assert artifacts.diagnostics["path_b_unsupported_candidates"] == 1
    assert artifacts.diagnostics["path_b_verified_candidates"] == 0
