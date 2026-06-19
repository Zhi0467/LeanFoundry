"""Private runtime AND/OR search tree.

This is the mutable search-time structure. It intentionally differs from the
durable ``ProofTree`` projection, which only stores a solved slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from leanfoundry.schemas import FactorizedProofState


class StateNodeStatus(StrEnum):
    """Runtime status for an OR proof-state node.

    ``PROVED`` means structurally closed in the search tree. The concrete
    engine must still run final ``verify_one`` before accepting a theorem.
    """

    OPEN = "open"
    PROVED = "proved"
    DISPROVED = "disproved"


class ActionNodeStatus(StrEnum):
    """Runtime status for an AND tactic/action node."""

    OPEN = "open"
    PROVED = "proved"
    DEAD = "dead"


@dataclass(slots=True)
class StateNode:
    """OR node: one reached Lean proof state."""

    node_id: str
    state: FactorizedProofState
    depth: int
    parent_action: ActionNode | None = None
    actions: list[ActionNode] = field(default_factory=list)
    status: StateNodeStatus = StateNodeStatus.OPEN
    visit_count: int = 0
    failure_message: str | None = None

    @property
    def is_terminal(self) -> bool:
        """Return whether no more search should be run below this state."""

        return self.status is not StateNodeStatus.OPEN

    @property
    def is_expanded(self) -> bool:
        """Return whether policy actions have been attached to this state."""

        return bool(self.actions)

    @property
    def open_goal_count(self) -> int:
        """Return the number of Lean goals represented by this state."""

        return len(self.state.goal_components)

    def proved_action(self) -> ActionNode | None:
        """Return the first proved action, preserving insertion order."""

        for action in self.actions:
            if action.status is ActionNodeStatus.PROVED:
                return action
        return None


@dataclass(slots=True)
class ActionNode:
    """AND node: one tactic/action chosen from one parent state."""

    action_id: str
    parent_state: StateNode
    tactic: str
    prior: float
    value_estimate: float | None = None
    visit_count: int = 0
    children: list[StateNode] = field(default_factory=list)
    status: ActionNodeStatus = ActionNodeStatus.OPEN
    failure_message: str | None = None

    @property
    def is_terminal(self) -> bool:
        """Return whether this action no longer needs child search."""

        return self.status is not ActionNodeStatus.OPEN


@dataclass(slots=True)
class SearchTree:
    """Mutable AND/OR tree for one theorem search."""

    search_id: str
    root: StateNode
    tactic_calls_made: int = 0
    _next_state_index: int = 1

    @classmethod
    def create(
        cls,
        search_id: str,
        root_state: FactorizedProofState,
    ) -> SearchTree:
        """Create a tree with one root OR node."""

        root = StateNode(
            node_id=f"{search_id}:0",
            state=root_state,
            depth=0,
        )
        return cls(search_id=search_id, root=root)

    def add_action(
        self,
        parent_state: StateNode,
        tactic: str,
        *,
        prior: float,
        value_estimate: float | None = None,
    ) -> ActionNode:
        """Attach a tactic/action to an OR state."""

        action = ActionNode(
            action_id=f"{parent_state.node_id}#a{len(parent_state.actions)}",
            parent_state=parent_state,
            tactic=tactic,
            prior=prior,
            value_estimate=value_estimate,
        )
        parent_state.actions.append(action)
        return action

    def add_child_state(
        self,
        parent_action: ActionNode,
        state: FactorizedProofState,
    ) -> StateNode:
        """Attach a child OR state produced by an action."""

        if parent_action.is_terminal:
            raise ValueError("cannot add child state to a terminal action")
        child = StateNode(
            node_id=f"{self.search_id}:{self._next_state_index}",
            state=state,
            depth=parent_action.parent_state.depth + 1,
            parent_action=parent_action,
        )
        self._next_state_index += 1
        parent_action.children.append(child)
        if child.open_goal_count == 0:
            child.status = StateNodeStatus.PROVED
        self.refresh_from_state(child)
        return child

    def mark_action_proved(self, action: ActionNode) -> None:
        """Mark an action as closing its parent state."""

        if action.children and not all(
            child.status is StateNodeStatus.PROVED for child in action.children
        ):
            raise ValueError(
                "cannot prove action before all child states are proved"
            )
        action.status = ActionNodeStatus.PROVED
        action.failure_message = None
        self.refresh_from_action(action)

    def mark_action_dead(
        self,
        action: ActionNode,
        *,
        message: str | None = None,
    ) -> None:
        """Mark a tactic/action as unusable for proof search."""

        action.status = ActionNodeStatus.DEAD
        action.failure_message = message
        self.refresh_from_action(action)

    def mark_state_disproved(
        self,
        state_node: StateNode,
        *,
        message: str | None = None,
    ) -> None:
        """Mark a state as logically disproved.

        The first engine slice does not generate disproved states; this method
        keeps the AND/OR invariant explicit for later negation pruning.
        """

        state_node.status = StateNodeStatus.DISPROVED
        state_node.failure_message = message
        self.refresh_from_state(state_node)

    def refresh_from_state(self, state_node: StateNode) -> None:
        """Propagate status changes from a state toward the root."""

        if state_node.parent_action is not None:
            self.refresh_from_action(state_node.parent_action)

    def refresh_from_action(self, action: ActionNode) -> None:
        """Refresh an action, then propagate to its parent state."""

        self._refresh_action_status(action)
        self._refresh_state_status(action.parent_state)
        parent_action = action.parent_state.parent_action
        if parent_action is not None:
            self.refresh_from_action(parent_action)

    def _refresh_action_status(self, action: ActionNode) -> None:
        if action.status is ActionNodeStatus.DEAD:
            return
        if not action.children:
            if action.status is ActionNodeStatus.PROVED:
                return
            return
        if any(
            child.status is StateNodeStatus.DISPROVED
            for child in action.children
        ):
            action.status = ActionNodeStatus.DEAD
            return
        if all(
            child.status is StateNodeStatus.PROVED for child in action.children
        ):
            action.status = ActionNodeStatus.PROVED
            return
        action.status = ActionNodeStatus.OPEN

    def _refresh_state_status(self, state_node: StateNode) -> None:
        if any(
            action.status is ActionNodeStatus.PROVED
            for action in state_node.actions
        ):
            state_node.status = StateNodeStatus.PROVED
            state_node.failure_message = None
            return
        if state_node.status is StateNodeStatus.DISPROVED:
            return
        state_node.status = StateNodeStatus.OPEN


__all__ = [
    "ActionNode",
    "ActionNodeStatus",
    "SearchTree",
    "StateNode",
    "StateNodeStatus",
]
