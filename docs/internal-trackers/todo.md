# LeanFoundry Internal Todo

This file is future-facing: active implementation plans, unresolved design
questions, and remaining work. It has four parts: settled **Current Contracts**,
the **SearchConfig** reference, the **Current Path-A Baseline**, and the
**Roadmap** of everything after it.

Historical implementation notes live in
[`implementation-log.md`](implementation-log.md). Concrete design-doc/code
mismatches are tracked in [`issues.md`](issues.md).

## Current Contracts

1. Lean `/exec` ownership
   - `lean-client` owns the wire schema.
   - LeanFoundry imports `lean_client.exec_models` directly.
   - Only `leanfoundry/env_backend/kimina_backend.py` constructs the
     `AsyncLeanExecBackend` transport.

2. Search shape
   - v0 is AND/OR tree search, not graph search.
   - No state merging unless a complete Lean state fingerprint is designed and
     validated.
   - Runtime tree state is mutable search state; persisted `ProofTree` is a
     solved projection only.

3. Goal focus
   - Expansion groups backend-returned goals by transitive closure of
     `sibling_dep`.
   - Split children resume through `goal_group`; `goal_id` and `auto_resume` are
     not the right abstraction.
   - A single coupling group steps whole-state with `focus=None`.

4. Verification gate
   - Runtime `PROVED` is structural only.
   - Whole-proof artifacts still require final `verify_one` / `/exec/verify`;
     per-node training data does not (see Contract 7).

5. Client ownership
   - Engines receive `policy_client`, `value_client`, `env_backend`, and
     `SearchConfig` through `search(...)`.
   - Engines do not construct model or backend clients.
   - `value_mode` controls label-emission ownership, not value-client
     construction.

6. Operational statuses
   - `error` is a Lean tactic result and counts against tactic budget.
   - `invalid_state_token` and `cancelled` poison the current expansion and
     discard partial attachments.
   - `invalid_state_token` fails the theorem attempt immediately in v0; token
     re-derivation/restart is deferred until replay/resume exists.
   - `overloaded` is backend backpressure. All-overloaded surfaces as an
     operational status with zero tactic budget after the backend/client retry
     layer is exhausted.
     It is not theorem/search evidence and must not count toward value-label
     effort.
   - Mixed `overloaded` plus executed statuses for one step item is a backend
     protocol violation, not a partial-width expansion. Charge the executed
     tactic attempts, discard partial attachments, and fail the theorem attempt
     as an operational/backend error.

7. Root outcome and training semantics
   - Per-node policy/value training data is gated on per-step backend
     acceptance, not on whole-proof `/exec/verify`. Every tactic edge in the
     tree was executed by Lean during search (a real `ExecStepResult`), and
     coupling groups are metavariable-closed, so the per-node `(state, tactic)`
     and `(state, outcome)` tuples are verifier-grounded per step. The minimum
     soundness requirement is that a `complete` step is a genuine closure
     (sorry/admit-free). Whole-proof `/exec/verify` is demoted to an optional
     artifact gate plus a sampled soundness audit; it is not the data gate.
   - Runtime `DISPROVED` is only assigned when synthetic negation/inversion, or
     another future semantic falsity certificate, proves the state false. It is a
     full-weight value negative for the disproved state; tactics inside the
     synthetic negation proof may train the negation goal, not the original goal.
   - Runtime states remain `OPEN | PROVED | DISPROVED` in v0. Do not add runtime
     `EXHAUSTED` unless durable resume or a deliberately finite per-state action
     source gives it a separate operational meaning.
   - Root runtime `OPEN` at attempt stop maps to the top-level
     `EXHAUSTED`/unproved outcome: the attempt ended without proof or disproof
     because its configured search effort ended. This is value-label eligible
     only after the configured effort gate and with censored-negative weight. It
     is not policy data and not mathematical falsity.

## SearchConfig

Tree search and direct whole-proof search use different budget units.

1. `max_tactic_calls` — hard cap on Lean tactic attempts for one tree-search
   theorem. Primary stop condition and solved@budget x-axis.
2. `tactics_per_expansion` — policy tactic candidates per selected state. Backend
   limits still cap the concrete step item width.
3. `max_direct_candidates` — hard cap on whole-proof candidates for `DIRECT` /
   `SELF_CORRECT`. A pass@k-style budget, not a tactic-call budget.
4. `direct_candidates_per_round` — whole-proof candidates per self-correction
   round; still capped by `max_direct_candidates`.
5. `puct_exploration_weight` — PUCT exploration multiplier for high-prior,
   under-visited actions.
6. `best_first_missing_value_score` — score `BEST_FIRST` assigns to unvalued open
   leaves. Default `0.0` preserves the value-free fallback.
