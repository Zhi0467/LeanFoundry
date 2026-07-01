# Slime Rollout Adapter — Implementation Spec

Self-contained brief to implement the LeanFoundry↔Slime training adapter
**end to end**. An agent with this repo checked out and this file should be able
to implement it without further context. Read
[`AGENTS.md`](../../AGENTS.md) for repo conventions first. Conceptual background:
design notes **v11.13** (adapter ownership) and **v11.14** (training-data model)
in [`leanfoundry_system_design_v11.md`](leanfoundry_system_design_v11.md), and
the "Slime adapter plan" + "Training-data model" sections in
[`todo.md`](../internal-trackers/todo.md). This spec is the authoritative
implementation contract; if it disagrees with those prose notes, this wins.

Scope = the **full training adapter contract**. The shortest runnable route is
roadmap **Phase 2** (reference clients) + **Phase 3** (the adapter), but the
whole implementation also includes self-correction turn artifacts, value-client
modes, negation-backed DISPROVED labels, and env-profile enforcement. Optional
tree-to-proof rendering is still out of scope for training data.

---

## 0. Status and prerequisites (already done)

- Slime is pinned in [`pyproject.toml`](../../pyproject.toml) `[tool.uv.sources]`
  to commit `a897e1f40357fdf3b148f1eb4ce26e1aeccfcd2c`, exposed only through the
  `[training]` optional extra. **Every Slime API in §3 is quoted from that exact
  commit.** If you bump the pin, re-verify §3 and re-run the compat tests.
- `tests/test_slime_compat.py` (marker `slime`) asserts the `Sample` data
  contract. Extend it as you depend on more Slime surface. Run with
  `uv run --extra training pytest -m slime` on a CUDA box; it skips otherwise.
- Path-A search core is implemented and is what you call: `run_search_batch`,
  `SearchConfig`, `TheoremSpec`, the `PolicyClient`/`ValueClient` protocols, the
  `EnvBackend`, and the `TrainingArtifacts` envelope. Signatures in §2.

## 1. The training-data model (why the branches exist)

LeanFoundry has **two generation modes = two training targets**. The adapter
turns each into Slime `Sample`s. This is the whole reason `to_samples` branches.

| Mode (`SearchConfig.algorithm`) | Produces | Slime `Sample` shape |
|---|---|---|
| Tree (`PUCT_TREE`/`BEST_FIRST`/`AND_OR_TREE`) | Markovian per-node `(state, tactic)` step pairs (lineage A; search distilled into a step policy) | **one Sample per proved node**: prompt = state, response = tactic |
| Direct (`DIRECT`) | One verified whole proof per candidate (lineage B) | **one Sample per candidate**: prompt = statement, response = whole proof |
| `SELF_CORRECT` | Multi-round whole-proof + verifier feedback | **one multi-turn Sample**: mask the verifier-feedback spans, train the model's proof turns |

Non-negotiable consequences (see v11.14):
- **Never render a whole proof from the tree to make training data.** Tree →
  step pairs (no render); direct → the model's own proof (no render).
- **No history-conditional / injected-state trajectory Sample.** A proof state
  is Markov. `loss_mask` is used only within a Sample's own response and for
  self-correct feedback masking — never to interleave goal states.
- Reward/grouping/enhancement (EI vs GRPO, `/- tactic state -/` comments,
  reflection) are training-side knobs; the adapter exposes hooks, picks neutral
  defaults, and bakes nothing in.

### 1.a What the literature says

Tree search producing step-level data is not a lazy fallback. It matches the
step-prover lineage, not a shortcut around proof rendering:

- HyperTree Proof Search (arXiv:2205.11491) frames theorem proving as
  interaction between a policy over proof states/goals and tactics plus a
  critic/value signal, then improves the prover with online search traces. This
  is close to the mechanism family LeanFoundry is exposing, so state-tactic
  search data should be treated as prior art, not as our novelty claim.
- LeanDojo/ReProver (arXiv:2306.15626) trains and evaluates a tactic generator
  from proof states, with retrieval concatenated into the state prompt.
- BFS-Prover (arXiv:2502.03438) builds expert-iteration data from successful
  tree-search trajectories and DPO preference pairs over state-tactic choices.
- DeepSeek-Prover-V1.5 (arXiv:2408.08152) is the useful comparison on the other
  side: strong whole-proof/RL training plus RMaxTS as an inference-time search
  wrapper improves over single-pass whole-proof generation, so crossed eval is
  needed before attributing gains to the training target itself.

So the default LeanFoundry tree objective is expert-iteration / SFT over
positive step rows, optionally paired with value labels. The research question
is not "can we invent state-tactic data?" — the literature already uses it. The
question for the downstream training repo is whether, under a fixed curriculum,
env profile, verifier budget, and eval suite, lineage-A step rows, lineage-B
whole-proof rows, self-correction, or mixed data produce the best prover in
their native and crossed eval modes. Use GRPO only if the trainer explicitly
supports the tree row grouping chosen in §7.

