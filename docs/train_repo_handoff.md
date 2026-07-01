# LeanFoundry → Training Repo Handoff

Read-this-first guide for a training-repo engineer (human or agent) who wants to
**consume LeanFoundry as a package** and run RL/expert-iteration over Lean proof
search with Slime. It is written so you can wire the integration up **without
reading LeanFoundry source**. When you need adapter internals, the authoritative
contract is [`slime_adapter_spec.md`](design/slime_adapter_spec.md); this file is
the operator-facing summary plus an honest handoff status.

> TL;DR: LeanFoundry gives Slime a drop-in `generate_rollout` that turns theorem
> prompts into verifier-grounded training samples. You stand up two services
> (a Lean server and an SGLang router), point Slime at LeanFoundry's rollout
> function and arg hook, and feed a theorem dataset. LeanFoundry owns proof
> search, Lean verification, and Slime `Sample` construction. You own the model,
> the cluster, weight sync, the dataset, and the training loop.

---

## 1. Ownership boundary — who does what

| Concern | Owner |
|---|---|
| Proof search (tree / direct / self-correct), tactic & proof generation orchestration | **LeanFoundry** |
| Lean verification and artifact extraction (`TrainingArtifacts`) | **LeanFoundry** |
| Slime `Sample` construction: tokens, `loss_mask`, `response_length`, rollout-id grouping | **LeanFoundry** |
| Env-profile enforcement, negation-backed `DISPROVED` labels, value labels | **LeanFoundry** |
| Model weights, Megatron/SGLang cluster, **weight sync / reload** | **Training repo** |
| Theorem dataset + `data_source` (see §4) | **Training repo** |
| Loss/objective choice, reward normalization, curriculum, eval | **Training repo** |
| Model-specific prompt/parse/reward hooks (optional overrides) | **Training repo** |

The rule LeanFoundry enforces internally: **the search engine never builds model
clients** — `generate_rollout` is the composition root that injects them. You do
not plumb `Sample`s, HTTP transport, or search code. You provide config + data +
(optionally) subclass one runner.

---

## 2. Install

LeanFoundry ships the Slime adapter in-repo under the `training` optional extra.
Core LeanFoundry never imports Slime; only `leanfoundry.slime.*` does.

```toml
# training repo pyproject.toml
[project]
dependencies = ["leanfoundry"]

[project.optional-dependencies]
train = ["leanfoundry[training]"]

[tool.uv.sources]
leanfoundry = { git = "https://github.com/Zhi0467/LeanFoundry.git", branch = "main" }
```

The `training` extra pins **Slime to an exact commit**
(`a897e1f40357fdf3b148f1eb4ce26e1aeccfcd2c`) plus `megatron-core==0.18.0` and
`torch-memory-saver` (Linux + Python ≥ 3.12). If you bump the Slime pin,
re-run LeanFoundry's `slime` compat suite — the whole `Sample`/`RolloutManager`
contract below is verified against that exact commit.

**SGLang is deliberately NOT a LeanFoundry dependency.** Installing `sglang`
into the same venv wants to replace large core packages (torch, transformers,
CUDA wheels). Your trainer image supplies SGLang. LeanFoundry's own live smokes
keep real SGLang isolated in a separate `.venv-sglang`.

---

## 3. Two services you must stand up

LeanFoundry connects to **already-running** services; it launches neither.

1. **Lean execution server (Kimina).** The `EnvBackend` speaks to it over HTTP.
   ```sh
   docker run --rm --name kimina-lean-server -p 8000:8000 \
     zzzzhi/kimina-lean-server:latest
   curl -fsS http://127.0.0.1:8000/exec/limits
   ```
   Use an immutable image tag for reproducible jobs. Point `--lean-api-url` at it.

   **Mathlib cold boot:** the first request that needs a Mathlib worker triggers
   an `import Mathlib` load, awaited inline in the HTTP request but bounded
   *server-side* by `worker_startup_timeout_seconds` (600 s). LeanFoundry's
   client HTTP read timeout defaults to **600 s** for exactly this reason — a
   shorter client timeout would abort a boot the server would have finished.
   Tactic compute itself is bounded separately by the step timeout. See §5 for
   the timeout knobs.

2. **SGLang router (your trainer stack).** Slime sets `sglang_router_ip` /
   `sglang_router_port` at runtime; LeanFoundry's policy client POSTs to
   `http://{ip}:{port}/generate`. You do not configure these as LeanFoundry
   args — they come from Slime.

---

## 4. Wiring into Slime — three steps

