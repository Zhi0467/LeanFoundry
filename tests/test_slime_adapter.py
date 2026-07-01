from __future__ import annotations

import asyncio
import importlib
import sys
import types
from argparse import Namespace
from dataclasses import dataclass, field
from enum import Enum

import pytest

from leanfoundry.proofsearch import SearchResult, SearchStatus
from leanfoundry.proofsearch.to_rows import TrainingRow, TrainingSegment
from leanfoundry.schemas import (
    FactorizedProofState,
    GoalComponent,
    PolicyExample,
    SelfCorrectTrace,
    SelfCorrectTurn,
    TrainingArtifacts,
)


class FakeTokenizer:
    def encode(
        self,
        text: str,
        add_special_tokens: bool = False,
    ) -> list[int]:
        return [ord(char) for char in text]


@dataclass
class FakeSample:
    class Status(Enum):
        PENDING = "pending"
        COMPLETED = "completed"
        TRUNCATED = "truncated"
        ABORTED = "aborted"
        FAILED = "failed"

    group_index: int | None = None
    index: int | None = None
    rollout_id: int | None = None
    prompt: str = ""
    tokens: list[int] = field(default_factory=list)
    response: str = ""
    response_length: int = 0
    label: str | None = None
    reward: float | None = None
    loss_mask: list[int] | None = None
    status: Status = Status.PENDING
    metadata: dict = field(default_factory=dict)
    train_metadata: dict | None = None


@dataclass
class FakeRolloutFnTrainOutput:
    samples: list[list[FakeSample]]
    metrics: dict | None = None


@dataclass
class FakeRolloutFnEvalOutput:
    data: dict
    metrics: dict | None = None


@pytest.fixture()
def fake_slime_modules(monkeypatch):
    slime_module = types.ModuleType("slime")
    utils_module = types.ModuleType("slime.utils")
    types_module = types.ModuleType("slime.utils.types")
    types_module.Sample = FakeSample
    rollout_module = types.ModuleType("slime.rollout")
    base_types_module = types.ModuleType("slime.rollout.base_types")
    base_types_module.RolloutFnTrainOutput = FakeRolloutFnTrainOutput
    base_types_module.RolloutFnEvalOutput = FakeRolloutFnEvalOutput
    processing_module = types.ModuleType("slime.utils.processing_utils")
    processing_module.loaded_checkpoints = []

    def load_tokenizer(checkpoint, **kwargs):
        processing_module.loaded_checkpoints.append((checkpoint, kwargs))
        return FakeTokenizer()

    processing_module.load_tokenizer = load_tokenizer
    monkeypatch.setitem(sys.modules, "slime", slime_module)
    monkeypatch.setitem(sys.modules, "slime.utils", utils_module)
    monkeypatch.setitem(sys.modules, "slime.utils.types", types_module)
    monkeypatch.setitem(sys.modules, "slime.rollout", rollout_module)
    monkeypatch.setitem(
        sys.modules,
        "slime.rollout.base_types",
        base_types_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "slime.utils.processing_utils",
        processing_module,
    )
    for module_name in [
        "leanfoundry.slime.samples",
        "leanfoundry.slime.runner",
        "leanfoundry.slime.rollout",
    ]:
        sys.modules.pop(module_name, None)
    return processing_module