7. `try_negation` — optional synthetic negation search for single-goal states.
   Default false.
8. `min_censored_negative_effort` — value-label emission gate, not a stop
   condition.
9. `censored_negative_weight` — training weight for searched-but-unproved states.
10. `value_mode` — bonded/unbonded label-emission behavior. Value output
    format (numeric head vs natural-language boxed/JSON scalar) is a
    `ValueClient` implementation detail unless traces show it needs a search
    config knob.

Not first-class config fields until design docs, traces, or profiling justify
them: wall-clock cap per theorem, max tree nodes, max depth, max expansions,
per-state action cap, outer decomposition/revision budgets. Backend per-request
timeouts belong to the `/exec` request/config layer, not tree-search semantics.

## Current Path-A Baseline

The training baseline is per-node extraction, decoupled from whole-proof
rendering (AlphaZero-style per-state training: observation = Lean proof state,
target = the tactic, value = verifier-grounded outcome). Whole proofs are a
deliverable (Path B), not a data gate.

Records emitted per completed attempt (proved or not):
- PolicyExample positives from proved subtrees. Store BOTH formulations on one
  record: `state` (Markovian observation) and `proof_prefix` (the root->state
  tactic path = optional provenance / incremental-script context, walked from
  `parent_action`). `proof_prefix` is not a history-conditional training target.
  The target stays the single proved `tactic` string. Visit counts and failed
  siblings remain in the tree for future RL/weighting, but are not the target.
- ValueLabel per explored state: proved=1, disproved=full-weight-0,
  explored-unproved=censored-negative. Effort is node-local.

Minimum rendering: none of the branching kind. State text is the backend's
per-goal pretty; `proof_prefix` is a concatenation of tactics along a single
root->node path (linear, always succeeds). No bullets, focus, or whole-tree
collapse is ever needed for training data.

