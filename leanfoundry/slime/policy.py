"""Slime/SGLang policy client wiring."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from leanfoundry.policy import HTTPPolicyClient, PolicyContext
from leanfoundry.policy import PolicySamplingParams
from leanfoundry.schemas import FactorizedProofState


class SGLangPolicyClient(HTTPPolicyClient):
    """Policy client pointed at Slime's SGLang router."""

    def __init__(self, args: Any, **hooks: Any) -> None:
        self.tactic_sampling_params = _sglang_sampling_params(
            args,
            prefix="lf_tactic",
        )
        self.proof_sampling_params = _sglang_sampling_params(
            args,
            prefix="lf_proof",
        )
        super().__init__(
            base_url=(
                f"http://{args.sglang_router_ip}:"
                f"{args.sglang_router_port}"
            ),
            generate_path="/generate",
            **hooks,
        )

    async def sample_tactics(
        self,
        states: Sequence[FactorizedProofState],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
        context: Sequence[PolicyContext] | None = None,
    ) -> list[list[str]]:
        """Return tactic candidates with SGLang-shaped sampling params."""

        return await super().sample_tactics(
            states,
            n=n,
            params=_merge_sampling_params(self.tactic_sampling_params, params),
            context=context,
        )

    async def sample_proofs(
        self,
        prompts: Sequence[str],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
    ) -> list[list[str]]:
        """Return whole-proof candidates with SGLang-shaped sampling params."""

        return await super().sample_proofs(
            prompts,
            n=n,
            params=_merge_sampling_params(self.proof_sampling_params, params),
        )


def _sglang_sampling_params(args: Any, *, prefix: str) -> dict[str, Any]:
    """Translate LeanFoundry Slime args to SGLang `/generate` params."""

    params: dict[str, Any] = {}
    for arg_name, sglang_name in (
        ("temperature", "temperature"),
        ("top_p", "top_p"),
        ("top_k", "top_k"),
        ("min_p", "min_p"),
        ("max_new_tokens", "max_new_tokens"),
        ("regex", "regex"),
    ):
        value = getattr(args, f"{prefix}_{arg_name}", None)
        if value is not None:
            params[sglang_name] = value

    max_tokens = getattr(args, f"{prefix}_max_tokens", None)
    if max_tokens is not None and "max_new_tokens" not in params:
        params["max_new_tokens"] = max_tokens

    for arg_name in ("stop", "stop_token_ids", "logit_bias"):
        value = getattr(args, f"{prefix}_{arg_name}", None)
        if value is not None:
            params[arg_name] = _decode_json_arg(value)

    extra = getattr(args, f"{prefix}_extra_sampling_params", None)
    if extra is not None:
        decoded = _decode_json_arg(extra)
        if not isinstance(decoded, Mapping):
            raise TypeError(
                f"{prefix}_extra_sampling_params must be a mapping"
            )
        params.update(dict(decoded))
    return params


def _merge_sampling_params(
    defaults: Mapping[str, Any],
    params: PolicySamplingParams | Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge adapter defaults with call-site overrides for SGLang."""

    merged = dict(defaults)
    if params is not None:
        overrides = _sampling_params_to_dict(params)
        max_tokens = overrides.pop("max_tokens", None)
        merged.update(overrides)
        if max_tokens is not None and "max_new_tokens" not in overrides:
            merged["max_new_tokens"] = max_tokens
    return merged


def _sampling_params_to_dict(
    params: PolicySamplingParams | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(params, PolicySamplingParams):
        data = params.model_dump(exclude_none=True)
        extra = data.pop("extra", None)
        if extra is not None:
            data.update(dict(extra))
        return data
    return dict(params)


def _decode_json_arg(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    if stripped[0] not in "[{\"" and stripped not in {"true", "false"}:
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


__all__ = ["SGLangPolicyClient"]