1. **Register LeanFoundry args** via Slime's parser hook. Do not duplicate them.
   ```python
   from slime.utils.arguments import parse_args
   from leanfoundry.slime import add_leanfoundry_arguments

   args = parse_args(add_custom_arguments=add_leanfoundry_arguments)
   ```
   `add_leanfoundry_arguments` registers only the `lean_*` and `lf_*` flags
   (§5). Slime keeps ownership of `--hf-checkpoint`, `--rollout-batch-size`,
   `--over-sampling-batch-size`, `--n-samples-per-prompt`, `--sglang-router-ip`,
   `--sglang-router-port`, `--loss-type`, etc.

2. **Point the rollout function at LeanFoundry:**
   ```
   --rollout-function-path leanfoundry.slime.generate_rollout
   ```

3. **Provide a theorem `data_source`** whose samples match the contract below.

### 4.a Dataset / `data_source` contract (fail-loud)

Slime calls your source as `data_source.get_samples(n)` **or** `data_source(n)`
(both accepted). Each returned prompt group's **first** element is treated as the
theorem sample. That sample must carry:

| Field | Required | Meaning |
|---|---|---|
| `prompt` | ✅ | The Lean statement (non-empty string). |
| `metadata["env_profile"]` | ✅ | Pinned env profile; **must not be `"default"`**. |
| `metadata["header"]` | ✅ | Lean header / imports string (may be `""`). |
| `metadata["id"]` or `["theorem_id"]` | optional | Stable id (used for grouping/eval keys). |
| `metadata["theorem_name"]` | optional | |
| `metadata["source"]` | optional | Defaults to `"unknown"`. |
| `metadata["informal_statement"]` | optional | |
| `metadata["initial_lean_block"]` | optional | |
| `metadata["allowed_axioms"]` | optional | List of strings when present. |

LeanFoundry **raises** on a missing statement, a missing/`"default"`
`env_profile`, or a missing `header` — it never invents defaults. For the first
integration, keep **one env profile per run**; a batch that mixes profiles (or
disagrees with the backend profile) is rejected unless you explicitly set
`--lf-allow-mixed-env-profiles`.

### 4.b Optional: model-specific hooks

Defaults produce valid prompts/tactics for a competent instruct model, so you
can run first and tune later. To customize, subclass `SlimeRolloutRunner` and
override only the model-specific methods, then pass
`--lf-runner-class your.module.YourRunner`:

```python
from leanfoundry.slime.runner import SlimeRolloutRunner

class YourRunner(SlimeRolloutRunner):
    def tactic_prompt(self, state, context=None): ...   # state.pretty_state -> prompt
    def proof_prompt(self, theorem): ...                # header + statement -> prompt
    def parse_tactic(self, text): ...                   # completion -> tactic
    def parse_proof(self, text): ...                    # completion -> whole proof
    def value_prompt(self, state): ...
    def parse_value_score(self, payload): ...           # -> float in [0, 1]
```

Everything else (transport, retry, n-sampling, Sample plumbing, search) is
inherited. There is no need to touch `to_samples`, `rollout.py`, or search code.

---

## 5. Arguments reference (`lean_*` / `lf_*`)

All registered by `add_leanfoundry_arguments`. Defaults shown; every value is
overridable on the Slime CLI.

### Lean backend
| Flag | Default | Notes |
|---|---|---|
| `--lean-api-url` | *(required)* | Kimina server URL. |
| `--lean-api-key` | `None` | Optional auth. |
| `--lean-env-profile` | *(required)* | Pinned, non-`default` profile (may fall back to `--env-profile`). |
| `--lean-timeout-ms` | `120000` | Blanket per-call budget; fans out to acquire+step when those are unset. Well under the server's 600 000 ms cap so runaways are reaped. |
| `--lean-acquire-timeout-ms` | `None` | Wait-for-free-worker bound (inherits blanket). |
| `--lean-step-timeout-ms` | `None` | Tactic-compute bound (inherits blanket). Server rejects values above its cap. |
| `--lean-http-timeout-seconds` | `600` | Client HTTP read timeout; sized to survive a cold Mathlib worker boot. |
| `--lean-retries` | `3` | |
| `--lean-max-overloaded-retries` | `0` | |
| `--lean-overload-backoff-seconds` | `0.0` | |