def test_to_samples_sets_tokens_loss_mask_and_groups(
    fake_slime_modules,
) -> None:
    samples_module = importlib.import_module("leanfoundry.slime.samples")
    rows = [
        TrainingRow(
            kind="self_correct",
            prompt="P:",
            response="bad\nfeedback\ngood",
            reward=1.0,
            group_key="theorem-1",
            meta={"env_profile": "mathlib"},
            segments=(
                TrainingSegment("bad", True),
                TrainingSegment("\nfeedback\n", False),
                TrainingSegment("good", True),
            ),
        ),
        TrainingRow(
            kind="tactic",
            prompt="S:",
            response="simp",
            reward=1.0,
            group_key="theorem-1",
            meta={"env_profile": "mathlib"},
        ),
    ]

    groups = samples_module.to_samples(
        rows,
        rollout_id=9,
        tokenizer=FakeTokenizer(),
    )

    assert len(groups) == 1
    assert [sample.index for sample in groups[0]] == [0, 1]
    first = groups[0][0]
    assert first.status == FakeSample.Status.COMPLETED
    assert first.tokens == [ord(char) for char in "P:bad\nfeedback\ngood"]
    assert first.response_length == len("bad\nfeedback\ngood")
    assert first.loss_mask == [1, 1, 1] + [0] * 10 + [1, 1, 1, 1]
    assert first.metadata["lf_kind"] == "self_correct"
    assert first.metadata["rollout_id"] == 9


def test_runner_builds_theorems_and_rejects_mixed_profiles(
    fake_slime_modules,
) -> None:
    runner_module = importlib.import_module("leanfoundry.slime.runner")
    runner = runner_module.SlimeRolloutRunner()
    source_sample = FakeSample(
        prompt="theorem t : True := by",
        metadata={
            "env_profile": "mathlib",
            "header": "import Mathlib",
            "id": "t-1",
            "theorem_name": "t",
        },
    )

    theorem = runner.theorem_from_source_sample(source_sample, Namespace())

    assert theorem.id == "t-1"
    assert theorem.env_profile == "mathlib"
    with pytest.raises(ValueError, match="mixed env_profile"):
        runner.validate_env_profiles(
            [theorem, theorem.model_copy(update={"env_profile": "other"})],
            Namespace(lean_env_profile="default"),
        )


def test_runner_build_env_backend_requires_pinned_profile(
    fake_slime_modules,
) -> None:
    runner_module = importlib.import_module("leanfoundry.slime.runner")
    runner = runner_module.SlimeRolloutRunner()

    backend = runner.build_env_backend(
        Namespace(lean_api_url="http://lean", lean_env_profile="mathlib")
    )

    assert backend.config.env_profile == "mathlib"
    with pytest.raises(ValueError, match="lean_env_profile"):
        runner.build_env_backend(Namespace(lean_api_url="http://lean"))
    with pytest.raises(ValueError, match="default"):
        runner.build_env_backend(
            Namespace(lean_api_url="http://lean", lean_env_profile="default")
        )


def test_runner_source_samples_accepts_slime_groups_and_callables(
    fake_slime_modules,
) -> None:
    runner_module = importlib.import_module("leanfoundry.slime.runner")
    runner = runner_module.SlimeRolloutRunner()
    first = FakeSample(prompt="theorem a : True := by")
    duplicate = FakeSample(prompt="theorem a : True := by")
    second = FakeSample(prompt="theorem b : True := by")

    class GroupedDataSource:
        def get_samples(self, count):
            assert count == 2
            return [[first, duplicate], [second]]

    grouped = runner.source_samples(
        GroupedDataSource(),
        Namespace(rollout_batch_size=2),
    )
    callable_rows = runner.source_samples(
        lambda count: [first] if count == 1 else [],
        Namespace(over_sampling_batch_size=1),
    )

    assert grouped == [first, second]
    assert callable_rows == [first]
    with pytest.raises(ValueError, match="empty sample group"):
        runner.source_samples(
            lambda count: [[]],
            Namespace(over_sampling_batch_size=1),
        )


def test_runner_build_tokenizer_uses_hf_checkpoint(
    fake_slime_modules,
) -> None:
    runner_module = importlib.import_module("leanfoundry.slime.runner")
    runner = runner_module.SlimeRolloutRunner()

    tokenizer = runner.build_tokenizer(Namespace(hf_checkpoint="model/path"))
    second = runner.build_tokenizer(Namespace(hf_checkpoint="ignored"))

    assert isinstance(tokenizer, FakeTokenizer)
    assert second is tokenizer
    assert fake_slime_modules.loaded_checkpoints == [
        ("model/path", {"trust_remote_code": True})
    ]


