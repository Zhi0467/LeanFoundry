"""Default Slime rollout runner for LeanFoundry search."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from leanfoundry.env_backend import EnvBackend, EnvBackendConfig
from leanfoundry.env_backend import make_env_backend
from leanfoundry.env_profiles import (
    require_pinned_env_profile,
    validate_theorem_batch_env_profiles,
)
from leanfoundry.policy import (
    HTTPValueClient,
    PolicyContext,
    PolicyClient,
    ValueClient,
    default_proof_prompt,
    default_tactic_prompt,
    default_value_prompt,
    parse_boxed_or_json_score,
    strip_code_fence,
    strip_to_tactic,
)
from leanfoundry.proofsearch import SearchAlgorithm, SearchConfig
from leanfoundry.proofsearch.to_rows import TrainingRow
from leanfoundry.schemas import FactorizedProofState, TheoremSpec
from leanfoundry.slime.policy import SGLangPolicyClient
from leanfoundry.slime.samples import SlimeSampleOutput
from leanfoundry.slime.samples import to_samples as rows_to_samples


class SlimeRolloutRunner:
    """Overridable composition root used by ``generate_rollout``."""

    def __init__(self) -> None:
        self._tokenizer: Any | None = None

    def build_env_backend(self, args: Any) -> EnvBackend:
        """Build the Lean execution backend for this rollout process."""

        env_profile = _required_pinned_env_profile_arg(args)
        return make_env_backend(
            EnvBackendConfig(
                api_url=_required_arg(args, "lean_api_url"),
                env_profile=env_profile,
                api_key=_arg(args, "lean_api_key", None),
                timeout_ms=_arg(args, "lean_timeout_ms", 120000),
                acquire_timeout_ms=_arg(args, "lean_acquire_timeout_ms", None),
                step_timeout_ms=_arg(args, "lean_step_timeout_ms", None),
                http_timeout_seconds=_arg(
                    args,
                    "lean_http_timeout_seconds",
                    600,
                ),
                retries=_arg(args, "lean_retries", 3),
                max_overloaded_retries=_arg(
                    args,
                    "lean_max_overloaded_retries",
                    0,
                ),
                overload_backoff_seconds=_arg(
                    args,
                    "lean_overload_backoff_seconds",
                    0.0,
                ),
            )
        )

    def build_policy_client(self, args: Any) -> PolicyClient:
        """Build the default SGLang policy client."""

        return SGLangPolicyClient(
            args,
            tactic_prompt=self.tactic_prompt,
            proof_prompt=self.proof_prompt,
            parse_tactic=self.parse_tactic,
            parse_proof=self.parse_proof,
        )

    def build_value_client(self, args: Any) -> ValueClient | None:
        """Build an optional value client from run config."""

        if not _arg(args, "lf_use_value_client", False):
            return None
        value_mode = _arg(args, "lf_value_mode", "unbonded")
        if value_mode == "bonded":
            base_url = _router_base_url(args)
        else:
            base_url = _required_arg(args, "lf_value_base_url")
        return HTTPValueClient(
            base_url=base_url,
            generate_path=_arg(args, "lf_value_generate_path", "/generate"),
            value_prompt=self.value_prompt,
            output_mode=_arg(
                args,
                "lf_value_output_mode",
                "natural_language",
            ),
            parse_score=self.parse_value_score,
            budget_tokens=_arg(args, "lf_value_budget_tokens", 256),
        )

    def search_config(self, args: Any) -> SearchConfig:
        """Map Slime args to LeanFoundry search config."""

        return SearchConfig(
            algorithm=SearchAlgorithm(
                _arg(args, "lf_search_algorithm", SearchAlgorithm.PUCT_TREE)
            ),
            max_tactic_calls=_arg(args, "lf_max_tactic_calls", 100),
            max_direct_candidates=_arg(args, "lf_max_direct_candidates", 64),
            tactics_per_expansion=_arg(args, "lf_tactics_per_expansion", 8),
            puct_exploration_weight=_arg(
                args,
                "lf_puct_exploration_weight",
                1.0,
            ),
            best_first_missing_value_score=_arg(
                args,
                "lf_best_first_missing_value_score",
                0.0,
            ),
            direct_candidates_per_round=_arg(
                args,
                "lf_direct_candidates_per_round",
                8,
            ),
            try_negation=_arg(args, "lf_try_negation", False),
            value_mode=_arg(args, "lf_value_mode", "unbonded"),
            censored_negative_weight=_arg(
                args,
                "lf_censored_negative_weight",
                0.25,
            ),
            min_censored_negative_effort=_arg(
                args,
                "lf_min_censored_negative_effort",
                50,
            ),
        )

    def source_samples(self, data_source: Any, args: Any) -> list[Any]:
        """Pull theorem records from Slime's data source."""

        batch_size = _arg(
            args,
            "over_sampling_batch_size",
            _arg(args, "rollout_batch_size", 1),
        )
        if hasattr(data_source, "get_samples"):
            samples = data_source.get_samples(batch_size)
        elif callable(data_source):
            samples = data_source(batch_size)
        else:
            raise TypeError(
                "data_source must be callable or expose get_samples"
            )
        return [_source_sample_from_group(sample) for sample in samples]

    def theorems_from_source(
        self,
        source_samples: Iterable[Any],
        args: Any,
    ) -> list[TheoremSpec]:
        """Convert Slime input samples into theorem specs."""

        return [
            self.theorem_from_source_sample(source_sample, args)
            for source_sample in source_samples
        ]

    def theorem_from_source_sample(
        self,
        source_sample: Any,
        args: Any,
    ) -> TheoremSpec:
        """Convert one Slime input sample or dict into a theorem spec."""

        prompt = _sample_field(source_sample, "prompt")
        metadata = dict(_sample_field(source_sample, "metadata", {}) or {})
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("source sample prompt must be a Lean statement")
        env_profile = metadata.get("env_profile")
        header = metadata.get("header")
        if not isinstance(env_profile, str) or env_profile == "default":
            raise ValueError("source sample metadata must include env_profile")
        if not isinstance(header, str):
            raise ValueError("source sample metadata must include header")
        return TheoremSpec(
            lean_statement=prompt,
            env_profile=env_profile,
            header=header,
            source=str(metadata.get("source", "unknown")),
            id=_optional_str(metadata.get("id") or metadata.get("theorem_id")),
            theorem_name=_optional_str(metadata.get("theorem_name")),
            informal_statement=_optional_str(
                metadata.get("informal_statement")
            ),
            initial_lean_block=_optional_str(
                metadata.get("initial_lean_block")
            ),
            allowed_axioms=_optional_str_list(metadata.get("allowed_axioms")),
        )

    def validate_env_profiles(
        self,
        theorems: list[TheoremSpec],
        args: Any,
    ) -> None:
        """Reject ambiguous or mixed env profiles unless explicitly allowed."""

        if not theorems:
            return
        validate_theorem_batch_env_profiles(
            theorems,
            backend_env_profile=_arg(
                args,
                "lean_env_profile",
                _arg(args, "env_profile", None),
            ),
            allow_mixed=_arg(args, "lf_allow_mixed_env_profiles", False),
        )

    def to_samples(
        self,
        rows: Iterable[TrainingRow],
        rollout_id: int,
        args: Any,
    ) -> SlimeSampleOutput:
        """Convert rows into Slime Sample groups."""

        row_list = list(rows)
        if not row_list:
            return []
        return rows_to_samples(
            row_list,
            rollout_id=rollout_id,
            tokenizer=self.build_tokenizer(args),
            args=args,
        )

    def build_tokenizer(self, args: Any) -> Any:
        """Load Slime's configured tokenizer."""

        if self._tokenizer is not None:
            return self._tokenizer
        from slime.utils.processing_utils import load_tokenizer

        self._tokenizer = load_tokenizer(
            args.hf_checkpoint,
            trust_remote_code=True,
        )
        return self._tokenizer

    def tactic_prompt(
        self,
        state: FactorizedProofState,
        context: PolicyContext | None = None,
    ) -> str:
        return default_tactic_prompt(state, context)

    def proof_prompt(self, theorem: TheoremSpec) -> str:
        return default_proof_prompt(theorem)

    def parse_tactic(self, text: str) -> str:
        return strip_to_tactic(text)

    def parse_proof(self, text: str) -> str:
        return strip_code_fence(text)

    def value_prompt(self, state: FactorizedProofState) -> str:
        return default_value_prompt(state)

    def parse_value_score(self, payload: str | dict[str, Any]) -> float:
        return parse_boxed_or_json_score(payload)


