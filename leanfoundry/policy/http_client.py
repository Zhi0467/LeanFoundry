"""HTTP implementations of LeanFoundry policy and value clients."""

from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from leanfoundry.policy.base import PolicyContext, PolicySamplingParams
from leanfoundry.schemas import FactorizedProofState, TheoremSpec


JsonObject = Mapping[str, Any]


class HTTPClientError(RuntimeError):
    """Raised when a model HTTP endpoint returns unusable data."""


class _UrllibJsonTransport:
    """Tiny async JSON POST transport to avoid a runtime HTTP dependency."""

    async def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
    ) -> Any:
        """POST JSON and decode a JSON response."""

        return await asyncio.to_thread(self._post_json_sync, url, payload)

    def _post_json_sync(
        self,
        url: str,
        payload: Mapping[str, Any],
    ) -> Any:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            message = f"model endpoint request failed: {exc}"
            raise HTTPClientError(message) from exc
        if not response_body:
            return {}
        try:
            return json.loads(response_body)
        except json.JSONDecodeError as exc:
            message = "model endpoint returned non-JSON data"
            raise HTTPClientError(message) from exc


class HTTPPolicyClient:
    """Model-agnostic PolicyClient over a JSON generation endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        generate_path: str = "/generate",
        tactic_prompt: Callable[
            [FactorizedProofState, PolicyContext | None],
            str,
        ] | None = None,
        proof_prompt: Callable[[TheoremSpec], str] | None = None,
        parse_tactic: Callable[[str], str] | None = None,
        parse_proof: Callable[[str], str] | None = None,
        http: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.generate_path = generate_path
        self.tactic_prompt = tactic_prompt or default_tactic_prompt
        self.proof_prompt = proof_prompt or default_proof_prompt
        self.parse_tactic = parse_tactic or strip_to_tactic
        self.parse_proof = parse_proof or strip_code_fence
        self.http = http or _UrllibJsonTransport()

    async def sample_tactics(
        self,
        states: Sequence[FactorizedProofState],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
        context: Sequence[PolicyContext] | None = None,
    ) -> list[list[str]]:
        """Return n tactic candidates for each proof state."""

        contexts = _contexts_for_states(states, context)
        return [
            [
                self.parse_tactic(text)
                for text in await self._generate_texts(
                    self.tactic_prompt(state, contexts[index]),
                    n=n,
                    params=params,
                )
            ]
            for index, state in enumerate(states)
        ]

    async def sample_proofs(
        self,
        prompts: Sequence[str],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
    ) -> list[list[str]]:
        """Return n whole-proof candidates for each prompt."""

        return [
            [
                self.parse_proof(text)
                for text in await self._generate_texts(
                    prompt,
                    n=n,
                    params=params,
                )
            ]
            for prompt in prompts
        ]

    async def _generate_texts(
        self,
        prompt: str,
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
    ) -> list[str]:
        if n < 1:
            raise ValueError("n must be positive")
        payload = {
            "text": prompt,
            "sampling_params": _sampling_params_dict(params, n=n),
        }
        response = await _post_json(self.http, self._url(), payload)
        texts = _extract_generated_texts(response)
        if len(texts) != n:
            raise HTTPClientError(
                "model endpoint returned "
                f"{len(texts)} completions, expected {n}"
            )
        return texts

    def _url(self) -> str:
        return f"{self.base_url}/{self.generate_path.lstrip('/')}"


class HTTPValueClient:
    """Model-agnostic ValueClient over a JSON endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        generate_path: str = "/generate",
        value_prompt: Callable[[FactorizedProofState], str] | None = None,
        output_mode: Literal["numeric_head", "natural_language"]
        = "natural_language",
        parse_score: Callable[[str | Mapping[str, Any]], float]
        | None = None,
        budget_tokens: int = 256,
        http: Any = None,
    ) -> None:
        if budget_tokens < 1:
            raise ValueError("budget_tokens must be positive")
        self.base_url = base_url.rstrip("/")
        self.generate_path = generate_path
        self.value_prompt = value_prompt or default_value_prompt
        self.output_mode = output_mode
        self.parse_score = parse_score or parse_boxed_or_json_score
        self.budget_tokens = budget_tokens
        self.http = http or _UrllibJsonTransport()

    async def estimate(
        self,
        states: Sequence[FactorizedProofState],
    ) -> list[float]:
        """Return one validated score in [0, 1] per state."""

        scores: list[float] = []
        for state in states:
            payload = {
                "text": self.value_prompt(state),
                "sampling_params": {
                    "n": 1,
                    "max_tokens": self.budget_tokens,
                },
                "value_output_mode": self.output_mode,
            }
            response = await _post_json(self.http, self._url(), payload)
            if self.output_mode == "numeric_head":
                score = self.parse_score(response)
            else:
                texts = _extract_generated_texts(response)
                if len(texts) != 1:
                    raise HTTPClientError(
                        "value endpoint returned "
                        f"{len(texts)} completions, expected 1"
                    )
                score = self.parse_score(texts[0])
            scores.append(_validate_score(score))
        return scores

    def _url(self) -> str:
        return f"{self.base_url}/{self.generate_path.lstrip('/')}"


def default_tactic_prompt(
    state: FactorizedProofState,
    context: PolicyContext | None = None,
) -> str:
    """Render the Markov proof state for tactic prediction."""

    if context is not None and context.proof_prefix:
        return (
            "/- tactic history:\n"
            f"{context.proof_prefix}\n"
            "-/\n"
            f"{state.pretty_state}"
        )
    return state.pretty_state


