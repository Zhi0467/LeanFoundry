from __future__ import annotations

import asyncio

import pytest

from leanfoundry.policy import (
    HTTPClientError,
    HTTPPolicyClient,
    HTTPValueClient,
    PolicyContext,
    PolicySamplingParams,
    parse_boxed_or_json_score,
)
from leanfoundry.schemas import FactorizedProofState, GoalComponent


class FakeJsonTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def post_json(self, url: str, payload: dict[str, object]) -> object:
        self.calls.append((url, payload))
        return self.responses.pop(0)


def _state() -> FactorizedProofState:
    return FactorizedProofState(
        env_profile="lean4.29.1_mathlib_5e932f97",
        goal_components=[
            GoalComponent(
                target="True",
                pretty="⊢ True",
                hypotheses=[],
            )
        ],
        pretty_state="case main\n⊢ True",
        state_token="state-token",
    )


def test_http_policy_client_samples_tactics_with_hooks() -> None:
    transport = FakeJsonTransport(
        [
            {
                "outputs": [
                    {"text": "```lean\nsimp\n```"},
                    {"text": " exact True.intro "},
                ]
            }
        ]
    )
    client = HTTPPolicyClient(
        base_url="http://model.local/",
        http=transport,
    )

    result = asyncio.run(
        client.sample_tactics(
            [_state()],
            n=2,
            params=PolicySamplingParams(
                temperature=0.2,
                top_p=None,
                extra={"stop": ["\n\n"]},
            ),
        )
    )

    assert result == [["simp", "exact True.intro"]]
    assert transport.calls == [
        (
            "http://model.local/generate",
            {
                "text": "case main\n⊢ True",
                "sampling_params": {
                    "temperature": 0.2,
                    "stop": ["\n\n"],
                    "n": 2,
                },
            },
        )
    ]


def test_http_policy_client_renders_optional_policy_context() -> None:
    transport = FakeJsonTransport([{"outputs": [{"text": "trivial"}]}])
    client = HTTPPolicyClient(
        base_url="http://model.local/",
        http=transport,
    )

    result = asyncio.run(
        client.sample_tactics(
            [_state()],
            n=1,
            context=[PolicyContext(proof_prefix="constructor")],
        )
    )

    assert result == [["trivial"]]
    _, payload = transport.calls[0]
    assert payload["text"] == (
        "/- tactic history:\n"
        "constructor\n"
        "-/\n"
        "case main\n⊢ True"
    )


def test_http_policy_client_samples_whole_proofs() -> None:
    transport = FakeJsonTransport(
        [{"choices": [{"message": {"content": "```lean\nby trivial\n```"}}]}]
    )
    client = HTTPPolicyClient(base_url="http://model.local", http=transport)

    result = asyncio.run(
        client.sample_proofs(["theorem t : True := by"], n=1)
    )

    assert result == [["by trivial"]]


def test_http_policy_client_rejects_wrong_completion_count() -> None:
    transport = FakeJsonTransport([{"outputs": [{"text": "simp"}]}])
    client = HTTPPolicyClient(base_url="http://model.local", http=transport)

    with pytest.raises(HTTPClientError, match="expected 2"):
        asyncio.run(client.sample_tactics([_state()], n=2))


def test_http_value_client_parses_natural_language_boxed_score() -> None:
    transport = FakeJsonTransport(
        [{"outputs": [{"text": "The state is easy. \\boxed{0.82}"}]}]
    )
    client = HTTPValueClient(
        base_url="http://model.local",
        budget_tokens=64,
        http=transport,
    )

    result = asyncio.run(client.estimate([_state()]))

    assert result == [0.82]
    _, payload = transport.calls[0]
    assert payload["value_output_mode"] == "natural_language"
    assert payload["sampling_params"] == {"n": 1, "max_tokens": 64}
    assert "case main" in payload["text"]


def test_http_value_client_parses_numeric_head_score() -> None:
    transport = FakeJsonTransport([{"score": 0.25}])
    client = HTTPValueClient(
        base_url="http://model.local",
        output_mode="numeric_head",
        http=transport,
    )

    assert asyncio.run(client.estimate([_state()])) == [0.25]


def test_parse_boxed_or_json_score_accepts_json_text() -> None:
    assert parse_boxed_or_json_score('{"score": 0.5}') == 0.5
    assert parse_boxed_or_json_score('analysis {"score": 0.75}') == 0.75


def test_parse_boxed_or_json_score_rejects_invalid_scores() -> None:
    with pytest.raises(HTTPClientError):
        parse_boxed_or_json_score("\\boxed{1.2}")
    with pytest.raises(HTTPClientError):
        parse_boxed_or_json_score("not a score")