def _router_base_url(args: Any) -> str:
    return f"http://{args.sglang_router_ip}:{args.sglang_router_port}"


def _arg(args: Any, name: str, default: Any) -> Any:
    return getattr(args, name, default)


def _required_arg(args: Any, name: str) -> Any:
    value = getattr(args, name, None)
    if value is None:
        raise ValueError(f"missing required Slime arg: {name}")
    return value


def _required_pinned_env_profile_arg(args: Any) -> str:
    value = _arg(args, "lean_env_profile", _arg(args, "env_profile", None))
    if value is None:
        raise ValueError(
            "missing required Slime arg: lean_env_profile or env_profile"
        )
    env_profile = str(value)
    require_pinned_env_profile(env_profile)
    return env_profile


def _sample_field(sample: Any, name: str, default: Any = None) -> Any:
    if isinstance(sample, dict):
        return sample.get(name, default)
    return getattr(sample, name, default)


def _source_sample_from_group(sample: Any) -> Any:
    """Return the theorem prompt sample from a Slime prompt group."""

    if isinstance(sample, tuple):
        sample = list(sample)
    if not isinstance(sample, list):
        return sample
    if not sample:
        raise ValueError("data_source returned an empty sample group")
    return sample[0]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("allowed_axioms must be a list when present")
    return [str(item) for item in value]


__all__ = ["SlimeRolloutRunner"]