def default_proof_prompt(theorem: TheoremSpec) -> str:
    """Render a theorem prompt for whole-proof generation."""

    pieces = [theorem.header.strip(), theorem.lean_statement.strip()]
    if theorem.informal_statement:
        pieces.append(f"/-- {theorem.informal_statement.strip()} -/")
    return "\n\n".join(piece for piece in pieces if piece)


def default_value_prompt(state: FactorizedProofState) -> str:
    """Render a value-estimation prompt with a parseable scalar contract."""

    return (
        "Estimate the probability that this Lean proof state can be solved. "
        "Reason briefly if useful, then end with a scalar in [0, 1] as "
        "\\boxed{score}.\n\n"
        f"{state.pretty_state}"
    )


def strip_to_tactic(text: str) -> str:
    """Normalize a generated tactic string."""

    return strip_code_fence(text).strip()


def strip_code_fence(text: str) -> str:
    """Strip one surrounding Markdown code fence when present."""

    stripped = text.strip()
    fence_match = re.fullmatch(
        r"```(?:lean|lean4)?\s*\n?(.*?)\n?```",
        stripped,
        flags=re.DOTALL,
    )
    if fence_match is not None:
        return fence_match.group(1).strip()
    return stripped


def parse_boxed_or_json_score(payload: str | Mapping[str, Any]) -> float:
    """Parse a value-model score from JSON or natural-language text."""

    if isinstance(payload, Mapping):
        return _score_from_mapping(payload)
    text = payload.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, Mapping):
        return _score_from_mapping(parsed)
    boxed_match = re.search(r"\\boxed\{([^{}]+)\}", text)
    if boxed_match is not None:
        return _parse_score_number(boxed_match.group(1))
    json_like_match = re.search(
        r'"(?:score|value|probability)"\s*:\s*([-+]?\d+(?:\.\d+)?)',
        text,
    )
    if json_like_match is not None:
        return _parse_score_number(json_like_match.group(1))
    return _parse_score_number(text)


async def _post_json(
    http: Any,
    url: str,
    payload: Mapping[str, Any],
) -> Any:
    if hasattr(http, "post_json"):
        result = http.post_json(url, payload)
        if hasattr(result, "__await__"):
            return await result
        return result
    if callable(http):
        result = http(url, payload)
        if hasattr(result, "__await__"):
            return await result
        return result
    raise TypeError("http transport must expose post_json(url, payload)")


def _sampling_params_dict(
    params: PolicySamplingParams | Mapping[str, Any] | None,
    *,
    n: int,
) -> dict[str, Any]:
    if params is None:
        data: dict[str, Any] = {}
    elif isinstance(params, PolicySamplingParams):
        data = params.model_dump(exclude_none=True)
        extra = data.pop("extra", None)
        if extra is not None:
            data.update(extra)
    else:
        data = dict(params)
    data["n"] = n
    return data


def _contexts_for_states(
    states: Sequence[FactorizedProofState],
    context: Sequence[PolicyContext] | None,
) -> list[PolicyContext | None]:
    if context is None:
        return [None for _state in states]
    if len(context) != len(states):
        raise ValueError("context must match state count")
    return list(context)


def _extract_generated_texts(response: Any) -> list[str]:
    if isinstance(response, str):
        return [response]
    if isinstance(response, Sequence) and not isinstance(
        response,
        (bytes, bytearray, str),
    ):
        return [_text_from_candidate(candidate) for candidate in response]
    if not isinstance(response, Mapping):
        raise HTTPClientError("model endpoint returned unsupported JSON shape")
    for key in ("texts", "outputs", "choices", "completions", "generations"):
        value = response.get(key)
        if value is not None:
            if isinstance(value, str):
                return [value]
            if isinstance(value, Sequence):
                return [
                    _text_from_candidate(candidate) for candidate in value
                ]
            raise HTTPClientError(
                f"model response field {key!r} is not a list"
            )
    for key in ("text", "response", "output", "generated_text"):
        value = response.get(key)
        if isinstance(value, str):
            return [value]
    raise HTTPClientError("model endpoint response did not contain text")


def _text_from_candidate(candidate: Any) -> str:
    if isinstance(candidate, str):
        return candidate
    if isinstance(candidate, Mapping):
        for key in ("text", "output", "response", "generated_text", "content"):
            value = candidate.get(key)
            if isinstance(value, str):
                return value
        message = candidate.get("message")
        if isinstance(message, Mapping):
            content = message.get("content")
            if isinstance(content, str):
                return content
    raise HTTPClientError("completion candidate did not contain text")


def _score_from_mapping(payload: Mapping[str, Any]) -> float:
    for key in ("score", "value", "probability"):
        if key in payload:
            return _parse_score_number(payload[key])
    for key in ("output", "response", "text"):
        value = payload.get(key)
        if isinstance(value, str):
            return parse_boxed_or_json_score(value)
    outputs = payload.get("outputs")
    if isinstance(outputs, Sequence) and outputs:
        return parse_boxed_or_json_score(_text_from_candidate(outputs[0]))
    raise HTTPClientError("value response did not contain a score")


def _parse_score_number(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        message = f"value score is not numeric: {value!r}"
        raise HTTPClientError(message) from exc
    return _validate_score(score)


def _validate_score(score: float) -> float:
    if not 0.0 <= score <= 1.0:
        raise HTTPClientError(f"value score out of range [0, 1]: {score}")
    return score


__all__ = [
    "HTTPClientError",
    "HTTPPolicyClient",
    "HTTPValueClient",
    "default_proof_prompt",
    "default_tactic_prompt",
    "default_value_prompt",
    "parse_boxed_or_json_score",
    "strip_code_fence",
    "strip_to_tactic",
]