def test_runner_builds_bonded_and_unbonded_value_clients(
    fake_slime_modules,
) -> None:
    from leanfoundry.policy import HTTPValueClient

    runner_module = importlib.import_module("leanfoundry.slime.runner")
    runner = runner_module.SlimeRolloutRunner()

    bonded = runner.build_value_client(
        Namespace(
            lf_use_value_client=True,
            lf_value_mode="bonded",
            sglang_router_ip="127.0.0.1",
            sglang_router_port=30000,
            lf_value_output_mode="natural_language",
            lf_value_budget_tokens=128,
        )
    )
    unbonded = runner.build_value_client(
        Namespace(
            lf_use_value_client=True,
            lf_value_mode="unbonded",
            lf_value_base_url="http://value.local",
            lf_value_output_mode="numeric_head",
            lf_value_budget_tokens=16,
        )
    )

    assert isinstance(bonded, HTTPValueClient)
    assert bonded.base_url == "http://127.0.0.1:30000"
    assert bonded.output_mode == "natural_language"
    assert bonded.budget_tokens == 128
    assert isinstance(unbonded, HTTPValueClient)
    assert unbonded.base_url == "http://value.local"
    assert unbonded.output_mode == "numeric_head"
    assert unbonded.budget_tokens == 16


def test_async_generate_rollout_runs_search_and_returns_samples(
    fake_slime_modules,
    monkeypatch,
) -> None:
    rollout_module = importlib.import_module("leanfoundry.slime.rollout")
    runner_module = importlib.import_module("leanfoundry.slime.runner")

    class FakeEnv:
        async def connect(self) -> None:
            pass

    class FakeRunner(runner_module.SlimeRolloutRunner):
        def build_env_backend(self, args):
            return FakeEnv()

        def build_policy_client(self, args):
            return object()

        def build_value_client(self, args):
            return None

        def build_tokenizer(self, args):
            return FakeTokenizer()

    source_sample = FakeSample(
        prompt="theorem t : True := by",
        metadata={
            "env_profile": "mathlib",
            "header": "import Mathlib",
            "id": "t-1",
        },
    )

    class FakeDataSource:
        def get_samples(self, count):
            assert count == 1
            return [source_sample]

    state = FactorizedProofState(
        env_profile="mathlib",
        goal_components=[
            GoalComponent(target="True", pretty="⊢ True", hypotheses=[])
        ],
        pretty_state="⊢ True",
    )

    model_versions = []

    async def fake_run_search_batch(theorems, **kwargs):
        assert theorems[0].id == "t-1"
        model_versions.append(kwargs["model_version"])
        return [
            SearchResult(
                attempt_id="attempt-1",
                theorem_id="t-1",
                status=SearchStatus.PROVED,
                training_artifacts=TrainingArtifacts(
                    policy_examples=[
                        PolicyExample(
                            state=state,
                            tactic="trivial",
                            theorem_id="t-1",
                            env_profile="mathlib",
                            depth=0,
                        )
                    ]
                ),
                search_budget_used=1,
            )
        ]

    monkeypatch.setattr(rollout_module, "_RUNNER", FakeRunner())
    monkeypatch.setattr(rollout_module, "_ENV", None)
    monkeypatch.setattr(rollout_module, "_POLICY", None)
    monkeypatch.setattr(rollout_module, "_VALUE", None)
    monkeypatch.setattr(rollout_module, "_VALUE_BUILT", False)
    monkeypatch.setattr(
        rollout_module,
        "run_search_batch",
        fake_run_search_batch,
    )

    output = asyncio.run(
        rollout_module.async_generate_rollout(
            Namespace(
                over_sampling_batch_size=1,
                lean_env_profile="mathlib",
            ),
            3,
            FakeDataSource(),
        )
    )

    assert isinstance(output, FakeRolloutFnTrainOutput)
    assert output.metrics == {
        "lf_results": 1,
        "lf_rows": 1,
        "lf_rows_tactic": 1,
        "lf_status_proved": 1,
    }
    assert len(output.samples) == 1
    assert output.samples[0][0].response == "trivial"
    assert output.samples[0][0].metadata["lf_kind"] == "tactic"

    eval_output = asyncio.run(
        rollout_module.async_generate_rollout(
            Namespace(
                over_sampling_batch_size=1,
                lean_env_profile="mathlib",
            ),
            4,
            FakeDataSource(),
            evaluation=True,
        )
    )

    assert isinstance(eval_output, FakeRolloutFnEvalOutput)
    assert eval_output.data["t-1"]["status"] == "proved"
    assert eval_output.data["t-1"]["search_budget_used"] == 1
    assert eval_output.metrics == {
        "lf_results": 1,
        "lf_rows": 1,
        "lf_rows_tactic": 1,
        "lf_status_proved": 1,
    }
    assert model_versions == [3, 4]