Whole-proof and self-correction data are a different lineage. They train on
statement -> proof, or statement + failed proof + Lean feedback -> corrected
proof. Mixing the lineages is allowed, but the adapter must keep `lf_kind` and
metrics separated so the training repo can ask whether whole-proof, step-policy,
or mixed training actually wins.

## 2. LeanFoundry APIs you call (exact, from the current repo)

```python
# leanfoundry/proofsearch/driver.py
async def run_search_batch(
    theorems: Sequence[TheoremSpec],
    *,
    policy_client: PolicyClient,
    value_client: ValueClient | None,
    env_backend: EnvBackend,
    config: SearchConfig,
    max_concurrent: int | None = None,
    attempt_contexts: Sequence[SearchAttemptContext] | None = None,
    replay_store: ReplayStore | None = None,
    model_version: int = 0,
) -> list[SearchResult]: ...

# leanfoundry/policy/base.py — IMPLEMENT THESE (Protocols, structural)
class PolicyClient(Protocol):
    async def sample_tactics(self, states: Sequence[FactorizedProofState], *,
                             n: int, params=None) -> list[list[str]]: ...
    async def sample_proofs(self, prompts: Sequence[str], *,
                            n: int, params=None) -> list[list[str]]: ...
class ValueClient(Protocol):
    async def estimate(self, states: Sequence[FactorizedProofState]) -> list[float]: ...
class PolicySamplingParams(LeanFoundryModel):
    temperature: float = 0.8; top_p: float | None = 0.95
    max_tokens: int | None = None; extra: Mapping | None = None

# leanfoundry/proofsearch/base.py
class SearchAlgorithm(StrEnum):
    DIRECT; SELF_CORRECT; TACTIC_BEAM; BEST_FIRST; PUCT_TREE; AND_OR_TREE; OPTIMISTIC; MCGS; AND_OR_MCGS
class SearchConfig(LeanFoundryModel):           # algorithm-neutral; one config, both modes
    algorithm: SearchAlgorithm = PUCT_TREE
    max_tactic_calls: int = 100; tactics_per_expansion: int = 8
    max_direct_candidates: int = 64; direct_candidates_per_round: int = 8
    puct_exploration_weight: float = 1.0; best_first_missing_value_score: float = 0.0
    try_negation: bool = False
    value_mode: Literal["bonded","unbonded"] = "unbonded"
    censored_negative_weight: float = 0.25; min_censored_negative_effort: int = 50
class SearchResult(LeanFoundryModel):
    status: SearchStatus            # PROVED|DISPROVED|EXHAUSTED|ERROR|CANCELLED
    theorem_id: str | None; proof_tree: ProofTree | None
    training_artifacts: TrainingArtifacts | None
    search_budget_used: int; diagnostics: dict[str, float|int|str]
    attempt_id / search_item_id / verify_item_id: str | None

# leanfoundry/schemas/theorem.py
class TheoremSpec(LeanFoundryModel):
    lean_statement: str; env_profile: str; header: str
    source: str = "unknown"; id: str | None = None; theorem_name: str | None = None
    informal_statement: str | None = None; initial_lean_block: str | None = None
    allowed_axioms: list[str] | None = None

# leanfoundry/schemas/trajectory.py + value.py — what you READ to build Samples
class TrainingArtifacts: proof_candidates: list[ProofTree]; policy_examples: list[PolicyExample]
                         value_labels: list[ValueLabel]; failures: list[ExtractionFailure]; diagnostics: dict
class PolicyExample:     state: FactorizedProofState; proof_prefix: str; tactic: str
                         theorem_id: str|None; env_profile: str; depth: int; model_version: int|None
class ProofTree:         roots: list[TacticNode]; rendered_lean: str; verified: bool
class ValueLabel:        state: FactorizedProofState; label: Literal[0,1]; weight: float
                         disproved: bool; theorem_id: str|None; env_profile: str; ...
class FactorizedProofState: env_profile: str; goal_components: list[GoalComponent]
                            pretty_state: str; state_token: str|None; serialized_lean_state: bytes|None
class GoalComponent:     target: str; pretty: str; hypotheses: list[LocalContextEntry]; name: str|None

# Backend construction
from leanfoundry.env_backend import EnvBackendConfig, make_env_backend
# EnvBackendConfig(api_url: str, env_profile="default", api_key=None, timeout_ms=5000, ...)
```

The **policy prompt content** is built from `FactorizedProofState`: use
`state.pretty_state` (already prompt-facing) for the tactic prompt; for direct,
build the prompt from `TheoremSpec.header + lean_statement` (+ optional
`informal_statement`). Exact templating is a model-specific hook (§4.a/§5).

## 3. Slime APIs you use (verbatim from commit `a897e1f`)