### Search
| Flag | Default | Notes |
|---|---|---|
| `--lf-search-algorithm` | `puct_tree` | Mainline: `direct`, `self_correct` (whole-proof lineage); `puct_tree`/`best_first`/`and_or_tree` (step lineage). |
| `--lf-max-tactic-calls` | `100` | Tree budget (also charges negation search). |
| `--lf-tactics-per-expansion` | `8` | |
| `--lf-max-direct-candidates` | `64` | Direct/self-correct budget. |
| `--lf-direct-candidates-per-round` | `8` | |
| `--lf-puct-exploration-weight` | `1.0` | |
| `--lf-best-first-missing-value-score` | `0.0` | |
| `--lf-max-concurrent` | `None` | Search concurrency across the batch. |
| `--lf-runner-class` | `None` | Import path to your `SlimeRolloutRunner` subclass. |
| `--lf-try-negation` | `False` | Enables negation search → full-weight `DISPROVED` labels. |
| `--lf-allow-mixed-env-profiles` | `False` | |
| `--lf-include-failed-self-correct-negatives` | `False` | |
| `--lf-include-tree-whole-proof-rows` | `False` | Opt-in tree-rendered whole-proof audit rows (see §6). |
| `--lf-censored-negative-weight` | `0.25` | |
| `--lf-min-censored-negative-effort` | `50` | Effort gate before an exhausted state emits a censored negative. |

### Sampling (two independent prefixes: `--lf-tactic-*` and `--lf-proof-*`)
Each prefix exposes: `-temperature`, `-top-p`, `-top-k`, `-min-p`,
`-max-new-tokens`, `-max-tokens`, `-regex`, `-stop`, `-stop-token-ids`,
`-logit-bias`, `-extra-sampling-params`. All default `None` (SGLang defaults).
`-extra-sampling-params` takes a JSON string merged into the `/generate` payload.

### Value client (optional)
| Flag | Default | Notes |
|---|---|---|
| `--lf-use-value-client` | `False` | Off by default. |
| `--lf-value-mode` | `unbonded` | `bonded` reuses the policy router; `unbonded` needs `--lf-value-base-url`. |
| `--lf-value-base-url` | `None` | Required in unbonded mode. |
| `--lf-value-generate-path` | `/generate` | |
| `--lf-value-output-mode` | `natural_language` | or `numeric_head`. |
| `--lf-value-budget-tokens` | `256` | |

---

## 6. The training data you receive

`generate_rollout` returns a Slime `RolloutFnTrainOutput(samples=..., metrics=...)`
(or `RolloutFnEvalOutput` when `evaluation=True`). There are **two lineages**;
each `Sample` carries `metadata["lf_kind"]` so you can route losses and reports:

| `lf_kind` | Source | Sample shape |
|---|---|---|
| `tactic` | Tree search (`puct_tree`/`best_first`/`and_or_tree`) | One `Sample` per proved node: `prompt` = proof state, `response` = tactic. |
| `whole_proof` | `direct` | One `Sample` per verified whole proof. |
| `self_correct` | `self_correct` | One multi-turn `Sample`; verifier-feedback spans masked (`trainable=False`), model proof turns trainable. |

**Never treat a whole proof rendered from the tree as the training path.** Tree
data is step-level `(state, tactic)` by design (lineage A). For tree algorithms,
LeanFoundry **suppresses** rendered whole-proof rows by default;
`--lf-include-tree-whole-proof-rows` is an explicit opt-in for audit/enrichment
only.

### 6.a Grouping and rollout ids (the part that matters for loss)

- **Tree rows** use Slime's **compact fanout** nesting
  (`list[list[list[Sample]]]`). All step samples from **one theorem search share
  one `Sample.rollout_id`**, so loss aggregation counts *searches*, not step
  rows, and does not over-count. The Slime step id is preserved separately in
  `metadata["slime_rollout_id"]`; `metadata["rollout_id"]` mirrors the trainer
  rollout id.
- **Direct / self-correct rows** are regular Slime groups, one rollout id per
  sample, with `group_index` as the prompt-level grouping key for custom reward
  post-processing.
- Do **not** pad tree groups to `n_samples_per_prompt` and do **not** collapse
  step rows into one giant Sample — either destroys lineage-A supervision.

### 6.b Objective / loss

The **default tree objective is expert-iteration / SFT over positive step rows**:
set Slime's `--loss-type sft_loss`. Tree step rows are positives (reward `1.0`),
emitted only for proved actions on a structurally solved tree.

**GRPO on tree groups is not safe out of the box.** Fixed-width per-prompt
advantage normalization assumes fixed candidate counts; tree searches yield a
*variable* number of step rows. If you want GRPO on tree data you must supply a
custom reward post-process keyed by group/rollout id. GRPO on `direct` /
`self_correct` fixed-size groups is fine. Mixed lineages can be concatenated in
one `RolloutFnTrainOutput`; route by `lf_kind`.

### 6.c Sample construction detail

Trainable spans built from real SGLang rollouts (carrying log-probs) use Slime's
native `Sample.append_response_tokens(...)`. Verifier-grounded rows **without**
rollout log-probs use an explicit
`leanfoundry_verified_without_rollout_logprobs` construction path — Slime's
native append raises if you ask it to train tokens without log-probs, so this
split is deliberate. `metadata["lf_trainable_token_source"]` records which path a
row used. LeanFoundry guarantees
`len(loss_mask) == response_length == len(response_token_ids)`.

