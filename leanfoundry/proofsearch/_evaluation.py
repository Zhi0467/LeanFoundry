"""Private value-evaluation helpers for tree search."""

from __future__ import annotations

from leanfoundry.policy import ValueClient
from leanfoundry.proofsearch._tree import ActionNode, StateNodeStatus


async def evaluate_new_children(
    actions: list[ActionNode],
    *,
    value_client: ValueClient | None,
) -> None:
    """Estimate values for open child states created by an expansion."""

    if value_client is None:
        return
    children = [
        child
        for action in actions
        for child in action.children
        if child.status is StateNodeStatus.OPEN
    ]
    if not children:
        return
    values = await value_client.estimate([child.state for child in children])
    if len(values) != len(children):
        raise ValueError("value_client returned the wrong number of values")
    for child, value in zip(children, values, strict=True):
        child.value_estimate = value


__all__ = [
    "evaluate_new_children",
]