```python
# Entry point Slime calls (default --rollout-function-path
#   = slime.rollout.sglang_rollout.generate_rollout). We REPLACE it with ours:
#   --rollout-function-path leanfoundry.slime.generate_rollout
# slime/rollout/sglang_rollout.py
def generate_rollout(
    args: Namespace, rollout_id: int, data_source: Any, evaluation: bool = False
) -> RolloutFnTrainOutput | RolloutFnEvalOutput: ...
# from slime.rollout.base_types import RolloutFnEvalOutput, RolloutFnTrainOutput
# from slime.utils.types import Sample
#
# In Slime's default wrapper, prompts come from
# `data_source.get_samples(args.over_sampling_batch_size)`, and each group has
# exactly `args.n_samples_per_prompt` generated candidates. We replace the whole
# rollout function, so tree mode may return compact fanout groups; see §7.
# Training return: RolloutFnTrainOutput(samples=<regular-or-compact-sample-groups>, metrics=<dict>)

# slime/utils/types.py
@dataclass
class Sample:
    prompt; tokens; response; response_length; reward; label; loss_mask
    rollout_log_probs; status  # Sample.Status: PENDING|COMPLETED|TRUNCATED|ABORTED|FAILED
    metadata; train_metadata; ...
    def append_response_tokens(self, args=None, *, tokens=None, log_probs=None,
                               trainable: bool = True, meta_info=None, text=None,
                               update_terminal_info=True): ...
    # also: to_dict(), from_dict(), get_reward_value()

# SGLang generation endpoint (from examples/search-r1/generate_with_search.py):
#   POST  http://{args.sglang_router_ip}:{args.sglang_router_port}/generate
#   payload: {"text": <prompt+accumulated response>, "sampling_params": {...}}
#   response carries generated token ids + (optional) logprobs.

# Relevant args (slime/utils/arguments.py + slime/backends/sglang_utils/arguments.py):
#   --rollout-function-path        default slime.rollout.sglang_rollout.generate_rollout
#   --custom-generate-function-path  per-sample def generate(args, sample, sampling_params)->Sample
#   --rollout-batch-size           required, # prompts per step
#   --n-samples-per-prompt         default 1
#   --over-sampling-batch-size     batch the data_source is called with
#   args.sglang_router_ip / args.sglang_router_port   SGLang server address
```

**CONFIRM at implementation time (do not assume):**
- C1. `data_source` call form — callable `data_source(n)` vs
  `data_source.get_samples(n)`. The theorem payload contract is fixed here:
  the input `Sample.prompt` is the Lean statement, and `Sample.metadata` must
  carry at least `env_profile`, `header`, and a stable theorem id/name when one
  exists. Optional metadata: `source`, `theorem_name`, `allowed_axioms`,
  `informal_statement`, and `initial_lean_block`. `theorems_from_source` fails
  loudly if required fields are missing; it does not invent defaults.
- C2. `/generate` response schema (key names for output token ids / logprobs /
  finish reason). Read `examples/search-r1/generate_with_search.py`.
- C3. `append_response_tokens` — does it accept token ids only, or also tokenize
  `text=`? Whether you must pass a tokenizer via `args`. Read the method body in
  `slime/utils/types.py`.
- C4. `RolloutFnTrainOutput`/`RolloutFnEvalOutput` constructor fields and the
  eval-path shape. Read `slime/rollout/base_types.py`.
- C5. Which Slime loss/objective the training config uses for each mode. Direct
  GRPO-style objectives expect fixed candidate groups; tree-step EI/SFT returns
  compact fanout groups with shared `Sample.rollout_id` (§7), so do not route
  it through a fixed-per-prompt GRPO loss unless that loss explicitly supports
  compact tree fanout.