---

## 7. Handoff status — proven vs. what you must verify

This is the honest line. LeanFoundry has driven the contract as far as it can
**without a full trainer image**.

**Proven (in LeanFoundry's suites, against pinned Slime):**
- Core stays Slime-free; adapter imports isolated to `leanfoundry.slime.*`.
- `Sample` data contract, including that native append requires rollout
  log-probs and the verified-row fallback path.
- Tree compact fanout reaches Slime's **trainer-side data boundary**: it passes
  through `RolloutManager._convert_samples_to_train_data(...)`,
  `_split_train_data_by_dp(...)`, `process_rollout_data(...)`, and Megatron
  `DataIterator`, with asserted `rollout_ids`, `rollout_mask_sums`,
  `global_batch_sizes`, and microbatch indices (rollout-count, not sample-count,
  normalization).
- Live smokes: deterministic local `/generate` + live Lean across `direct`,
  `puct_tree`, `self_correct`; and a tiny **real-SGLang** tree-EI smoke that runs
  live `puct_tree`, confirms step-level (`lf_kind="tactic"`) output, and does one
  local `torch` optimizer step over the emitted tensors.

**NOT proven — your co-debug surface:**
- A **full Slime/Megatron model actor step** (real forward/backward) consuming
  LeanFoundry tree output with `--loss-type sft_loss`. LeanFoundry's venv omits
  SGLang and the installed Slime package omits its source `megatron_utils/kernels`
  — closing this needs your trainer image, not another adapter unit test.
- **Weight sync / reload** between train and rollout. This is squarely Slime's
  job; LeanFoundry does not touch it.
- **GRPO/advantage normalization on ragged tree groups** (see §6.b). Defused for
  the default SFT path; unverified for GRPO.

### Likely first breakages (and where to look)
1. *No trainable tokens / append raises* → row lacked rollout log-probs; confirm
   `metadata["lf_trainable_token_source"]` and §6.c.
2. *Loss over-counts tree steps* → check siblings share `Sample.rollout_id`
   (§6.a); you probably routed tree data through a fixed-width GRPO loss instead
   of `sft_loss`.
3. *Empty rollout / no rows* → search proved nothing at budget, or dataset
   metadata failed validation (§4.a). Check `metrics["lf_status_*"]` and
   `lf_rows_*`.
4. *Client timeouts on first Mathlib batch* → don't shrink
   `--lean-http-timeout-seconds` below the server's 600 s startup budget (§3).

---

## 8. Running the compat & live smokes yourself

From a LeanFoundry checkout (useful to confirm the contract on your box before
wiring the full trainer):

```sh
# Hermetic (no Slime, no GPU):
uv run --no-dev --with pytest pytest -q

# Slime API-compat + trainer-data-boundary (needs [training], CUDA box):
uv run --extra training pytest -q -m slime

# Deterministic local Slime + live Lean smoke (needs a running Kimina server;
# starts an in-process /generate server + temp tokenizer, so no SGLang needed):
LEANFOUNDRY_SLIME_E2E=1 \
LEANFOUNDRY_SLIME_E2E_LOCAL_GENERATOR=1 \
LEANFOUNDRY_SLIME_E2E_LEAN_API_URL=http://127.0.0.1:8000 \
LEANFOUNDRY_SLIME_E2E_ENV_PROFILE=<your_pinned_profile> \
  uv run --extra training pytest -q tests/test_slime_live.py
# (drop LOCAL_GENERATOR and instead set *_SGLANG_ROUTER_IP/_PORT and
#  *_HF_CHECKPOINT to run against a real deployed router.)

# Tiny real-SGLang tree-EI smoke (opt-in; launches real SGLang + live Lean;
# also needs LEANFOUNDRY_SGLANG_PYTHON and the Lean/profile vars above):
LEANFOUNDRY_SLIME_TREE_EI_E2E=1 \
  uv run pytest -q tests/test_slime_tree_ei_live.py
```

---

## 9. Where to go deeper

- [`design/slime_adapter_spec.md`](design/slime_adapter_spec.md) — authoritative
  adapter implementation contract (Sample branches, §7 grouping, confirm-anchors
  against the pinned Slime commit). Read when adapter internals matter.
- [`design/leanfoundry_system_design_v11.md`](design/leanfoundry_system_design_v11.md)
  — v11 architecture, §v11.13 adapter ownership, §v11.14 training-data model.
- [`internal-trackers/implementation-log.md`](internal-trackers/implementation-log.md)
  — dated record of exactly what has landed and been validated.
- [`internal-trackers/todo.md`](internal-trackers/todo.md) — future-facing work.
- [`../AGENTS.md`](../AGENTS.md) — repo conventions if you contribute back.
