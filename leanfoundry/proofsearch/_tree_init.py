"""Private initialization helpers for AND/OR tree search."""

from __future__ import annotations

from dataclasses import dataclass

from lean_client.exec_models import ExecStateInfo

from leanfoundry.env_backend import EnvBackend
from leanfoundry.proofsearch._common import verifier_feedback
from leanfoundry.proofsearch._expansion import goal_info_to_component
from leanfoundry.proofsearch._tree import SearchTree
from leanfoundry.schemas import FactorizedProofState, TheoremSpec

INITIAL_BLOCK_TACTIC = "__initial_sorry_block__"


@dataclass(frozen=True, slots=True)
class InitializedSearchTree:
    """Runtime tree plus the Lean block it was initialized from."""

    tree: SearchTree
    initial_code: str


async def initialize_search_tree(
    env_backend: EnvBackend,
    theorem: TheoremSpec,
    *,
    search_id: str,
) -> InitializedSearchTree:
    """Execute the initial sorry block and build the runtime tree root."""

    initial_code = initial_code_for_theorem(theorem)
    response = await env_backend.create_states(
        search_id,
        initial_code,
        env_profile=theorem.env_profile,
    )
    if len(response.items) != 1:
        raise ValueError("create_states must return one item for one request")

    item = response.items[0]
    if item.status not in {"open", "complete"}:
        raise ValueError(
            "create_states failed: "
            f"{verifier_feedback(item.status, item.messages)}"
        )

    tree = SearchTree.create(
        search_id,
        FactorizedProofState(
            env_profile=theorem.env_profile,
            goal_components=[],
            pretty_state=theorem.lean_statement,
            state_token=None,
        ),
    )
    initial_action = tree.add_action(
        tree.root,
        INITIAL_BLOCK_TACTIC,
        prior=1.0,
    )
    for state_info in item.states:
        tree.add_child_state(
            initial_action,
            _state_info_to_proof_state(theorem, state_info),
        )
    if not item.states:
        tree.mark_action_proved(initial_action)
    return InitializedSearchTree(tree=tree, initial_code=initial_code)


def initial_code_for_theorem(theorem: TheoremSpec) -> str:
    """Return the Lean code sent to ``/exec/create_states``."""

    if theorem.initial_lean_block is not None:
        return theorem.initial_lean_block
    if theorem.header:
        return f"{theorem.header.rstrip()}\n\n{theorem.lean_statement}"
    return theorem.lean_statement


def _state_info_to_proof_state(
    theorem: TheoremSpec,
    state_info: ExecStateInfo,
) -> FactorizedProofState:
    components = [
        goal_info_to_component(goal_info) for goal_info in state_info.goals
    ]
    return FactorizedProofState(
        env_profile=theorem.env_profile,
        goal_components=components,
        pretty_state="\n\n".join(component.pretty for component in components),
        state_token=state_info.state_token,
    )


__all__ = [
    "INITIAL_BLOCK_TACTIC",
    "InitializedSearchTree",
    "initial_code_for_theorem",
    "initialize_search_tree",
]