> **2026-06-30:** C1, C3, C4, and C6 are now checked against the pinned Slime
> commit and covered by fake adapter tests or `tests/test_slime_compat.py`:
> grouped `get_samples(...)` output is normalized to one theorem per prompt
> group, callable sources are accepted, tokenizer loading uses
> `args.hf_checkpoint`, and train/eval return objects match
> `RolloutFnTrainOutput` / `RolloutFnEvalOutput`. C2 remains endpoint-live
> coverage, and C5 remains training-config work.
>
> **2026-07-01:** C3/C6 are now sharper: the pinned Slime
> `Sample.append_response_tokens(...)` requires rollout log-probabilities for
> trainable tokens. `leanfoundry/slime/samples.py` therefore uses native append
> only when a row carries `slime_response_log_probs`; verifier-grounded
> LeanFoundry search rows without SGLang log-probs use an explicit
> `leanfoundry_verified_without_rollout_logprobs` construction path. The live
> smoke now covers direct, `puct_tree`, and `self_correct`, and requires at
> least one emitted row. `LEANFOUNDRY_SLIME_E2E_LOCAL_GENERATOR=1` starts a
> deterministic SGLang-compatible `/generate` endpoint plus temporary HF
> tokenizer for local adapter e2e when no deployed router exists.
>
> **2026-07-01:** `tests/test_slime_tree_ei_live.py` adds a tiny real-SGLang
> tree EI e2e. It writes a tiny random GPT-2 checkpoint, launches real SGLang,
> runs `puct_tree` against live Lean, asserts the emitted Slime `Sample` is a
> tactic row, and performs one local `torch` optimizer step over
> `tokens`/`response_length`/`loss_mask`. This found and fixed the tree-row
> contract bug: Slime rollouts now suppress rendered `whole_proof` rows for tree
> algorithms by default; `lf_include_tree_whole_proof_rows=True` is the explicit
> opt-in for tree-rendered whole-proof enrichment/audit rows.
>
> **2026-07-01:** LeanFoundry now exports
> `leanfoundry.slime.add_leanfoundry_arguments(parser)` for Slime's
> `parse_args(add_custom_arguments=...)` hook. It registers LeanFoundry-owned
> `lean_*` and `lf_*` flags; Slime remains responsible for native training,
> checkpoint, rollout-batch, and SGLang-router arguments.
>
> **2026-07-01:** Tree/tactic rows now return Slime's compact fanout shape and
> assign trainer rollout ids per theorem search. The pinned Slime
> `build_dp_schedule(...)` path is covered by `tests/test_slime_compat.py`,
> proving that two theorem searches with three emitted step samples schedule as
> two rollouts. This is scheduler-contract evidence; a full Slime/Megatron
> train step with `loss_type=sft_loss` is still the remaining live check.
>
> **2026-07-01:** The local training compatibility path now reaches Slime's
> trainer-side data boundary. With `megatron-core` and `torch-memory-saver` in
> the `[training]` extra, `tests/test_slime_compat.py` runs compact tree fanout
> through the pinned Slime `RolloutManager` conversion/split methods,
> `process_rollout_data(...)`, and Megatron `DataIterator`. It asserts the
> train-side rollout ids, per-rollout mask sums, global batch sizes, and
> microbatch indices consumed by the model actor iterator. The full actor/model
> step remains live-stack gated because the project venv intentionally does not
> install SGLang and the pinned installed Slime package omits its source
> `megatron_utils/kernels` package.
- C6. Tokenizer source and token/loss-mask semantics. The adapter is responsible
  for constructing the exact tokens the trainer consumes. It must use Slime's
  configured tokenizer/checkpoint (or verified SGLang token ids when returned),
  set `response_length` to the number of generated response tokens, and keep
  `loss_mask` aligned with the response tokens.

## 4. Module layout — build exactly this

```
leanfoundry/policy/
  http_client.py        # Phase 2: HTTPPolicyClient + HTTPValueClient (NO slime import)
leanfoundry/proofsearch/
  to_rows.py            # Phase 2: to_training_rows() (NO slime import)
leanfoundry/slime/      # Phase 3: the ONLY place that imports slime/sglang; under [training]
  __init__.py           #   re-exports generate_rollout + add_leanfoundry_arguments
  arguments.py          # argparse hook for LeanFoundry-owned lean_* / lf_* flags
  policy.py             # SGLangPolicyClient(HTTPPolicyClient)
  samples.py            # to_samples(): rows -> Slime Sample groups (the 3 branches)
  runner.py             # SlimeRolloutRunner (overridable methods)
  rollout.py            # generate_rollout(args, rollout_id, data_source, evaluation)
```

**Invariant test (add it):** a test that imports `leanfoundry.proofsearch` and
`leanfoundry.policy` with `slime` uninstalled and asserts no `ModuleNotFoundError`
— i.e. `leanfoundry/slime/` is never imported by core. `policy/http_client.py`
and `proofsearch/to_rows.py` must not import slime either.

### 4.a `HTTPPolicyClient` (Phase 2, `policy/http_client.py`)
Model-agnostic `PolicyClient` over an OpenAI/SGLang-compatible HTTP endpoint.

```python
class HTTPPolicyClient:  # structurally a PolicyClient
    def __init__(self, *, base_url, generate_path="/generate",
                 tactic_prompt: Callable[[FactorizedProofState], str] = default_tactic_prompt,
                 proof_prompt:  Callable[[TheoremSpec], str]         = default_proof_prompt,
                 parse_tactic:  Callable[[str], str] = strip_to_tactic,
                 parse_proof:   Callable[[str], str] = strip_code_fence,
                 http=None): ...
    async def sample_tactics(self, states, *, n, params=None) -> list[list[str]]:
        # for each state: POST tactic_prompt(state), n samples; map completions via parse_tactic
    async def sample_proofs(self, prompts, *, n, params=None) -> list[list[str]]:
        # prompts are already strings; POST, n samples; map via parse_proof
```
- Owns: HTTP transport, concurrency, retry, n-sampling, the default state→prompt
  rendering (`state.pretty_state`). The four `*_prompt`/`parse_*` callables are
  the **only** model-specific surface; everything else is reusable. No proof
  search logic, no slime.
