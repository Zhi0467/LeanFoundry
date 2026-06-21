from __future__ import annotations

from leanfoundry.proofsearch._extract import extract_proof_tree
from leanfoundry.proofsearch._tree import SearchTree, StateNode
from leanfoundry.proofsearch._tree_init import (
    SYNTHETIC_INITIALIZATION_ACTION_TACTIC,
)
from leanfoundry.proofsearch.extraction import extract_tactic_node_from_state
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
    TheoremSpec,
)


def make_state(token: str = "state-token") -> FactorizedProofState:
    return FactorizedProofState(
        env_profile="test-env",
        goal_components=[GoalComponent(target="True", pretty="|- True")],
        pretty_state="|- True",
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