def test_async_generate_rollout_can_emit_failed_self_correct_negatives(
    fake_slime_modules,
    monkeypatch,
) -> None:
    rollout_module = importlib.import_module("leanfoundry.slime.rollout")
    runner_module = importlib.import_module("leanfoundry.slime.runner")

    class FakeEnv:
        async def connect(self) -> None:
            pass

    class FakeRunner(runner_module.SlimeRolloutRunner):
        def build_env_backend(self, args):
            return FakeEnv()

        def build_policy_client(self, args):
            return object()

        def build_value_client(self, args):
            return None

        def build_tokenizer(self, args):
            return FakeTokenizer()

    source_sample = FakeSample(
        prompt="theorem t : True := by",
        metadata={
            "env_profile": "mathlib",
            "header": "import Mathlib",
            "id": "t-1",
        },
    )

    class FakeDataSource:
        def get_samples(self, count):
            assert count == 1
            return [source_sample]

    async def fake_run_search_batch(theorems, **kwargs):
        return [
            SearchResult(
                attempt_id="attempt-1",
                theorem_id="t-1",
                status=SearchStatus.PROVED,
                training_artifacts=TrainingArtifacts(
                    self_correct_traces=[
                        SelfCorrectTrace(
                            turns=[
                                SelfCorrectTurn(
                                    turn_index=1,
                                    proof="bad proof",
                                    verifier_status="rejected",
                                    verifier_feedback="error: bad",
                                    verify_item_id="verify:1",
                                ),
                                SelfCorrectTurn(
                                    turn_index=2,
                                    proof="good proof",
                                    verifier_status="accepted",
                                    verify_item_id="verify:2",
                                    accepted=True,
                                ),
                            ]
                        )
                    ]
                ),
                search_budget_used=2,
            )
        ]

    monkeypatch.setattr(rollout_module, "_RUNNER", FakeRunner())
    monkeypatch.setattr(rollout_module, "_ENV", None)
    monkeypatch.setattr(rollout_module, "_POLICY", None)
    monkeypatch.setattr(rollout_module, "_VALUE", None)
    monkeypatch.setattr(rollout_module, "_VALUE_BUILT", False)
    monkeypatch.setattr(
        rollout_module,
        "run_search_batch",
        fake_run_search_batch,
    )

    output = asyncio.run(
        rollout_module.async_generate_rollout(
            Namespace(
                over_sampling_batch_size=1,
                lean_env_profile="mathlib",
                lf_include_failed_self_correct_negatives=True,
            ),
            5,
            FakeDataSource(),
        )
    )

    assert output.metrics == {
        "lf_results": 1,
        "lf_rows": 2,
        "lf_rows_self_correct": 2,
        "lf_status_proved": 1,
    }
    samples = output.samples[0]
    assert [sample.response for sample in samples] == [
        "bad proof",
        "good proof",
    ]
    assert [sample.reward for sample in samples] == [0.0, 1.0]
    assert samples[0].metadata["self_correct_objective"] == (
        "failed_negative"
    )