- `default_tactic_prompt(state)` → `state.pretty_state` (+ optional newline cue).
  `default_proof_prompt(theorem)` → `f"{theorem.header}\n{theorem.lean_statement}"`.

### 4.a.1 `HTTPValueClient` (Phase 2, `policy/http_client.py`)
Model-agnostic `ValueClient` over the same transport. It supports both
deployment modes (bonded vs unbonded) and both output formats (numeric head vs
natural-language scalar).

```python
class HTTPValueClient:  # structurally a ValueClient
    def __init__(self, *, base_url, generate_path="/generate",
                 value_prompt: Callable[[FactorizedProofState], str] = default_value_prompt,
                 output_mode: Literal["numeric_head", "natural_language"] = "natural_language",
                 parse_score: Callable[[str | dict], float] = parse_boxed_or_json_score,
                 budget_tokens: int = 256,
                 http=None): ...
    async def estimate(self, states) -> list[float]:
        # returns one finite score per state in [0, 1], or raises a structured error
```

- **Unbonded**: points at a separate value endpoint/checkpoint.
- **Bonded**: points at the same SGLang/policy checkpoint but uses a value task
  prompt/token so the same model produces a value estimate. Bonding is about
  model ownership and label emission; `ValueClient.estimate(...)` still returns
  floats.
- **Numeric-head mode**: the endpoint returns a score/logit/JSON scalar; parse
  directly and validate `[0, 1]`.
- **Natural-language mode**: the prompt may allow the model to think within
  `budget_tokens`, but the final answer must contain a parseable scalar, e.g.
  `\boxed{0.73}` or `{"score": 0.73}`. Invalid/missing/out-of-range outputs are
  diagnostics or hard failures, not silent `0.5` defaults unless a caller
  explicitly configures a fallback.

### 4.b `to_training_rows()` (Phase 2, `proofsearch/to_rows.py`)
Collapse a `SearchResult` into framework-neutral rows (no slime types).

```python
@dataclass(frozen=True)
class TrainingRow:
    kind: Literal["tactic", "whole_proof", "self_correct"]
    prompt: str            # what the model conditioned on
    response: str          # what the model should produce (the trainable text)
    reward: float          # see §6
    group_key: str         # theorem id / attempt id — rows sharing a search
    meta: dict             # env_profile, theorem_id, depth, state_token, etc.
    segments: tuple[TrainingSegment, ...] = ()

@dataclass(frozen=True)
class TrainingSegment:
    text: str
    trainable: bool

def to_training_rows(result: SearchResult, theorem: TheoremSpec) -> list[TrainingRow]:
    # algorithm == DIRECT:       one row per accepted ProofTree in proof_candidates
    #                            (prompt=proof_prompt(theorem), response=rendered_lean, reward=1.0)
    # algorithm in TREE family:  one row per PolicyExample (kind="tactic",
    #                            prompt=tactic_prompt(ex.state), response=ex.tactic, reward=1.0)
    # algorithm == SELF_CORRECT: turns reconstructed from the attempt (see §1 row 3)
```
Reuses the rendering helpers (`tactic_prompt`/`proof_prompt`) so `to_samples` is
a pure Slime wrap. **Does not import slime.**

`SELF_CORRECT` is backed by the implemented neutral trace artifact:
`SelfCorrectTrace(turns=[SelfCorrectTurn(...)])`. Each turn carries the proof
text proposed by the model, verifier status, rendered verifier feedback,
`verify_item_id`, and whether the turn was accepted. `to_training_rows` emits
`kind="self_correct"` rows for accepted corrections whose prompt contains the
theorem plus prior failed proof and Lean feedback, and whose trainable response
is the accepted correction. If a multi-turn `Sample` is used, `segments` marks
verifier-feedback spans `trainable=False` and model proof spans
`trainable=True`.

### 4.c `SGLangPolicyClient` (Phase 3, `slime/policy.py`)
```python
class SGLangPolicyClient(HTTPPolicyClient):
    def __init__(self, args, **hooks):
        super().__init__(base_url=f"http://{args.sglang_router_ip}:{args.sglang_router_port}",
                         generate_path="/generate", **hooks)
```
Only adds: endpoint from Slime `args`, and (if needed) a payload adapter to
Slime's `/generate` schema. Model-specific hooks pass through to the base.

### 4.d `to_samples()` (Phase 3, `slime/samples.py`)
```python
from slime.utils.types import Sample
SlimeSampleOutput = list[list[Sample] | list[list[Sample]]]

def to_samples(rows: list[TrainingRow], *, rollout_id, tokenizer, args) -> SlimeSampleOutput:
    # 1. build a Sample per row:
    #      s = Sample(prompt=row.prompt, label=..., metadata={...})
    #      s.reward = row.reward
    #      If row.meta carries slime_response_log_probs:
    #          append segments with Sample.append_response_tokens(...,
    #          log_probs=<matching trainable slice>, trainable=...)
    #      Else:
    #          append verifier-grounded row tokens directly, setting response,
    #          response_length, and loss_mask without pretending rollout
    #          log-probs exist.
    #      s.status = Sample.Status.COMPLETED
    # 2. assign Sample.index / group_index and rollout identity:
    #      tree/tactic rows from one theorem search share one Sample.rollout_id
    #      and keep the Slime step id in metadata["slime_rollout_id"].
    #      direct/self-correct rows get one rollout id per sample by default.
    # 3. group into Slime's regular or compact-fanout shape honoring §7.
```

