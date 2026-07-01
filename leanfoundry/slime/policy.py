"""Slime/SGLang policy client wiring."""

from __future__ import annotations

from typing import Any

from leanfoundry.policy import HTTPPolicyClient


class SGLangPolicyClient(HTTPPolicyClient):
    """Policy client pointed at Slime's SGLang router."""

    def __init__(self, args: Any, **hooks: Any) -> None:
        super().__init__(
            base_url=(
                f"http://{args.sglang_router_ip}:"
                f"{args.sglang_router_port}"
            ),
            generate_path="/generate",
            **hooks,
        )


__all__ = ["SGLangPolicyClient"]