Minimum checking: per-step backend acceptance is the grounding (done during
search). The one hard requirement is sorry/admit-free `complete` steps. The
`/exec` step result exposes no sorry/axiom signal and a sorry-closed goal
reports `complete`, so reject `sorry`/`admit` (as Lean tokens, via the existing
lexer) at expansion attach-time by marking the action DEAD. The tree then can
never be proved through sorry, so extraction is sound by construction and search
never rewards sorry (reward-hack guard). No backend change. Axiom policy beyond
sorry (e.g. `native_decide`'s `ofReduceBool`) is out of scope; a `native_decide`
proof is real, and `/exec/verify`'s `allowed_axioms` covers it for Path B.

Storage (the durable buffer): concrete SQLite `ReplayStore` plus a writer that
turns `TrainingArtifacts` into durable rows (policy examples, value labels,
verified A-type proof rows, and one trajectory record) as attempts land.
Deterministic content-hash ids make writes idempotent; rows keep provenance through
`attempt_id`-derived trajectory ids, `theorem_id`, and `model_version`. This
durable store is a side archive for eval/HER/offline; it is NOT the online RL
conduit (Slime owns that, below).

Decisions:
- Policy target is the single proved `tactic` string (SFT / expert-iteration). A
  fixed-head visit-count distribution is an AlphaZero artifact for an enumerable
  action space; it does not map to an unbounded LLM tactic generator.
- Core extraction is algorithm-neutral. Whether the per-node data is consumed as
  EI positives or grouped for GRPO is the training side's choice; LeanFoundry
  does not bake grouping into core artifacts.

Slime adapter plan (read from THUDM/slime source). Slime is the **default** RL
engine, so the adapter ships **in this repo** as `leanfoundry/slime/` under the
`[training]` optional extra (NOT in the training repo). Hard invariant:
`import leanfoundry.proofsearch` must never pull in `slime`/`sglang`; only
`[training]` installs touch `leanfoundry/slime/`. The old push-shaped
`leanfoundry/rl_engine/` (`RLEngineBase.submit_samples`, `SlimeAdapter`,
`Checkpoint`) was the wrong model and has been deleted.
- Integration is PULL, not push. Slime loads a function via
  `--rollout-function-path leanfoundry.slime.generate_rollout` and calls
  `generate_rollout(args, rollout_id, data_buffer, evaluation) -> list[list[Sample]]`.
  The loop is online on-policy batched: per `rollout_id`, generate with current
  weights, train (GRPO/PPO via Megatron), sync weights to SGLang.
- `generate_rollout` is the **composition root**: it builds `SGLangPolicyClient`
  and injects it into `run_search_batch`, so the "engine never builds clients"
  rule still holds. It is a module-level callable (Slime imports it by path) over
  process-lifetime resources (backend, policy client), not rebuilt per call.
- Build everything model-agnostic here as runnable defaults on a
  `SlimeRolloutRunner` with override hooks, so the training repo subclasses/
  overrides rather than reimplements: `build_env_backend`, `build_policy_client`
  (default `SGLangPolicyClient`), `build_value_client`, `theorems_from_buffer`,
  `search_config`, `to_samples`, plus model-specific hooks `tactic_prompt`/
  `parse_tactic`, `proof_prompt`/`parse_proof`, `value_prompt`/
  `parse_value_score`, and `reward`/`group`. Transport, n-sampling,
  state->prompt rendering, value scalar parsing, and
  `TrainingArtifacts`->Sample + token/loss-mask construction are LF defaults,
  not train-repo work.
- One shared `SearchConfig` already serves both modes (`algorithm` field), but
  the two Slime-facing edges branch by mode — two training targets, see the
  training-data model below. Policy call: direct uses `sample_proofs`, tree uses
  `sample_tactics`. `to_samples`: tree -> Markovian per-node `(state, tactic)`
  step `Sample`s, one per proved node, sharing one `rollout_id` (lineage-A
  search-distilled step data; one node = one Sample is correct, NOT a
  trajectory); direct -> one whole-proof `Sample` per candidate
  (`prompt=statement`, `response=proof`, `reward=verify`), ~1:1 with Slime's
  default per-prompt rollout; `SELF_CORRECT` -> a multi-turn `Sample` masking the
  verifier-feedback spans (`append_response_tokens(trainable=False)`) and
  training the model's proof turns. This requires a persisted self-correct trace
  artifact: failed proof text, Lean feedback, next proof attempt, verifier
  result, and final acceptance. Use the full rollout function (not Slime's
  per-sample hook) so one search = one rollout and its step Samples share a
  `rollout_id` instead of being generated independently.
- Dataset ingress contract: input `Sample.prompt` is the Lean statement;
  metadata must carry non-default `env_profile` and `header`, plus theorem id/name
  when available. Initial implementation fails if one rollout/training run mixes
  env profiles or if theorem/profile/backend disagree; multi-profile routing is
  future explicit work, not implicit fallback.
- Side-write the same artifacts to the durable `ReplayStore` (eval/HER/offline);
  Slime owns the online buffer + trainer.
- The train repo is then thin: deployment launch (Megatron/SGLang topology,
  weight sync), the theorem dataset, eval, run hyperparameters, and at most a
  small subclass overriding model-specific hooks.
- Cost accepted: LeanFoundry now owns Slime API-compat. The adapter is pinned
  through `[tool.uv.sources]` and guarded by `[training]` compat tests (#20);
  bump Slime deliberately and re-run `pytest -m slime` rather than tracking
  Slime `main` implicitly. Path-A core/store is landed.
- This implies two model-agnostic reference pieces that are NOT Slime-specific
  and land first as their own slice (roadmap Phase 2): `HTTPPolicyClient` (the
  base for `SGLangPolicyClient`), `HTTPValueClient` (numeric-head or
  natural-language scalar parsing; bonded/unbonded endpoints), and
  `to_training_rows()` (so `to_samples` is a thin Slime-`Sample` wrap). The
  adapter (Phase 3) handles all search modes in one slice — tree step pairs,
  direct whole proof, self-correct — since they are just `config.algorithm`
  branches of `to_samples`. There is no separate trajectory slice; the
  history-conditional target was dropped (see the training-data model below).

## Training-data model (two generation modes = two targets)

LeanFoundry emits two clean training-data types, one per search mode; combining,
enhancing, and grouping them is the training repo's job — and the experiment it
runs is precisely *does training with a search algorithm (heavy machinery) beat
plain whole-proof generation, or do they match?*

- Tree search -> Markovian per-node `(state, tactic)` step pairs = **lineage A**
  (step-level prover). The search algorithm's selection/value/backup picks the
  proved tactic at each state; the pairs distill that search behavior into a step
  policy (expert iteration). Train as a step policy; roll out interactively /
  agentically at eval, where a goal state is in-distribution.
- Direct full-generation rollout -> verified whole proof = **lineage B**
  (whole-proof prover). One `/exec/verify`; the model's own output, no rendering.
- Neither target renders a whole proof FROM the tree. Tree -> step pairs (no
  render); direct -> the model's own proof (no render). Path-B whole-proof
  rendering stays a deferred product/audit artifact (Phase 6), never a data gate.
- Hybrid / interactive inference (feed a state, let the model generate to the
  end) needs no special training target — it is inference-only and benign. A
  model trained on either target can be run in hybrid mode; DeepSeek-Prover-V1.5
  trains whole proofs (with `/- tactic state: -/` comment augmentation to keep
  the resume point in-distribution) and runs truncate-and-resume MCTS only at
  inference (arXiv:2408.08152). State-comment annotation, reflection, and
  correction formatting are training-repo enhancements.
- No history-conditional / injected-state trajectory target. A proof state is
  Markov (a sufficient statistic), so interleaving injected goal states as masked
  context is nonstandard and redundant. `PolicyExample.proof_prefix` is optional
  provenance / incremental-script context only; reconstructing it as a script for
  a branching proof is the render problem. `loss_mask` /
  `append_response_tokens(trainable=…)` is used only within a Sample's response
  and for self-correct (masking verifier feedback), never for state interleaving.
- Optional failed self-correct negatives are training configuration, not default
  core rows. `lf_include_failed_self_correct_negatives` makes the Slime rollout
  adapter include reward-0 `kind="self_correct"` rows for rejected turns with
  `self_correct_objective="failed_negative"` metadata; default remains off.

## Roadmap (after Path-A)

Organized into phases by dependency, not strict serial order. Items the Path-A
baseline already covers are not repeated. A phase that depends on an earlier one
says so; otherwise phases can overlap. The detailed Slime adapter design lives in
the "Slime adapter plan" section above; the phases below only sequence it. The
shortest path to a running training loop is Phase 2 -> Phase 3.

### Phase 1 — Data-integrity foundations and durable spine
Gates *trustworthy* training data and eval, not the mechanics of a first loop, so
it can overlap Phases 2-3 — but finish it before any real training run, because
ambiguous env profiles silently contaminate the data the adapter feeds out.
- Env-profile enforcement baseline landed: shared validators reject default
  profiles at durable/training ingress, validate theorem headers against an
  optional `EnvProfile` registry, and reject mixed theorem batches unless
  explicit routing is enabled. Benchmark loaders and eval runners now accept
  optional profile registries, and the Slime training backend builder requires
  an explicit non-default `lean_env_profile` / `env_profile`. Low-level
  `EnvBackendConfig` keeps its dev default for direct test/client use.
- Durable artifact shape beyond the Path-A store landed for the current spine:
  SQLite stores theorem/proof/trajectory/policy/value/lifecycle/extraction
  failure/TTT-trace rows with deterministic ids and migrations, while eval
  artifacts are manifest-backed files with content hashes. SQLite migrations
  now run through an ordered registry, with upgrade coverage for legacy
  v4/v5/v6/v7 DBs into the current v8 schema. Stable-schema release governance
  is documented in `docs/design/schema_release_governance.md`.
- Fixed-model eval runner baseline landed: `FixedModelEvalRunner` uses
  `run_search_batch`, reports direct/self-correct pass@k from verifier attempt
  indices, tree solved@budget from `max_tactic_calls`, status counts, and basic
  throughput in `EvalArtifactManifest`. Manifest-backed artifact writing now
  materializes `eval_manifest.json`, `results.jsonl`, `benchmark.jsonl`, and a
  compact `report.md` with content hashes. All direct/self-correct verifier
  attempts are preserved in `TrainingArtifacts.direct_verification_attempts`,
  serialized in `results.jsonl`, and counted in manifest metrics. Plain
  `DIRECT` verifies the full sampled pool before returning a successful result;
  the first accepted proof is the result proof, and all accepted verified
  candidates are kept as whole-proof `proof_candidates`. `SELF_CORRECT` still
  stops once a correction is accepted.
- Benchmark/env-profile manifest schema and JSONL loaders landed:
  `BenchmarkManifest` records source, split, env profile, compatibility status,
  contamination policy, fixed held-out assignment, dataset commit, and expected
  theorem count; `load_benchmark_jsonl(...)` validates compatibility,
  env-profile consistency, and expected row count before eval.
  `load_benchmark_source(...)` loads the manifest source directly from local
  paths, `file://`, HTTP(S), or explicit Hugging Face file URIs.
  `BenchmarkManifest.row_format` plus `BenchmarkRowAdapter` support
  benchmark-specific schema transforms. Built-in MiniF2F Lean4 JSONL adaptation
  landed through `MINIF2F_LEAN4_ROW_FORMAT` /
  `make_minif2f_lean4_row_adapter(...)`; built-in PutnamBench Lean4 JSONL
  adaptation landed through `PUTNAMBENCH_LEAN4_ROW_FORMAT` /
  `make_putnambench_lean4_row_adapter(...)`, requiring the manifest env
  profile's registered header because the public rows have no per-row header;
  built-in MathOlympiadBench Lean4 JSONL adaptation landed through
  `MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT` /
  `make_matholympiadbench_lean4_row_adapter(...)`; built-in ProofNet Lean4
  JSONL adaptation landed through `PROOFNET_LEAN4_ROW_FORMAT` /
  `make_proofnet_lean4_row_adapter(...)`, explicitly initializing public rows
  that end at `:=` with `by sorry` and rejecting non-placeholder statements.
  Remaining: add more concrete adapters only when a chosen public benchmark
  needs one.
- Backend validation harness baseline landed:
  `validate_backend_case(...)` replays tree-shaped known tactic trajectories
  through an injected `EnvBackend`, preserves LeanFoundry's goal-coupling split
  and focused `goal_group` child replays, and verifies the supplied complete
  proof through `/exec/verify`. Operator runner landed:
  `leanfoundry-validate-backend` / `python -m
  leanfoundry.env_backend.validation_cli` loads JSON/JSONL validation cases,
  enforces one `env_profile` per run, exits nonzero on failed reports, and
  emits per-case plus aggregate create/replay/verify/total latency seconds.
  Live scripted `/exec` e2e landed against a local Kimina server:
  `tests/test_e2e_search.py` passed with `LEANFOUNDRY_E2E=1` against
  `http://127.0.0.1:8017`. Remaining: supply real LeanDojo/LeanTree validation
  cases, run the CLI in the target deployment, and interpret latency/cache
  behavior with backend telemetry before a real training run.
- Attempt-lifecycle baseline landed: bounded cleanup now records deferred item
  ids, cancel unwind records item statuses/failures when a replay store is
  present, and SQLite persists `attempt_lifecycle_outbox` rows with retry count,
  last status/error, optional next retry, and terminal flags. Reconciliation
  baseline landed: pending lifecycle rows can be retried against the backend,
  cleanup rows are marked deleted/deferred/failed/orphaned, cancel rows are
  marked cancelling/drained/cleaned/failed, and direct-search active verifier
  cancellations are persisted through replay. Periodic reconciliation baseline
  landed as `reconcile_attempt_lifecycle_periodically(...)`, with bounded or
  infinite scheduler passes and warning/critical operator alerts for failed
  or orphaned backend items. Deployment hook landed:
  `leanfoundry-reconcile-lifecycle` / `python -m
  leanfoundry.replay.lifecycle_cli` runs the reconciler from cron or a service
  supervisor, prints JSON diagnostics, and can exit nonzero on alerts.
  Remaining: site-specific pager/metrics integration if the deployment needs
  it.

### Phase 2 — Reference model clients (model-agnostic, no Slime dependency)
Baseline landed: `HTTPPolicyClient`, `HTTPValueClient`, `to_training_rows()`,
and `make_env_backend(config)` are implemented without importing `slime`.
Remaining Phase-2-adjacent work:
- Self-correct trace rows landed: `DirectSearchEngine(self_correct=True)`
  persists ordered failed-proof / verifier-feedback / corrected-proof turns,
  and `to_training_rows(...)` emits `kind="self_correct"` rows for accepted
  corrections with the previous failed proof and feedback in the prompt.
- Reuse the clients in Phase 1 eval runners and Phase 3 Slime adapter rather
  than adding trainer-specific transport code.

### Phase 3 — Slime adapter (first working training loop)
Baseline built under `leanfoundry/slime/`: `SGLangPolicyClient`,
`SlimeRolloutRunner`, `samples.py`, and `rollout.py`. It owns row-to-Sample
token/loss-mask construction, metadata validation, rollout composition, and the
pull-shaped `generate_rollout` entrypoint. The push-shaped `rl_engine/` package
is deleted.
Remaining Phase 3 work:
- Run the adapter under `[training]` against the pinned Slime package, SGLang,
  and a Lean backend; an opt-in live smoke harness now exists, but it still
  needs to be executed in a configured deployment environment.
- Fake integration coverage landed for grouped/callable `data_source` inputs,
  tokenizer loading from `args.hf_checkpoint`, and `RolloutFnEvalOutput`.
  Opt-in live-smoke coverage landed in `tests/test_slime_live.py`: with
  `[training]`, `LEANFOUNDRY_SLIME_E2E=1`, a Lean API URL/profile, SGLang
  router address, and HF checkpoint, it drives real `async_generate_rollout`
  through direct whole-proof search. Remaining: run it against actual services
  before a real training run.
- Real self-correct rows landed once `SelfCorrectTrace` was added; the adapter
  carries them through existing `TrainingSegment` / loss-mask construction.
- Slime API-compat is pinned and drift-tested (#20, landed): bump the commit
  deliberately and re-run `pytest -m slime`.

### Phase 4 — Extraction hardening
- Step-level extraction baseline landed: every proved runtime action now emits a
  lineage-A `(state, tactic)` policy row, including multiple proved actions at
  one state and proved internal subtrees under an unproved root. Bonded value
  labels are emitted for every proved runtime state. Whole-proof candidates stay
  canonical/verified; `step_her_multiplier` tracks the emitted step rows.
- Optional rendered-HER artifacts: if a proved subtree can be rendered as a
  standalone proof, reverify under the same `env_profile` and emit
  render-candidate/verified metrics. Baseline accounting landed:
  `extract_training_artifacts(...)` now emits action-level
  `path_b_render_candidates`, `path_b_renderable_candidates`,
  `path_b_unsupported_candidates`, and `path_b_verified_candidates` diagnostics
  for the existing narrow renderer and top-level verified artifact. This is a
  Path-B artifact stream, not the step-data gate. Remaining: actual standalone
  subproof rendering/reverification waits for a backend-sourced proof/script
  capability or a deliberately designed identity-based client renderer.
- Failure-kind split baseline landed: unsupported proof rendering, rendering
  errors, and verifier rejection are distinct `ExtractionFailure.kind` values,
  and base extraction diagnostics stay on failure envelopes. Unsupported
  extraction failures now carry a structured `node_id` when the renderer can
  localize the bad runtime child.
- Policy history/comment context baseline landed as inference context only:
  `PolicyClient.sample_tactics(...)` accepts `PolicyContext`, expansion derives
  `proof_prefix` from parent runtime actions, and the default HTTP tactic prompt
  can include it as Lean comments. This does not change `FactorizedProofState`
  and is NOT a separate training target.

### Phase 5 — Value serving and negation semantics
Required before serious value-guided tree training; can start after the first
adapter loop but is not optional for the full Aristotle-like implementation.
- Value serving baseline landed: `HTTPValueClient` supports numeric-head/JSON
  scalars and natural-language boxed/JSON scalar parsing; the Slime runner can
  build bonded value clients against the SGLang router or unbonded clients
  against a separate endpoint. `value_mode` remains label-emission ownership.
- Conservative negation baseline landed: `try_negation` is provenance-gated,
  applies to eligible single-goal states, renders a simple synthetic negated
  theorem through the backend, counts successful Lean tactic attempts against
  `max_tactic_calls`, and can mark the state/root `DISPROVED`.
- Label semantics baseline landed: proved negation emits full-weight
  `ValueLabel(label=0, disproved=True)` through the existing disproved-state
  extraction path. Root-open/exhausted attempts remain censored negatives after
  effort gating; operational failures/backpressure are not value negatives.
  Durable negation attempt artifacts landed:
  `TrainingArtifacts.negation_attempts` records synthetic negated theorem
  code, tactic attempts, proved tactic, source state, and operational status;
  replay persists them in `negation_attempts` with deterministic ids.
  Local definitions/`let` entries are now accepted by typed abstraction in the
  synthetic theorem; unsupported names/empty types still fail closed.
  Persistent negation action retry landed: failed negation tactics leave the
  synthetic action open for later selected retries, and repeated policy outputs
  fail closed. Nested negation proof search landed: the synthetic action owns
  the negated-theorem proof state as a child, and open subgoals inside that
  proof are searched by the normal AND/OR tree. Remaining: broader
  local-context rendering only if backend traces expose contexts this
  abstraction cannot soundly cover.

### Phase 6 — Path-B richer rendering (deferred deliverable, never a data gate)
- Whole-proof emission is a product deliverable, not a training-data gate (Path-A
  is per-node grounded). The robust route is backend-sourced: a future `/exec`
  proof-term/script capability the backend assembles from the closed proof. Do
  NOT build client-side whole-tree -> surface reconstruction; surface focusing
  (non-contiguous / jointly-coupled goal groups) has no faithful bullet encoding
  to re-derive, and the backend owns the only kernel-checked proof object.
- If ever done client-side instead: resolve a stable goal identity first
  (`GoalComponent` has order/name, not identity); render by identity
  (`case <tag> =>`, `on_goal`/`pick_goal`/`rotate`, positional `·` only for
  tagless single splits); render coupled groups as one contiguous block; add real
  Lean fixtures (linear, swap-sensitive multi-state, named-tag cases/induction,
  tagless positional, nested-`by`, contiguous and non-contiguous coupled), a
  sorry-placeholder cardinality invariant, and a parent-`state_token` replay
  oracle. The current narrow `extract_proof_tree` stays only for direct/easy
  cases and the optional sampled audit.

### Phase 7 — Deferred algorithms and extensions
- Tactic beam, optimistic/RMaxTS, graph/MCGS: off the core path until replay/eval
  proves the direct/tree/best-first baseline; graph/MCGS also needs a complete
  state-identity fingerprint.
- Extension A scale-out contracts landed: `leanfoundry.scaleout` records router
  metrics/autoscale decisions, binary router frame codecs, pure router
  scheduling transitions, a reference asyncio TCP router service, router-backed
  EnvBackend adapters, and portable state snapshot references.
  `RouterFrame`, `RouterCommand`, `encode_router_frame(...)`, and
  `decode_router_frame(...)` now implement the documented network-byte-order
  frame header with strict exact-frame decoding; payloads remain opaque bytes
  until a router adapter owns command-specific request bodies.
  `AsyncRouterService` now accepts backend `REGISTER` connections, routes
  client `REQUEST` frames to backends as `FORWARD`, delivers backend
  `RESPONSE` frames to clients as `DELIVER`, and requeues in-flight work after
  backend disconnects.
  `RouterServiceSnapshot` / `AsyncRouterService.snapshot()` now expose local
  queue/backend/client/counter diagnostics, and disconnected clients drop
  still-pending requests instead of leaving them queued forever.
  `RouterCommand.CANCEL`, `cancel_inflight_requests(...)`, and
  `RouterBackendWorker` task cancellation now give abandoned in-flight router
  work a local cancellation protocol; late responses are dropped. Concrete Lean
  kernel/backend cancellation remains best-effort and backend-owned.
  `leanfoundry.scaleout.health` now derives local `/healthz`, `/readyz`, and
  Prometheus-text `/metrics` responses from `RouterServiceSnapshot`, and
  `leanfoundry-router --health-port ...` can serve them for a site supervisor.
  `RouterEnvBackend` / `RouterBackendWorker` now carry lean-client `/exec`
  operations over those frames for limits, create_states, one-state
  step_batch, verify, cleanup, cancel, and stats while preserving the
  one-proof-state expansion scheduler unit.
  `leanfoundry-router` and `leanfoundry-router-worker` now provide stable
  local process entrypoints for a site supervisor to launch the reference
  router and backend workers.
  `RouterState` plus `register_backend(...)`, `enqueue_request(...)`,
  `complete_request(...)`, and `disconnect_backend(...)` now cover FIFO
  assignment to idle backend slots, completion drain, duplicate-id rejection,
  and disconnect requeue for in-flight requests.
  `make_inline_state_ref(...)` / `decode_inline_state_ref(...)` now implement
  RAW inline state-payload encoding, decoding, and integrity checks.
  `make_file_state_ref(...)` / `decode_file_state_ref(...)` now implement
  local `file://` URI payload writes/reads with payload-size and decoded-state
  integrity checks. `decode_http_state_ref(...)` and `decode_uri_state_ref(...)`
  now support read-only `http://` / `https://` URI payload fetches with the same
  validation, suitable for public or signed object-store URLs. The `[scaleout]`
  extra now installs `zstandard` and tests real ZSTD inline/file state-ref
  round-trips; default installs still fail closed when ZSTD is requested.
  Remaining: production router
  hardening/deployment, site-specific supervisor manifests and metrics/pager
  integration, backend state export/import, credentialed object-store clients
  and remote writes, Postgres or Redis replay store, distributed cleanup/cancel
  semantics, concrete backend/kernel abort guarantees, and deployment
  integration.
- Extension B promotion contract landed: staging rows preserve the Lean header,
  schema version 7 backfills legacy staging rows, and
  `evaluate_promotion(...)` converts syntax-checked / judged / deduped staging
  rows into `TheoremRecord`s or returns rejection reasons.
  `verify_staging_statement_code(...)`, `KiminaStatementVerifier`, and
  `staging_record_with_syntax_result(...)` now provide a local statement
  syntax/type-check wrapper over lean-client's legacy REPL `api_check` route
  and update the staging `syntax_checked` gate field from normalized results.
  `HTTPSemanticJudge`, `parse_semantic_judge_response(...)`, and
  `staging_record_with_semantic_judge_result(...)` now provide a local
  semantic-judge service contract and populate `semantic_judge_score` from a
  validated `[0, 1]` score; promotion still owns thresholding.
  `run_formalization_draft_loop(...)` now provides local draft/retry
  orchestration over an injected `Formalizer` and `StatementVerifier`, carries
  verifier feedback into the next attempt, and returns a staging row only after
  syntax acceptance.
  `HTTPFormalizer`, `formalizer_payload(...)`, and
  `parse_formalizer_response(...)` now provide the concrete service/prompt
  contract for model-backed statement drafting: payloads carry the staging id,
  informal statement, env profile, header, attempt index, and verifier
  feedback, and responses must contain a structured non-empty
  `lean_statement`.
  `formal_statement_dedup_hash(...)` and
  `staging_record_with_dedup_hash(...)` provide exact local
  statement/header/profile dedup hashes, and
  `estimate_difficulty_from_quick_search(...)` maps quick-search results to the
  numeric `difficulty_estimate` field.
  `HTTPEmbeddingDeduplicator`, `embedding_dedup_payload(...)`, and
  `parse_embedding_dedup_response(...)` now provide a local embedding-dedup
  service contract, and
  `PromotionGateConfig(require_embedding_unique=True)` lets promotion reject
  missing, errored, or duplicate embedding-dedup results. Remaining: real
  formalizer/judge/embedding model checkpoints, deployed services/indexes,
  judge and embedding threshold calibration, running the statement
  verifier/judge/dedup checks over real staged corpora, and running
  quick-search difficulty estimation on real model/backend results.
- Extension C TTT contract landed: `leanfoundry.ttt` exposes trainer/reload
  protocols, `TTTConfig`, adapter request/result schemas, and per-round/session
  traces with main-replay promotion off by default. `run_ttt_session(...)`
  now provides a generic callback-driven loop over search, sample extraction,
  fine-tune, reload, and policy rebinding. `evaluate_ttt_trace_promotion(...)`
  now provides the local opt-in promotion decision gate with env-profile,
  trace-key dedup, failed-stage, solved-status, and successful-reload checks.
  Promoted trace replay writes landed through `TTTTraceReplayRecord`,
  `ReplayStore.put_ttt_trace_replay_records(...)`, SQLite
  `ttt_trace_replay`, and `persist_promoted_ttt_trace(...)`. These rows store
  trace artifacts and promotion decisions only; they are not synthetic
  policy/value/A-type training rows. Remaining: MCGS or another approved
  per-problem search source and concrete trainer-side fine-tune/reload.
- Extension D ablation contract landed: `AblationExperimentPlan` records the
  frozen curriculum, W/W+SC/T-step/T-noval/Mix arms, per-arm
  replay/checkpoint namespaces, hard generation/training/verifier ledgers,
  `budget_account_id` checks, and native crossed-eval cells.
  `build_frozen_curriculum_from_pass_sweep(...)` now constructs the frozen pool
  deterministically from complete direct pass@N verifier-attempt evidence.
  `check_budget_request(...)` now applies one ledger cell to one observed usage
  snapshot and refuses account mismatches or hard-cap overruns.
  `SQLiteBudgetMeterStore` now provides local durable meter cells and atomic
  SQLite reservations using that guard, including drift checks for existing
  cells and hard-cap serialization across concurrent local callers.
  `leanfoundry-budget-meter` now exposes init/reserve/snapshot commands for
  scripts and returns nonzero when a reservation is refused.
  Remaining: run the actual pass@N sweep on the selected model/pool, run
  training in the downstream repo, wire distributed meter services and
  worker-side live measurements in deployment, and write final outcome reports.

## Current Local Audit Boundary — 2026-06-30

The local implementation baseline is green through:

- `uv run --no-dev --with pytest pytest -q` -> 336 passed, 8 skipped.
- `LEANFOUNDRY_E2E=1 LEANFOUNDRY_E2E_API_URL=http://127.0.0.1:8017
  LEANFOUNDRY_E2E_ENV_PROFILE=default uv run --no-dev --with pytest pytest -q
  tests/test_e2e_search.py` -> 7 passed against a local one-worker Kimina
  `/exec` server.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py
  tests/test_slime_live.py -q` -> 3 passed, 1 skipped.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.

Remaining work is intentionally not hidden as "todo code" in the current core:

- **Live/external validation:** local scripted `/exec` e2e passed and the
  backend validation CLI now emits latency summaries; still run it over real
  LeanDojo/LeanTree trajectories, run the opt-in Slime/SGLang/Lean live smoke,
  and interpret backend cache behavior plus deployment lifecycle behavior in
  the target environment.
- **Dataset-specific adapters:** add concrete `BenchmarkRowAdapter`s only after
  selecting public datasets whose native rows are not already LeanFoundry
  theorem JSONL.
- **Deployment-specific wiring:** pager/metrics integration for lifecycle
  reconciliation, durable/concurrency-safe budget-meter counters, service
  supervisors, and cluster autoscaler integration depend on the deployment site.
- **Training-repo execution:** optimizer loops, checkpoint production,
  Slime/Megatron/SGLang launch topology, W&B/reporting, actual pass@N sweep
  execution, and ablation outcome reports belong to the downstream consumer.
- **Deliberately gated algorithms:** tactic beam, optimistic/RMaxTS, graph/MCGS,
  AND/OR MCGS, robust whole-proof rendering from arbitrary trees, and TTT
  orchestration wait for replay/eval evidence, state-identity design, backend
  proof/script support, or a concrete trainer adapter.

Do not treat these as silently complete. They are either external runs,
site-specific integration, training-repo work, or explicitly gated future
research/engineering.