Token construction is adapter-owned. For tactic rows, the whole tactic response
is trainable. For whole-proof rows, the whole verified proof response is
trainable. For self-correct rows, verifier feedback and any other environment
observations are appended with `trainable=False`; model proof attempts are
appended with `trainable=True`. Native Slime append is only valid for trainable
spans when rollout log-probs exist; otherwise the explicit verified-row fallback
is the correct path. The adapter must assert:
`len(sample.loss_mask) == sample.response_length`,
`sample.response_length == len(response_token_ids)`, and `sample.tokens` matches
the prompt+response tokenization expected by the Slime trainer.

### 4.e `SlimeRolloutRunner` (Phase 3, `slime/runner.py`)
Every step is an overridable method; the training repo subclasses and overrides
only model-specific ones.
```python
class SlimeRolloutRunner:
    # construction (built once, reused across rollout_ids):
    def build_env_backend(self, args) -> EnvBackend: ...        # KiminaEnvBackend(EnvBackendConfig(api_url=args.lean_api_url))
    def build_policy_client(self, args) -> PolicyClient: ...     # SGLangPolicyClient(args, **self.hooks())
    def build_value_client(self, args) -> ValueClient | None: ...# HTTPValueClient, bonded/unbonded, or None
    def search_config(self, args) -> SearchConfig: ...           # map args -> SearchConfig fields
    # per-rollout:
    def theorems_from_source(self, prompts, args) -> list[TheoremSpec]: ...  # map input Samples -> TheoremSpec (see C1)
    def to_samples(self, rows, rollout_id, args) -> SlimeSampleOutput: ...
    # model-specific hooks (override these; safe defaults provided):
    def tactic_prompt(self, state) -> str: ...
    def proof_prompt(self, theorem) -> str: ...
    def parse_tactic(self, text) -> str: ...
    def parse_proof(self, text) -> str: ...
    def value_prompt(self, state) -> str: ...
    def parse_value_score(self, payload) -> float: ...
    def reward(self, row) -> float: ...                          # §6
```

### 4.f `generate_rollout` (Phase 3, `slime/rollout.py`) — the composition root
```python
_RUNNER: SlimeRolloutRunner | None = None
_ENV = None; _POLICY = None; _VALUE = None

def generate_rollout(args, rollout_id, data_source, evaluation=False):
    # 1. lazily build runner + process-lifetime resources (env, policy, value)
    # 2. prompts = data_source(args.over_sampling_batch_size)        # CONFIRM C1
    #    theorems = runner.theorems_from_source(prompts, args)
    #    runner.validate_env_profiles(theorems, args)
    # 3. results = await run_search_batch(theorems,
    #        policy_client=_POLICY, value_client=_VALUE, env_backend=_ENV,
    #        config=runner.search_config(args), replay_store=args.replay_store,
    #        model_version=rollout_id)                              # side-archive to ReplayStore
    # 4. rows = [r for res, th in zip(results, theorems) for r in to_training_rows(res, th)]
    #    groups = runner.to_samples(rows, rollout_id, args)
    # 5. return RolloutFnTrainOutput(samples=groups, metrics={...})  # or RolloutFnEvalOutput if evaluation
```
This is the **composition root**: it builds the policy client and injects it
into `run_search_batch`, so the "engine never builds clients" rule holds. It is
a module-level callable Slime imports by path; resources are reused, not rebuilt.

## 5. The thin training-repo surface (what is NOT in this repo)

After this lands, the training repo only: (a) launches the Megatron/SGLang
cluster (weight sync, GPU topology); (b) provides the theorem dataset such that
each prompt carries statement+env_profile+header+theorem_name (matches C1); (c)
passes `leanfoundry.slime.add_leanfoundry_arguments` to Slime's parser hook and
sets `--rollout-function-path leanfoundry.slime.generate_rollout`; (d) optionally
subclasses `SlimeRolloutRunner` to override model-specific prompt/parse/reward
hooks; (e) runs eval. Tree EI launches should set Slime's `loss_type` to
`sft_loss` unless the downstream repo supplies a custom objective for
compact tree fanout. No transport, no Sample plumbing, no search code.
Slime still supplies native flags such as `--hf-checkpoint`,
`--rollout-batch-size`, `--over-sampling-batch-size`, `--sglang-router-ip`,
and `--sglang-router-port`.

