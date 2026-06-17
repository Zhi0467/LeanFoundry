def test_leanfoundry_imports() -> None:
    import leanfoundry

    assert leanfoundry.__version__ == "0.0.1"


def test_theorem_spec_carries_initial_block_and_source() -> None:
    from leanfoundry.schemas import TheoremSpec

    spec = TheoremSpec(
        lean_statement="theorem t : True := by sorry",
        env_profile="lean4.29.1_mathlib_5e932f97",
        header="import Mathlib",
        source="autoformalized",
        initial_lean_block="import Mathlib\n\ntheorem t : True := by\n  sorry",
    )

    assert spec.source == "autoformalized"
    assert spec.initial_lean_block is not None


def test_negation_pruning_is_provenance_gated() -> None:
    from leanfoundry.proofsearch import should_try_negation
    from leanfoundry.schemas import TheoremSpec

    known_true = TheoremSpec(
        lean_statement="theorem t : True := by trivial",
        env_profile="lean4.29.1_mathlib_5e932f97",
        header="import Mathlib",
        source="leandojo",
    )
    speculative = known_true.model_copy(update={"source": "autoformalized"})

    assert not should_try_negation(known_true)
    assert should_try_negation(speculative)


def test_tactic_node_preserves_branching_tree_shape() -> None:
    from leanfoundry.schemas import FactorizedProofState, ProofTree, TacticNode

    state = FactorizedProofState(
        env_profile="lean4.29.1_mathlib_5e932f97",
        theorem_header_options_hash="header",
        goal_components=[],
        tactic_history_hash="root",
        pretty_state="|- True /\\ True",
    )
    child = TacticNode(state=state, tactic="trivial", proved=True)
    root = TacticNode(
        state=state,
        tactic="constructor",
        children=[child, child],
    )
    tree = ProofTree(
        roots=[root], rendered_lean="by\n  constructor\n  case left => trivial"
    )

    dumped = tree.model_dump()

    assert len(dumped["roots"][0]["children"]) == 2
