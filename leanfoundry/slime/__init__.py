"""LeanFoundry Slime rollout adapter.

This package is available only when the optional ``training`` extra installs
Slime. Core LeanFoundry modules must not import it.
"""

from __future__ import annotations

from typing import Any


def add_leanfoundry_arguments(*args: Any, **kwargs: Any) -> Any:
    """Lazy argparse hook for Slime custom-argument registration."""

    from leanfoundry.slime.arguments import (
        add_leanfoundry_arguments as _add_arguments,
    )

    return _add_arguments(*args, **kwargs)


def generate_rollout(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper so importing ``leanfoundry.slime`` stays cheap."""

    from leanfoundry.slime.rollout import generate_rollout as _generate_rollout

    return _generate_rollout(*args, **kwargs)


__all__ = ["add_leanfoundry_arguments", "generate_rollout"]