## 6. Reward derivation (explicit; default, overridable via `runner.reward`)

- **Direct whole-proof row:** `1.0` (the `ProofTree` is in `proof_candidates`
  only if it passed final `/exec/verify`); skip/negatively-weight unverified.
- **Tree step row:** `1.0` for every `PolicyExample` (these are emitted only for
  proved actions on a structurally solved tree — they are positives). For GRPO
  you also need negatives/baseline: derive from `ValueLabel`s
  (`label`, `weight`, `disproved`) and from `SearchStatus.EXHAUSTED` attempts.
  Grouping/advantage is a training-side choice. The default tree path is
  step-level EI/SFT on positive rows (`loss_type=sft_loss` downstream), not
  fixed-size GRPO.
- **Self-correct:** reward the final accepted attempt; mask feedback turns.
  For turn-level SFT, only the correction attempt after feedback is trainable.
  For RL, the final accepted correction receives reward `1.0`; failed
  correction traces can be kept as negatives only if the objective is explicitly
  configured for them.

## 6.a Negation and negative value labels

Full-weight negative value labels require semantic falsity evidence. In the
current design, that means proving the **negation** of the state. Exhaustion is
different: a searched-but-unproved state says only "not solved at this budget"
and may emit a censored negative after the effort gate.

Implementation requirements:
- `try_negation` wires a synthetic negation search for eligible single-goal
  states and charges that work against `max_tactic_calls`.
- A state becomes runtime `DISPROVED` only when the negation proof succeeds (or
  a future equally strong falsity certificate exists). That state emits
  `ValueLabel(label=0, disproved=True, weight=1.0)`.
- `EXHAUSTED`/root-open attempts emit no policy data and only effort-gated
  censored value labels (`disproved=False`, reduced weight).
- `OPEN`, `ERROR`, `overloaded`, `invalid_state_token`, and other operational
  outcomes are not mathematical negatives.
- Tactics inside a successful negation proof may be positive policy examples for
  the synthetic negation goal, not for the original goal being disproved.

## 7. Grouping contract — exact behavior by mode

The default Slime rollout implementation asserts
`len(group) == args.n_samples_per_prompt` inside its own generation loop. Our
adapter replaces that loop via
`--rollout-function-path leanfoundry.slime.generate_rollout`, so the fixed-size
assert is not a global Slime contract. The returned type is still
`RolloutFnTrainOutput(samples=..., metrics=dict)`, but tree rows use Slime's
compact fanout nesting rather than pretending the flat default shape is
fanout-safe.

Use these group shapes:

1. **Direct / self-correct:** one group per theorem prompt, fixed-size when using
   GRPO-style objectives. Each candidate proof/revision is one `Sample`; group
   size should match `args.n_samples_per_prompt` when a downstream objective
   computes per-prompt advantages. LeanFoundry's default conversion assigns one
   `Sample.rollout_id` per sample, matching Slime's normal fallback behavior;
   `group_index` remains the prompt-level grouping key for custom reward
   post-processing.
2. **Tree step mode:** one compact fanout group per theorem search:
   `list[list[list[Sample]]]` at the rollout return boundary. Each proved node
   becomes one `Sample` with `prompt=state`, `response=tactic`, and all samples
   from that theorem search share the same `Sample.rollout_id`.
   `metadata["slime_rollout_id"]` keeps the Slime rollout step id for debugging;
   `metadata["rollout_id"]` mirrors the trainer rollout id. The pinned Slime
   `Sample` type and `RolloutManager` validation explicitly support this fanout
   pattern: when one rollout execution is split into multiple training samples,
   siblings should share `rollout_id` so loss aggregation does not over-count
   the rollout. Slime's DP scheduler then counts theorem searches, not emitted
   step rows, for `global_batch_size`.
3. **Mixed mode:** concatenate direct fixed-size groups and tree compact fanout
   groups in one `RolloutFnTrainOutput`, with `metadata["lf_kind"]` set to
   `"whole_proof"`, `"self_correct"`, or `"tactic"` so the trainer can route
   losses and reports by target.

Do **not** pad tree groups to `n_samples_per_prompt`; padding changes loss
weighting and hides the fact that a proof search naturally yields a variable
number of step examples. Do **not** aggregate all step rows into one giant Sample;
that destroys lineage-A supervision. If a Slime training objective refuses
compact fanout groups, use direct/self-correct for that objective and keep tree
mode on the step-level EI/SFT objective until the training repo adds support for
this fanout contract.

## 8. Stale push adapter

Done: `leanfoundry/rl_engine/` (`RLEngineBase`, `Checkpoint`, `SlimeAdapter`)
has been removed. The supported adapter boundary is now the pull-shaped
`leanfoundry.slime.generate_rollout` entrypoint.

## 9. Hard runtime dependency from Phase 1

Search reads `TheoremSpec.env_profile` / the backend `env_profile`. If the
dataset (C1) does not pin a real profile, training data is silently
profile-ambiguous (Phase 1, "enforce env profiles"). The adapter must require a
non-default `env_profile` per theorem and fail loudly otherwise — do not default
it. For the initial implementation, one rollout/training run should use one
consistent env profile. `validate_env_profiles` must fail if a batch mixes
profiles or if a theorem profile disagrees with the backend profile, unless
explicit multi-profile routing is implemented first.

## 10. Tests / validation (definition of done)

Hermetic (must pass in the default suite, no slime, no GPU):
- `HTTPPolicyClient`: monkeypatched HTTP; `sample_tactics`/`sample_proofs` return
  `list[list[str]]` of the right shape; prompt/parse hooks are applied.
- `HTTPValueClient`: boxed-scalar parsing, JSON-scalar parsing, numeric-head
  parsing, invalid/missing/out-of-range failures, and `[0, 1]` validation.
- `to_training_rows`: a faked `SearchResult` for direct and tree search yields
  the expected rows (direct → whole_proof rows; tree → one tactic row per
  `PolicyExample`). No slime import.
- Self-correct trace artifact tests: failed proof + Lean feedback + corrected
  proof becomes the expected prompt/response/segment layout after the trace
  artifact lands.
- Env-profile validation: missing/default profiles fail; mixed batch profiles
  fail unless explicit routing is configured.
- Negation semantics: a fake runtime tree with a proved negation emits
  `disproved=True` full-weight labels; exhausted/open attempts emit only
  censored negatives after effort gating.
- Core-stays-clean import test (§4).

Under `[training]` (marker `slime`, skipped by default):
- `add_leanfoundry_arguments`: parser tests cover the LeanFoundry-owned
  namespace fields consumed by `runner.py`, `policy.py`, and `rollout.py`, and
  verify CLI JSON-like sampling strings reach SGLang as decoded payload fields.
- Extend `tests/test_slime_compat.py` for any new Slime surface you depend on
  (`generate_rollout` signature, `RolloutFnTrainOutput`, `data_source`, the args
  in §3).
- `to_samples`: rows → regular Slime groups or compact fanout groups;
  `loss_mask`/`reward`/`status` set; response tokens and loss masks are
  aligned; self-correct masks feedback spans; direct groups and tree compact
  fanout groups follow §7; all tree sibling samples share
  `Sample.rollout_id`.
- Slime trainer-data boundary: compact tree fanout passes through pinned Slime
  `RolloutManager._convert_samples_to_train_data(...)`,
  `_split_train_data_by_dp(...)`, `process_rollout_data(...)`, and Megatron
  `DataIterator`, preserving rollout ids, `rollout_mask_sums`,
  `global_batch_sizes`, and `micro_batch_indices`.
- An opt-in live smoke (`tests/test_slime_live.py`) against a stub
  `data_source`, a live SGLang-compatible router, a live Lean backend, and a HF
  tokenizer checkpoint. It exercises direct, `puct_tree`, and `self_correct`,
  asserts `RolloutFnTrainOutput`, and requires at least one emitted row so token
  construction is actually exercised. For local adapter e2e without a deployed
  router, set `LEANFOUNDRY_SLIME_E2E_LOCAL_GENERATOR=1`; the test starts a
  deterministic `/generate` server and temporary tokenizer while still using
  real Slime and live Lean.
- An opt-in tiny EI smoke (`tests/test_slime_tree_ei_live.py`) that launches
  real SGLang with a tiny generated HF checkpoint, runs live `puct_tree`, checks
  the tree data is step-level (`lf_kind="tactic"`), and performs one local
  optimizer step over the emitted Slime sample tensors. This is not a full
  Megatron/Slime trainer run.

Run: `uv run --no-dev --with pytest pytest` (hermetic),
`uv run --no-dev --with flake8 flake8 leanfoundry tests`,
`uv run --extra training pytest -m slime` (on a CUDA box), `git diff --check`.
Log the slice in [`implementation-log.md`](../internal-trackers/implementation-log.md).

## 11. Confirm-anchors recap (resolve each against commit `a897e1f`)
C1 `data_source` call form + input-Sample→theorem mapping · C2 `/generate`
response schema · C3 `append_response_tokens` tokenization/tokenizer source ·
C4 `RolloutFnTrainOutput`/`RolloutFnEvalOutput` fields + eval shape · C5 the
loss/objective compatibility for direct fixed groups vs tree compact fanout
groups (§7) · C6 tokenizer/token/loss-mask construction.

Resolved in the baseline: C1, C3, C4, and C6. C2 now has opt-in coverage from
both a deterministic local generator and a tiny real-SGLang tree EI smoke. C5
has local optimizer-step evidence for one tactic-level tree sample plus
trainer-data boundary coverage through Slime `RolloutManager` and Megatron
`DataIterator`, but remains live/config gated for the real Slime/Megatron model
step, compact tree fanout under `loss_type=sft_loss`, and weight-sync/reload
loop.
