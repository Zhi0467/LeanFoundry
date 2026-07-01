# LeanFoundry
## Full System Design — v11

> **v11.85 (2026-07-01):** The tree compact-fanout handoff now reaches Slime's
> trainer-side data boundary in the local compatibility suite. The `[training]`
> extra includes `megatron-core==0.18.0` and `torch-memory-saver==0.0.9.post1`
> on Linux/Python >= 3.12, and `tests/test_slime_compat.py` drives
> LeanFoundry tactic samples through the pinned Slime
> `RolloutManager._convert_samples_to_train_data(...)`,
> `_split_train_data_by_dp(...)`, `process_rollout_data(...)`, and Megatron
> `DataIterator`. The asserted train data keeps rollout ids `[0, 0, 2]`,
> per-rollout mask sums `[11, 11, 5]`, one global batch of two theorem-search
> rollouts, and three microbatches. This proves the local trainer input shape
> up to the model actor iterator. It is still not a full Slime/Megatron model
> step: importing the pinned installed Slime actor reaches missing trainer-stack
> dependencies/packaging (`sglang` is intentionally isolated in `.venv-sglang`,
> and the installed Slime wheel omits the source `megatron_utils/kernels`
> package). The remaining completion proof is a trainer-image run that uses the
> full Slime/SGLang/Megatron stack and executes `loss_type=sft_loss` plus weight
> sync.

> **v11.84 (2026-07-01):** Tree-search Slime samples now use Slime's compact
> fanout contract, not a flat ragged `list[list[Sample]]`. `tactic` rows from
> one theorem search are returned as `list[list[list[Sample]]]` at the Slime
> boundary (`prompt/search x compact-rollout x step-samples`); siblings share
> one `Sample.rollout_id`, while `metadata["slime_rollout_id"]` preserves the
> Slime rollout step id. Direct and self-correct rows remain regular Slime
> sample groups and get one rollout id per sample unless a downstream custom
> objective deliberately regroups them. A new compatibility test exercises the
> pinned Slime `build_dp_schedule(...)` path and proves two theorem searches
> schedule as two rollouts instead of being collapsed into one Slime step.
> This clarifies the objective boundary: tree lineage-A `(proof_state,
> tactic)` data is expert-iteration/SFT data (`loss_type=sft_loss` for the
> default downstream launch), not fixed-width GRPO. A full Slime/Megatron
> trainer step with this compact fanout is still the remaining live proof.

> **v11.83 (2026-07-01):** The Slime handoff now includes an argparse provider:
> `leanfoundry.slime.add_leanfoundry_arguments(parser)`. The downstream training
> repo should pass this function to Slime's
> `parse_args(add_custom_arguments=...)` hook instead of duplicating
> LeanFoundry's `lean_*` / `lf_*` flag inventory. Slime still owns generic
> trainer, checkpoint, rollout-batch, and SGLang router flags such as
> `--hf-checkpoint`, `--rollout-batch-size`, and `--sglang-router-ip`.

> **v11.82 (2026-07-01):** Tree-search Slime rollouts now enforce the
> lineage-A data contract by default. The live real-SGLang tree EI smoke
> (`tests/test_slime_tree_ei_live.py`) first exposed that tree search was
> emitting a verified rendered `whole_proof` row before the intended tactic row.
> The Slime rollout composition root now suppresses whole-proof rows for tree
> algorithms unless `lf_include_tree_whole_proof_rows=True` is set. The same
> e2e writes a tiny random GPT-2 checkpoint, serves it through real SGLang,
> runs `puct_tree` against live Lean, verifies a tactic-level `Sample`, and
> performs one local `torch` optimizer step over the emitted
> `tokens`/`response_length`/`loss_mask`. This proves the local tree EI sample
> contract, not full Slime/Megatron trainer acceptance or weight sync.

> **v11.81 (2026-07-01):** The local Slime adapter e2e now has a deterministic
> SGLang-compatible generator. With the Docker Kimina backend on
> `http://127.0.0.1:8017`, `LEANFOUNDRY_SLIME_E2E=1
> LEANFOUNDRY_SLIME_E2E_LOCAL_GENERATOR=1 ... tests/test_slime_live.py`
> passed all three modes (`direct`, `puct_tree`, `self_correct`). This uses the
> real pinned Slime package, real `async_generate_rollout`, real tokenizer
> loading from a temporary HF checkpoint, and live Lean execution, but the model
> endpoint is deterministic test infrastructure rather than a deployed SGLang
> model server. Remaining before trainer-complete claims: run against the real
> SGLang/Megatron deployment, prove tree compact fanout is accepted by the
> trainer objective, and run a full Slime/Megatron training run.

> **v11.80 (2026-07-01):** The Slime `Sample` construction boundary is now
> explicit. `leanfoundry/slime/samples.py` uses Slime's native
> `Sample.append_response_tokens(...)` only when a row carries
> `slime_response_log_probs`; the pinned Slime API rejects trainable appended
> tokens without rollout log-probabilities. LeanFoundry's default search rows
> are already verifier-grounded and do not carry those SGLang rollout
> log-probs, so they use an explicit `leanfoundry_verified_without_rollout_logprobs`
> fallback while still setting prompt/response tokens, `response_length`, and
> `loss_mask`. The opt-in live Slime smoke now covers `direct`, `puct_tree`,
> and `self_correct` modes and requires at least one emitted row. This is
> adapter/API evidence, not a trainer-complete claim: real Slime/SGLang trainer
> acceptance, tree compact fanout, and a full training run remain unproven until
> the live stack exists and passes.

> **v11.79 (2026-07-01):** Local `/exec` e2e was recovered after starting the
> Docker Kimina backend. The server image `zzzzhi/kimina-lean-server:9820b9a`
> ran on `http://127.0.0.1:8017` with one Pantograph worker, bounded
> `/exec/limits`, and `LEANFOUNDRY_E2E=1 ... tests/test_e2e_search.py` passed
> all seven live tests. Superseded by v11.81 for local Slime adapter e2e
> evidence.

> **v11.78 (2026-07-01):** Completion evidence is now live-e2e gated. A
> runtime path is not considered done until its relevant live e2e has actually
> run and passed in the target environment; hermetic tests, fake transports,
> skipped e2e tests, import-only compatibility checks, and checklists do not
> prove completion. The `main` branch is currently core-only after the
> extension split: Extension A-D implementation snapshots are preserved on
> `extensions/codex-full`, but are not trusted current `main` implementation.
> Do not merge that branch wholesale into `main`; future extension work must
> cherry-pick or re-implement reviewed pieces onto current `main`. Any lower
> historical note saying an extension component "landed" should be read as
> history from the pre-split snapshot unless the corresponding package exists
> on `main` and has live-e2e evidence.

> **v11.77 (2026-06-30):** Backend validation reports now carry live-run
> latency diagnostics. `BackendValidationReport` records create, replay-step
> aggregate, verify, and total elapsed seconds, and
> `leanfoundry-validate-backend` includes aggregate latency totals/means in its
> JSON summary. This makes the validation CLI usable for backend latency
> sweeps; real LeanDojo/LeanTree trajectory material, cache-hit interpretation,
> state-token-size telemetry, and production backend profiling remain live
> environment work.

> **v11.76 (2026-06-30):** Extension B now has a concrete formalizer
> service/prompt contract. `HTTPFormalizer` implements the existing injected
> `Formalizer` protocol over a JSON endpoint, `formalizer_payload(...)`
> carries staging id, informal statement, env profile, header, attempt index,
> verifier feedback, and a default prompt, and
> `parse_formalizer_response(...)` requires a structured non-empty
> `lean_statement`. The draft/retry loop is still model-agnostic and injected;
> this is a service boundary and prompt policy, not a deployed formalizer
> checkpoint, model calibration, or live corpus result.

> **v11.75 (2026-06-30):** Eval loading now has a second built-in
> public-benchmark row adapter and the named MathOlympiadBench eval target has
> a concrete adapter too. `PUTNAMBENCH_LEAN4_ROW_FORMAT` /
> `putnambench_lean4_jsonl` adapts the public PutnamBench Lean 4 JSONL mirror's
> `problem_name`, `formal_statement`, optional `informal_statement`, and
> `split` fields into `TheoremSpec`s. Because that mirror has no per-row Lean
> header, the loader requires an `EnvProfile` registry entry for the manifest's
> `env_profile` and uses that registered header.
> `MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT` /
> `matholympiadbench_lean4_jsonl` adapts MathOlympiadBench `name` or
> `problem_id`, `formal_statement`, `header`, optional `informal_prefix`, and
> `split` rows. `PROOFNET_LEAN4_ROW_FORMAT` / `proofnet_lean4_jsonl` adapts
> ProofNet rows with `name`, `formal_statement`, `header`, optional
> `informal_prefix`, and `split`; it is intentionally a theorem-initialization
> transform that only accepts statements ending at `:=` and fills that exact
> placeholder with `by sorry`. Split mismatches fail closed. These adapters
> preserve full Lean blocks, including helper declarations before the theorem,
> without changing the core theorem schema.

> **v11.74 (2026-06-30):** Extension C promoted TTT traces now have a durable
> replay surface. `TTTTraceReplayRecord` stores the promoted
> `TTTSessionTrace`, the `TTTTracePromotionDecision`, the stable `trace_key`,
> env profile, checkpoint, final status, adapter id, round count, and model
> version; SQLite schema v8 persists these rows in `ttt_trace_replay`.
> `persist_promoted_ttt_trace(...)` is the explicit caller-owned write path.
> This admits trace artifacts only; it does not turn TTT traces into A-type
> proofs, policy examples, or value labels. Concrete trainer fine-tuning/reload
> and a selected per-problem search source remain downstream/future work.

> **v11.73 (2026-06-30):** Eval loading now includes the first built-in
> public-benchmark row adapter. `MINIF2F_LEAN4_ROW_FORMAT` /
> `minif2f_lean4_jsonl` adapts MiniF2F Lean 4 JSONL rows with `id` or `name`,
> `split`, `formal_statement`, `header`, and optional `informal_stmt` into
> `TheoremSpec`s using the manifest-owned `env_profile`; manifest split
> mismatches fail closed. Callers can still override the adapter for a different
> MiniF2F variant. Other public benchmark adapters remain future work until
> their row formats and env-profile compatibility are selected.

> **v11.72 (2026-06-30):** The lean-client boundary now has an explicit
> adapter pass-through regression. `tests/test_env_backend.py` verifies that
> `KiminaEnvBackend` forwards `limits`, `create_states`, `step`, `verify_one`,
> `verify`, `cleanup`, `cancel`, `stats`, and `close` to the pinned
> `AsyncLeanExecBackend` façade shape, including `goal_group` tuple-to-list
> conversion. This strengthens the local client-boundary evidence; backend
> server internals, state-store behavior, cache/latency, and kernel cancellation
> guarantees still require live backend/server-side validation.

> **v11.71 (2026-06-30):** System-landscape claims were refreshed against
> primary source pages for the core referenced prover/tooling systems. The
> landscape now includes OProver and Pythagoras-Prover as 2026 open whole-proof
> / agentic baselines. This refresh supports the boundary claim that
> LeanFoundry is infrastructure for controlled search/training experiments, not
> a claim to invent state-tactic data or to be the latest prover checkpoint.
> External benchmark and open/closed-source claims remain background context and
> should be refreshed again before publication.

> **v11.70 (2026-06-30):** Literature/novelty framing is tightened around the
> training-data question. HTPS, LeanDojo/ReProver, and BFS-Prover-style systems
> already use proof-state/tactic step data or search-distilled step-prover
> training; LeanFoundry's step-level Path-A data is therefore prior-art-aligned,
> not a novel data shape and not a lazy fallback for tree rendering. The
> downstream training-repo question is the controlled comparison: under fixed
> curriculum, verifier budget, env profile, and evals, do lineage-A step rows,
> lineage-B whole-proof rows, self-correction rows, or mixtures produce the
> best prover in native and crossed evaluation?

> **v11.69 (2026-06-30):** Extension B now has an
> embedding-similarity dedup service contract and optional promotion gate.
> `HTTPEmbeddingDeduplicator` posts staging rows and a similarity threshold to
> a JSON endpoint, `parse_embedding_dedup_response(...)` validates duplicate
> flags and scores against the threshold, and
> `PromotionGateConfig(require_embedding_unique=True)` lets promotion reject
> missing, errored, or duplicate embedding-dedup results. This is an
> integration contract and gate only; real embedding models, vector indexes,
> corpus calibration, service deployment, and live staged-corpus runs remain
> external/future work.

> **v11.68 (2026-06-30):** Extension C TTT trace promotion now has a local
> decision gate. `evaluate_ttt_trace_promotion(...)` requires config opt-in by
> default, checks env-profile and trace-key dedup inputs, rejects failed stages,
> and by default promotes only solved sessions with a successfully reloaded
> adapter. It returns a trace marked `promoted_to_main_replay=True` when the
> gate passes. Concrete trainer/reload execution and MCGS/per-problem search
> sources remain external/future work.

> **v11.67 (2026-06-30):** Extension D local budget metering now has a script
> entrypoint. `leanfoundry-budget-meter` initializes SQLite meter cells from a
> JSON ledger or plan-shaped object, atomically reserves usage, prints cell
> snapshots, and returns nonzero when a reservation is refused. This is an
> operator/script hook over `SQLiteBudgetMeterStore`, not a distributed
> metering service, trainer integration, or worker-side measurement pipeline.

> **v11.66 (2026-06-30):** Extension D budget enforcement now has a local
> durable SQLite meter. `SQLiteBudgetMeterStore` initializes plan ledger cells,
> validates existing cell drift, and uses `BEGIN IMMEDIATE` transactions to
> atomically reserve metered usage through `check_budget_request(...)`. This
> closes the single-process/local-file durable counter gap. Distributed
> metering services, trainer integration, live worker-side measurements, and
> multi-node database deployment remain training/deployment work.

> **v11.65 (2026-06-30):** Extension A router cancellation now has local
> protocol semantics. `RouterCommand.CANCEL` lets `AsyncRouterService` cancel
> an in-flight backend assignment after the client disconnects;
> `cancel_inflight_requests(...)` frees the scheduler slot and drains queued
> work; `RouterBackendWorker` cancels the local task for that router request.
> Late backend responses for already-cancelled work are dropped. This is local
> router/worker cancellation, not a guarantee that every concrete Lean backend
> operation can abort kernel execution instantly.

> **v11.64 (2026-06-30):** Extension A state portability now has a read-only
> HTTP(S) URI fetch path. `decode_http_state_ref(...)` and
> `decode_uri_state_ref(...)` read `PortableStateRef(location=URI)` payloads
> from `http://`, `https://`, or existing `file://` references, enforce exact
> payload size, decode the configured codec, and verify the decoded state hash.
> This supports common object-store public/signed-URL reads; credentialed
> object-store clients, remote writes, lifecycle policy, and state
> export/import from the Lean backend remain deployment/backend work.

> **v11.63 (2026-06-30):** Extension A reference router diagnostics now have
> optional HTTP health and metrics endpoints. `leanfoundry.scaleout.health`
> derives `/healthz`, `/readyz`, and `/metrics` responses from
> `RouterServiceSnapshot`; `leanfoundry-router` can serve them with
> `--health-port`. This is a local supervisor hook and Prometheus-text export,
> not a production deployment, restart policy, TLS/auth layer, pager
> integration, or cluster autoscaler integration.

> **v11.62 (2026-06-30):** Extension B now has local formalization
> draft/retry orchestration. `run_formalization_draft_loop(...)` takes an
> injected `Formalizer` and `StatementVerifier`, checks each generated Lean
> statement with the staging statement-check wrapper, passes verifier feedback
> into the next attempt, and returns an accepted staging row only when syntax
> checking passes. The concrete HTTP formalizer service/prompt boundary landed
> later in v11.76; deployment, real model calibration, embedding-similarity
> dedup service, real judge calibration, and live staged-corpus evaluation were
> still future/external at this slice.

> **v11.61 (2026-06-30):** Extension B now has a semantic-judge service
> contract. `HTTPSemanticJudge` posts staged informal/formal statement pairs to
> a JSON endpoint, `parse_semantic_judge_response(...)` validates a score in
> `[0, 1]`, and `staging_record_with_semantic_judge_result(...)` populates the
> staging row's `semantic_judge_score`. Promotion remains the layer that
> applies the threshold. A real judge model, calibration corpus, service
> deployment, and human-quality evaluation remain future/external work.

> **v11.60 (2026-06-30):** Extension B now has a local statement-check wrapper.
> `verify_staging_statement_code(...)` builds the Lean snippet used to check a
> staged theorem statement with a `sorry` body, `KiminaStatementVerifier` calls
> lean-client's legacy REPL `api_check` route, and
> `staging_record_with_syntax_result(...)` updates the staging row's
> `syntax_checked` gate field from the normalized result. This is syntax/type
> checking only; it does not run an LLM draft/retry loop, semantic judge,
> embedding dedup service, or live statement-check corpus.

> **v11.59 (2026-06-30):** Extension A reference router hardening now has
> local health diagnostics and pending-client cleanup. `RouterServiceSnapshot`
> exposes backend-slot, queue, client-request, stored-frame, assignment,
> delivery, requeue, and dropped-pending counters from `AsyncRouterService`.
> Client disconnects now drop requests that are still pending and leave already
> forwarded backend work to finish and be discarded, because the reference
> router has no backend cancellation protocol yet. This is not a production
> health endpoint or metrics exporter; supervisors still need site-specific
> probing, alerting, restart policy, and backend cancellation semantics.

> **v11.58 (2026-06-30):** Extension A reference router processes now have
> console entrypoints. `leanfoundry-router` starts `AsyncRouterService`, and
> `leanfoundry-router-worker` builds `RouterBackendWorker` around the normal
> `make_env_backend(EnvBackendConfig(...))` composition root. This gives
> systemd/Slurm/Kubernetes or local scripts stable process commands without
> making LeanFoundry own site-specific supervision, health checks, restart
> policy, metrics export, or autoscaler wiring.

> **v11.57 (2026-06-30):** Extension A ZSTD state payloads now have an
> explicit optional dependency contract. The `[scaleout]` extra installs
> `zstandard`, default installs still fail closed with a clear runtime error
> when `StateSnapshotCodec.ZSTD` is requested, and focused tests cover both the
> absent-extra path and real ZSTD inline/file state-ref round-trips under
> `uv run --extra scaleout`. Deployment still must decide whether workers and
> routers install this extra consistently.

> **v11.56 (2026-06-30):** Extension A now has a router-backed EnvBackend
> adapter baseline. `RouterEnvBackend` sends lean-client `/exec` operations as
> JSON payloads inside router `REQUEST` frames, and `RouterBackendWorker` wraps
> an injected `EnvBackend`, executes those operations, and returns typed
> responses through router `RESPONSE`/`DELIVER` frames. Covered operations are
> limits, create_states, step_batch through the one-state `EnvBackend.step(...)`
> hot path, verify, cleanup, cancel, and stats. This keeps the router service
> payload-opaque while giving search/eval code a real `EnvBackend` client for a
> reference router deployment. Lean state export/import, remote payload
> transport, production process supervision, distributed replay, and cluster
> deployment remain future/deployment work.

> **v11.55 (2026-06-30):** Extension A URI state payloads now have local
> `file://` helpers. `make_file_state_ref(...)` writes encoded state bytes to a
> file URI and returns a `PortableStateRef(location=URI)`, while
> `decode_file_state_ref(...)` reads and validates payload size, decoded
> SHA-256, and raw size before returning state bytes. This does not implement
> remote/object-store URI adapters, Lean backend state export/import, or router
> payload transfer; it only makes local URI references executable and
> integrity-checked.

> **v11.54 (2026-06-30):** Extension A now has a reference asyncio TCP router
> service over the binary frame codec. `AsyncRouterService` accepts backend
> `REGISTER` connections, client `REQUEST` frames, forwards opaque payloads as
> `FORWARD`, delivers backend `RESPONSE` payloads as `DELIVER`, and requeues
> in-flight requests when a backend connection drops. Backend registration uses
> a small JSON payload (`RouterBackendRegistration`) inside the binary frame.
> This is a local correctness harness, not the production C++/deployment router:
> superseded in part by v11.56, which adds a router-backed EnvBackend adapter.
> State export/import, remote URI payload transfer, distributed replay,
> connection hardening, metrics, and autoscaler integration remain
> future/deployment work.

> **v11.53 (2026-06-30):** Extension A router framing now has a local binary
> codec. `RouterCommand`, `RouterFrame`, `encode_router_frame(...)`, and
> `decode_router_frame(...)` implement the documented
> `uint64 request_id | uint8 command | uint16 response_count | uint32 payload`
> frame in network byte order with strict exact-frame decoding. Command
> payloads remain opaque bytes at this layer. Superseded in part by v11.54,
> which adds a reference asyncio TCP service over this codec, and v11.56, which
> adds `/exec` adapter payloads; state export/import and distributed replay
> remain future/deployment work.

> **v11.52 (2026-06-30):** Extension A router semantics now have a local pure
> scheduler baseline. `RouterState` plus `register_backend(...)`,
> `enqueue_request(...)`, `complete_request(...)`, and
> `disconnect_backend(...)` implement deterministic FIFO assignment to idle
> backend CPU slots, completion-driven queue draining, duplicate-id rejection,
> and disconnect requeue for in-flight requests. This is not the TCP REPL
> router service, backend adapter, state export/import path, distributed replay
> store, or deployment autoscaler; it only makes the core routing state
> transition rules executable and testable.

> **v11.51 (2026-06-30):** Extension A state portability now has local
> byte-level helpers. `make_inline_state_ref(...)` builds an inline
> `PortableStateRef` from state bytes, and `decode_inline_state_ref(...)`
> decodes and validates inline payloads against SHA-256 and raw-size metadata.
> RAW inline payloads are supported in core; ZSTD remains optional and requires
> an installed `zstandard` runtime. Superseded in part by v11.57, which adds
> the `[scaleout]` extra for that runtime, and v11.55, which adds local
> `file://` URI helpers. Backend state export/import, router service/adapter
> work, and distributed replay remain future/deployment work.

> **v11.50 (2026-06-30):** Extension B now has local staging metadata helpers.
> `formal_statement_dedup_hash(...)` / `staging_record_with_dedup_hash(...)`
> provide exact normalized statement/header/env-profile dedup hashes, and
> `estimate_difficulty_from_quick_search(...)` maps a quick search
> `SearchResult` into the numeric `difficulty_estimate` used by
> `TheoremRecord`. These helpers do not replace semantic LLM judging,
> embedding-similarity dedup, LLM draft/retry, or statement verifier services.

> **v11.49 (2026-06-30):** Extension C now has a generic local TTT
> orchestrator. `run_ttt_session(...)` alternates injected search, sample
> extraction, `TTTAdapter.fine_tune(...)`, adapter reload, and
> `AdaptablePolicyClient.with_adapter(...)`, producing `TTTSessionTrace`
> artifacts for success, insufficient-sample stops, training failures, and
> reload failures. MCGS or another selected per-problem search source and
> concrete LoRA optimization/reload remain external/future work. Superseded in
> part by v11.68, which adds the local trace-promotion decision gate.

> **v11.48 (2026-06-30):** Extension D budget enforcement now has a local
> request guard. `check_budget_request(...)` evaluates one metered request
> against a `BudgetLedgerEntry` cell, verifies the request's
> `budget_account_id`, refuses hard-cap overruns, and returns remaining-budget
> diagnostics. Durable usage accounting, concurrency control, and service
> integration remain deployment work; the core helper only makes the hard-cap
> rule executable and testable.

> **v11.47 (2026-06-30):** Extension D frozen-curriculum construction now has
> a deterministic local helper. `build_frozen_curriculum_from_pass_sweep(...)`
> consumes aligned theorem/search-result pairs from one direct whole-proof
> pass@N sweep, requires complete verifier-attempt evidence for candidates
> `1..N`, computes per-theorem accepted-candidate rates, assigns difficulty
> buckets, and rank-splits the fixed pool into training rounds. Running the
> sweep on a real model, optimizer execution, checkpoint production, and live
> budget-meter enforcement remain training/deployment work.

> **v11.46 (2026-06-30):** The `/exec` validation harness now has an operator
> entry point. `leanfoundry-validate-backend` /
> `python -m leanfoundry.env_backend.validation_cli` loads
> `BackendValidationCase` JSON or JSONL, enforces one coherent `env_profile`
> per validation run, connects to a live `EnvBackend`, emits JSON report
> summaries, and exits nonzero on replay or final-verification failures. Real
> LeanDojo/LeanTree case material and cache/latency measurement remain
> deployment/data validation work.

> **v11.45 (2026-06-30):** Extension A now has minimal scale-out contracts.
> `leanfoundry.scaleout` records future router metrics, the queue-depth
> autoscaling decision formula, and portable state snapshot references with
> codec/location/hash/size invariants. This does not implement the REPL router,
> backend state export/import, Postgres/Redis replay, or deployment autoscaler;
> it gives those future components typed inputs and outputs without changing the
> single-machine core.

> **v11.44 (2026-06-30):** Extension B now has a minimal promotion contract.
> Autoformalization staging records preserve the Lean header/import block needed
> to become `TheoremRecord`s, with SQLite schema version 7 adding `header` to
> legacy staging rows. `leanfoundry.formalization.evaluate_promotion(...)`
> converts a syntax-checked, semantically judged, deduped staging row into a
> B-type theorem record, or returns machine-readable rejection reasons. LLM
> drafting, verifier-wrapper retries, semantic judging, embedding dedup, and
> difficulty estimation remain future pipeline work.

> **v11.43 (2026-06-30):** Extension C / TTT now has a local contract baseline.
> `leanfoundry.ttt` exposes framework-neutral `TTTAdapter` and
> `AdaptablePolicyClient` protocols, while `leanfoundry.schemas.ttt` records
> `TTTConfig`, adapter fine-tune requests/results, and per-round/session traces.
> The contract keeps optimizer execution and concrete SGLang/LoRA reload in the
> downstream training repo, keeps trace promotion out of the main replay buffer
> by default, and did not yet claim a runnable loop. Superseded in part by
> v11.49, which adds callback-driven local orchestration; MCGS and real adapter
> reload implementations remain future work.

> **v11.42 (2026-06-30):** Extension D now has a local ablation contract, not a
> trainer. `AblationExperimentPlan` records the frozen curriculum, the five
> standard arms (W, W+SC, T-step, T-noval, Mix), per-arm replay/checkpoint
> namespaces, hard generation/training/verifier ledgers, and crossed-eval cells.
> Helpers in `leanfoundry.evals.experiment_plan` materialize the default arms,
> ledgers, and native eval matrix. No-value tree arms are schema-guarded from
> value serving and value metrics. Actual optimizer execution, checkpoint
> production, and live budget-meter enforcement remain training/deployment work.

> **v11.41 (2026-06-30):** Plain `DIRECT` whole-proof search now uses the
> backend's batch verifier surface. The engine builds one `ExecVerifyItem` per
> sampled candidate, submits the pass@k pool through `EnvBackend.verify(...)`,
> preserves one `DirectVerificationAttempt` per candidate, and keeps pass@k
> semantics ordered by candidate index. `SELF_CORRECT` stays sequential because
> each next prompt depends on the previous verifier feedback.

> **v11.40 (2026-06-30):** Optional Path-B render accounting now has
> diagnostics without changing the training-data gate. `extract_training_artifacts(...)`
> records `path_b_render_candidates`, `path_b_renderable_candidates`,
> `path_b_unsupported_candidates`, and `path_b_verified_candidates` over proved
> action subtrees. These are action-level counters for the existing narrow
> renderer and top-level verification artifact; they do not emit extra training
> rows or attempt arbitrary standalone subproof verification.

> **v11.39 (2026-06-30):** The `/exec` validation harness now has a reusable
> code surface. `leanfoundry.env_backend.validation.validate_backend_case(...)`
> replays tree-shaped known tactic trajectories through an injected
> `EnvBackend`, carries LeanFoundry's goal-coupling split into focused
> `goal_group` child replays, and verifies the supplied complete proof through
> `/exec/verify`. This closes the local harness API gap; running it over real
> LeanDojo/LeanTree trajectories against a live backend remains deployment/data
> validation work.

> **v11.38 (2026-06-30):** Current-vs-future boundaries are reconciled in the
> long-form design text. The core implementation is direct whole-proof search,
> self-correction, AND/OR tree search with PUCT or best-first selection,
> step-level Path-A extraction, eval artifacts, replay persistence, optional
> Slime rollout integration, value-client serving, and conservative synthetic
> negation. Graph/MCGS, tactic beam, optimistic/RMaxTS, arbitrary Path-B proof
> rendering, Extension A scale-out, Extension B formalization, Extension C TTT,
> and Extension D ablation infrastructure remain explicit future/deferred work.
> `lean_client.exec_models` is the shared wire schema and may be imported by
> protocol-facing modules; only `kimina_backend.py` constructs the concrete
> `AsyncLeanExecBackend` client.

> **v11.37 (2026-06-30):** Benchmark loading now supports manifest-owned
> sources beyond explicit local paths. `load_benchmark_source(...)` reads
> `BenchmarkManifest.source`, validates compatibility/profile/count as before,
> and supports local paths, `file://` URIs, HTTP(S) JSONL, and explicit
> Hugging Face file URIs of the form `hf://repo` or `hf://org/repo` with
> `?path=...` plus optional `revision=...` (falling back to
> `benchmark_commit` or `main`). `BenchmarkManifest.row_format` records the
> source row contract: the default is serialized `TheoremSpec` JSONL, while
> non-default formats require a registered or built-in `BenchmarkRowAdapter` at
> load time. `minif2f_lean4_jsonl` is the first built-in public-benchmark row
> format. This keeps benchmark-specific schema transforms out of the core
> schema while making remote/public dataset loading a typed extension point.

> **v11.36 (2026-06-30):** Failed self-correct attempts can now be emitted as
> optional reward-0 training rows without changing the default core data
> contract. `to_training_rows(...,
> include_failed_self_correct_negatives=True)` emits `kind="self_correct"`
> rows for rejected turns with metadata
> `self_correct_objective="failed_negative"`, while accepted corrections remain
> reward-1 rows. The Slime rollout path exposes this through
> `lf_include_failed_self_correct_negatives`; the default remains off.

> **v11.35 (2026-06-30):** Attempt-lifecycle reconciliation now has an
> operator-facing command. `leanfoundry-reconcile-lifecycle` (or
> `python -m leanfoundry.replay.lifecycle_cli`) opens a SQLite replay DB,
> connects to the configured Lean backend, runs one or more reconciliation
> passes through `reconcile_attempt_lifecycle_periodically(...)`, prints JSON
> diagnostics, emits alert JSON for warning/critical lifecycle outcomes, and
> can return nonzero for cron/systemd alerting. This is deployment wiring for
> running the existing cleanup/cancel outbox; pager/metrics integration remains
> site-specific.

> **v11.34 (2026-06-30):** Slime live-stack validation now has an opt-in smoke
> harness in `tests/test_slime_live.py`. With `[training]` installed and
> `LEANFOUNDRY_SLIME_E2E=1`, it drives the real
> `leanfoundry.slime.async_generate_rollout` path through the pinned Slime
> package, a live SGLang router, a live Kimina Lean backend, and the configured
> tokenizer checkpoint. Superseded by v11.80 for mode coverage and row-emission
> strength. Default test runs skip it, and actually executing it remains
> deployment-environment work.

> **v11.33 (2026-06-30):** Direct whole-proof search now treats
> `max_direct_candidates` as the full `DIRECT` pass@k pool. It samples one pool,
> verifies every returned candidate, records every `DirectVerificationAttempt`,
> returns the first accepted proof as `SearchResult.proof_tree`, and stores
> every accepted verified proof in `TrainingArtifacts.proof_candidates`.
> `SELF_CORRECT` still stops when a correction is accepted because later
> generations would belong to future feedback rounds. Eval pass@k is computed
> from accepted verifier candidate indices, not from total verifier attempts.
> Superseded in part by v11.41, which changed the plain `DIRECT` verifier
> transport from a sequential `verify_one` loop to `EnvBackend.verify(...)`.

> **v11.32 (2026-06-30):** Nested negation proof search now uses the normal
> AND/OR tree. The synthetic negation action attaches the backend-created
> negated-theorem proof state as its child; tactics inside that proof are
> searched like ordinary actions, and open subgoals continue as ordinary child
> states. When that child subtree is proved, the synthetic action marks the
> original source state `DISPROVED`, emits a durable `NegationAttempt`, and
> policy positives are extracted for the synthetic negation proof states rather
> than the original false state.

> **v11.31 (2026-06-30):** Durable schema release governance is now explicit in
> [`schema_release_governance.md`](schema_release_governance.md). Released
> migrations are immutable, new durable changes append numbered migrations,
> Pydantic models remain the source of truth, supported released versions need
> upgrade tests, and destructive changes require preservation or an explicit
> export/import path. This closes the release-policy residual left after the
> ordered SQLite migration registry landed in v11.28.

> **v11.30 (2026-06-30):** Negation is no longer a one-shot check. The tree
> search now initializes a synthetic childless OR action for eligible states,
> stores the rendered negated theorem/backend negation state on that action,
> and lets normal selection revisit the action for additional tactic batches.
> Failed negation tactics leave the action open; repeated policy outputs fail
> closed instead of looping; a completed negation tactic marks the source state
> `DISPROVED` and emits durable attempt artifacts for each retry. Superseded in
> part by v11.32, which attaches and searches the synthetic negation proof state
> as a normal child subtree.

> **v11.29 (2026-06-30):** Synthetic negation rendering now accepts typed local
> definitions by abstracting each `let`/local definition as a normal typed
> parameter in the generated theorem. This asks Lean to prove a stronger
> statement than the original state-under-definition, so a successful negation
> check remains sound. Entries with missing names, invalid binder identifiers,
> or empty types still fail closed. This closes the common local-definition
> rendering gap for the one-shot baseline; full Aristotle-style persistent
> negation sub-search remains future work.

> **v11.28 (2026-06-30):** SQLite replay migrations now use an ordered
> migration registry instead of a hand-written ladder. New migrations append to
> the registry and bump `SCHEMA_VERSION`; legacy v4/v5 upgrade coverage proves
> current DBs reach the v6 schema with extraction-failure and negation-attempt
> tables. Superseded in part by v11.44, which bumps the current schema to v7
> with the formal-staging header migration, and later by v11.74, which bumps
> the current schema to v8 with promoted TTT trace replay. The remaining
> compatibility question is release governance for future stable schemas, not
> the mechanics of applying known migrations.

> **v11.27 (2026-06-30):** Synthetic negation checks now produce durable
> proof-attempt artifacts. `TrainingArtifacts.negation_attempts` stores a
> `NegationAttempt` for each concrete check: source state/node, negated target,
> rendered synthetic theorem, backend negation state, tactic statuses/messages,
> charged tactic calls, proved flag, proved tactic, and operational status. The
> replay store persists these in `negation_attempts` with deterministic ids.
> These artifacts justify/audit `DISPROVED` value labels; they are not policy
> positives for the original goal. Full Aristotle-style persistent negation
> sub-search and richer local-context rendering remain future work.

> **v11.26 (2026-06-30):** Extraction failures are now durable replay
> artifacts. `ExtractionFailureRecord` and the `extraction_failures` SQLite
> table persist `TrainingArtifacts.failures` with theorem/env/attempt/model
> provenance, deterministic ids, failure kind, message, and optional node id.
> Replay diagnostics now include `replay_extraction_failures`. Eval remains
> file-backed with content hashes; the SQLite replay spine owns online/offline
> training artifacts and failure audit rows.

> **v11.25 (2026-06-30):** Env-profile manifests are now wired into eval
> ingress. `load_benchmark_jsonl(...)`,
> `validate_benchmark_theorems(...)`, and `FixedModelEvalRunner.run(...)`
> accept an optional `EnvProfile` registry and validate theorem headers against
> the pinned profile metadata before running eval. The Slime training backend
> builder now requires an explicit non-default `lean_env_profile` or
> `env_profile`; low-level `EnvBackendConfig` keeps its `"default"` value as a
> direct dev/test transport convenience, not as a training ingress default.

> **v11.24 (2026-06-30):** Lifecycle reconciliation now has a scheduler/alert
> baseline. `reconcile_attempt_lifecycle_periodically(...)` runs bounded or
> infinite reconciliation passes over the replay outbox, sleeps between passes,
> aggregates diagnostics, and can call an operator alert sink. Failed backend
> rows emit warning alerts; orphaned cleanup rows emit critical alerts.
> Deployment-specific wiring to cron, supervisors, metrics, or paging remains
> outside core LeanFoundry.

> **v11.23 (2026-06-30):** Direct and self-correct whole-proof search now
> preserve all verifier attempts as eval provenance. `TrainingArtifacts` has
> `direct_verification_attempts`, a list of `DirectVerificationAttempt`
> records with candidate index, proof text, verifier status/feedback,
> `verify_item_id`, and accepted flag. This is not a training-row source:
> `to_training_rows(...)` still emits whole-proof rows only for verified
> `ProofTree` candidates and self-correct rows only for accepted corrections.
> Eval manifests count recorded direct verifier attempts, and
> `results.jsonl` contains the per-candidate trace.

> **v11.22 (2026-06-30):** `SELF_CORRECT` now persists a neutral trace artifact
> for accepted corrections. `SelfCorrectTrace` contains ordered
> `SelfCorrectTurn`s with proof text, verifier status, rendered verifier
> feedback, verifier item id, and accepted flag. `to_training_rows(...)` emits
> `kind="self_correct"` rows when a later turn is accepted: the prompt contains
> the theorem, previous failed proof, and feedback; the response is the accepted
> correction. Failed-correction negatives remain an explicit training-objective
> choice and are not default core rows.

> **v11.21 (2026-06-30):** Lifecycle outbox rows are now retryable, not only
> observable. `ReplayStore.get_pending_attempt_lifecycle_records(...)` exposes
> non-terminal rows ready for reconciliation, and
> `reconcile_attempt_lifecycle(...)` retries cleanup/cancel against the backend
> and persists terminal or pending outcomes. Cleanup rows can end as
> `deleted`, `deferred`, `failed`, or terminal `orphaned`; cancel rows can end
> as `cancelling`, `drained`, `cleaned`, or `failed`. Direct whole-proof search
> now carries active `verify_item_id:k` cancel diagnostics into replay. A
> periodic scheduler/operator alerting loop landed later in v11.24; deployment
> integration remains outside core LeanFoundry.

> **v11.20 (2026-06-30):** Evaluation now has a local manifest-backed artifact
> path. `BenchmarkManifest` is not only schema: `load_benchmark_jsonl(...)`
> validates theorem rows against compatibility, env profile, and expected count.
> `FixedModelEvalRunner.run(..., benchmark_manifest=..., artifact_dir=...)`
> writes `eval_manifest.json`, `results.jsonl`, `benchmark.jsonl`, and
> `report.md`, with result/benchmark/report SHA-256 hashes recorded in the
> manifest metrics. This is the infrastructure artifact spine for local eval
> runs; remote benchmark adapters remain future work.

> **v11.19 (2026-06-30):** Policy prompt history/comment context now has an
> inference-only API path. `PolicyClient.sample_tactics(...)` accepts a
> `PolicyContext`; tree expansion derives `PolicyContext.proof_prefix` from the
> runtime parent-action path, preserving inline comments, and the default HTTP
> tactic prompt renders non-empty prefixes as Lean comments before the current
> proof state. This does not mutate `FactorizedProofState`, does not define a
> history-conditional training target, and does not change the Path-A row shape:
> `PolicyExample.proof_prefix` remains provenance / optional prompt context.

> **v11.18 (2026-06-30):** Value serving and negation now have runnable
> baselines. `HTTPValueClient` supports both numeric-head/JSON scalar outputs
> and natural-language reasoning that ends in a parseable boxed/JSON scalar; the
> Slime runner can build bonded value clients against the SGLang router or
> unbonded clients against a separate endpoint. `try_negation` is
> provenance-gated and can run a conservative backend-grounded negation check
> for eligible single-goal states by rendering a simple synthetic `¬ target`
> theorem, stepping sampled tactics on that negation state, charging completed
> attempts against `max_tactic_calls`, and marking the original state/root
> `DISPROVED` if the negation closes. This is not yet the full Aristotle
> UCB-competing persistent negation sub-search; richer local-context rendering,
> and retryable/persistent negation traces remain future work. Durable
> one-shot negation proof-attempt artifacts landed later in v11.27.

> **v11.17 (2026-06-30):** Path-A step extraction is node-general for proved
> runtime work. `TrainingArtifacts.policy_examples` now contains one positive
> `(state, tactic)` row for every proved runtime action, including multiple
> proved actions at the same state and proved internal subtrees under an
> unproved root. In bonded mode, proved value labels are emitted for every
> proved runtime state. Whole-proof `ProofTree` candidates remain canonical and
> final-verifier-gated; rendered-HER subproof artifacts are still optional
> Path-B work. Extraction failures are classified as `unsupported`,
> `rendering`, or `verification`.

> **v11.16 (2026-06-30):** Search-attempt lifecycle observability now has a
> durable baseline. Cleanup diagnostics include the concrete backend item ids
> still deferred after bounded retries, and best-effort cancel reports item
> statuses or transport failures. When a replay store is present,
> `persist_search_result(...)` writes those observations to
> `attempt_lifecycle_outbox` with retry counts, last status/error, optional
> `next_retry_at`, and a terminal flag. This is a durable sink/outbox only:
> backend reconciliation, retry scheduling, terminal-orphan policy, and direct
> search's active `verify_item_id:k` cancellation diagnostics remain future
> lifecycle work.

> **v11.15 (2026-06-30):** Full training-adapter contract tightened. The
> authoritative implementation handoff is
> [`slime_adapter_spec.md`](slime_adapter_spec.md). The downstream training repo
> is thin: it launches Megatron/SGLang, supplies theorem records, chooses
> hyperparameters/eval, and overrides model-specific prompt/parse/reward hooks;
> LeanFoundry owns correct token/loss-mask construction for Slime `Sample`s.
> Literature alignment: tree-search data is step-level expert-iteration/SFT
> data (`proof_state -> tactic`) in the HTPS/ReProver/BFS-Prover lineage; it is
> not a lazy substitute for whole-proof rendering. Whole-proof and
> self-correction remain separate lineage-B targets. `SELF_CORRECT` needs a
> persisted failed-proof / Lean-feedback / corrected-proof trace artifact before
> it can emit real training rows. Value serving must support bonded and
> unbonded deployment plus two parseable output modes: numeric-head/JSON scalars
> and natural-language reasoning that ends in a validated scalar such as
> `\boxed{0.73}`. Negation is required for semantic `DISPROVED`: only a proved
> negation yields full-weight negative value labels; `EXHAUSTED`/open is merely
> a censored negative after effort gating. Training rollouts fail on missing,
> default, or mixed `env_profile`s until explicit multi-profile routing exists.

> **v11.14 (2026-06-30):** Training-data model clarified — **two generation
> modes = two training targets**, and hybrid inference is benign. (1) Tree search
> emits Markovian per-node `(state, tactic)` step pairs = **lineage A**
> (step-level prover): running the search algorithm distills its
> selection/value/backup decisions into a step policy (expert iteration); train
> as a step policy and roll out interactively/agentically at eval, where a goal
> state is in-distribution. (2) Direct full-generation rollout emits a verified
> whole proof = **lineage B** (whole-proof prover): one `/exec/verify`, the
> model's own output, no rendering. LeanFoundry emits both; a model may train on
> either or a mix (plus self-correct/reflection/comment-augmented data), and how
> to combine, enhance, and group it (EI vs GRPO, `/- tactic state -/` comments,
> etc.) is the **training repo's** choice — that comparison (does training *with*
> a search algorithm beat plain whole-proof generation?) is the experiment the
> training repo runs. **Hybrid/interactive inference** (feed the model a state,
> let it generate to the end) needs **no special training target** — it is
> inference-only and benign: DeepSeek-Prover-V1.5 trains *whole proofs* (with
> `/- tactic state -/` comment augmentation to keep the resume point
> in-distribution) and runs truncate-and-resume MCTS **only at inference**
> (arXiv:2408.08152); a whole-proof- or step-trained model can be run in hybrid
> mode without bespoke data. **Correction to v11.13:** there is NO separate
> history-conditional / injected-state trajectory training target. A proof state
> is Markov (a sufficient statistic), so interleaving injected goal states as
> masked context is nonstandard and redundant; `PolicyExample.proof_prefix` is
> optional provenance / incremental-script context only, and reconstructing it as
> a script for a branching proof is the render problem. `loss_mask` /
> `append_response_tokens(trainable=…)` is used only within a Sample's response
> and for self-correct (masking verifier feedback), never for state interleaving.
> **Rendering a whole proof FROM the tree is never on the data path** (tree →
> step pairs; direct → the model's own proof); Path-B whole-proof rendering stays
> a deferred product/audit artifact, never a data gate.

> **v11.13 (2026-06-30):** Slime adapter ownership reversed. Because Slime is
> the **default** RL engine, its rollout adapter is now first-class code that
> ships **in this repo** under the existing `[training]` optional extra
> (`leanfoundry/slime/`), not a sketch in the training repo. Hard invariant
> unchanged: `import leanfoundry.proofsearch` must never pull in `slime`/
> `sglang`; the adapter is an optional subpackage that only `[training]`
> installs import, and core stays framework-free. The adapter is the
> composition root — it builds `SGLangPolicyClient` and injects it into
> `run_search_batch`, so the "engine never builds clients" rule still holds.
> Everything model-agnostic (transport, n-sampling, state rendering, sample +
> loss-mask construction) is provided here as runnable defaults on a
> `SlimeRolloutRunner` with override hooks; the **training repo is thin** —
> deployment launch (Megatron/SGLang topology, weight sync), the theorem
> dataset, eval, run hyperparameters, and at most a small subclass overriding
> model-specific hooks (`prompt_template`/`parse_completion`, reward/grouping).
> One `SearchConfig` already serves both search modes (the `algorithm` field
> discriminates direct whole-proof vs interactive tree), but the adapter's two
> Slime-facing edges branch by mode: policy call (`sample_proofs` vs
> `sample_tactics`) and `to_samples` shaping (one whole-proof Sample per
> candidate vs per-node Markovian `(state, tactic)` step Samples sharing a
> `rollout_id`; the trajectory/loss-mask wording here is corrected by v11.14).
> Cost accepted: LeanFoundry now owns Slime API-compat, so this is gated
> on pinning a Slime commit in `[tool.uv.sources]` plus `[training]` compat
> tests (issue #20). Supersedes the §5.4 "keep Slime in the training repo"
> framing below.

> **v11.12 (2026-06-24):** Path-A core is now implemented end to end: schema,
> sorry/admit rejection, render-free runtime extraction, SQLite replay store,
> and driver wire-up. The top-level search result contract remains strict:
> `SearchStatus.PROVED` means the optional rendered whole-proof artifact passed
> final `/exec/verify`; per-node policy/value artifacts may still be emitted
> from structurally solved runtime trees when rendering or verification fails.
> The v0 tree selector is the implemented local root-to-leaf PUCT/hardest-child
> descent; the global highest-UCB/LCB formulation remains reference material,
> not the current contract.

> **v11.11 (2026-06-24):** Contract 7 is updated for the Path-A training data
> baseline. Per-node policy/value data is grounded by accepted `/exec` step
> transitions and a sorry/admit rejection guard, not by whole-proof
> `rendered_lean` verification. Final `/exec/verify` remains required for
> optional whole-proof artifacts and sampled soundness audits. `PolicyExample`
> carries both the Markovian `state` and a prompt-ready `proof_prefix` string;
> whole-tree-to-surface rendering is not a training-data gate. The durable proof
> verification flag is backend-neutral (`verified_by_backend`), not
> kimina-named.

> **v11.10 (2026-06-23):** The `lean-client` lock was refreshed to kimina
> commit `310e6c13`. Kimina's dev server launch defaults now size worker count
> from CPU and available memory, then derive in-flight and queued request caps
> from that worker count. LeanFoundry must still treat `/exec/limits` as the
> runtime truth and avoid duplicating launch-default arithmetic inside search.

> **v11.9 (2026-06-21):** The first operational/extraction/lifecycle slice
> landed. `EnvBackendConfig` forwards lean-client's existing
> `max_overloaded_retries` and `overload_backoff_seconds` knobs; LeanFoundry
> still has no search-loop overload retry. Training extraction now returns an
> explicit `TrainingArtifacts` envelope with proof candidates, policy examples,
> value labels, failures, and diagnostics. That slice initially gated
> proof/policy/proved-value artifacts on final `/exec/verify`; v11.11 supersedes
> the policy/value part with the Path-A per-step data gate. Root-runtime-`OPEN`
> attempts become top-level `EXHAUSTED` and may emit only effort-gated censored
> value labels.
> `SearchAttemptContext` is runner-owned and carries separate
> `search_item_id`/`verify_item_id`; tree search cleans checked search state
> after verification, while cancelled runner tasks cancel and retry cleanup for
> the search item. The proof renderer remains canonical and narrow; richer
> identity-based focusing is still future work.

> **v11.8 (2026-06-21):** The next lifecycle and extraction slices need explicit
> contracts before code changes. Overload retry should be a backend/client config
> pass-through (`max_overloaded_retries`, `overload_backoff_seconds`), not a
> second search-loop retry. Checked cleanup requires `EnvBackend.cleanup(...)`
> and `cancel(...)` to return the concrete lean-client wire models so the runner
> can see `deleted`/`deferred` and cancel statuses. Training extraction should
> return an explicit artifact envelope carrying proof candidates, policy
> examples, value labels, rendering failures, and diagnostics, with theorem,
> attempt, verification, model-version, and effort context. Do not hide those
> artifacts in `ProofTree` or scalar `SearchResult.diagnostics`.

> **v11.7 (2026-06-21):** v0 does not distinguish runtime `OPEN` from runtime
> `EXHAUSTED`, because LeanFoundry has no durable resume path and no deliberately
> finite per-state LM action source. Runtime OR-state statuses remain
> `OPEN | PROVED | DISPROVED`. A root that is still `OPEN` when the configured
> attempt budget stops becomes the top-level `EXHAUSTED`/unproved attempt
> outcome. That outcome may produce effort-gated censored value negatives, but no
> policy positives and no mathematical falsity claim. `DISPROVED` is reserved for
> synthetic negation/inversion or another future semantic falsity certificate.

> **v11.6 (2026-06-21):** The next extraction slice must be training-artifact
> extraction, not merely solved-proof projection. The current
> `extract_proof_tree(...)` is a narrow helper for one proved proof candidate
> before final verification: it does not emit `DISPROVED` labels,
> root-unproved censored negatives, or alternative proved actions. Multiple
> proved actions can exist at one OR state because one expansion sends a tactic
> batch and attaches every executed result before the outer loop can stop on
> `PROVED`. The training extractor must therefore make the policy/value contract
> explicit: verified proved paths produce proof/policy data and value label 1;
> disproved states produce full-weight value label 0 with `disproved=true`;
> root-open-at-stop unproved attempts may produce effort-gated censored value
> label 0. Rendering remains a separate unresolved compiler problem from proof
> tree to Lean text.

> **v11.5 (2026-06-21):** Operational and terminal-state semantics are now fixed
> for the next implementation slice. Mixed `overloaded` plus executed tactic
> statuses for one step item is a backend protocol failure: charge the tactics
> that actually ran, discard partial attachments, and fail the theorem attempt.
> All-overloaded is backpressure, not search evidence. LeanFoundry should wire
> the existing lean-client retry/backoff knobs (`max_overloaded_retries`,
> `overload_backoff_seconds`) through backend config instead of adding a second
> search-loop retry layer. Those retries are outside `max_tactic_calls` and
> outside value-label effort accounting. If all-overloaded is still returned
> after that retry layer is exhausted, the result is an operational error, not
> `EXHAUSTED`. `invalid_state_token` fails immediately in v0; token
> re-derivation/restart waits for durable replay/resume. Runtime OR-states should
> distinguish only structural `OPEN`/`PROVED` from semantic `DISPROVED`; the
> top-level `EXHAUSTED`/unproved outcome is just root `OPEN` at attempt stop.
> Proved states train policy/value only after final verification, disproved
> states are full-weight value negatives, and unproved attempt outcomes are
> effort-gated censored value negatives.

> **v11.4 (2026-06-21):** Runtime tree initialization uses one synthetic root
> OR-state and one synthetic initialization AND-action above the real
> backend-created initial proof states. This is only a tree-shape device so the
> same AND/OR status rule handles one or many initial holes. `ProofTree`
> extraction skips the synthetic layer: each `ProofTree.roots` entry is built
> from a real initial backend state, paired with the proved tactic selected at
> that state.

> **v11.3 (2026-06-21):** The first concrete search-engine loop slice landed:
> direct whole-proof search and AND/OR tree search now sit behind a
> `build_engine(config)` factory. The tree wedge takes a pluggable selection
> strategy and uses product backup for AND-action child values plus max backup
> for OR-state action values; terminal status still comes from the structural
> tree, and final `/exec/verify` remains the acceptance gate. Graph/MCGS,
> negation pruning, HER, real model adapters, and bonded value-label emission
> remain deferred. The first extractor intentionally rejects split actions with
> a multi-goal focused child, rather than emitting a misleading one-bullet Lean
> script; richer group-focus rendering is deferred. Direct whole-proof search
> uses its own `max_direct_candidates` / `direct_candidates_per_round` budget
> fields, separate from tree-search `max_tactic_calls`. Tree-selection
> hyperparameters are explicit config fields: `puct_exploration_weight` and
> `best_first_missing_value_score`.

> **v11.2 (2026-06-19):** v0 search is AND/OR **tree** search, not graph search.
> States reached by different paths are **not merged**, because sound merging
> needs a state-identity fingerprint that captures Lean state the pretty-print
> omits — a hard, unsolved problem — and merging is only an optimization, not a
> correctness requirement. Consequence: `FactorizedProofState` is reduced to the
> minimal tree-search node (open goals + resume token). The merge-identity
> fields (`theorem_header_options_hash`, `tactic_history_hash`,
> `metavariable_coupling_groups`, `local_context_by_component`) are removed, and
> goals are referenced by position rather than a string id. Metavariable
> coupling is read from the backend response at expansion time to decide goal
> bundling, then discarded — not stored. The v0.3 graph-merging canonicalization
> in §3.1 is not pursued unless a validated fingerprint is built. See §3.1.

> **v11.1 (2026-06-17):** Clarifications from an interface walkthrough, folded
> into the gaps and deployment sections (no architectural change):
> - **G2** is a *label-representation* gap (the durable schema cannot encode
>   disproved-vs-censored, so the bit is lost at write time), distinct from the
>   *weight* of a censored negative, which is the tunable in R3.
> - **G3**'s `TacticNode` tree is **not** a second live structure. It is a
>   projection *extracted* from the live AND/OR search graph for one solved
>   slice at data-emission time. Two custom classes are required: the AND/OR
>   search graph (the live engine) and the small `TacticNode` tree (the
>   serialized/rendered proof). See §3.1 and A.5.
> - **G4** only bites the flywheel path: cold-start extracted data (LeanDojo/
>   LeanTree) carries no model-authored inline comments; comments are produced
>   by the policy *during search*, and the gap is "do not strip them at record
>   time." Honoring it now is free.
> - **G5** is gated **per-theorem on provenance** (`TheoremSpec.source`, already
>   present as `theorems.source`): default **off** for known-true targets
>   (leandojo/mathlib/minif2f), turned **on** for autoformalized and speculative-
>   decomposition statements where falseness is plausible. A Lean proof *state*
>   holds a *list* of goals; OR is over candidate actions, AND is over the
>   subgoals one action produces — the single-goal restriction exists because
>   `¬P` is only a clean action when there is one goal. See §3.5.1.
> - **Deployment**: the **Docker image is the prioritized path** (it seals the
>   Lean toolchain + Mathlib build, the real cost). `lean_client.launch_server`
>   only works inside this monorepo and is dev-only; downstream LeanFoundry runs
>   the server out-of-band and connects over HTTP. `connect()` round-trips
>   `GET /exec/limits` (and rejects unbounded caps), which doubles as the
>   connectivity check before any work. See Development Workflow.

> **v11 (2026-06-17):** Adds Part V / Extension D — a controlled training-target
> study run under a frozen theorem-to-round curriculum and matched compute. The
> comparison is whole-proof generation targets (lineage B), search-generated
> step-level targets (lineage A), self-correction/comment enhancements, and mixed
> recipes. This is additive and decoupled: Stages 2-4 of the core training
> pipeline keep their existing dynamic frontier filtering and adaptive exit
> criteria unchanged as the production "how far can we go" recipe. Extension D is
> a separate, smaller-scale study answering whether the heavy search machinery
> earns its keep as a data generator, compared with direct whole-proof generation,
> using its own frozen buckets and arms. See §25-32.

> **v10 (2026-06-09):** §2 reconciled with the shipped `/exec` backend —
> structured `goals` (`GoalInfo`) and `messages` (`ExecMessage`), per-result
> `diagnostics`, the new `/exec/verify` warm-pool certification endpoint
> ("path C"), and the `LEAN_SERVER_MODE=verify|exec` mode split. Throughout
> this document, references to "strict `/verify`" / "Kimina re-verification"
> for *proof* acceptance now mean `/exec/verify` in exec mode; the REPL
> `/verify` is verify-mode-only and used for autoformalized *statement*
> checks (Extension B). The client surface is now the single
> `AsyncLeanExecBackend` façade, and the server always runs as a **separate
> process** (Docker image or `python -m server`) reached over HTTP — never
> launched in-process by the client. Training, search, and roadmap design are
> unchanged from v8/v9.

---

## Project Branding

This project is called **LeanFoundry**.

LeanFoundry is a distributed high-performance Lean proof-search runtime
for search-based theorem-proving agents. It is not a single model,
dataset, or training recipe. Its purpose is to turn Lean into a scalable
execution substrate for training-time search, Expert Iteration, verifier-
guided data generation, and evaluation.

The infrastructure repo is model-agnostic and training-agnostic. Any
policy model, value model, search algorithm, or RL/SFT pipeline should
be able to plug into it through stable interfaces.

> **LeanFoundry is a distributed Lean proof-search runtime: stateless
> tactic execution, high-throughput verification, search orchestration,
> trajectory capture, and evaluation for training theorem-proving agents.**

The training repo is a separate demonstration built on LeanFoundry. It
uses one concrete recipe — currently Qwen3.6-27B + Slime + SGLang +
SFT/Expert Iteration/GRPO — to prove that the infrastructure works.
LeanFoundry should not be tethered to this recipe. The infra repo owns
execution, search, replay, and evaluation. The training repo owns model
choice, optimizer, curriculum, and experiment configuration.

---

## Open Questions and Concerns

This section is the live record of unresolved design decisions, empirical unknowns, and confirmed gaps. Anything here must be resolved or explicitly deferred before the relevant component is considered production-ready.

---

### Resolved Baseline Gaps and Remaining Design Gaps

**G1 — TheoremSpec.initial_lean_block exists (resolved baseline).**
`TheoremSpec.initial_lean_block: str | None` is now part of the in-memory
theorem request and theorem table. When set, tree search initializes from that
Lean block through `/exec/create_states`; when absent, it initializes from the
single theorem statement as before. MCGS graph semantics remain deferred, but
the sorry-initialized input surface is no longer missing.

**G2 — state_value_labels distinguishes disproved from censored negative (resolved baseline).**
`ValueLabel` and `state_value_labels` now carry both `weight` and `disproved`.
A state marked DISPROVED via synthetic negation, inversion, or another
future semantic falsity certificate is definitively
mathematically false — label=0 at full weight. A state searched but not proved
is a censored negative — reduced weight because "not found by this policy" is
not the same as false.

The remaining open question is not representation; it is the downstream
reward-shaping knob for censored negatives (R3).

**G3 — trajectory tactic_sequence stores the solved tree projection (resolved baseline).**
After a `cases` or `constructor` tactic producing multiple subgoals, the proof
is a branching tree. A flat list of `(state, tactic)` pairs cannot represent
this structure and cannot reconstruct Lean's branching syntax. LeanFoundry now
uses a `TacticNode` tree projection for solved proof slices:
```python
@dataclass
class TacticNode:
    state: FactorizedProofState
    tactic: str
    children: list["TacticNode"]  # AND-children after split; single child for linear step
```
Depth-first traversal yields flat `(state, tactic)` pairs for policy SFT. Any
proved subtree is a future HER candidate. `rendered_lean` is optional Path-B
artifact text for final verification, not a Path-A data gate.

This does **not** mean maintaining a second live structure in parallel with the search graph. There are two distinct structures with two distinct lifetimes, and both are custom (no off-the-shelf library provides them):

1. **The live AND/OR runtime tree** — the engine's working structure (OR over a state's candidate actions, AND over the subgoals one action produces). It holds *everything*: dead branches, failed tactics, censored states, visit counts, value estimates, and negation sub-searches. It is not graph-merged in v0 and is not itself training data. This is a substantial custom class — the heart of the Search Engine.

2. **The serialized `TacticNode` tree** — a *projection* extracted from the solved slice of the runtime tree at data-emission time, then written to `trajectories.tactic_sequence`. It is trivially custom (the 3-field dataclass above). A tree, not a graph, because (a) optional rendering to Lean text is inherently tree-shaped (`case inl => … case inr => …`), and (b) proved-node reuse needs a witness subtree — a future merged DAG node would have several parents and no unambiguous single subtree.

Node-general proved-node extraction now emits step-level Path-A policy/value
rows directly from proved runtime work. The remaining rendering work is the
optional Path-B artifact stream; the baseline durable representation is no
longer a flat list and whole-proof rendering is not a data gate.

**G4 — Inline comments are preserved when the model emits them.**
Aristotle's policy generates (hidden CoT) + (inline comment) + (tactic).
Inline comments can persist in the action history and serve as external
persistent memory — future policy calls may see earlier reasoning context
embedded in the proof prefix. LeanFoundry records the full tactic/action text
the model produced, comments included, and exposes `PolicyContext.proof_prefix`
for inference-time prompt construction. Whether a downstream recipe asks the
model to emit comments is a training-repo/model-hook choice, not a separate
core data target.

Scope note: comments do not exist in cold-start extracted data (LeanDojo/LeanTree proofs are human/extracted and carry no model-authored CoT comments), so G4 has no effect on Stage 1 SFT from those sources. Comments are produced by *our own policy* during search, only once it is prompted Aristotle-style to emit them; G4 is therefore a constraint on the *trajectory-recording* path of the flywheel (Stages 2+): record the model's full output verbatim so comments survive into the next round's SFT. Honoring it costs nothing now and is inert until commented generation is enabled (whether the base model emits useful comments at cold-start is a separate recipe question, adjacent to R5).

**G5 — Conservative negation pruning has a current baseline.**
For each eligible single-goal state `⊢ P`, `try_negation=True` may add a
synthetic action to prove `¬P` in the same local context. The current
implementation is provenance-gated, persistent, and searched by the normal
AND/OR tree: the synthetic action owns the negated-theorem proof state as a
child subtree, failed tactics leave it open for later selection, repeated
policy outputs fail closed, and a completed negation proof marks the source
state `DISPROVED`. Successful negation emits full-weight value negatives for
the original state; tactics inside the negation proof train the synthetic
negation goal, not the original false goal. Durable `NegationAttempt` artifacts
record the rendered theorem, tactic attempts, statuses, and charged tactic
calls.

Semantics, to avoid two common confusions:
- A Lean proof *state* holds a **list** of goals, not one (wire type `goals: list[GoalInfo]`). After `constructor` on `A ∧ B`, one state carries `⊢ A` and `⊢ B`. Whether to split a multi-goal state into separate nodes is a *search-engine* decision (the AND-split), and per the LeanTree lesson (§3.1) metavariable-coupled goals are **not** split — so multi-goal nodes do occur. The synthetic action is restricted to single-goal states because `¬P` is only a clean single action when there is exactly one goal `P`.
- The negation is an extra entry in the state's **OR** action pool (a state is proved if *any* action proves it). A tactic never produces "OR goals": the subgoals one tactic produces are conjunctive (**AND** — all must close). OR is over *which action you choose*; AND is over *the subgoals an action spawns*.

Provenance gating (per-theorem, not global): `try_negation` defaults
**False** and, when enabled in config, is further gated by
`TheoremSpec.source` (carried from the existing `theorems.source` column — see
§4.2):
- **Off** for known-true targets (`leandojo`, `mathlib`, `minif2f`): every subgoal of a true theorem is itself true, so trying to disprove subgoals mostly wastes budget (and `¬P` is a *full sub-search*, retried under UCB, not one cheap step).
- **On** for `autoformalized` statements and speculative subgoal-decomposition lemmas: these can be genuinely false, and negation is how search auto-rejects wrong statements / bad decompositions. This is central to the Extension B autoformalization flywheel — but it is a *pruning* accelerator; the flywheel's engine remains HER + pass-rate bucketing.

No new persisted column is required — the provenance label already exists in
the data spine and reaches the in-memory `TheoremSpec`. See R4 for the
cost/benefit unknown that keeps this off by default for known-true LeanDojo
core runs, and §3.5.1 for the mechanism.

---

### Needs Research (Empirical Unknowns)

**R1 — Request-level dispatcher / two-level batching design.**
Two parallelism levels exist: proof-search level (many theorem/proof-graph searches running simultaneously) and tactic-candidate level (N tactics sampled for one selected proof state). The current backend decision is that the **scheduler unit is the proof-state expansion request**, not an individual tactic. One expansion request contains `state_token + tactics[]` and leases exactly one Lean worker; that worker loads the state once and applies the tactic candidates internally. Many expansion requests from many proof graphs are then batched into one Env Backend `/exec/step_batch` request, matching Kimina's existing "one HTTP request contains many independent items" design. This avoids the bad behavior where 16 tactic candidates from one state become 16 manager jobs and cause the Kimina pool to cold-start 16 identical compatible workers.

Within one theorem, tree-search iterations remain strictly sequential —
iteration N's selection depends on backpropagation from iteration N-1. Across
theorem/proof-graph searches, expansion requests are independent and can be
batched. The concrete v0 client boundary is the `lean-client` package:
LeanFoundry's EnvBackend adapter uses the single `AsyncLeanExecBackend` façade
(which owns the HTTP client, the proof-state env, and the step batcher, sized
from `/exec/limits`), so request width and in-flight count come from the
backend's `/exec/limits` response. Remaining empirical questions are the
EnvClient microbatch window, max items per HTTP request, queue-depth
backpressure, and worker-pool sizing. These are v0 profiling parameters, not
open semantic design questions.

**R2 — Step-level HER yield and optional whole-proof HER verification gap.**
For LeanFoundry's primary lineage-A data path, HER means proved-node reuse:
every proved runtime state can emit local `(state, tactic)` positives and value
labels without rendering a standalone Lean proof. The empirical unknown is how
many additional proved nodes appear beyond the root witness path once
node-general extraction is implemented. Separately, optional lineage-B HER
artifacts may try to render proved subtrees as standalone proofs; those still
need `/exec/verify`, and their candidate/verified gap remains a diagnostic for
the optional whole-proof artifact path, not a gate for step-level training.

**R3 — Value function censored-negative weight.**
The current design uses weight=0.25 for censored negatives. This is a guess. If too high, the value function becomes overly pessimistic and the policy stops exploring hard states. If too low, value is uncalibrated for failing states. Requires ablation once Stage 3 search-based EI is running.

**R4 — Whether negation pruning should be enabled at LeanDojo scale.**
Negation pruning pays off when a significant fraction of budget is wasted on
provably-false subgoals. The mechanism exists, but at LeanDojo difficulty the
benefit/risk ratio is unknown. Keep it provenance-gated and off by default for
known-true sources until search traces show how often goals are genuinely
disprovable and how much budget the synthetic sub-search consumes.

**R5 — Dynamic CoT budget training with Qwen3.6's thinking mode.**
Aristotle trains CoT budget implicitly by only training on thinking traces that preceded successful actions. Qwen3.6-27B has native `<think>...</think>` tokens. Whether to enable thinking for tactic prediction (currently disabled by default), and how to train dynamic budget without dedicated trace infrastructure, is unresolved. Empirical ablation recommended: SFT with thinking enabled vs disabled for Format 2; measure tactic accuracy and proof discovery rate.

---

### Open Algorithmic Questions

**A1 — State canonicalization for MCGS graph merging (v0.3 gate).**
Graph merging requires a canonical identity for proof states that correctly handles metavariable coupling and global-state tactics like `aesop` and `simp_all`, which cannot be safely deduplicated. The exact canonicalization is unsolved. The gate — merging disabled until a correctness acceptance test passes — is the right response. Whether the gate can realistically be passed without excluding common Mathlib tactics is unknown.

**A2 — LeanTree version compatibility with our env_profile.**
LeanTree is built on Lean 4.19.0. Our current backend prototype pins to Lean 4.29.1 to match Pantograph. Whether LeanTree traces replay correctly under our env_profile is unknown and must be verified empirically before any LeanTree data enters training. Track A integration (dataset warm-start) in the training repo is blocked on this check.

---

### Semantic Faithfulness (Extension B Specific)

**S1 — REPL /verify is a syntactic check only.**
Autoformalized statements that pass Kimina `/verify` (with `:= by sorry`) are confirmed to typecheck — not to mean the same thing as the NL source. Known failure modes: vacuous hypothesis addition, quantifier inversion (∃∀ vs ∀∃), convention inversion, missing conjuncts, definitional mismatch. The semantic judge LLM provides a probabilistic filter but not a guarantee. Semantic faithfulness is undecidable in general. Extension B output requires human spot-checking before entering held-out eval sets.

**S2 — Formalizer + checker co-training convergence is unproven.**
The mid-term Extension B design proposes training formalizer and faithfulness checker together. Whether this loop converges is unknown. Do not invest engineering effort in it until the baseline pipeline (LLM draft → /verify → judge → staging) is producing reliable output.

---

## System Landscape

LeanFoundry's position relative to existing systems:

| System | What it is | Open? | Relation to LeanFoundry |
|---|---|---|---|
| AlphaProof (DeepMind) | Closed AlphaZero-style RL prover interacting with Lean; Nature paper reports 2024 IMO silver-medal-level performance. | no | Strong closed precedent for verifier-grounded RL; not reusable infra. |
| Aristotle (Harmonic) | Closed IMO-gold-level system with Lean proof search, informal lemma generation/formalization, geometry solver, MCGS, EI, HER, value labels, TTT, and large-scale stateless REPL infrastructure. | no | Closest north star. LeanFoundry is the open infrastructure analogue at smaller scale. |
| HyperTree Proof Search (HTPS) | Neural theorem-proving algorithm using policy/value guidance, online proof search, and training from successful search traces. | paper/code | Direct prior for search-generated step data and value-guided tree search; confirms that state-tactic training data is prior art, not LeanFoundry's novelty. |
| BFS-Prover-V2 (ByteDance Seed) | Open step-level Lean 4 prover system with multi-stage Expert Iteration, adaptive tactic filtering, periodic retraining, and planner-enhanced multi-agent tree search at inference. | model/code | Important open prover/search baseline; not a reusable Kimina/Harmonic-style stateless execution/search/replay/eval framework. |
| BFS-Prover V1 | Best-first tree-search prover with self-filtering EI and DPO from compiler feedback. | model/code | Strong algorithmic baseline for best-first search; not infrastructure-first. |
| DeepSeek-Prover-V1.5 | Lean-feedback RL plus RMaxTS-style search. | partial | Search/RL prior; not reusable execution runtime. |
| DeepSeek-Prover-V2 | Recursive subgoal decomposition and proof synthesis; open models/data. | model/data | Strong teacher/baseline; not tactic-level stateless training runtime. |
| Goedel-Prover-V2 | Whole-proof/self-correction/scaffolded data synthesis with EI/RL-style recipes and released models/code/data. | model/code/data | Strong teacher/baseline; not MCGS/stateless tactic runtime infra. |
| Kimina Lean Server | High-performance Lean verifier/server with REPL worker pool, header/body split, LRU header reuse, batch verification, and feedback extraction. | yes | Best execution substrate to fork; LeanFoundry adds tactic stepping, search, replay, EI, and eval. |
| Kimina-Prover / Kimina-Prover-RL | Whole-proof RL/formal reasoning recipe using Kimina Lean Server; public materials explicitly emphasize strong results without MCTS/value/process rewards. | model/recipe | Useful baseline and infra dependency; not training-time MCGS runtime. |
| LeanDojo / LeanDojo-v2 | Data extraction, theorem/proof-state tracing, gym/tooling, training/eval/deployment framework for Lean provers. | yes | Upstream data/tooling foundation; LeanFoundry is the high-throughput search execution and replay layer. |
| LeanTree | White-box Lean 4 proof-state factorization and dataset for intermediate states. | yes | Relevant state representation prior; not full search-training runtime. |
| nanoproof | Minimal open AlphaProof/HyperTree Proof Search-style implementation using LeanTree server, MCTS prover, and distributed RL loop. | yes | Closest open experimental prior; still not a production-grade stateless Kimina/Harmonic-style infra framework. |
| OProver | 2026 Lean 4 whole-proof/agentic framework with repair trajectories, retrieval memory, and iterative post-training over public Lean resources. | paper | Strong open whole-proof/repair baseline; reinforces that agentic repair data is a training-recipe baseline, not a LeanFoundry core-search novelty. |
| Pythagoras-Prover | 2026 compute-efficient open Lean prover family spanning autoregressive and diffusion-style proof generation plus augmented formalization data. | paper | Strong recent whole-proof/proof-generation baseline; not a stateless search/replay/eval infrastructure framework. |
| InternLM-StepProver / MPS-Prover / StepFun-Prover / Leanabell | Stepwise/tool-integrated prover systems using critics, search, verifier feedback, or RL. | mixed | Important baselines; generally model/prover pipelines rather than model-agnostic runtime infrastructure. |
| Seed-Prover 1.5 / Delta-Prover | High-performing ByteDance formal proving systems with large-scale agentic RL and test-time scaling. | proofs/project | Latest competitive reference; not open reusable infra. |
| Lean Copilot / Prover-Agent / Ax-Prover | Lean-native or agentic proof-assistant workflows using LLMs, Lean feedback, or auxiliary lemmas. | mixed | Adjacent human/agent tooling; not LeanFoundry-equivalent training-time search infrastructure. |
| **LeanFoundry** | Open distributed Lean proof-search runtime: stateless tactic execution, batch verification, search orchestration, trajectory capture, HER/value labels, replay storage, and solved@budget evals. | **yes** | Infrastructure layer, not a single prover checkpoint or one-off training recipe. |

The key gap is not "open Lean provers." Many open Lean provers now exist.
The key gap is **open, reusable infrastructure for training-time search**:
a model-agnostic runtime that exposes stateless Lean tactic execution,
high-throughput verification, MCGS/AND-OR search orchestration, trajectory
capture, HER extraction, value labels, replay storage, and reproducible
solved@budget evaluation.

The step-level data shape itself is not the novelty. HTPS, LeanDojo/ReProver,
BFS-Prover-style systems, and related step provers already train from
proof-state/tactic interactions or search traces. LeanFoundry's novelty target
is infrastructure and experimental control: one runtime can generate lineage-A
step rows, lineage-B whole-proof rows, self-correction rows, value labels, and
crossed eval artifacts under the same backend, curriculum, env profile, and
budget accounting.

Existing open systems cover important pieces of this stack, but sit at different
layers. LeanDojo is data + gym; Kimina is verifier/server infrastructure;
BFS-Prover-V2, Goedel-Prover-V2, DeepSeek-Prover-V2, Kimina-Prover,
StepFun-Prover, Leanabell, InternLM-StepProver, MPS-Prover, Seed-Prover,
DAP-style agents, Prover-Agent, OProver, Pythagoras-Prover, Delta-Prover, and
Ax-Prover are prover systems, models, or training recipes. Harmonic's Aristotle
appears closest architecturally, but the high-performance search/runtime
infrastructure is closed. LeanFoundry's contribution is the open infrastructure
layer that lets different policies, value models, search algorithms, and
training recipes plug into a common Lean proof-search substrate.

Source freshness note, 2026-06-30: this landscape was refreshed against
primary arXiv/project pages for the named core systems. It remains background
context, not a code contract. Re-run the source refresh before public release,
benchmark claims, or citation-heavy writing.

LeanDojo remains an upstream data/tooling dependency. LeanFoundry uses
LeanDojo data and forks Kimina as the execution backend; the search engine,
trajectory capture, replay store, training-time EI integration, and solved@budget
eval framework are the net-new open infrastructure.

---

## Extensions and Roadmap

This document describes one fully designed core system and four explicitly
scoped extensions. Understanding the boundaries between them is important
for planning implementation work.

### Core System (Part I + Part II)

Single-machine infrastructure and training pipeline using LeanDojo data.
Build and validate this end-to-end before activating any extension.
All components are specified to implementation level.

### Extension A: Multi-Machine Scale-Out (Part III)
> **Status: Designed, implementation deferred until single-machine system
> is stable and producing results on LeanDojo novel_premises split.**

Reproduces Harmonic's distributed REPL infrastructure ("Running Lean at
Scale", Sep 2025). Key new component: a custom C++ REPL router providing
per-message routing, global request queueing, and autoscaling. No
algorithmic changes required — only infrastructure configuration changes.

Trigger: single-machine throughput (proof attempts per hour) is the
bottleneck, not model capability.

### Extension B: Autoformalization Data Pipeline (Part IV)
> **Status: Architecture outlined, implementation PENDING RESEARCH.
> Do not build until the core system has been trained to satisfactory
> performance on the full LeanDojo dataset.**

Converts informal mathematical statements into verified Lean 4 statements,
expanding the theorem pool beyond LeanDojo's fixed 98k theorems. Key
design decisions depend on empirical results from training runs.

Trigger: model has plateaued on LeanDojo novel_premises split, and data
diversity (not compute) is the limiting factor.

### Extension C: Test-Time Training Module (Part V, §21-24)
> **Status: Off-main snapshot / future work after the 2026-07-01 split.
> Concrete trainer, selected per-problem search source, and any mainline TTT
> contract remain future work.**

Per-problem LoRA fine-tuning on search traces found during inference,
for olympiad-level targets with no other training signal. Evaluation-time
only; does not replace or modify Stages 1-4.

### Extension D: Controlled Algorithm Ablation Study (Part V, §25-32)
> **Status: Design sketch. Run after Stage 1 checkpoint and a hygiene-
> passed curated pool exist. Does not modify Stages 2-4.**

Holds base checkpoint, theorem-to-round curriculum, and total compute
fixed, and varies the training target/recipe: whole-proof lineage B,
search-generated step-policy lineage A, self-correction/comment enhancements,
and mixed training. This answers whether search is worth its training-time cost
as a step-data generator — a question the production pipeline's adaptive,
dynamically-filtered recipe (Stages 2-4) is not designed to answer, since its
frontier and exit criteria move with the live policy rather than staying fixed
across arms.

Trigger: Stage 1 cold-start checkpoint exists and is stable; runs
alongside, not instead of, the core pipeline's own Stage 2-4 progression.

---

## System Architecture

LeanFoundry decomposes into five modules. The network topology between them
is a first-class design concern because proof search is throughput-bound:
latency on any link between Search Engine and Env Backend directly limits
proofs-per-hour.

### Single machine

```
┌────────────────────────────────────────────────────────────────────┐
│                    Single Machine  (8 × H100)                      │
│                                                                    │
│  ┌─────────────────────┐   weight sync    ┌───────────────────┐   │
│  │      Trainer        │◄────────────────►│ Inference Engine  │   │
│  │     (Megatron)      │   NVLink / NCCL  │    (SGLang)       │   │
│  │ profiled update GPUs │                  │ profiled rollout  │   │
│  └──────────┬──────────┘                  └────────┬──────────┘   │
│             │ read samples                          │              │
│             │ (local socket)                        │ HTTP         │
│             ▼                                       │ sample_tactics()
│  ┌─────────────────────┐   write A-type  ┌──────────▼──────────┐  │
│  │    Data Buffer      │◄────────────────│   Search Engine     │  │
│  │     (SQLite)        │   read B-type   │  direct / tree /    │  │
│  │                     │────────────────►│  self-correct       │  │
│  └─────────────────────┘                 └──────────┬──────────┘  │
│                                                      │             │
│  ┌─────────────────────┐          HTTP  /exec/step_batch          │
│  │     Evaluation      │◄─────────────────────────── │            │
│  │  solved@budget      │                              ▼            │
│  │  pass@k / curves    │                  ┌───────────────────┐   │
│  └─────────────────────┘                  │   Env Backend     │   │
│                                           │ Kimina/Pantograph │   │
│                                           │ profiled workers  │   │
│                                           └───────────────────┘   │
│                                                                    │
│  * GPU and worker allocation are profiled alternatives — see Phase -1            │
└────────────────────────────────────────────────────────────────────┘
```

### Cluster (Extension A)

```
  Training Nodes                      Inference Nodes
  ┌───────────────────────┐           ┌───────────────────────┐
  │  Trainer (Megatron)   │◄─────────►│  Inference Engine     │
  │  multi-GPU, NCCL/IB   │ weight    │  SGLang cluster       │
  │                       │ sync TCP  │  Slime-managed        │
  └───────────┬───────────┘           └───────────┬───────────┘
              │ TCP                               │ HTTP
              ▼                                   │ sample_tactics()
  ┌───────────────────────┐   write   ┌───────────▼───────────┐
  │    Data Buffer        │◄──────────│   Search Engine       │
  │  PostgreSQL /         │   read    │   CPU nodes           │
  │  Redis Streams        │──────────►│   search orchestration│
  └───────────────────────┘           └───────────┬───────────┘
                                                  │ TCP
                                                  ▼
                                      ┌───────────────────────┐
                                      │   Env Backend         │
                                      │  Kimina/Pantograph    │
                                      │  + C++ REPL Router    │
                                      │  CPU-only preemptible │
                                      └───────────────────────┘

  ┌──────────────────────────────────────────────────┐
  │  Evaluation  (separate; reads from Data Buffer)  │
  └──────────────────────────────────────────────────┘
```

Network links and their throughput relevance:

```
Search Engine ↔ Env Backend      /exec/step_batch over HTTP/TCP
  Critical path. Every proof-state expansion in MCGS traverses this link.
  Latency p95 directly bounds proofs-per-hour.
  Single machine: localhost, ~0.1ms.
  Cluster: TCP to REPL router, target <5ms p95.

Search Engine ↔ Inference Engine  PolicyClient over HTTP
  Called once per MCGS node expansion (sample N tactics).
  Batching amortizes cost. Less latency-sensitive than Env Backend link.

Trainer ↔ Inference Engine        weight sync via NVLink/NCCL
  Triggered after each training update.
  Must complete before next search round starts (in concurrent mode).
  Single machine: NVLink, fast. Cluster: TCP, can be pipelined.

Search Engine ↔ Data Buffer       write A-type, read B-type
  Write path: after each proof found (low frequency).
  Read path: theorem batch fetch at round start (low frequency).
  Not on the critical latency path.
```

---

## Design Principles

From a systems RL engineering perspective, the following principles govern
every design decision in LeanFoundry. They are listed here so that future
contributors can evaluate trade-offs against a consistent set of values.

**P1 — Decouple rollout from optimization.**
Data generation (search, rollout) and gradient updates have different
resource profiles (CPU + Lean env vs GPU) and different failure modes.
Mixing them in one process means one failure drags down the other. Separate
processes allow independent scaling and independent restart.

**P2 — Stateless workers.**
Any process executing tactics, serving inference, or processing data must
carry its state in the request or in a backend-owned state token, not in the
process. In the single-node Env Backend, `state_token` resolves to a local
tmp/shared Pantograph state file; no public API exposes process-local
Pantograph `state_id`. Worker death loses no search state. This is the
prerequisite for preemptibility and horizontal scaling.

**P3 — Durable data spine.**
The Data Buffer is the durable archive for theorem inputs, verified proof
artifacts, trajectories, policy/value rows, lifecycle outbox records,
extraction failures, and negation attempts. In the current single-machine
baseline this is WAL-mode SQLite plus manifest-backed eval files; Slime owns
the online training buffer. Future cluster training may promote the same
contracts to PostgreSQL or a queue-backed service, but in-memory queues are not
the source of truth for replayable LeanFoundry artifacts.

**P4 — Algorithm-agnostic interfaces.**
`/exec/step_batch` does not know whether MCGS or beam search is calling
it. `PolicyClient` does not know which search algorithm is using it.
The Slime adapter converts framework-neutral rows into trainer samples without
changing the search engines. Each interface expresses only its minimum
contract. Components can be swapped without modifying their callers.

**P5 — Critical path latency is a first-class metric.**
The Search Engine ↔ Env Backend link is on the critical path of every
node expansion. Its p95 latency directly bounds proofs-per-hour. This is
not an afterthought — it drives protocol choice (HTTP vs gRPC vs shared
memory), worker count, and NUMA affinity configuration.

**P6 — Training stability over throughput.**
Reward hacking, distribution collapse, and data contamination are more
dangerous than slow throughput. `env_profile` enforcement, axiom
validation, and curriculum controls are non-negotiable correctness
guarantees. Specific algorithmic mechanisms (regularization terms,
constraint strengths) are determined empirically, not prescribed here.

**P7 — Profile before committing.**
Phase -1 exists because memory pressure, GPU allocation, and sequence
length interact in ways that cannot be predicted analytically. No
training begins without a completed `resource_profile_manifest.json`.
Commitments made before profiling are hypotheses, not decisions.

**P8 — The data flywheel compounds.**
Every design decision should ask: does this accelerate the flywheel or
cap it? Better model → better search prior → more proofs discovered →
better training data → better model. HER is a flywheel accelerator
(10–50× data at zero Lean cost). Pass-rate bucketing ensures each EI
round trains at the capability frontier. Autoformalization prevents the
flywheel from stalling when LeanDojo signal is exhausted.

**P9 — Explicit complexity escalation.**
Extensions A, B, C are future/off-main work with
explicit trigger conditions:
- Extension A (cluster scale-out): single-machine search throughput is
  the measured bottleneck
- Extension B (autoformalization scale): model plateaus on LeanDojo
  novel_premises split
- Extension C (test-time training): core pipeline is stable
Complexity before the trigger condition is premature and pollutes the
design with requirements that don't exist yet.

**P10 — Preemptibility is a correctness property, not a performance
optimization.**
The design target is that long-running components can be killed without losing
accepted durable artifacts or leaking backend state. The current baseline
supports idempotent replay writes, cleanup/cancel outbox persistence, and
reconciliation hooks; it does not yet checkpoint an in-flight search tree for
exact resume. Future graph/MCGS, cluster scale-out, and training orchestration
must add explicit checkpoint/resume and atomic weight-sync semantics rather
than assuming process lifetime.

---

# Part I: Reusable Infrastructure

---

## 1. Environment Profiles

Every Lean execution is tied to a specific environment profile. This is
not optional bookkeeping — mixing data across Mathlib versions silently
corrupts training data because tactics that work on one commit may fail
on another.

An environment profile is:

```python
@dataclass
class EnvProfile:
    lean_version: str          # e.g. "4.29.1"
    mathlib_commit: str        # full git SHA
    imports: list[str]         # e.g. ["Mathlib", "Aesop"]
    header: str                # full import header string
    header_hash: str           # sha256 of header (used for LRU keying)
    loogle_index_path: str     # version-pinned, built from same commit
    premise_index_path: str    # version-pinned
```

Rules:
- Every A-type training sample must have a verified env_profile field
- Env Backend scheduler uses header_hash for LRU routing
- Never mix env_profiles in a single training batch
- When consuming external data (Goedel, DeepSeek proofs), re-verify
  under our own env_profile before adding to training set

Default env_profile for the current backend prototype: Lean 4.29.1 +
Mathlib at commit `5e932f97dd25535344f80f9dd8da3aab83df0fe6`, chosen to
match the tested Pantograph version. All data generation uses one pinned
profile. Update only between major training phases.

---

## 2. Kimina `/exec` Env Backend

### 2.1 What Kimina Already Has

Kimina Lean Server (project-numina/kimina-lean-server) provides:
- A pool of pre-started REPL worker processes
- Routing of requests to idle workers
- LRU cache keyed by import header: workers pre-loaded with Mathlib
  are reused across requests with the same header, avoiding repeated
  ~60s Mathlib import overhead
- Whole-proof batch verification endpoint (/verify) — REPL/verify-mode only
- Infotree extraction (tactic state annotations) — REPL/verify-mode only

This is the infrastructure we build on. We do NOT build a separate
LeanStepServer. The Env Backend adds `/exec` proof-state stepping,
verification, cleanup, and cancellation while keeping the server-owned
scheduler/worker lifecycle.

### 2.2 Current Backend Decision: Kimina Pool + Pantograph Worker

The v0 Env Backend is a fork/adaptation of Kimina Lean Server, but the
tactic-level worker is Pantograph. Kimina contributes the service shell:
FastAPI endpoints, batch request handling, a capped free/busy worker pool,
exact-header reuse, idle LRU eviction, timeouts, diagnostics, and `/verify`.
Pantograph contributes the proof-state operations Kimina's REPL interface
does not currently expose: `goal_start`, `load_sorry`, `goal_tactic`,
`goal_save`, and `goal_load`.

The key design correction is the scheduler unit:

```text
one proof-state expansion item = one worker lease
one expansion item = state_token + tactics[]
one worker loads the state once and tries all tactics internally
```

Do **not** flatten the `tactics[]` list into manager-level jobs. Kimina's
manager only reuses free exact-header workers. If tactic candidates were
submitted independently, the first tactic would take the only compatible free
worker, and the second tactic would see no free match and cold-start another
identical compatible worker until `max_repls` is reached. That is correct for
independent `/check` code-check items, but wrong for one proof-state expansion.

The implementation boundary is intentionally narrower than the server internals:
LeanFoundry depends on the `lean-client` Python package and talks to a running
server over HTTP. It does not import `server.settings`, `server.main`,
`PantographManager`, or backend worker classes. The only place that may mention
Kimina by name inside LeanFoundry is a small EnvBackend adapter/launcher module;
the SearchEngine sees an `EnvBackend` interface, not a concrete server.

### 2.2.1 Server Mode: verify | exec

The server boots in exactly one mode, selected by `LEAN_SERVER_MODE` (default
`exec`). A search/RL deployment runs **exec mode**: it constructs only the
Pantograph worker pool + state store and mounts `/exec/*` (including
`/exec/verify`) + `/health`; the legacy REPL routes (`/api/check`, `/verify`)
are not mounted. A batch-verification deployment runs **verify mode**: the Lean
REPL pool + `/api/check` + `/verify`, with no Pantograph pool. One process never
constructs both stacks. Search-path proof acceptance therefore uses
`/exec/verify` (§2.7), not the REPL `/verify`. In all cases the server runs as a
**separate process** — its Docker image or `python -m server` from a checkout —
reached over HTTP; the client (§3) never launches it in-process.

### 2.3 State Representation: Opaque Token, Local Tmp File Backing

For the single-node system, the public protocol carries an opaque
`state_token`, not a serialized blob and not a raw filesystem path. The backend
owns a local state store:

```text
state_token -> /dev/shm/leanfoundry-state/<env>/<hash>.state
```

The backing file is Pantograph's serialized goal state, produced by
`goal_save` and restored by `goal_load`. The token metadata records:

```python
@dataclass
class StateRecord:
    token: str
    path: str
    env_profile: str
    header_hash: str
    lean_version: str
    mathlib_commit: str
    imports: list[str]
    raw_bytes: int
    created_at: float
    last_accessed_at: float
    ttl_seconds: int
```

Why token-over-blob for v0:
- Single-node workers can all read the same local file path.
- We avoid sending and writing the same state bytes repeatedly.
- The API remains portable: later multi-node mode can resolve the same token
  through a content-addressed object store or shared filesystem.

The backend may expose debug/export endpoints for blob materialization, but
normal proof search uses `state_token`.

### 2.4 Request Semantics: Batch Across States, Not Across Tactics

`/exec/step_batch` is batch-first like Kimina `/check`, but the batch item is
a proof-state expansion request rather than an independent whole-code check.

```text
HTTP request
  item 0 -> one worker -> load S0 once -> try 16 tactics -> return children
  item 1 -> one worker -> load S1 once -> try 16 tactics -> return children
  ...
```

This provides parallelism across proof graphs / selected frontier states while
keeping all tactic candidates for one state inside one worker lease.

### 2.5 Worker Procedure

For each expansion item:

```python
async def step_item(worker: PantographWorker, item: StepItem) -> StepItemResult:
    base = worker.goal_load(state_store.path(item.state_token))
    results = []
    for tactic in item.tactics:
        try:
            child = worker.goal_tactic(base, tactic)
            child_token = state_store.save(worker, child)
            results.append(StepResult(
                tactic=tactic,
                status="complete" if child.is_solved else "open",
                state_token=child_token,
                goals=child.goals,    # structured GoalInfo objects, not strings
            ))
        except TacticFailure as err:
            results.append(StepResult(tactic=tactic, status="error", messages=err.messages))
    return StepItemResult(node_id=item.node_id, results=results)
```

The worker must delete temporary in-process goal states after each item to keep
Lean memory stable. A `complete` status here means the tactic closed the goals
in the interactive session; final reward-grade acceptance still requires
`/exec/verify` (full standalone compile + `#print axioms`), which rejects
`sorry`/`sorryAx` and disallowed axioms (§2.7).

### 2.6 Scheduler Policy

The scheduler is Kimina-shaped:

```text
Priority order for worker selection:
  1. free worker with matching env_profile + header_hash
  2. if total workers < max_repls: create/prep a new worker
  3. if pool full and some worker is free: evict oldest free worker
  4. if all workers busy: wait until release or timeout
```

Rules:
- One expansion item leases one worker.
- Never split `tactics[]` into separate manager jobs.
- Never cold-start workers on the request critical path solely to fan out one
  item's tactics.
- Prewarm duplicate compatible workers only by configuration or background
  policy, not as a hidden side effect of one tactic batch.
- Worker count is memory-budgeted and empirically profiled. Kimina's dev
  launcher now uses CPU plus available-memory defaults, but production
  LeanFoundry runs should still profile and override these values explicitly
  when needed.

Kimina config knobs that become first-class training config:

```yaml
env_backend:
  # The server's own launch settings (env vars / CLI flags) used when you run
  # its Docker image or `python -m server`. The client connects over HTTP; it
  # does not launch the server in-process.
  workers: ${profiled_worker_pool_size}
  max_lean_processes_per_env_profile: ${profiled_worker_pool_size}
  recommended_items_per_step_batch: ${profiled_worker_pool_size}
  recommended_in_flight_step_batches: 8
  # May be omitted for the server default:
  # max_in_flight_exec_requests = min(workers, 8)
  # max_queued_exec_requests = min(max_in_flight_exec_requests * 4, 32)
  max_in_flight_exec_requests: ${profiled_or_server_default}
  max_queued_exec_requests: ${profiled_or_server_default}
  max_state_store_bytes: 17179869184
  state_store_dir: "/dev/shm/leanfoundry-state"
  single_process: true
  state_ttl_seconds: 3600
  pantograph_project_dir: "/workspace/mathlib4"
  pantograph_imports: ["Mathlib"]
```

The launch config is app-level configuration. Search code should discover
request-shaping values from `/exec/limits`; it should not duplicate these
defaults in the SearchEngine.

### 2.7 Batch API

All endpoints are batch-first. Single-item batches are valid.

The execution API is search-algorithm-agnostic. The search algorithm
(MCGS, beam search, direct sampling, etc.) lives entirely in the Search
Engine / rollout. Env Backend executes tactic steps and verifies proofs; it
knows nothing about search structure beyond opaque `node_id` correlation.

**GET /exec/limits**

Advertises enforced caps and client recommendations. LeanFoundry should call
this through `AsyncLeanExecBatcher.from_server_limits(env)` instead of hardcoding
request width or in-flight count. The client refuses unbounded safety caps.
Concrete values are server-returned; an 8-worker launch can look like:

```json
{
  "max_pantograph_workers": 8,
  "max_lean_processes_per_env_profile": 8,
  "max_items_per_step_batch": 1024,
  "max_tactics_per_step_item": 64,
  "max_attempts_per_step_batch": 8192,
  "max_create_items_per_request": 1024,
  "max_in_flight_exec_requests": 8,
  "max_queued_exec_requests": 32,
  "max_state_store_bytes": 17179869184,
  "max_acquire_timeout_ms": 600000,
  "max_step_timeout_ms": 600000,
  "recommended_items_per_step_batch": 8,
  "recommended_in_flight_step_batches": 8,
  "single_process": true,
  "cleanup_policy": "defer_while_in_flight"
}
```

**POST /exec/create_states**

Initializes Pantograph states from Lean code containing one or more sorry goals.

```json
{
  "env_profile": "lean4.29.1_mathlib_5e932f97",
  "items": [
    {
      "item_id": "thm_001:attempt_0",
      "code": "import Mathlib\n\ntheorem t (n : Nat) : n + 0 = n := by\n  sorry",
      "acquire_timeout_ms": 5000,
      "step_timeout_ms": 5000,
      "debug": false
    }
  ]
}
```

Response:

```json
{
  "items": [
    {
      "item_id": "thm_001:attempt_0",
      "status": "open",
      "states": [
        {
          "state_token": "st_root...",
          "goals": [
            {
              "target": "n + 0 = n",
              "pretty": "n : Nat\n⊢ n + 0 = n",
              "hypotheses": [{"type": "Nat", "name": "n", "value": null}],
              "name": null,
              "sibling_dep": []
            }
          ]
        }
      ],
      "messages": [],
      "diagnostics": {"acquire_ms": 12.0, "lean_ms": 340.0}
    }
  ]
}
```

**POST /exec/step_batch**

Request:
```json
{
  "items": [
    {
      "node_id": "graph7:n123",
      "state_token": "st_root...",
      "tactics": ["simp", "rw [Nat.add_comm]", "nlinarith"],
      "acquire_timeout_ms": 5000,
      "step_timeout_ms": 5000
    }
  ]
}
```

Response:
```json
{
  "items": [
    {
      "node_id": "graph7:n123",
      "results": [
        {
          "tactic": "simp",
          "status": "complete",
          "state_token": null,
          "goals": [],
          "messages": []
        },
        {
          "tactic": "rw [Nat.add_comm]",
          "status": "open",
          "state_token": "st_child...",
          "goals": [
            {
              "target": "0 + n = n",
              "pretty": "n : Nat\n⊢ 0 + n = n",
              "hypotheses": [{"type": "Nat", "name": "n", "value": null}],
              "name": null,
              "sibling_dep": []
            }
          ],
          "messages": []
        }
      ],
      "diagnostics": {"acquire_ms": 0.0, "lean_ms": 210.0}
    }
  ]
}
```

`messages` entries are structured `ExecMessage` objects
(`{severity, data, pos?, end_pos?}`); positions are body-relative and the
router applies the import-header line offset before returning them.

Additional operational endpoints:
- `POST /exec/cleanup` deletes all states for completed `item_id`s.
- `POST /exec/cancel` marks `item_id`s for cancellation.
- `GET /exec/stats` exposes state-store, lifecycle, limiter, and worker stats.

**POST /exec/verify** (warm-pool proof certification — "path C")

Reward-grade acceptance for an assembled proof runs on the same warm Pantograph
pool as stepping — no separate REPL service, no cold start. The worker compiles
the full proof standalone and appends `#print axioms <theorem_name>`, rejecting
Lean errors, `sorry`/`sorryAx`, and any axiom outside the item's allow-list. A
completed stepped state is not a sufficient certificate on its own — it does not
enumerate the proof term's transitive axiom dependencies.

Request:
```json
{
  "env_profile": "lean4.29.1_mathlib_5e932f97",
  "items": [
    {
      "item_id": "thm_001:final",
      "code": "import Mathlib\n\ntheorem foo (n : Nat) : n + 0 = n := by\n  rw [Nat.add_zero]",
      "theorem_name": "foo",
      "allowed_axioms": null,
      "acquire_timeout_ms": 5000,
      "step_timeout_ms": 10000,
      "debug": false
    }
  ]
}
```
`allowed_axioms: null` inherits the server default trusted set
(`propext, Classical.choice, Quot.sound`, via the `verify_allowed_axioms`
setting); `[]` demands an axiom-free proof.

Response:
```json
{
  "items": [
    {
      "item_id": "thm_001:final",
      "status": "accepted",
      "theorem_name": "foo",
      "axioms": [],
      "messages": [],
      "diagnostics": {"acquire_ms": 4.0, "lean_ms": 1200.0}
    }
  ]
}
```
`status` is `accepted | rejected | error | overloaded | cancelled`.

The legacy REPL **`POST /verify`** (Kimina's original
`{statements:[{id, header, proof}]}` whole-file check) still exists but only in
**verify mode** (see §2.2.1) — used for autoformalized *statement* checks
(Extension B), not search-path proof acceptance.

### 2.8 Validation Harness

Before trusting the Kimina `/exec` Env Backend for training, validate it
reproduces known proof trajectories with correct focus, replay, verification,
and cache behavior. The reusable local surface is
`leanfoundry.env_backend.validation.validate_backend_case(...)`: callers provide
a `BackendValidationCase` with a theorem, a tree-shaped tactic replay, and the
complete proof code to check through `/exec/verify`. The runnable operator
entry point is `leanfoundry-validate-backend` /
`python -m leanfoundry.env_backend.validation_cli`; it accepts
`BackendValidationCase` JSON or JSONL, enforces a single `env_profile` for the
run, and emits a JSON summary with one report per case plus aggregate latency
seconds. Each report records create latency, aggregate replay-step latency,
verify latency when verification runs, and total case latency.

For each known proof in LeanDojo:

```
1. Initialize root/sorry states through /exec/create_states
2. Replay each known tactic through /exec/step_batch
3. Compare resulting Pantograph goals to trace goals where trace data exists
4. Render final proof from collected tactic history
5. Verify final proof through /exec/verify
6. Measure create/replay/verify latency from the validation report; combine
   with backend telemetry for state-token size and cache efficiency
7. Stress queueing with many proof-state items per batch
```

Acceptance metrics:
```
init_success_rate               > 0.99
step_replay_success_rate        > 0.99
render_verify_success_rate      > 0.99
header_cache_hit_rate           > 0.90
worker_utilization              > 0.70
queue_wait_p95                  < 100ms
step_latency_p50                < 500ms
step_latency_p95                < 5000ms (some tactics are slow)
state_token_size_p50            < 5MB
goal_load_time_p50              < 200ms
```

If this harness is weak, search training produces garbage silently.
Validate before any training run.

---

## 3. Search Engine

The search engine is a Python process that orchestrates direct and tree search. It has no
Lean knowledge — it only knows about nodes, actions, values, and scores.
All Lean execution is delegated to an `EnvBackend` client. The `/exec` wire
schema is owned by the `lean-client` package, so protocol-facing modules may
import `lean_client.exec_models` directly. Only
`leanfoundry/env_backend/kimina_backend.py` constructs the concrete
`AsyncLeanExecBackend` façade; search code receives an injected `EnvBackend`
and does not build backend transports.

### 3.1 Proof Tree Structure and State Equivalence

A proof is an AND/OR hypergraph:
- **Node (state)**: a `FactorizedProofState` = goal components, local
  context per component, and metavariable-coupling metadata
- **Hyperedge (action)**: a tactic applied to a state, producing zero
  or more new states
- A state is **proved** if ANY action proves it (OR)
- An action **succeeds** if ALL resulting states are proved (AND)

State semantics are owned by the **infrastructure repo**. Dataset selection is
owned by the **training repo**. This means LeanFoundry can adopt LeanTree-style
factorized proof-state semantics without hard-coding the LeanTree dataset as a
required training source.

State merging is a correctness-sensitive optimization, not a v0 assumption.
A naive hash of pretty-printed goals and local context is useful for diagnostics
but is not sufficient for correctness-critical graph merging.

Aristotle's report treats state equivalence more carefully: goal expressions,
local-context expressions, and local variable names must match; multi-goal
states are split only when there are no metavariables; and tactics with global
or search-internal state, such as `aesop`, complicate action/state equivalence.
LeanTree adds an important compatible lesson: split independent goals, but do
**not** split goals coupled by metavariables. LeanFoundry therefore gates graph
merging by version:

```
v0.1 / v0.2:
  - tree search only
  - exact textual proof-state matching for diagnostics and dedup only
  - no correctness-critical graph merging

v0.3:
  - Aristotle-compatible + LeanTree-inspired canonicalization research path
  - canonical identity includes:
      env_profile
      theorem/header/options/imports hash
      normalized goal-component expressions
      normalized local context expressions per component
      local variable names
      metavariable coupling groups
      metavariable assignments when exposed
      universe metadata when exposed
      tactic history hash for merge-unsafe tactics
  - split multi-goal states only when no metavariable coupling is present
  - mark tactics with global-state behavior as merge-unsafe unless validated

Acceptance gate:
  - every merged proof path renders to Lean and passes `/exec/verify`
  - Pantograph state-token replay agrees with trace goals where trace data exists
  - no drop in render_verify_success_rate
  - solved@budget improves over graph-merge-off tree MCTS
```

Infrastructure-owned state schema (v0 tree search; see v11.2 note). A node
stores its open goals and the token to resume them — not how it was assembled.
The merge-identity fields and per-component context dict of earlier drafts are
removed; goals are referenced by position:

```python
@dataclass
class FactorizedProofState:
    env_profile: str
    goal_components: list[GoalComponent]   # open goals, in Lean's order
    pretty_state: str
    state_token: str | None = None
    serialized_lean_state: bytes | None = None
```

Diagnostic-only hash (not a merge key — see v11.2; merging is not done):

```python
def diagnostic_state_hash(state: FactorizedProofState) -> str:
    return sha256(json.dumps({
        "env_profile": state.env_profile,
        "pretty_state": state.pretty_state,
    }, sort_keys=True)).hexdigest()
```

The "Graph" in MCGS is enabled only after this gate passes. Until then,
PUCT tree MCTS and best-first search are the correctness baselines.

### 3.1.1 LeanTree Integration

LeanTree integration has two tracks with a strict repo boundary.

**Track A — optional dataset warm-start and validation traces**

Owner: **training repo**. The training repo decides whether to use the
LeanTree dataset, which version/split to ingest, and how much weight to give it
in SFT or critic warm-starting. The infra repo only provides normalized schemas,
replay validators, and EnvBackend APIs.

If selected by the training repo, LeanTree data can be used for:

```text
- Stage 1 tactic-policy SFT
  input  = factorized proof state / goal component
  target = next tactic edge

- Value/critic warm-start
  weak labels from proof_depth, proof_size, solved subtree structure

- Env Backend validation
  replay LeanTree proof-tree edges through /exec/step_batch
  compare resulting post-tactic FactorizedProofState
```

Known public dataset facts to verify at ingest time: the Hugging Face dataset
card lists LeanTree as CC-BY-4.0; describes sources from Mathlib 4.19.0 and
DeepSeek-Prover-V1; reports 74,706 factorized tactic proofs from Mathlib and
26,201 from DeepSeek-Prover-V1; and exposes node fields including
`proof_size`, `proof_depth`, tactic edges, goal types, hypotheses, imports,
open namespaces/context, and source spans.

Do **not** create a LeanTree-specific HER or curriculum stage. HER remains a
general LeanFoundry EI mechanism over whatever verified Stage 2/3 proofs are
discovered. LeanTree metadata may help audit or weight samples, but it is not a
separate HER pipeline.

**Track B — factorized state semantics for search**

Owner: **infrastructure repo**. LeanTree informs the `FactorizedProofState`
abstraction used by the search engine: goal components, local context per
component, metavariable coupling groups, tactic history hash, pretty state, and
optional serialized Lean state. This replaces the old `goals + local_context`
hash direction for MCGS state identity.

Kimina remains the online backend:

```text
LeanFoundry EnvBackend = Kimina-style high-throughput serving
                         + LeanTree-style factorized proof-state semantics
```

Kimina owns online serving, batching, header LRU, verification, worker
profiling, and `/exec/step_batch`. LeanTree contributes offline data format,
proof-tree extraction ideas, factorization semantics, and validation targets;
LeanFoundry does not run a separate LeanTree server beside Kimina in the core
system.

Pre-integration checks are split by owner:

```text
Training repo checks:
  - exact dataset version, size, source split, license, file format, fields
  - whether proof_depth/proof_size are present per node
  - raw whole-state tactic SFT vs factorized-state tactic SFT
  - prompt length reduction
  - tactic validity / next-tactic accuracy
  - value warm-start impact on tree solved@budget

Infra repo checks:
  - can LeanTree traces replay under our env_profile?
  - how many samples fail after Kimina re-verification?
  - does LeanTree require Lean 4.19 or support our Lean/Mathlib version?
  - how LeanTree detects metavariable coupling
  - whether global tactics like aesop/simp_all create unsafe splitting cases
  - whether state equivalence is strong enough for MCGS merging
```

Integration path:

```text
1. training repo ingests LeanTree dataset offline, if selected
2. infra replay validator replays traces through Env Backend
3. only after replay validation, port factorized_state into /exec/step_batch
4. only after state-equivalence validation, enable MCGS graph merging
```

### 3.2 AND/OR UCB Selection

The v0 implementation uses local root-to-leaf PUCT descent over the AND/OR tree.
At an OR state, PUCT chooses one action using prior, value, visits, and
`puct_exploration_weight`; at an AND action, search descends into the hardest
open child using the implemented structural heuristic (more open goals, fewer
visits, then stable order). The older global highest-UCB plus LCB-hardest-child
formulation is reference material, not the current contract.

```python
def select(tree: SearchGraph) -> FactorizedProofState:
    node = tree.root
    while node.is_expanded:
        action = best_puct_action(node)
        if not action.children:
            return node
        node = hardest_open_child(action)
    return node

def ucb_score(action, c_explore=1.0):
    exploit = action.value_estimate
    explore = c_explore * action.prior * (
        sqrt(action.parent.visit_count) / (1 + action.visit_count)
    )
    return exploit + explore
```

### 3.3 Tree Expansion

Tree-search iterations within a single theorem are strictly sequential: each
iteration's UCB/LCB selection depends on backpropagation from the previous
iteration. At expansion time, the policy samples N candidate tactics for the
selected proof state. These N tactics form one Env Backend expansion item:
`state_token + tactics[]`. The backend must not schedule those tactics as N
independent manager jobs; one worker loads the state once and evaluates the
candidates internally.

Parallelism comes from batching many such expansion items across concurrent
proof graphs / theorem searches. The EnvClient coalesces those items into
`/exec/step_batch` requests, and the Kimina-style backend executes items in
parallel up to the worker-pool cap.
See concern R1 for cross-theorem batching.

The policy prompt must include the full action history with inline comments
preserved — comments are persistent memory across the proof (see concern G4).

```python
async def expand(state: FactorizedProofState, model_client, env_client, n_tactics=8):
    # 1. Sample N tactics in one batched call
    #    Prompt includes full tactic history WITH inline comments (see G4)
    tactics = await model_client.sample_tactics(
        prompt=build_policy_prompt(state, state.tactic_history),
        n=n_tactics,
        temperature=0.8
    )

    # 2. Submit one proof-state expansion item.
    #    EnvClient may microbatch this item with other graph searches, but
    #    the tactics for this state remain one backend item / one worker lease.
    results = await env_client.step(
        node_id=state.id,
        state_token=state.state_token,
        tactics=tactics,
        timeout_ms=5000
    )

    # 3. Estimate value of each new state in one batched call
    new_states = [r.new_state for r in results if r.status != "error"]
    values = await model_client.estimate_value(new_states)

    return results, values
```

### 3.4 Hindsight Experience Replay (HER)

A proved runtime node is a reusable training root. LeanFoundry has two HER
surfaces, and they must not be conflated:

1. **Lineage-A step HER (primary data path):** emit local `(state, tactic)`
   policy positives and proved value labels from any proved runtime state. This
   does **not** render a standalone Lean proof. The edge was already executed by
   `/exec/step_batch`, the child subtree is structurally proved, and the
   sorry/admit guard prevents reward-hack closures. This is the natural
   step-level analogue of HER: a proved internal state becomes another supervised
   proof-state example.
2. **Lineage-B whole-proof HER (optional artifact path):** attempt to render a
   proved subtree as a standalone Lean proof, deduplicate it, and re-verify it
   under the same `env_profile` before inserting an A-type whole-proof row. This
   path is useful for audits or whole-proof training enrichment, but it is not a
   training-data gate for lineage A.

The proof witness is represented as a `TacticNode` tree (see concern G3). For
lineage-A extraction, depth-first traversal of proved nodes yields step rows.
For optional whole-proof HER, the same tree can provide render candidates.

Track two multipliers separately:

```
step_her_multiplier       = proved_step_rows / root_witness_step_rows
render_her_candidate_mult = rendered_subproof_candidates / verified_root_proofs
render_her_verified_mult  = verified_rendered_subproofs / verified_root_proofs
```

The step multiplier is the one that matters for the default search-training
loop. The render candidate/verified gap is a Path-B artifact diagnostic (see
concern R2). Render candidates that fail re-verification — typically because
they reference outer local context not present when run as standalone roots —
are discarded from the optional whole-proof artifact stream only.

```python
def extract_step_her_rows(proved_nodes: list[StateNode]) -> list[PolicyExample]:
    rows = []
    for state in proved_nodes:
        action = state.proved_action()
        if action is None:
            continue
        rows.append(PolicyExample(
            state=state.state,
            tactic=action.tactic,
            proof_prefix=proof_prefix_for_state(state),
        ))
    return rows
```

Node-general step extraction now writes proved-node rows to `policy_examples`
and proved/disproved/censored values to `state_value_labels` directly from
accepted search steps. Only optional rendered Path-B HER artifacts would enter
`a_type_data`, and only after independent `/exec/verify`.

### 3.5 Value Function Data

Proved states are positive labels. There are two distinct kinds of negative
labels, which must not be conflated (see concern G2):

**Censored negatives**: states searched but not proved. These are NOT
mathematically false — they are "not found by this policy at this budget."
Train with reduced weight (weight=0.25, subject to ablation — see R3).
Only include states with sufficient search effort (min 50 tactics tried)
to avoid labeling under-explored states as negative.

**Disproved states**: states where the logical negation of the goal was
proved via negation pruning (see G5). These ARE definitively mathematically
false. Train with full weight. Stored with `disproved=TRUE` in the schema.

The runtime interface stays simple: `ValueClient.estimate(states)` returns one
finite probability-like float in `[0, 1]` per state. Implementations may be:

- **unbonded**: a separate value endpoint/checkpoint;
- **bonded**: the policy checkpoint prompted or tasked as a value model;
- **numeric-head**: endpoint returns a direct scalar/logit/JSON score;
- **natural-language**: model reasons within a token budget, then emits a
  parseable scalar such as `\boxed{0.73}` or `{"score": 0.73}`.

Invalid, missing, or out-of-range value outputs are diagnostics or hard
failures. They are not silently converted into neutral scores unless a caller
explicitly configures a fallback for an experiment.

```python
def extract_value_labels(
    proof_tree: TacticNode,
    failed_nodes: list[FactorizedProofState],
    disproved_nodes: list[FactorizedProofState],
    min_effort: int = 50
) -> list[ValueLabel]:
    labels = []

    # Positive: states on verified paths to proof
    for node in all_proved_nodes(proof_tree):
        labels.append(ValueLabel(
            state=node.state, label=1,
            depth=node.depth, effort=node.total_tactics_tried,
            weight=1.0, disproved=False,
        ))

    # Disproved: negation proved — definitive, full weight
    for node in disproved_nodes:
        labels.append(ValueLabel(
            state=node, label=0,
            weight=1.0, disproved=True,
        ))

    # Censored negative: not solved after sufficient effort
    for node in failed_nodes:
        if node.total_tactics_tried >= min_effort:
            labels.append(ValueLabel(
                state=node, label=0,
                depth=node.depth, effort=node.total_tactics_tried,
                weight=0.25,   # see R3: this weight needs ablation
                disproved=False,
            ))

    return labels
```

### 3.5.1 Negation Pruning (try_negation flag, default False)

> See concern G5. The current implementation is a conservative persistent
> backend-grounded negation action. It is initialized once for an eligible
> state, attaches the synthetic negation proof state as its child, competes as
> an open OR action under the normal selector, and searches tactics/subgoals
> inside that synthetic proof with the same AND/OR machinery. Negation is gated
> per-theorem by provenance, not globally: `try_negation` is off for known-true
> targets
> (`leandojo`/`mathlib`/`minif2f`) and on for `autoformalized` and
> speculative-decomposition statements where the goal may be genuinely false.
> It is restricted to single-goal states (a Lean state may hold multiple goals;
> `¬P` is a clean action only when there is one).

```python
def should_try_negation(spec: TheoremSpec) -> bool:
    # provenance label already lives in theorems.source (§4.2);
    # TheoremSpec carries it through to the engine.
    return spec.source in {"autoformalized"}   # extend per Extension B / decomposition
```

Target behavior: for each new single-goal state with goal `⊢ P`, a synthetic
action is added to the state's action pool: prove `¬P` (i.e., `P → False`) in
the same local context. This action competes under normal UCB selection
alongside other candidate tactics and receives a real child subtree. If a
negation tactic leaves open subgoals, those states are expanded normally; if
the child subtree closes, the source state is marked `DISPROVED`. Policy rows
inside the child subtree are positives for the synthetic negation goal, not for
the original false state.

Rendering is fail-closed. Ordinary hypotheses render as typed theorem
parameters. Local definitions / `let` entries are also rendered as typed
parameters, intentionally dropping the defining value: proving the negated
target for every value of that parameter is stronger than proving it under the
local definition, so success remains a valid falsity certificate. Missing names,
invalid binder identifiers, and empty types are unsupported and emit a durable
negation attempt artifact instead of guessing Lean surface syntax.

If the negation is proved, the state is marked DISPROVED. Propagation sends
"dead" upward through all parent AND-nodes containing this state: an AND-node
with any DISPROVED child can never succeed and is eliminated from its parent
OR-node's options. This is the hard-termination complement to soft budget
exhaustion.

```python
async def expand_with_negation(state, model_client, env_client, n_tactics=8):
    # Normal tactic candidates
    tactics = await model_client.sample_tactics(
        prompt=build_policy_prompt(state, state.tactic_history),
        n=n_tactics, temperature=0.8
    )

    # Synthetic negation action: prove ¬P
    neg_tactic = build_negation_tactic(state.goal)   # e.g. "push_neg; ..."
    all_tactics = tactics + [neg_tactic]

    results = await env_client.step(
        node_id=state.id,
        state_token=state.state_token,
        tactics=all_tactics, timeout_ms=5000
    )

    neg_result = results[-1]
    if neg_result.status == "proved":
        return DisprovedException(state)   # propagate DISPROVED upward

    normal_results = results[:-1]
    new_states = [r.new_state for r in normal_results if r.status != "error"]
    values = await model_client.estimate_value(new_states)
    return normal_results, values
```

The DISPROVED state is recorded in `state_value_labels` with `disproved=TRUE`
and `label=0` at full weight. Cost: one extra Kimina step per expansion when
enabled. Benefit: eliminates dead branches immediately rather than exhausting
budget on them.

---

## 3.6 Supported Search Algorithms

LeanFoundry supports multiple search modes behind `SearchEngine` and
`build_engine(config)`. The current code has two implemented wedges:
direct whole-proof search (`DIRECT`, `SELF_CORRECT`) and AND/OR tree search
(`TREE`, with pluggable PUCT and best-first selection strategies). Beam,
optimistic/RMaxTS-style search, graph/MCGS, and richer HER remain future
algorithms until replay/eval shows the simpler baselines are insufficient.
All implemented modes use `EnvBackend` for Lean execution and `PolicyClient`
for model calls; search code does not construct those clients.

### 1. Direct Whole-Proof Sampling

The model samples complete Lean proofs from theorem statements.
LeanFoundry verifies every sampled candidate in the pass@k pool and reports
pass@k from accepted candidate indices. Current implementation batches the
plain `DIRECT` candidate pool through `EnvBackend.verify(...)`; self-correction
uses sequential `verify_one` calls because verifier feedback conditions the
next prompt.

Use cases: baseline evaluation, whole-proof Expert Iteration, GRPO
rollouts, comparison against Goedel/DeepSeek-style systems.

### 2. Self-Correction Search

The model generates a proof, receives Lean error feedback from Kimina,
and revises for one or more rounds.

Use cases: Goedel-style evaluation, self-correction SFT data generation,
compiler-feedback training traces.

### 3. AND/OR Tree Search With Best-First Selection

LeanFoundry expands the open leaf with the strongest implemented best-first
score: value estimate when present, otherwise `best_first_missing_value_score`,
then fewer open goals, fewer visits, and stable order. It does not currently
combine policy logprob, depth, and novelty.

Use cases: value-model evaluation, search-efficiency baseline, stronger
alternative to fixed-width beam search.

### 4. AND/OR Tree Search With PUCT Selection

PUCT selection scores actions locally under the current root-to-leaf descent.
For split actions, the engine attacks the hardest open child under the selected
action. Value backup uses product over AND children and max over OR actions.

Use cases: tree-search baseline before graph merging is added, policy/value
integration tests, and solved@budget curves.

### 5. Tactic Beam Search (deferred)

Maintain a beam of proof prefixes and keep the best resulting prefixes by a
future scoring rule. Deferred until the direct/tree baselines and eval runners
make the comparison meaningful.

### 6. Optimistic Search / RMaxTS-Style Search (deferred)

Add optimism bonuses for underexplored states or actions. Deferred until the
baseline tree path has durable replay/eval and real trace evidence.

### 7. MCGS: Monte Carlo Graph Search (deferred)

Graph search requires a complete Lean state-identity fingerprint before states
reached by different paths can be merged soundly. Until that gate passes, v0
search is tree search and does not merge states.

### 8. AND/OR MCGS (deferred)

The full Aristotle-style graph algorithm combines OR-over-actions,
AND-over-subgoals, graph merging, hardest-child prioritization, HER, and value
labels. LeanFoundry keeps this as the north-star reference, not the current
implemented contract.

---

## 3.7 Search Implementation Roadmap

```
current baseline
  direct whole-proof sampling
  self-correction loop
  AND/OR tree search with PUCT selection
  AND/OR tree search with best-first selection
  Path-A policy/value extraction and SQLite replay store

next core work
  env-profile ingress policy
  eval runners and benchmark/env-profile manifests
  policy history/comment API contract
  DISPROVED semantics before enabling try_negation

later algorithms
  tactic beam search
  optimistic / RMaxTS-style search
  validated MCGS state merging
  AND/OR MCGS with node-general proved-node extraction
```

---

## 4. Data Stores

### 4.1 A-Type Data (Theorem + Verified Proof)

Used for whole-proof SFT artifacts. A row enters this table only when a
complete rendered proof passed final `/exec/verify` in a known `env_profile`.
Path-A per-state policy/value rows do not require a whole-proof render and are
stored separately.

```sql
CREATE TABLE a_type_data (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  header TEXT NOT NULL,
  lean_proof TEXT NOT NULL,
  proof_hash TEXT NOT NULL,
  verified_by_backend BOOLEAN NOT NULL DEFAULT TRUE,
  proof_type TEXT,
  tactic_sequence TEXT,
  correction_input TEXT,
  source TEXT NOT NULL,
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 B-Type Data (Theorem Statement Only, No Proof)

Used for Expert Iteration and GRPO. The model finds the proof.

```sql
CREATE TABLE theorems (
  id TEXT PRIMARY KEY NOT NULL,
  lean_statement TEXT NOT NULL CHECK (length(lean_statement) >= 1),
  informal_statement TEXT,
  env_profile TEXT NOT NULL CHECK (length(env_profile) >= 1),
  header TEXT NOT NULL,
  theorem_name TEXT,
  allowed_axioms TEXT,
  initial_lean_block TEXT,
  difficulty_estimate REAL,
  pass_rate_current REAL,
  pass_rate_updated_at TIMESTAMP,
  source TEXT NOT NULL DEFAULT 'unknown' CHECK (length(source) >= 1),
  split TEXT NOT NULL DEFAULT 'train',
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`source` is the provenance label propagated into `TheoremSpec.source`; it gates
`try_negation` (§3.5.1).

### 4.3 Trajectories (Replay Buffer)

```sql
CREATE TABLE trajectories (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT NOT NULL REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_type TEXT NOT NULL,
  whole_proof TEXT,
  tactic_sequence TEXT,
  search_budget_used INTEGER,
  is_subproof BOOLEAN NOT NULL DEFAULT FALSE,
  parent_trajectory_id TEXT,
  model_version INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

`tactic_sequence` stores serialized `ProofTree` JSON for the solved projection,
not the live AND/OR runtime tree. `whole_proof` is nullable because Path-A
attempts can emit per-state training data even when Path-B rendering or final
verification fails.

Positive Path-A policy rows are stored separately:

```sql
CREATE TABLE policy_examples (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_state_hash TEXT NOT NULL,
  proof_state_pretty TEXT,
  proof_prefix TEXT NOT NULL DEFAULT '',
  tactic TEXT NOT NULL,
  depth INTEGER NOT NULL CHECK (depth >= 0),
  model_version INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Value labels use the same replay provenance:

```sql
CREATE TABLE state_value_labels (
  id TEXT PRIMARY KEY NOT NULL,
  theorem_id TEXT REFERENCES theorems(id),
  env_profile TEXT NOT NULL,
  proof_state_hash TEXT NOT NULL,
  proof_state_pretty TEXT,
  label INTEGER NOT NULL CHECK (label IN (0, 1)),
  weight REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0),
  disproved BOOLEAN NOT NULL DEFAULT FALSE,
  depth INTEGER CHECK (depth IS NULL OR depth >= 0),
  tactics_tried_on_subtree INTEGER CHECK (
    tactics_tried_on_subtree IS NULL OR tactics_tried_on_subtree >= 0
  ),
  model_version INTEGER NOT NULL,
  CHECK (NOT disproved OR (label = 0 AND weight = 1.0))
);
```

`disproved=TRUE` is reserved for semantic falsity certificates such as
provenance-gated `try_negation`. `label=0, disproved=FALSE` is a censored
negative and carries a reduced `weight`.

### 4.4 Formalizer Output (B-Type Statements from Extension B)

When Extension B is active, autoformalized statements land here first
and require additional vetting before entering the main theorems table:

```sql
CREATE TABLE formal_statements_staging (
  id TEXT PRIMARY KEY NOT NULL,
  informal_source TEXT,
  informal_statement TEXT,
  lean_statement TEXT NOT NULL,
  env_profile TEXT NOT NULL,
  formalizer_version TEXT,
  semantic_judge_score REAL CHECK (
    semantic_judge_score IS NULL
    OR (semantic_judge_score >= 0 AND semantic_judge_score <= 1)
  ),
  syntax_checked BOOLEAN NOT NULL DEFAULT FALSE,
  dedup_hash TEXT,
  promoted_to_theorems BOOLEAN NOT NULL DEFAULT FALSE
);
```

---

# Part II: Training Recipe

---

## 5. Hardware Configuration

### 5.1 Machine Spec

```
GPUs:  8x H100 80GB SXM
CPUs:  512 cores (verify NUMA topology before allocating workers)
RAM:   1-2TB (verify before setting worker_pool_size)
Disk:  4TB NVMe SSD
```

**Env Backend worker sizing:**

Worker count is empirical, not derived from CPU count alone. Kimina uses
multiple Lean REPL worker processes and LRU header/import reuse. Public
references support import/header reuse and process pooling, not a guarantee
that Mathlib RSS is loaded once and shared across hundreds of workers.

Phase -1 therefore includes RSS/PSS and latency sweeps at 64, 128, 256,
and 400 workers for lightweight REPL verification, but Pantograph/mathlib
tactic stepping must use a separate smaller sweep. Initial profiling with
`Mathlib.Data.Finset.Card` + `Mathlib.Data.Nat.Basic` showed roughly 1.3GB RSS
per warm Pantograph worker on macOS, so practical single-node pools are likely
in the 4-32 worker range depending on RAM and imports. The selected
`worker_pool_size` is the largest stable point with acceptable queue latency,
no restart storm, and enough RAM headroom.

```yaml
kimina_worker_rss_sweep:
  worker_counts: [4, 8, 16, 32]
  headers:
    - "import Mathlib\nimport Aesop"
  workload:
    proof_mix: [verify, init_state_token, step_state_token, extract_trace]
    duration_minutes: 30
  metrics:
    - total_rss_gb
    - total_pss_gb_if_available
    - per_worker_rss_p50_p95_max
    - startup_prewarm_time
    - header_cache_hit_rate
    - step_sec
    - queue_wait_p50_p95
    - tactic_latency_p50_p95
    - restart_count
    - oom_count
    - disk_cache_pressure
    - numa_imbalance
```

Pin each worker group to its local NUMA node after the sweep. Cross-NUMA
memory access can degrade Lean process latency. Verify the actual topology
with `numactl --hardware` before configuring affinity.

### 5.2 Base Model: Qwen3.6-27B

**Why Qwen3.6-27B specifically:**

Qwen3.6-27B is the latest open-weight dense model from the Qwen family
(released April 2026, Apache 2.0). Key properties:
- 27B parameters (dense, not MoE)
- Long-context capable, but LeanFoundry does not assume 262K rollout context
- Native thinking mode: may generate `<think>...</think>` before output
- SGLang/vLLM/Transformers-compatible
- Not Lean-specialized, so improvements are attributable to our framework

**Serving contract for LeanFoundry:**

```
- Serve Qwen3.6-27B in text-only mode for Lean tasks.
- Initial rollout/search context buckets: 8K / 16K / 32K.
- Do not depend on 262K context for routine search.
- Tactic prediction disables thinking by default.
- Whole-proof and self-correction may allow thinking, but only extracted Lean
  code is sent to the verifier.
- Any `<think>` leakage inside Lean code is stripped or rejected.
```

**Why dense over MoE (Qwen3.6-35B-A3B):**

Dense 27B is the v0 default for engineering simplicity and clean attribution.
MoE is not rejected on principle. With Expert Parallelism, expert parameters
and optimizer state are sharded across GPUs, so the memory profile differs
substantially from the naive "total parameters" argument. MoE requires a
separate EP-aware fit, throughput, weight-sync, and routing stability profile
before adoption. MoE is a v0.2 optimization candidate after the dense path
is profiled and stable.

**Why not start from DeepSeek-Prover or Goedel-Prover:**

Starting from an already-specialized prover checkpoint makes the framework's
contribution harder to attribute. Use them as teachers (to generate SFT
data) and baselines (to compare against), not as the main actor's starting
point.

**GPU allocation (baseline, subject to profiling):**

The 6/2 Megatron/SGLang split is an initial profiling baseline, not a
settled architecture. Full 27B fine-tuning is state-memory constrained:
BF16 weights + FP32 gradients + FP32 optimizer states ≈ 18 bytes per
parameter. At 27B on 6 training GPUs (TP=2, PP=3, DP=1), this is
approximately 81GB per GPU before activations — likely not feasible
without relief.

The likely concrete allocation after profiling is 8 GPUs for training
updates (TP=4, PP=2 or TP=2, PP=4), with phase-separated rollout/search
and update cycles for EI and search-based EI stages. The 6/2 co-located layout
is tested for GRPO only if the fit gate passes with margin.

```
Initial profiling baseline:
  Training (Megatron):  GPU 0-5  (6 cards), TP=2, PP=3
  Inference (SGLang):   GPU 6-7  (2 cards), TP=2

Likely post-profiling layout:
  Training updates:     all 8 GPUs, TP=4, PP=2 or TP=2, PP=4
  Rollout/search phase: 2-4 GPUs + Env Backend on CPU
  (phase-separated, not concurrent)

CPU allocation (512 cores):
  Env Backend pool:     profiled_worker_pool_size (NUMA-pinned, see 5.1)
  Search Engine:        32 cores (asyncio, NUMA 0)
  Data Buffer:          4 cores  (SQLite server, NUMA 3)
  OS/misc:              remaining cores
```

---

### 5.3 Phase -1: Systems Fit and Throughput Profiling

No full training begins until this phase completes and produces a
`resource_profile_manifest.json` for every stage.

#### Required gates

```
Gate A: model-load-only
  Load model shards. Build optimizer. Allocate grad buffers. No forward.
  Pass if peak_reserved < 68GB on every rank.

Gate B: forward-only
  seq_len = p95 length bucket from the format length audit (below).
  micro_batch = 1.
  Pass if peak_reserved < 72GB.

Gate C: full update
  forward + backward + optimizer step, 10 measured steps.
  Pass if peak_reserved < 74GB and no rank grows across steps.

Gate D: long-run stability
  100 steps on the selected config.
  Pass if memory growth < 1GB and no OOM.

Gate E: Env Backend worker sweep
  Run 64/128/256/400 worker RSS/PSS and latency sweep from 5.1.
  Pass when selected worker_pool_size has stable RSS, acceptable queue_wait_p95,
  and no restart/OOM storm.
```

#### Format length audit (run before memory profiling)

```python
def build_length_report(dataset, tokenizer):
    rows = []
    for sample in dataset:
        prompt_len = len(tokenizer.encode(sample["prompt"]))
        target_len = len(tokenizer.encode(sample["target"]))
        rows.append({
            "format": sample["format"],
            "source": sample["source"],
            "prompt_len": prompt_len,
            "target_len": target_len,
            "total_len": prompt_len + target_len,
        })
    return percentile_table(rows, by=["format", "source"],
                            percentiles=[50, 75, 90, 95, 99, 100])
```

Report p50/p75/p90/p95/p99/max for each format (whole_proof, tactic,
self_correction, value, grpo). Use p95 as the default seq_len for dry
runs; route p99 examples to special long-context microbatch=1 runs.

#### Memory dry-run matrix

```yaml
memory_dry_run:
  seq_lens: [4096, 8192, 16384, 32768]
  micro_batch_sizes: [1, 2]
  parallelism:
    - {gpus: 6, tp: 2, pp: 3}
    - {gpus: 8, tp: 4, pp: 2}
    - {gpus: 8, tp: 2, pp: 4}
  recompute: [none, selective, full]
  sequence_parallel: [true]
  stages:
    - stage1_sft_whole_proof
    - stage1_sft_tactic_policy
    - stage1_sft_self_correction
    - stage3_search_tactic_policy
    - stage3_value_training
    - stage4_grpo_whole_proof
    - stage4_grpo_self_correction
```

Instrumentation:

```python
import torch, time, json, os

def log_rank_memory(tag, step, path="memory_profile.jsonl"):
    torch.cuda.synchronize()
    row = {
        "tag": tag, "step": step,
        "rank": int(os.environ.get("RANK", -1)),
        "allocated_gb": torch.cuda.max_memory_allocated() / 1024**3,
        "reserved_gb": torch.cuda.max_memory_reserved() / 1024**3,
        "timestamp": time.time(),
    }
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")
```

Wrap training phases with NVTX ranges for CPU/GPU idle analysis in
Nsight Systems.

#### Resource profile manifest

Gate C produces a mandatory manifest before Stage 1 begins:

```json
{
  "model": "qwen3.6-27b",
  "env_profile": "lean4_mathlib_pinned",
  "stage": "stage1_sft",
  "parallelism": {"gpus": 8, "tp": 4, "pp": 2},
  "seq_len": 16384,
  "micro_batch": 1,
  "recompute": "selective",
  "sequence_parallel": true,
  "peak_reserved_gb_max_rank": null,
  "tokens_per_sec": null,
  "mfu": null,
  "worker_pool_size": null,
  "kimina_step_sec": null,
  "kimina_queue_wait_p95_ms": null,
  "oom": null,
  "notes": "fill after profiling run"
}
```

#### Memory pressure response ladder

Ordered from least to most capability loss. Try earlier tiers first.

```
Tier 0: no capability loss
  1. Use all 8 GPUs for training updates (phase-separated EI).
  2. Sweep TP/PP: try TP=4 PP=2 and TP=2 PP=4.
  3. Enable sequence parallelism with TP.
  4. Length bucketing + packed batches.
  5. Activation checkpointing (selective then full).
  6. Recompute logprobs in GRPO instead of storing rollout tensors.
  7. Store rollouts on CPU, load per microbatch.

Tier 1: low risk, verify by ablation
  8. Route p99 long examples to separate long-context microbatch=1 runs.
  9. For tactic-policy samples, use current proof state + local context,
     not full theorem history when depth is large.

Tier 2: medium risk
  10. CPU-offload optimizer states if the Slime/Megatron path supports it.
  11. FP8 training after loss/eval ablation.

Tier 3: last resort
  12. LoRA/QLoRA-only for v0 demo.
  13. Smaller dense model.
```

Context parallelism (CP) is a candidate for long sequences but competes
with TP/PP for GPU resources on a single 8-GPU node. Only consider CP
after the model-state fit is resolved.

---

### 5.4 Slime Integration

Slime (THUDM) is the **default** online RL orchestrator: it provides
Megatron-LM + SGLang integration, weight synchronization, and a custom rollout
interface. Because it is the default, its rollout adapter ships **in this repo**
(`leanfoundry/slime/`) as runnable defaults, available only through the
`[training]` optional extra (see v11.13 note). The hard invariant is that the
adapter never enters the core execution path: `import leanfoundry.proofsearch`
must not pull in `slime`/`sglang`. The adapter is pinned and drift-tested under
`[training]`; bumping Slime is a deliberate compatibility event, not a silent
track of Slime `main`.

The source-level integration shape is pull, not push. Slime loads a rollout
function and calls it each rollout iteration; LeanFoundry does not stream
samples into Slime's buffer through `RLEngineBase.submit_samples(...)`. The
clean hook for theorem proving is the full rollout function:

```text
--rollout-function-path leanfoundry.slime.generate_rollout
```

The per-sample hook `--custom-generate-function-path` is useful for linear
agent episodes (tool call -> observation -> next model call). It is not the
right default for graph proof search because Slime's default rollout launches
`n_samples_per_prompt` samples independently. Mapping one tactic candidate to
one `Sample` would recreate the forbidden flattening problem. Mapping one full
theorem search to one `Sample` is possible for a prototype, but it makes env
batching across proof graphs and trajectory extraction awkward.

That function returns Slime training output from `runner.to_samples(...)`:
direct/self-correct rows use regular Slime sample groups, while tree/tactic
rows use Slime's compact fanout nesting with shared per-search
`Sample.rollout_id` (see v11.84). LeanFoundry's role inside it is
algorithm-neutral search and optional durable side-write to the SQLite
`ReplayStore`; Slime owns the online data buffer and trainer. The full rollout
function ships here (`leanfoundry/slime/rollout.py`) as the default
`generate_rollout`; the training repo just points
`--rollout-function-path leanfoundry.slime.generate_rollout` at it and supplies
config/overrides. Default body (simplified from the in-repo implementation;
helpers are model-agnostic defaults and `lf_runner_class` can override them):

```python
# leanfoundry/slime/rollout.py  (ships under the [training] extra)
from leanfoundry.proofsearch import run_search_batch
from leanfoundry.proofsearch.to_rows import to_training_rows
from leanfoundry.slime.runner import SlimeRolloutRunner


async def async_generate_rollout(args, rollout_id, data_source, evaluation=False):
    runner = SlimeRolloutRunner()  # or args.lf_runner_class
    env = runner.build_env_backend(args)
    await env.connect()
    policy = runner.build_policy_client(args)
    value = runner.build_value_client(args)  # bonded, unbonded, or None

    source_samples = runner.source_samples(data_source, args)
    theorems = runner.theorems_from_source(source_samples, args)
    runner.validate_env_profiles(theorems, args)
    config = runner.search_config(args)

    search_results = await run_search_batch(
        theorems,
        policy_client=policy,
        value_client=value,
        env_backend=env,
        config=config,
        model_version=rollout_id,
    )

    include_whole_proofs = config.algorithm in {"direct", "self_correct"}
    if getattr(args, "lf_include_tree_whole_proof_rows", False):
        include_whole_proofs = True

    rows = [
        row
        for result, theorem in zip(search_results, theorems)
        for row in to_training_rows(
            result,
            theorem,
            include_whole_proofs=include_whole_proofs,
            include_failed_self_correct_negatives=getattr(
                args,
                "lf_include_failed_self_correct_negatives",
                False,
            ),
        )
    ]
    return runner.to_samples(rows, rollout_id, args)
```

For tree mode, `Sample` represents one Markovian row per proved node:
`prompt=state`, `response=tactic`. Sibling step samples produced by the same
search share the same trainer `Sample.rollout_id`; the Slime rollout step id is
kept separately as metadata for debugging. Downstream loss aggregation can then
avoid over-counting one proof search just because it produced many local rows.
There is no history-conditional or injected-state trajectory sample. The
default downstream tree objective is EI/SFT; GRPO requires a custom objective
that explicitly supports this compact fanout. Core extraction keeps emitting
algorithm-neutral `TrainingArtifacts`.

---

## 6. Data for Each Stage

### Training Pipeline Overview

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  Phase -1: fit and throughput profiling                         │
  │  resource_profile_manifest.json required before any SFT begins  │
  └────────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 1: Cold-start SFT                                        │
  │                                                                 │
  │  Data Buffer (A-type) ──► Trainer                               │
  │  Sources: LeanDojo train split + reverified external A-type      │
  │  Three formats: whole_proof | tactic_prefix | self_correction   │
  └────────────────────────────┬────────────────────────────────────┘
                               │ checkpoint v1
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 2: Whole-proof Expert Iteration                          │
  │                                                                 │
  │  B-type train theorems ──► Inference Engine (sample N proofs)   │
  │       ──► Env Backend /exec/verify ──► pass-rate bucketing      │
  │                                                                 │
  │       pass_rate = 0        → Stage 3 queue                      │
  │       0 < pass_rate ≤ 0.75 → active EI → A-type                 │
  │       pass_rate > 0.75     → deprioritize                       │
  │                                                                 │
  │  New A-type → Data Buffer → Trainer (SFT) → checkpoint v2       │
  └────────────────────────────┬────────────────────────────────────┘
                               │ checkpoint v2
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 3: Search-based Expert Iteration                         │
  │                                                                 │
  │  B-type (pass_rate=0) ──► Search Engine                         │
  │       ├── PolicyClient → Inference Engine (sample_tactics)      │
  │       ├── /exec/step_batch → Env Backend (tactic execution)     │
  │       └── Path-A extraction → policy/value rows + replay        │
  │                                                                 │
  │  Policy/value rows → Trainer; verified whole proofs → A-type    │
  └────────────────────────────┬────────────────────────────────────┘
                               │ checkpoint v3
                               ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  Stage 4: GRPO                                                  │
  │                                                                 │
  │  B-type (0 < pass_rate ≤ 0.75) ──► LeanRollout                  │
  │       ├── Inference Engine: sample G proofs per theorem         │
  │       └── Env Backend /exec/verify: binary reward               │
  │                                                                 │
  │  (theorem, rollouts, rewards) → Trainer (GRPO)                  │
  │  Multi-task: whole-proof + self-correction                      │
  │  KL penalty against reference ──► checkpoint v4                 │
  └─────────────────────────────────────────────────────────────────┘
```

Autoformalization is **not** part of the core Stage 1–4 loop. Extension B
begins only after the LeanDojo-based core pipeline is stable and eval leakage
rules are locked. Until then, any external formal data must be reverified under
our env_profile and pass contamination filtering before entering training.

### The A/B Distinction

```
A-type data = theorem + verified proof  → used for SFT
B-type data = theorem statement only    → used for EI, search, GRPO

The training pipeline converts B into A:
  search finds a proof for a B-type theorem
  Env Backend /exec/verify accepts the rendered whole proof
  the (theorem, proof) pair becomes A-type data
  → added to replay buffer for future SFT rounds
```

### Stage 1 Data (A-type)

```
Primary:
  LeanDojo (state, tactic) pairs             ~220k tactic samples
  Mathlib proofs via Kimina infotree         ~100k theorems

Optional training-repo warm-start source:
  LeanTree factorized proof-tree dataset, if selected by training repo
    - tactic-policy SFT from factorized states and next tactic edges
    - value/critic warm-start from proof_depth/proof_size
    - validation traces replayed through Env Backend before use

Supplementary (re-verify under our env_profile before use):
  Goedel-Prover SFT data (1.79M samples)    best available A-type source
  DeepSeek-Prover-V1 proof data              large, diverse

Self-correction examples:
  Generate via teacher model (Goedel-Prover-V2-8B or similar):
    1. Sample failed proof attempts for known theorems
    2. Run Kimina, collect Lean error messages
    3. Ask teacher to produce corrected proof
    4. Env Backend /exec/verify accepts corrected proof
    5. (statement, failed_proof, errors, corrected_proof) is one sample

NOTE: any data not verified under our env_profile must be re-verified.
Mathlib version mismatches silently corrupt training data.
```

### Stage 2 Data (B-type, whole-proof EI)

```
Core training pool:
  LeanDojo train split theorems
  Optional external formal statements only if:
    - env_profile verification passes
    - theorem/proof overlap with eval splits is removed
    - split assignment is fixed before training

Eval-only by default:
  miniF2F test
  PutnamBench
  MathOlympiadBench

Do not use eval-only benchmarks for training, pass-rate bucketing,
prompt tuning, checkpoint selection, or curriculum construction.

Pass rate bucketing (updated each iteration):
  pass_rate = 0           → send to search queue (Stage 3 input)
  0 < pass_rate <= 0.75   → active training set for this stage
  pass_rate > 0.75        → deprioritize (mostly learned)

Quick-sampling for difficulty estimation:
  n=16 proofs, budget set by resource_profile_manifest
  Runs at start of each EI iteration to update pass_rate_current
```

### Stage 3 Data (B-type, Search-Based EI)

```
Input: Stage 2's pass_rate = 0 theorem pool
  + any B-type theorems from Extension B (when active)

Current Path-A output:
  proved tactic edge        → policy_examples row (state + proof_prefix + tactic)
  explored state            → value label when label-emission mode owns it
  rendered+verified proof   → optional whole_proof A-type sample
  attempt                   → trajectory + replay diagnostics

Deferred output:
  node-general proved-state rows → extra lineage-A step samples
  optional rendered proved subtree → verified Path-B whole-proof artifact
  node-general DISPROVED labels → full-weight value negatives
```

### Stage 4 Data (B-type, GRPO)

```
Filtered subset of all B-type theorems:
  current whole-proof pass_rate in [0.05, 0.75]
  prefer [0.10, 0.50] for strongest signal

Multi-task RL (following Goedel-V2 recipe):
  50% whole-proof generation tasks
  50% self-correction tasks (statement + failed proof + errors → corrected)
  batch size: 128
  n rollouts per prompt: 8
  dynamic filtering: remove prompts where all 8 rollouts succeed or all fail

Structure consistency reward (optional, from DeepSeek-Prover-V2):
  If model planned a subgoal decomposition but proof skips lemmas: -0.5
  Encourages proof structure faithfulness
```

---

## 7. Training Pipeline

### Stage 1: Cold-Start SFT

**Purpose**: teach the model Lean 4 syntax, basic tactic usage, and
proof structure. Do NOT expect it to "know how to prove" after this —
just learn the format.

Train three formats simultaneously (not sequentially):

**Format 1: Whole-proof generation**
```
Input:  theorem statement
Output: complete Lean proof
```

**Format 2: Tactic/prefix policy**
```
Input:  current proof state + tactic history so far
Output: next tactic
```

**Format 3: Self-correction**
```
Input:  theorem statement + failed proof + Lean error messages
Output: corrected proof
```

Format 3 is important because Goedel-Prover-V2's ablations show compiler
error messages substantially improve the model's ability to revise proofs.
It's also cheap to generate: use a teacher model on known theorems.

Qwen3.6-27B's native thinking mode (`<think>...</think>`) is useful here:
train with CoT in Format 1 and Format 3, where deliberate reasoning
helps. Format 2 (single tactic) does not need CoT.

Training:
```
Standard cross-entropy loss
~3 epochs over the full A-type dataset
No RL at this stage
```

Checkpoint this model. It is the starting point for Stage 2 and the
reference for measuring improvement.

### Stage 2: Whole-Proof Expert Iteration

**Purpose**: on the large pool of B-type theorems, find proofs the model
can discover through direct sampling, and train on them iteratively.

Each iteration:

```
1. Update pass rates
   Quick-sample all active B-type theorems (n=16, 10s budget via SGLang)
   Update pass_rate_current in theorems table

2. Select training set
   Take theorems with 0 < pass_rate <= 0.75
   This is the frontier: model can sometimes prove these, not always

3. Full sampling
   For each frontier theorem: sample n=32 proofs via SGLang
   Send to Env Backend /exec/verify in batch
   Collect all successful proofs

4. Add to A-type data
   For each verified proof: insert into a_type_data with source='search_found'
   Optional rendered-subproof HER is deferred and is not the Stage 2 data gate

5. Train
   Sample from full replay buffer (all A-type data, old and new)
   SFT on whole-proof and optional proof-prefix/tactic formats
   One pass over new data, fractional pass over old data

6. Update model in SGLang
   Slime handles weight sync from Megatron to SGLang

7. Collect pass_rate=0 theorems into the search queue for Stage 3
```

Run until frontier theorems are mostly cleared
(pass_rate=0 pool stops growing, frontier shrinks).

### Stage 3: Search-Based Expert Iteration

**Purpose**: find proofs for theorems that whole-proof sampling cannot
reach (pass_rate=0 from Stage 2). This is a training data generator,
not an optional inference enhancement.

Tree search during training produces lineage-A step data: Markovian
`(proof_state, tactic)` rows chosen by search, plus value labels when label mode
owns them. Optional rendered+verified whole proofs are audit/enrichment
artifacts, not the data path. Graph/MCGS and richer search features are later
upgrades to this loop, not prerequisites for the baseline.

Each iteration:

```
1. Take theorems from the search queue (Stage 2's pass_rate=0 pool)

2. Run tree search for each theorem
   Budget: 500 tactics per theorem
   Use Env Backend /exec/step_batch with Pantograph state_tokens
   Simultaneously:
     policy calls  → SGLang (sample 8 tactics per state)
     value calls   → ValueClient (bonded/unbonded; numeric or NL scalar)
     tactic exec   → Env Backend

3. Collect training data from search
   Proved tactic edges: insert into policy_examples
   State labels: insert into state_value_labels when label mode owns them
   Node-general proved-state rows: deferred extraction hardening
   Successful rendered+verified proofs: optional whole_proof A-type artifact

4. Train
   Policy loss:       cross-entropy on Path-A policy examples
   Value loss:        binary cross-entropy on state_value_labels
   Whole-proof loss:  optional, only from direct or rendered verified artifacts
   Combined default: policy_loss + value_loss * 0.5

5. Update model (Slime weight sync)

6. Re-attempt theorems that search just succeeded on with whole-proof
   sampling — some may now be achievable directly (useful for Stage 4)
```

Model averaging (after each search-training phase):
If whole-proof pass@32 improves but pass@1 drops, or if search proof
discovery rate per Lean call decreases, try:
```
θ_avg = α * θ_search + (1-α) * θ_pre_search,  α ∈ {0.5, 0.7, 0.9}
Select by: search proofs found per 10k Lean calls
```
Use averaging to preserve expansion diversity, not as a default step.

### Stage 4: GRPO

**Purpose**: once search has found proofs and trained the model on them,
use online RL to sharpen the model's direct generation ability on
theorems where it now has a nonzero success rate.

GRPO should NEVER run on theorems where the whole-proof pass rate is 0.
The GRPO signal requires nonzero reward. The correct sequence is:

```
Search finds proof for theorem T (Stage 3)
    ↓
SFT on that proof trains the model (Stage 3)
    ↓
Model now has nonzero pass rate on theorems related to T
    ↓
GRPO can now improve performance on those theorems (Stage 4)
```

GRPO loop:

```python
for batch in frontier_theorems(pass_rate_range=(0.05, 0.75)):
    # Sample G=8 whole proofs per theorem
    proofs = sglang.generate(batch, n=8, temperature=0.9)

    # Verify all through /exec/verify
    rewards = env_backend.verify_batch(batch, proofs)

    # GRPO objective
    advantages = group_normalize(rewards)  # per-theorem normalization
    policy_loss = -sum(advantages * log_probs(proofs))

    # KL penalty to prevent reward hacking
    kl_penalty = beta * KL(current_policy || reference_policy)
    loss = policy_loss + kl_penalty

    # Multi-task: interleave with self-correction task
    # (50% whole-proof, 50% self-correction, per Goedel-V2)

    loss.backward()
    optimizer.step()
    slime.sync_weights_to_sglang()
```

Reward hacking guard:
```
Reject proof-search tactics that contain:
  sorry / admit tokens

Reject final whole-proof artifacts that contain:
  sorry / sorryAx
  unauthorized axioms not in the approved Mathlib axiom set
  unsafe proof escapes (e.g. unsafeEval, Lean.ofScientific abuse)
  wrong env_profile (proof verified on different Mathlib commit)

Do NOT reject noncomputable:
  Many legitimate classical Mathlib proofs involve noncomputable
  definitions. Rejecting noncomputable discards valid mathematics.
```

### Training Stage Exit Criteria

Calendar estimates are intentionally deferred until Phase -1 produces measured
throughput, sequence-length distributions, memory headroom, rollout rate, Lean
step/sec, verified proofs/hour, and weight-sync overhead.

```
Phase -1 exits when:
  resource_profile_manifest.json exists for SFT, whole-proof EI,
  search-based EI, and GRPO.

Stage 1 exits when:
  SFT improves Lean syntax validity, valid tactic rate, direct pass@k,
  and self-correction success over the base model.

Stage 2 exits when:
  whole-proof EI frontier stabilizes or marginal verified proofs/hour drops
  below the configured threshold for two consecutive iterations.

Stage 3 exits when:
  search proofs_per_10k_calls plateaus across two iterations, or the
  pass_rate=0 queue stops yielding verified proofs under the current budget.

Stage 4 runs only when:
  target theorem buckets have nonzero pass rate and GRPO memory fit passes.

Cycle:
  checkpoint v4 becomes the candidate starting point for the next EI cycle
  only if held-out evals and solved@budget curves improve without contamination.
```

---

## 8. Key Metrics

```
Search quality:
  proof_success_rate          % of theorems proved per EI iteration
  search_proofs_per_10k_calls efficiency of tree/search execution
  replay_buffer_size          total verified proofs in A-type store
  value_function_auc          AUC on state_value_labels held-out set
  step_her_multiplier         proved step rows / root witness step rows
  render_her_candidate_mult   rendered subproof candidates / verified root proofs
  render_her_verified_mult    verified rendered subproofs / verified root proofs

Training metrics (W&B):
  pass_at_1                   direct generation success rate
  pass_at_32                  sampling-based success rate
  grpo_reward_mean            average reward per GRPO batch
  frontier_size               theorems in 0 < pass_rate <= 0.75 range

Infrastructure metrics:
  kimina_cache_hit_rate        should be > 0.90
  kimina_worker_utilization    should be > 0.70 during search
  tactic_latency_p50/p95       Kimina execution time
  weight_sync_time             Megatron→SGLang sync duration
  gpu_utilization              > 0.80 during training phase

Evaluation benchmarks:
  miniF2F test split (pass@1, pass@32)
  LeanDojo novel_premises split (primary: hardest split)
  PutnamBench (after Stage 3, aspirational)
```

---

## 8.5 Evaluation Protocol

### Eval ownership boundary

Evaluation splits across the two repos along the same line as everything
else: LeanFoundry eval measures what the infrastructure does given a fixed
model. Training repo eval measures how the model improves across training
iterations. These are different questions and must not be conflated.

```
LeanFoundry eval (infra repo owns):
  solved@budget curves — given a fixed model and fixed search algorithm,
    how many theorems are proved as tactic budget increases?
  proofs per 10k Lean calls — search efficiency across algorithm variants
  Search compute curves — state-token load/tactic/save latency, cache hit rates
  Search algorithm comparisons — direct vs tree PUCT vs tree best-first now;
    beam/MCGS variants later, all run against the same model checkpoint
  Infra throughput metrics — Kimina step/sec, queue wait, worker utilization
  Benchmark loaders, Kimina verification, eval artifact schemas

Training repo eval (training repo owns):
  pass@k progression across checkpoints
  Frontier bucket evolution per EI round
  Data flywheel curves — cumulative verified proofs, HER multiplier
  Benchmark comparison against external systems
  Checkpoint selection decisions
```

The training repo calls LeanFoundry's eval runners with a model endpoint
and receives structured artifact manifests. It never implements Lean
verification or search execution. The infra repo never imports checkpoints
or knows about training stages — it receives a PolicyClient endpoint and
a benchmark spec and produces eval artifacts.

Every eval run writes an artifact manifest:

```json
{
  "run_id": "eval_2026_05_05_model_v2",
  "infra_git_sha": "9a31...",
  "training_git_sha": "c81d...",
  "model_checkpoint": "model_v2",
  "env_profile": "lean4.29.1_mathlib_5e932f97",
  "benchmark": "miniF2F-test",
  "benchmark_commit": "...",
  "mode": "direct",
  "k_values": [1, 2, 4, 8, 16, 32, 64, 128],
  "sampling": {
    "temperature": 0.8,
    "top_p": 0.95,
    "max_tokens": 32768
  }
}
```

### Evaluation Modes

Four modes, not one:

```
1. direct
   theorem statement → whole proof, no feedback
   metric: pass@k (k = 1, 2, 4, 8, 16, 32, 64, 128)

2. self_correct
   initial proof attempt → Kimina errors → revision, 1-2 rounds
   metric: pass@k and pass@k per revision count

3. mcts_state_token
   Kimina/Pantograph state-token backend, stateless at the API level,
   load-balanced across proof-state expansion items
   metric: solved@budget, proofs per 10k Lean calls, latency breakdown
   (queue vs goal_load vs tactics loop vs goal_save)
```

### Benchmark Suite

```
Primary dev eval (used during training to guide decisions):
  LeanDojo novel_premises validation split

Primary final eval (reported in releases):
  LeanDojo novel_premises test split
  miniF2F test split

Secondary final eval (aspirational, add as system matures):
  ProofNet (if compatible with our env_profile)
  PutnamBench (after Stage 3 search-based training)
  MathOlympiadBench (360 olympiad problems, Goedel-V2 released)
    → eval-only, never training data
    → re-verify all statements under our env_profile before use
```

Goedel-V2 reference numbers for comparison:
- miniF2F test: 84.6% pass@32 (8B), 88.1% pass@32 (32B standard),
  90.4% pass@32 (32B self-correction)
- PutnamBench: 86 problems at pass@184

When comparing to Goedel-V2 numbers, note whether env_profiles match.
Their repo uses mathlib4 @ 2f65ba7 under Lean 4.9. If our env_profile
differs, label comparisons as "different verifier environment."

### Pass@k Protocol

Generate K_max samples once per theorem, compute all pass@k from the
same pool. Never regenerate for different k values.

```
K_max = 128  for routine eval
K_max = 1024 for expensive final scaling runs only

Report k = 1, 2, 4, 8, 16, 32, 64, 128
```

For each theorem, solved at k = any(verified[i] for i in range(k)).

When K_max > k, use unbiased estimator:

```python
# n = total samples, c = verified successes
pass_at_k = 1 - comb(n - c, k) / comb(n, k)
```

### Search Compute Curves

For tree/search evaluation, pass@k is the wrong primary metric. Search uses
Lean tactic calls as the budget, not proof samples. Report:

```
Budgets: 50, 100, 250, 500, 1000, 2000 tactic calls

Metrics:
  solved@budget             % theorems proved within budget
  proofs_per_10k_calls      search efficiency
  median_calls_per_solved   cost of a successful proof
  valid_tactic_rate         % tactics accepted by Lean (not error)
  unique_state_rate         state diversity in search tree
  average_proof_depth       depth of found proofs
  value_auc                 how well value function ranks states
  value_calibration_ece     calibration error of value estimates
```

These measure whether training-time search is genuinely improving search
efficiency, which is the core infrastructure claim of this project.

### Progression Curves

LeanFoundry (infra repo) produces and owns:

```
Curve 3: search solved% vs tactic budget
  x = budget (tactic calls), y = solved %
  one line per checkpoint (isolates search infrastructure contribution)

Curve 6: infra throughput
  x = time
  y = Kimina step/sec, cache hit rate, worker utilization, queue wait p95
```

Training repo produces and owns (consuming infra eval artifact manifests):

```
Curve 1: pass@1 and pass@32 across checkpoints
  x = training stage (base → SFT → whole-EI → search-EI → GRPO)
  y = miniF2F test pass rate

Curve 2: pass@k scaling per checkpoint
  x = k, y = benchmark success rate
  one line per checkpoint

Curve 4: frontier bucket evolution
  x = EI iteration
  y = count of theorems in:
      pass_rate = 0 (search queue)
      0 < pass_rate <= 0.75 (active frontier)
      pass_rate > 0.75 (learned)

Curve 5: data flywheel
  x = EI iteration
  y = cumulative verified proofs, search-found proofs, HER multiplier
```

### Evaluation Contamination Rules

1. miniF2F test, PutnamBench, MathOlympiadBench are never used for
   training, pass-rate bucketing, prompt tuning, or checkpoint selection.

2. miniF2F validation may be used during development, but all reported
   numbers must be test-only.

3. Any theorem whose proof appears in A-type training data is removed
   from held-out evaluation sets.

4. Autoformalized statements may be used for training but not for clean
   evaluation unless human-verified and assigned to a fixed eval split
   before any training begins.

5. All benchmark statements are re-verified under the exact eval
   env_profile before evaluation. Do not assume benchmark proofs are
   valid under our Mathlib commit.

---

## 9. Known Risks

**Risk: env_profile contamination**
External data (Goedel, DeepSeek proofs) verified on different Mathlib
commit. Silently produces training samples with invalid proofs.
Mitigation: mandatory Kimina re-verification of ALL external A-type data
under our env_profile before insertion. Reject without re-verification.

**Risk: Search finds only trivial proofs**
Replay buffer fills with easy Path-A examples or future step-HER rows.
Model learns to prove easy lemmas and stops improving on harder ones.
Mitigation: track proof complexity (search_budget_used). Filter out
trajectories with budget_used < 5 from tactic-policy training.
Use pass_rate bucketing to avoid overtraining on easy theorems.

**Risk: GRPO reward hacking**
Model finds proofs with sorry or unauthorized axioms.
Mitigation: sorry/admit is rejected at expansion attach-time, and final
`/exec/verify` rejects degenerate whole-proof artifacts.
Reference policy KL penalty prevents policy collapse.

**Risk: Weight sync stalls**
Megatron→SGLang sync takes too long, GPU idle during sync.
Mitigation: overlap sync with trajectory processing. During the ~10-30s
sync window, search can extract Path-A rows, compute state hashes, and write to
SQLite. Future HER extraction can use the same window. True idle time should be
< 5s.

**Risk: Env Backend worker pool exhausted**
The profiled worker pool saturates and new tactic calls queue beyond the p95
threshold.
Mitigation: monitor queue_wait_p95 and worker RSS. If queue_wait_p95 is
consistently > 200ms, reduce search parallelism, increase worker_pool_size if
RSS headroom allows, or move to Extension A scale-out.

**Risk: Tree-search memory overflow**
Long search trees for hard theorems exhaust RAM.
Mitigation: track node count, resident memory, and per-theorem expansion
profiles during real runs. Do not add `max_tree_nodes` to `SearchConfig`
until traces justify whether this is a semantic search budget or a separate
operational guard. If needed later, add a fail-closed operational cap and
persist enough diagnostics to tune it before introducing pruning.

**Risk: Later SFT/RL reduces diversity**
GRPO or fine-tuning improves pass@1 but reduces pass@32 and MCTS
expansion quality. Model converges to one proof style.
Mitigation: track both pass@1 and pass@32. If pass@32 drops > 20%
relative while pass@1 improves, apply checkpoint averaging before
the next EI round.

---

## 10. Repository Boundary and Release Contract

### Naming and Abstraction Principles

LeanFoundry's source code must not expose implementation names. Concrete
dependencies (Kimina, SGLang, Slime) are implementation details that may
change. The public API exposes only LeanFoundry's own abstractions:

```
Correct names in LeanFoundry source:   Incorrect (implementation leak):
  EnvBackend                             KiminaClient / kimina_url / server.Settings
  generate_rollout / TrainingRow         RLEngineBase / submit_samples
  SearchEngine                           ConcreteMCTSEngine / raw_mcts_search
  PolicyClient                           sglang_url
  /exec/step_batch                       /mcts/step_batch
```

- `lean_client.exec_models` is the canonical `/exec` wire schema and may be
  imported by EnvBackend, search helpers, replay lifecycle code, and tests.
  Only `leanfoundry/env_backend/kimina_backend.py` constructs
  `AsyncLeanExecBackend`; search, rollout, eval, and training code receive an
  `EnvBackend`, not a `KiminaClient`.
- LeanFoundry never imports the server package. No `server.settings`,
  `server.main`, `PantographManager`, or worker classes appear in LeanFoundry.
  The current server is an app process launched by `python -m server` or by
  `lean_client.launch_server`.
- `SGLang` does not appear in LeanFoundry core. It is isolated to the optional
  `[training]` Slime adapter and exposed to search only through `PolicyClient`
  / `ValueClient`.
- `MCTS` does not appear as a class name or endpoint name. The search
  algorithm type (MCGS, beam, direct) is a parameter to `SearchEngine`,
  not a hardcoded identity.
- `Slime` appears only in the optional `training` extra, docs, and
  `leanfoundry/slime/`. Core search/replay/eval imports do not import Slime.

This allows swapping any implementation without changing the public API.

### The Split

The two-repo structure reflects a clean conceptual boundary:

```
Infrastructure repo:
  Owns Lean execution, search, evaluation, schemas, replay storage.
  Model-agnostic. Anyone can point it at any model endpoint.

Training repo:
  Owns model choice, training framework (Slime/Megatron/SGLang),
  data recipes, checkpoints, and experiment reports.
  Demonstrates one concrete recipe on top of the infra.
```

Dependency direction is strictly one-way:

```
training repo → infra repo
infra repo    → never imports training repo
```

### Infrastructure Repo Contents

```
env_backend/
  EnvBackend protocol and implementation factory
  kimina_backend.py: the only adapter that imports lean_client
  optional launcher wiring around lean_client.ExecServerConfig and launch_server
  no imports from the server package

lean-client dependency:
  Installed from kimina-lean-server/packages/lean-client by pinned git SHA
  Provides AsyncLeanExecBackend (the façade consumers use), the underlying
  AsyncKiminaClient / AsyncLeanExecEnv / AsyncLeanExecBatcher layers,
  ExecServerConfig + launch_server (dev-only), and shared /exec Pydantic models

backend app process:
  Runs from the kimina-lean-server checkout or image via python -m server
  Exposes /exec/create_states, /exec/step_batch, /exec/cleanup, /exec/cancel,
  /exec/limits, /exec/stats, and legacy verification/checking endpoints
  Owns Pantograph workers, StateStore, lifecycle registry, admission limiter,
  lockfile, worker reuse, timeouts, and resource safety caps

proofsearch/
  SearchEngine protocol, build_engine(config), and SearchConfig
  direct.py: direct whole-proof and completion-with-feedback search
  and_or.py: AND/OR tree search with PUCT or best-first SelectionStrategy
  expansion/backprop/lifecycle helpers for EnvBackend.step(), cleanup, cancel
  Path-A extraction: policy_examples and value_labels from runtime tree
  value-label extraction, durable negation attempts, and persistent retries
  narrow optional proof rendering for direct/easy Path-B artifacts
  deferred: graph/MCGS and richer Path-B rendering

evals/
  Eval schemas, benchmark source loader, row-format adapter hook,
  fixed-model eval runner, pass@k/solved@budget metrics,
  artifact manifests, content hashes, and report generation
  future: concrete public-benchmark row adapters and deployment wiring

schemas/
  SQL migrations (theorems, a_type_data, trajectories, policy_examples,
  state_value_labels, formal_statements_staging, lifecycle outbox,
  extraction failures, negation attempts)
  Pydantic models for all data types
  Eval artifact schema

replay/
  ReplayStore protocol
  SQLiteReplayStore and deterministic row ids
  writer for theorem, trajectory, policy, value, A-type, extraction failure,
  lifecycle, and negation artifacts

slime/
  Optional `[training]` rollout adapter
  Pull-shaped generate_rollout entrypoint for Slime
  SGLang policy client, value-client wiring, row-to-Sample conversion,
  token/loss-mask construction, env-profile validation, and live smoke harness

docker/
  Env Backend image (backend SHA + env_profile hash in tag)
  env_profile build scripts (Lean + Mathlib at pinned commit)
```

### Training Repo Contents

```
configs/
  stage1_sft.yaml
  stage2_whole_ei.yaml
  stage3_search_ei.yaml
  stage4_grpo.yaml
  eval_final.yaml

rollouts/
  launch_slime_with_leanfoundry.py
  optional project subclass of leanfoundry.slime.SlimeRolloutRunner
  model-specific prompt/parse/reward/group hooks only

data_prep/
  load_leandojo.py
  load_leantree.py                  # optional; dataset choice owned here
  verify_external_a_type_data.py
  build_self_correction_data.py

scripts/
  train_sft.sh
  run_whole_ei.sh
  run_mcts_ei.sh
  run_grpo.sh
  run_eval.sh

reports/
  notebooks consuming infra eval artifact manifests
```

The training repo owns dataset choice and mixture weights, including whether
to ingest LeanTree. The infra repo owns proof-state semantics, EnvBackend
execution, replay validation, search, and eval. The training repo never calls
Lean directly. All Lean interaction goes through the infra repo's SDK and the
optional Slime rollout adapter:

```python
from leanfoundry.env_backend import EnvBackendConfig, make_env_backend
from leanfoundry.evals import FixedModelEvalRunner
from leanfoundry.proofsearch import (
    SearchAlgorithm,
    SearchConfig,
    run_search_batch,
)
from leanfoundry.slime import SlimeRolloutRunner
```

The concrete Kimina adapter is small and isolated:

```python
# leanfoundry/env_backend/kimina_backend.py
from lean_client import AsyncLeanExecBackend

class KiminaEnvBackend(EnvBackend):
    async def connect(self) -> None:
        # One façade owns the HTTP client, proof-state env, and step batcher.
        self._backend = await AsyncLeanExecBackend.connect(
            self.base_url, env_profile=self.env_profile
        )
```

All other LeanFoundry modules depend on `EnvBackend`; this adapter is the only
place that knows the current backend is Kimina-shaped.

### PolicyClient: The API Boundary

The search engine in the infra repo depends only on an abstract protocol,
not on SGLang or any specific inference framework:

```python
class PolicyClient(Protocol):
    async def sample_proofs(
        self,
        prompts: Sequence[str],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
    ) -> list[list[str]]: ...

    async def sample_tactics(
        self,
        states: Sequence[FactorizedProofState],
        *,
        n: int,
        params: PolicySamplingParams | Mapping[str, Any] | None = None,
        context: Sequence[PolicyContext] | None = None,
    ) -> list[list[str]]: ...

class ValueClient(Protocol):
    async def estimate(
        self,
        states: Sequence[FactorizedProofState],
    ) -> list[float]: ...
```

The training repo or LeanFoundry's optional Slime adapter can implement these
protocols with SGLang, vLLM, Transformers, an API model, or a rule-based system
for ablations. Policy sampling and value estimation are intentionally separate
interfaces.

### Versioning Contract

The training repo pins the infra repo by exact git SHA:

```yaml
# infra.lock (in training repo root)
infra_repo: github.com/your-org/lean-agent-infra
infra_git_sha: 9a31c7...
env_backend_image: ghcr.io/your-org/kimina-lean-server:9a31c7-env2f65ba7
lean_client_ref: 9a31c7...
env_profile: lean4.29.1_mathlib_5e932f97
```

All trajectories in the database store the infra SHA and env_profile
that produced them. All eval manifests store infra SHA + training SHA
+ model checkpoint SHA. This prevents "it worked on my machine" from
becoming the release story.

### Development Workflow

The **Docker image is the prioritized deployment path** for both dev and
release: it seals the expensive part (Lean toolchain via `setup.sh` + the
Mathlib build + the server's own venv) and exposes only an HTTP port, so the
consumer's environment needs nothing but the `lean-client` package. The
`Dockerfile` already defaults `LEAN_SERVER_MODE=exec` and `CMD python -m server`;
`compose.yaml` runs it. The real cost of standing up a server is the Lean/Mathlib
build, never Python packaging — which is exactly why it should never live inside
the consumer process.

Three ways to run the server, ranked:

```
1. Docker image (preferred, dev + release):
     docker run -e LEAN_SERVER_MODE=exec -e LEAN_SERVER_MAX_REPLS=8 \
       -p 8000:8000 projectnumina/kimina-lean-server:<tag>     # or: docker compose up
   Consumer venv holds only lean-client; zero shared environment.
   Release: pin the image by infra SHA + env_profile.

2. Server checkout with its own venv (when Docker is unavailable):
     uv sync --dev && uv run python -m server --workers 8 --port 8000
   A separate server-side environment (server deps + built Mathlib) and a
   separate process on its own host/container. LeanFoundry connects to the URL
   and never imports server modules.

3. lean_client.launch_server (dev-only, monorepo-bound):
   subprocess-spawns `python -m server`, so it only resolves when the target
   interpreter already has the server package (true in THIS monorepo, false for
   a downstream repo that pip-installed only lean-client). Not part of the
   stable consumer contract.
```

> **Current local state (2026-06-17):** only the `Dockerfile` exists in-repo —
> there is no pre-built image, and Docker is not installed on the dev machine.
> So local work uses option 2 (`uv run python -m server` from this checkout);
> building/pulling the image is the first step before treating Docker as the
> default. The consumer always reaches the server over HTTP regardless of which
> option launched it.

In all cases the training repo depends on `lean-client` (from
`packages/lean-client`, pinned by git SHA/tag) as its only Python import from
this backend repo; no server package publish/install is required downstream.
`connect()` round-trips `GET /exec/limits` (rejecting unbounded caps), which is
also the connectivity check before any real work.

---

# Part III: [EXTENSION A] Multi-Machine Scale-Out
> **Status: Off-main snapshot / future work after the 2026-07-01 split.
> Trigger: single-machine throughput is the bottleneck, not model capability.
> Current `main` has no `leanfoundry.scaleout` package, router CLIs, or
> `[scaleout]` extra. The pre-split implementation snapshot is preserved on
> `extensions/codex-full`; any future re-import needs fresh review and live
> e2e evidence. Function/package references below describe preserved
> snapshot/design material, not current `main`.**

## 11. What Changes at Multi-Machine Scale

Single machine: all communication is loopback or shared memory.
Multi-machine introduces three new problems:

**Problem 1: REPL scaling**
Lean execution (CPU-bound) needs to scale independently of GPU training.
On one machine the CPU:GPU ratio is fixed by hardware. At scale, add
CPU-only machines for Lean without buying GPUs.

**Problem 2: Routing**
With many Lean backend machines, requests need per-message routing with
a global queue. A naive load balancer causes connection pinning (the
Harmonic v1/v2 failure mode).

**Problem 3: Shared replay buffer**
Search processes on many machines all produce trajectories simultaneously.
Training needs a globally consistent replay buffer.

## 12. Multi-Machine Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Training Cluster                    │
│  Megatron across 3+ GPU nodes (NCCL via InfiniBand) │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  SGLang Cluster │  (2-4 GPU nodes, Slime-managed)
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  Shared Replay  │  PostgreSQL or Redis Streams
              │  Buffer         │  all search nodes write here
              └────────┬────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
  Search Node 1   Search Node 2   Search Node N
  (search, asyncio) (search, asyncio) (search, asyncio)
       └───────────────┼───────────────┘
                       │  TCP
              ┌────────▼────────┐
              │   REPL Router   │  Custom C++ (Harmonic v3 equivalent)
              │   (global queue)│
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
    Lean Backend 1  Backend 2    Backend N
    Env Backend     Env Backend  Env Backend
    (CPU-only,      (CPU-only,   (CPU-only,
     preemptible)    preemptible) preemptible)
```

## 13. REPL Router: Reproducing Harmonic v3

The most critical component to build. Harmonic's C++ router is not
open source but its full design is described in their Sep 2025 blog post.

**Key design principles from Harmonic v3:**

1. Simple binary protocol (not gRPC, not WebSocket)
2. Backends connect TO the router (inverted direction)
3. Global request queue with per-CPU tracking
4. No connection pinning: per-message routing

**Message format:**
```
| request_id (8 bytes) | command (1 byte) | response_count (2 bytes) |
| data_len (4 bytes) | data (...) |

Commands:
  0x01  REGISTER   backend → router: "I have N CPUs"
  0x02  REQUEST    client → router: "execute this tactic"
  0x03  RESPONSE   backend → router: "here is the result"
  0x04  FORWARD    router → backend: "execute this"
  0x05  DELIVER    router → client: "here is your result"
  0x06  HEARTBEAT  any → any: keepalive on idle connection
  0x07  CANCEL     router → backend: "cancel this request if still running"
```

The local frame-codec baseline is `RouterFrame`: `encode_router_frame(...)`
and `decode_router_frame(...)` implement this exact header in network byte
order and reject short frames, unknown command bytes, and length mismatches.
The payload is still opaque bytes here; command-specific payload schemas belong
to the later router adapter/service boundary.

**Why inverted backend connection direction:**

Normal load balancer (reverse proxy): router connects to backends,
needs health checks, service discovery, timeout management.

Harmonic's approach: backends connect TO the router and send REGISTER.
TCP disconnect = backend gone. No health checks or service discovery
needed. When a GCP preemptible instance is preempted, TCP drops,
router automatically re-queues in-flight requests.

**Router C++ pseudocode:**

```cpp
class REPLRouter {
    std::queue<Request> pending_queue;
    std::map<BackendId, BackendState> backends;
    std::map<uint64_t, ClientConn*> inflight;

    void on_backend_connect(Connection* conn) {
        auto msg = conn->read();
        assert(msg.command == REGISTER);
        backends[conn->id] = {
            .conn = conn,
            .total_cpus = msg.data.cpu_count,
            .idle_cpus = msg.data.cpu_count
        };
        drain_queue();
    }

    void on_client_request(Connection* client, Request req) {
        inflight[req.request_id] = client;
        auto backend = find_idle_backend();
        if (backend) {
            forward_to_backend(backend, req);
            backend->idle_cpus--;
        } else {
            pending_queue.push(req);
        }
    }

    void on_backend_response(BackendId id, Response resp) {
        auto client = inflight[resp.request_id];
        client->send(resp);
        inflight.erase(resp.request_id);
        backends[id].idle_cpus++;
        drain_queue();
    }

    void on_backend_disconnect(BackendId id) {
        // Re-queue in-flight requests from this backend
        for (auto& req : backends[id].inflight_requests)
            pending_queue.push(req);
        backends.erase(id);
        drain_queue();
    }

    void drain_queue() {
        while (!pending_queue.empty()) {
            auto backend = find_idle_backend();
            if (!backend) break;
            auto req = pending_queue.front();
            pending_queue.pop();
            forward_to_backend(backend, req);
            backend->idle_cpus--;
        }
    }
};
```

**Autoscaling algorithm (run every 60 seconds):**

```python
def autoscale(router_metrics, cluster):
    Lq   = router_metrics.queue_length
    Rmin = router_metrics.requests_last_minute
    Bmin = router_metrics.avg_backends_last_minute

    if Lq >= Rmin:
        # Queue will take > 1 min to clear. Scale to clear in Cm minutes.
        Cm = 5.0
        P = Rmin / max(Bmin, 1)          # requests per backend per minute
        target = (Rmin + (Lq / Cm)) / P
        cluster.set_min_replicas(int(target) + 1)
    else:
        # Queue draining fine. Let GKE CPU utilization autoscaling take over.
        cluster.set_min_replicas(1)
```

This algorithm reduced Harmonic's scale-up time from 2 hours to 10 minutes.
The key insight: GKE's default autoscaling only sees "CPUs are busy" — it
cannot see queue depth. This formula uses queue depth to determine how many
machines are actually needed.

The local baseline is `plan_router_scale(...)`: it accepts `RouterMetrics`
(`queue_length`, `requests_last_minute`, `avg_backends_last_minute`) and returns
an `AutoscaleDecision` with `target_min_replicas`, a reason, and the estimated
per-backend throughput. It is a pure decision helper; applying the decision to
GKE, Slurm, or another cluster manager remains deployment work.

The local router-state baseline is `RouterState`: `register_backend(...)`
adds a backend with a fixed CPU-slot capacity, `enqueue_request(...)` appends a
client request to the FIFO queue, `complete_request(...)` frees one in-flight
slot and drains pending work, `cancel_inflight_requests(...)` removes abandoned
in-flight work and drains pending work into the freed slots, and
`disconnect_backend(...)` removes a backend while requeueing its in-flight
requests. The helper deliberately has no socket service, client connection
table, backend state export/import, or payload transfer. Those remain the
deployment/router implementation; the
local helper only fixes the deterministic scheduling semantics that the router
service must preserve.

The reference router-service baseline is `AsyncRouterService`: it uses the
binary frame codec and the pure scheduler to route `REQUEST` frames from client
connections to registered backends, send assigned work as `FORWARD`, convert
backend `RESPONSE` frames into client `DELIVER` frames, and requeue in-flight
requests after backend disconnects. Backend `REGISTER` payloads are encoded as
`RouterBackendRegistration` JSON inside the binary frame. This is a local
correctness harness and future adapter target; it does not yet launch Lean
backends, export/import state, fetch URI payloads, provide production
connection hardening, or integrate with cluster autoscaling/metrics.

The router adapter baseline is `RouterEnvBackend` plus `RouterBackendWorker`.
`RouterEnvBackend` implements the normal LeanFoundry `EnvBackend` protocol for
clients by encoding lean-client request/response models as JSON payloads inside
router frames. `RouterBackendWorker` connects to the router as a backend,
decodes those payloads, calls an injected concrete `EnvBackend`, and returns
typed responses. The adapter covers limits, create_states, one-state
step_batch via `EnvBackend.step(...)`, verify, cleanup, cancel, and stats. It
does not alter the scheduler unit: one proof-state expansion is one router
request. It also does not provide Lean state export/import or remote payload
fetching; those remain separate backend/router integration work.

The reference process entrypoints are `leanfoundry-router` and
`leanfoundry-router-worker`. The first starts `AsyncRouterService` on a chosen
host/port; the second connects one worker to the router and builds its Lean
execution backend from `EnvBackendConfig`. These are stable commands for a
site supervisor to run. They do not include service discovery, restart policy,
TLS/auth, pager integration, or cluster autoscaler integration.

The local hardening baseline adds `RouterServiceSnapshot` and
`AsyncRouterService.snapshot()`: supervisors/tests can inspect connected
backends, total/idle backend slots, in-flight requests, pending requests,
active client requests, stored request frames, and assignment/delivery/requeue
drop counters. If a client disconnects before its request is assigned, the
router removes that pending request. If the request was already forwarded to a
backend, the router sends a `CANCEL` frame to that backend, removes the request
from scheduler state, and drains queued work into the freed backend slot.
`RouterBackendWorker` cancels the local task for the router request; if a
response races after cancellation, the router drops it because the request is no
longer in-flight. Concrete Lean backend cancellation is still best-effort and
depends on the injected backend's own cancellation behavior.

The optional local health baseline is `leanfoundry.scaleout.health`.
`router_health_report(...)` converts one `RouterServiceSnapshot` into a
readiness report; `/healthz` is liveness-only, `/readyz` can require at least
one registered backend slot, and `/metrics` renders the same snapshot fields in
Prometheus text format. `leanfoundry-router --health-port PORT` starts this
side server. It is intentionally a reference endpoint, not deployment-specific
monitoring, alert routing, auth, TLS, or autoscaler glue.

## 14. State Portability (Stateless Backends)

The key that makes multi-machine Lean execution work. Proof states travel
with requests rather than being stored on backends.

Harmonic found state files compress to ~8% of original size with zstd.

```python
# After running a tactic, export state and compress
state_bytes = lean_repl.export_state(state_id)
compressed = zstd.compress(state_bytes)   # 50MB → ~4MB typical
state_token = base64.b64encode(compressed).decode()

# Next request carries state inline
router.send({
    "command": "mcts_step",
    "state_token": state_token,
    "tactic": "ring"
})

# Backend decompresses and imports before executing
state_bytes = zstd.decompress(base64.decode(request.state_token))
lean_repl.import_state(state_bytes)
result = lean_repl.run_tactic(request.tactic)
```

The local baseline is `PortableStateRef`: a manifest for a state snapshot's
`state_id`, `env_profile`, codec (`raw` or `zstd`), payload location
(`inline_base64` or `uri`), SHA-256, raw size, and payload size. It validates
location-specific payload fields and exposes `compression_ratio`.
`make_inline_state_ref(...)` and `decode_inline_state_ref(...)` now implement
RAW inline payload round-tripping plus hash/size validation; ZSTD is supported
when the `[scaleout]` optional extra installs `zstandard`, and otherwise fails
closed with a runtime error.
`make_file_state_ref(...)` and `decode_file_state_ref(...)` now provide local
`file://` URI payload writes/reads with payload-size and decoded-state integrity
checks. `decode_http_state_ref(...)` and `decode_uri_state_ref(...)` add
read-only `http://` / `https://` payload fetches with the same payload-size,
codec, and decoded-state hash checks. This covers public or signed object-store
URLs that behave like HTTP(S) byte objects. Lean state export/import,
credentialed object-store clients, remote writes, lifecycle policy, router
payload transfer, and backend integration remain future/deployment work.

## 15. Distributed Replay Buffer

Single machine: SQLite (WAL mode).
Multi-machine: PostgreSQL or Redis Streams.

**PostgreSQL** (simpler, up to ~100 search nodes):
```python
async def save_trajectory(pool, trajectory):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO trajectories
            (id, theorem_id, env_profile, tactics, proof, model_version)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, trajectory.id, trajectory.theorem_id,
            trajectory.env_profile, json.dumps(trajectory.tactics),
            trajectory.proof, trajectory.model_version)
```

**Redis Streams** (higher throughput):
```python
# Search nodes publish
redis.xadd("trajectories", {
    "theorem_id": theorem_id,
    "tactics": json.dumps(tactics),
    "proof": proof,
    "model_version": str(model_version)
})

# Training nodes consume
entries = redis.xread({"trajectories": last_id}, count=256, block=1000)
```

## 16. Single → Multi Migration Path

The single-machine design was built to minimize migration friction:

```
Single machine               Multi-machine equivalent
────────────────────────────────────────────────────
Env Backend (localhost)  →   Env Backend pool behind REPL Router
Unix socket              →   TCP to router address
SQLite                   →   PostgreSQL or Redis Streams
SGLang (local)           →   SGLang cluster (Slime-managed)
Megatron (local GPUs)    →   Megatron across training nodes (NCCL)
```

The search process and MCTS algorithm code does not change at all.
The custom Slime rollout code does not change.
Only URLs in configuration files change.

Suggested migration order:
1. Move Lean backends to CPU-only preemptible machines + REPL router
2. Move replay buffer to PostgreSQL
3. Add training GPU nodes (Megatron scales via NCCL)
4. Add SGLang nodes (Slime router manages)

---

# Part IV: [EXTENSION B] Autoformalization Data Pipeline
> **Status: Core staging schema plus off-main snapshot / future work after the
> 2026-07-01 split.
> Do not build LLM drafting/retry/judge/dedup services until the core system
> produces satisfactory results on LeanDojo novel_premises split. Current
> `main` preserves staging headers; promotion gates, statement checking,
> formalizer/judge/dedup services, and draft/retry orchestration are
> off-main/future and need live staged-corpus/backend evidence. References
> below to those services describe preserved snapshot/design material, not
> current `main`.**

## 17. Why LeanDojo Alone Is Not Enough

LeanDojo's 98k theorems are sufficient to bootstrap, but Expert Iteration
exhausts useful signal after 10-20 iterations:

```
Iteration 1:  model proves 5k easy theorems → trains on them
Iteration 5:  those theorems are trivial, need harder ones
Iteration 15: most of LeanDojo below the model's frontier
```

Additionally, LeanDojo is entirely from Mathlib: biased toward certain
mathematical areas, no competition math, no graduated difficulty control.

Autoformalization produces a theorem pipeline that scales with model
capability, continuously providing theorems at the model's frontier.

## 18. Formalization Pipeline

```
Informal source (textbook, competition archive, research paper)
    ↓
Step 1: LLM translates statement to Lean 4 draft
    ↓
Step 2: Kimina /verify checks syntax and type correctness
    ↓ (on error)
Step 3: LLM receives errors, corrects draft (repeat up to N times)
    ↓ (on Kimina accept)
Step 4: Semantic judge LLM scores faithfulness (0-1)
    ↓ (if score > threshold)
Step 5: Deduplication check (embedding similarity)
    ↓
Insert into formal_statements_staging with all provenance fields
    ↓ (after manual spot-check or sufficient judge score)
Promote to theorems table as B-type data
```

The local baseline covers the deterministic contracts in this pipeline. A
`FormalStatementStagingRecord` must carry the Lean `header` used during syntax
checking. `run_formalization_draft_loop(...)` provides the local draft/retry
orchestration: an injected `Formalizer` drafts one Lean statement, the injected
statement verifier checks it, verifier messages are passed back as feedback
for the next attempt, and an accepted result carries a syntax-checked staging
row. `verify_staging_statement_code(...)` builds the checked Lean snippet by
adding a `sorry` body when needed, `KiminaStatementVerifier` normalizes
lean-client `api_check` responses into `StatementVerificationResult`, and
`staging_record_with_syntax_result(...)` updates the row's `syntax_checked`
field. `HTTPSemanticJudge` provides the local semantic-judge service contract:
it sends staged informal/formal statement pairs to a JSON endpoint, validates a
score in `[0, 1]`, and `staging_record_with_semantic_judge_result(...)`
populates the row's `semantic_judge_score`. `evaluate_promotion(...)` requires
syntax acceptance, a semantic judge score above the configured threshold, and a
dedup hash by default. If the row passes, it returns a `TheoremRecord` with the
same `lean_statement`, `informal_statement`, `env_profile`, and `header`;
otherwise it returns machine-readable rejection reasons. The local helpers
`formal_statement_dedup_hash(...)` and `staging_record_with_dedup_hash(...)`
populate exact normalized statement/header/profile hashes for cheap duplicate
filtering; this is not semantic or embedding-similarity dedup.
`HTTPEmbeddingDeduplicator` provides the local embedding-dedup service
contract: it sends the staged statement plus a similarity threshold to a JSON
endpoint, accepts only threshold-consistent `unique` / `duplicate` responses,
and returns a normalized `EmbeddingDedupResult`. When
`PromotionGateConfig(require_embedding_unique=True)` is enabled, promotion
rejects missing, errored, or duplicate embedding-dedup results. The baseline
now includes an HTTP formalizer service/prompt contract, but still does not
implement a deployed formalizer checkpoint, real judge model calibration, real
embedding model/index, corpus calibration, service deployment, or live
staged-corpus runs.

## 19. Difficulty Estimation

Do not add all formalized statements with equal priority. Estimate
difficulty to control the training curriculum:

```python
async def estimate_difficulty(theorem, model, env_backend, quick_budget=20):
    proof = await search(theorem, model, env_backend, budget=quick_budget)
    if proof and proof.tactics_used <= 5:
        return "easy"      # use only for SFT warmup data
    elif proof:
        return "frontier"  # high value for Expert Iteration
    else:
        return "hard"      # queue for future iterations
```

The local mapping helper is `estimate_difficulty_from_quick_search(...)`: given
a quick-search `SearchResult`, it emits both a bucket (`easy`, `frontier`,
`hard`) and the numeric `difficulty_estimate` stored on `TheoremRecord`.
Producing the quick-search result still requires a real model/backend run.

## 20. Informal Source Priority and Scaling Roadmap

Extension B is deferred. It is not a hidden Stage 1 dependency and should not
appear in the core pipeline diagram. Activate it only after the LeanDojo-based
core pipeline has plateaued and contamination rules are stable.

**Short term after activation: baseline formalizer staging**

```
Pipeline: LLM draft → /verify statement check → semantic judge → dedup → staging table
Sources: MATH dataset, AoPS common problems, Putnam/USAMO archives,
         Lean documentation examples
Output: B-type statements in formal_statements_staging, not direct training data
Promotion: fixed split assignment + env_profile verification + contamination check
```

**Mid term: formalizer + checker duo**

Train two specialized models that improve each other:

```
Formalizer: informal statement → Lean 4 draft
  Reward signal: /verify accept rate + checker faithfulness score
  Training: same EI framework as the prover — search over Lean 4 drafts

Faithfulness checker: (informal, Lean 4 statement) → faithfulness score
  Training: human-annotated pairs + model-generated negatives
  Role: provides reward signal to formalizer training loop
```

The formalizer + checker duo is structurally symmetric to the prover +
verifier pair. The same LeanFoundry infrastructure can drive formalizer
training with a different PolicyClient and a different reward function.

**Long term: arXiv-scale data**

Work in the direction of arXiv-scale formalization only after the short- and
mid-term pipelines produce reliable, non-leaky B-type theorem streams. The core
technical challenge is dependency resolution: arXiv theorem statements often
reference paper-specific notation and definitions that must be expressed as
Lean imports or local definitions before type-checking.

This is a long-term research direction, not a short-term engineering task.
Trigger: model has saturated the mid-term theorem pool and formalizer quality
is high enough to yield meaningful throughput.

---

# Extension C: Test-Time Training Module
> **Status: Off-main snapshot / future work after the 2026-07-01 split.
> Current `main` has no `leanfoundry.ttt` package, TTT schemas, TTT replay
> table, TTT adapter, or TTT orchestration loop. The downstream training repo
> still owns LoRA optimizer execution and concrete SGLang reload; MCGS or
> another selected per-problem search source remains future work. References
> below to TTT APIs describe preserved snapshot/design material, not current
> `main`.**

## 21. Motivation

Aristotle's Test-Time Training (TTT) fine-tunes the model on search traces
found during inference for a specific hard problem, then re-runs search with
the updated model. It is the highest-effort per-problem technique and most
useful for olympiad-level targets where no standard training signal exists.

TTT is blocked on components beyond the current Path-A baseline:
- search traces rich enough for per-problem fine-tuning
- node-general proved-node extraction or another path that can train from a
  target theorem's local traces
- a PolicyClient/model-adapter contract for loading an updated LoRA without
  restarting the search loop

The last item now has a local contract baseline:
`leanfoundry.ttt.TTTAdapter` receives `TTTAdapterTrainingRequest` objects and
returns `TTTAdapterTrainingResult` objects; `AdaptablePolicyClient` exposes the
policy-side `with_adapter(adapter_id)` hook. `TTTConfig`, `TTTRoundTrace`, and
`TTTSessionTrace` keep per-problem run metadata and make trace promotion to the
main replay buffer opt-in.

TTT orchestration belongs in LeanFoundry (infra repo) because it is
model-agnostic — the same loop works for any PolicyClient implementation.
The LoRA fine-tuning step is delegated to the training repo via an
interface; the infra repo does not own an optimizer.
The local implementation is `run_ttt_session(...)`: callers inject one
search-round function and one sample extractor, so the loop can run with current
tree search traces today while still allowing a future MCGS search source. The
orchestrator builds `TTTAdapterTrainingRequest`s, validates adapter results,
reloads the returned adapter id, binds the policy view through
`with_adapter(...)`, and records a `TTTSessionTrace`. It deliberately does not
write TTT traces to the main replay buffer automatically.

The local promotion gate is `evaluate_ttt_trace_promotion(...)`. It is opt-in:
`TTTConfig.promote_traces_to_main_replay` must be true unless a caller supplies
a looser policy. The default gate also checks the trace namespace/base
checkpoint against config, optionally checks the expected env profile, rejects
duplicate trace keys supplied by the caller, rejects failed stages, and promotes
only solved sessions with at least one successful adapter reload. A passing
decision returns a copy of the trace with `promoted_to_main_replay=True`.
Persisting the promoted trace is an explicit caller-owned write path:
`ttt_trace_replay_record_from_decision(...)` builds a deterministic
`TTTTraceReplayRecord`, and `persist_promoted_ttt_trace(...)` writes it through
`ReplayStore.put_ttt_trace_replay_records(...)` into SQLite
`ttt_trace_replay`. This stores the trace and promotion decision as replay
artifacts only; derived policy/value/A-type samples still require a separate
dataset policy.

## 22. TTT Interface

```python
class TTTAdapter(Protocol):
    async def fine_tune(
        self,
        request: TTTAdapterTrainingRequest,
    ) -> TTTAdapterTrainingResult:
        """Fine-tune a per-problem adapter and return its reload id."""
        ...

    async def reload(self, adapter_id: str) -> None:
        """Make an adapter id active for subsequent policy calls."""
        ...


class AdaptablePolicyClient(PolicyClient, Protocol):
    def with_adapter(self, adapter_id: str) -> PolicyClient:
        """Return a policy view that serves through adapter_id."""
        ...
```

The training repo implements `TTTAdapter` using SGLang's LoRA loading API.
LeanFoundry calls it; LeanFoundry does not contain optimizer code.

## 23. TTT Loop

```python
async def test_time_train(
    theorem: TheoremSpec,
    policy: PolicyClient,
    adapter: TTTAdapter,
    env_backend: EnvBackendClient,
    config: TTTConfig,
) -> ProofResult | None:

    session_id = new_ttt_session_id(theorem)
    current_adapter_id = None
    for round in range(config.max_rounds):
        # 1. Search with current policy
        result = await mcgs_search(theorem, policy, env_backend,
                                   budget=config.search_budget_tactic_calls)
        if result.proved:
            return result

        # 2. Extract training signal from search traces (HER)
        samples = extract_her_samples(result.search_graph)
        if not samples:
            break

        # 3. Fine-tune LoRA adapter on traces
        request = TTTAdapterTrainingRequest(
            session_id=session_id,
            theorem_id=theorem.id,
            env_profile=theorem.env_profile,
            round_index=round,
            base_checkpoint=config.base_checkpoint,
            parent_adapter_id=current_adapter_id,
            lora_rank=config.lora_rank,
            steps=config.fine_tune_steps,
            adapter_namespace=config.adapter_namespace,
            samples=samples,
        )
        train_result = await adapter.fine_tune(request)
        current_adapter_id = train_result.adapter_id

        # 4. Reload policy with updated adapter
        await adapter.reload(current_adapter_id)
        policy = policy.with_adapter(current_adapter_id)

    return None
```

## 24. TTT Scope

TTT is an evaluation-time capability, not a training-time technique.
It does not replace Stages 1-4 of the training pipeline. It is invoked
during evaluation on hard targets (olympiad problems, PutnamBench) after
the standard training pipeline is complete.

TTT results are not folded back into the main A-type training set without
careful deduplication and env_profile verification. Promoted TTT session
traces may be stored in `ttt_trace_replay` after the local promotion gate, but
that table is a trace-artifact ledger, not proof data. Any later conversion of
TTT traces into training rows requires the same provenance policy as any
external data.

---

# Part V: [EXTENSION D] Controlled Algorithm Ablation Study
> **Status: Training-repo / future work after the 2026-07-01 split. Current
> `main` has no ablation-plan schemas, budget guard, SQLite budget meter, or
> budget CLI. Run after Stage 1 checkpoint and a hygiene-passed curated pool
> exist. The training repo owns optimizer execution and checkpoint production.
> This Part is additive — it does not change Stages 2-4, their dynamic frontier
> filtering, or their adaptive exit criteria. Those remain the production "how
> far can we go" recipe. Extension D answers a different, narrower question
> under its own frozen conditions, run alongside the core pipeline rather than
> replacing any part of it. References below to ablation/budget APIs describe
> preserved snapshot/design material, not current `main`.**

## 25. Motivation and Relationship to the Core Pipeline

Stages 2-4 are optimized for one thing: maximize solved@budget on the
held-out splits, by any combination of whole-proof EI, search-based EI, and GRPO,
with the frontier and exit criteria adapting to the live policy at every
iteration. That design question is "how far can we go." It is deliberately
not a controlled comparison — Stage 3's queue is defined as Stage 2's
leftovers, exit criteria are adaptive, and nothing about the pipeline holds
still long enough to isolate why a given combination works.

Extension D asks a different question: holding the base checkpoint, the
theorem-to-round assignment, and total compute fixed, which training
target produces the best prover? The axis is **training data shape**, not
rendered proof discovery:

```
Lineage B — whole-proof target:
  theorem statement -> complete Lean proof. The model's own proof is verified
  once by /exec/verify. No tree rendering is involved.

Lineage A — step-policy target:
  Lean proof state -> next tactic. Tree search supplies the proof states and
  proved tactic edges. The search algorithm's selection/value/backup decisions
  are distilled into a step policy. No whole proof is rendered from the tree.

Mixed target:
  train one checkpoint on both whole-proof and step-policy rows, optionally with
  self-correction, reflection, and state-comment enhancements.
```

This requires arms that do not adapt their own curriculum or escalate their own
queues — the opposite of what makes Stages 2-4 effective in production. Hence a
separate Part, a separate frozen curriculum, and its own smaller-scale arms,
rather than instrumentation bolted onto the core pipeline.

## 26. Frozen Curriculum

Stage 2/3/4's dynamic pass_rate-based filtering is left exactly as
specified in §7 for the production pipeline. Extension D defines a
**separate, frozen** curriculum used only by its own arms:

```
1. From the shared Stage 1 checkpoint, compute whole-proof pass@N
   (fixed N, e.g. 32) once for every theorem in the curated pool.

2. Assign each theorem to a difficulty bucket and a training round
   from that single pass@N pass. Freeze this assignment.

3. Every arm in Extension D trains on the identical theorem-to-round
   mapping for every round. Only the algorithm applied to that fixed
   set varies between arms.
```

This is the fix for the coupling problem in the production pipeline:
there, Stage 3's queue is defined as Stage 2's pass_rate=0 leftovers, so
"what a given stage trains on" depends on what earlier stages already
did. That dependency is a feature for "how far can we go" and a confound
for a controlled comparison. Extension D removes it by construction, at
the cost of not adapting — which is exactly the cost that makes it
unsuitable as a replacement for Stages 2-4.

LeanFoundry owns the deterministic construction helper, not the model sweep:
`build_frozen_curriculum_from_pass_sweep(...)` takes aligned theorem /
`SearchResult` pairs from a direct whole-proof run, verifies that each theorem
has direct verification attempts for candidate indices `1..N`, computes the
observed accepted-candidate rate, assigns default buckets
`unsolved/hard/medium/easy`, and rank-splits the fixed pool into rounds. Weak
or partial sweep evidence fails closed instead of silently entering the
curriculum. Producing those results on a real checkpoint and executing the
resulting training arms remains the downstream training/deployment job.

## 27. Algorithm Arms

```
Arm W       — whole-proof EI / RL only (§7 Stage 2 mechanics, no tree data,
              frozen curriculum). Training rows are lineage B:
              prompt=statement, response=verified whole proof.

Arm W+SC    — Arm W, plus self-correction (Format 3: failed proof +
              Lean errors → revision), and optional tactic-state comments in
              whole-proof data. Still no tree-generated step rows.

Arm T-step  — Tree-search EI. Run the implemented AND/OR tree search on the
              frozen curriculum and train only lineage-A step rows:
              prompt=proof_state, response=proved tactic. Include value labels
              if `value_mode` owns them. Rendering from tree is not used.

Arm T-noval — Same lineage-A target as T-step, but with no value client / no
              value loss and a policy-prior or structural selector. This tests
              whether value-guided search improves the quality of step data,
              not whether search can render more whole proofs.

Arm Mix     — Multi-format training on lineage-B whole proofs + lineage-A
              tree step rows, optionally with self-correction/comment
              enhancements. This is the production-relevant question: can mixed
              data match or beat either pure target?
```

Arms are seeded from the identical Stage 1 checkpoint. None of them
feed into or modify the production Stage 2-4 pipeline's own state;
each Extension D arm keeps its own replay buffer and checkpoint
lineage. In the local contract this is represented by
`ExperimentArmSpec.replay_namespace` and
`ExperimentArmSpec.checkpoint_namespace`. Tree-value arms can declare bonded or
unbonded value serving with either numeric-head or natural-language boxed-score
outputs; `T-noval` is explicitly forbidden from declaring value serving.

## 28. Compute Ledger and Budget Enforcement

Three meters, tracked per arm per round:

```
generation: prefill + decode tokens (SGLang), convertible to FLOPs
training:   tokens through the optimizer (Megatron)
verifier:   per-request Lean CPU-seconds and wall time, from /exec
            diagnostics — measured on the worker, excluding queue wait
```

Every request and policy call carries a `budget_account_id`; a metering
service decrements the per-cell budget and refuses requests once
exhausted. This is enforcement, not just measurement — without hard
caps, the search arms can silently overspend relative to Arm W and the
comparison stops being interpretable.
`BudgetLedgerEntry` records the required generation, training, and verifier caps
per arm and frozen round. The schema verifies that every arm/round/meter cell is
present and that ledger entries use the arm's own `budget_account_id`.
The local guard `check_budget_request(...)` applies one ledger cell to one
observed usage snapshot: it verifies the request account id, computes remaining
budget before and after the proposed request, and refuses hard-cap overruns.
`SQLiteBudgetMeterStore` is the local durable meter: it creates/verifies ledger
cells in SQLite, stores `used` per arm/round/meter, and reserves usage inside a
`BEGIN IMMEDIATE` transaction before updating the counter. This is enough for
local runs and single-file coordination. `leanfoundry-budget-meter` exposes the
same store to scripts: `init` loads a JSON list of `BudgetLedgerEntry` objects
or an object with `budget_ledger`, `reserve` atomically spends one request and
returns nonzero on refusal, and `snapshot` prints durable usage for one cell.
Multi-node metering services, trainer-side wiring, worker-side measurement
collection, and production DB deployment remain deployment/training work.

For cross-architecture pass@K reporting, adopt DeepSeek-Prover-V1.5's
budget-alignment convention as the primary axis: K = total proofs
generated for whole-proof arms (W, W+SC), K = attempts × tactics per expansion
× expansion iterations for tree-step arms (T-step, T-noval), and both ledgers
for Mix. Report the three-ledger breakdown
secondarily — invocation counts alone hide the cost of macro-tactics
(`aesop`, `nlinarith`, `simp_all`), which can each absorb a single
"node" worth of K while consuming a highly variable amount of actual
Lean CPU time. Log macro-tactic call rate per arm as a covariate for
this reason.

## 29. Crossed Evaluation Design

Evaluating each arm only in its native inference mode confounds
"did this training algorithm produce a better core policy" with "does
this inference protocol help regardless of how the policy was trained." The
valid eval modes depend on the training target's prompt distribution:

```
                    native eval                         secondary eval
Arm W           |   whole-proof pass@K                  optional hybrid wrapper
Arm W+SC        |   self-correct / whole-proof pass@K   optional hybrid wrapper
Arm T-step      |   interactive/tree solved@budget      no direct pass@K unless
                                                        whole-proof format trained
Arm T-noval     |   interactive/tree solved@budget      same as T-step
Arm Mix         |   both pass@K and solved@budget       compare both heads/modes
```

Diagonal cells are the deployment-relevant numbers: this training
recipe, deployed in its own native mode, at matched budget. Off-diagonal
cells are diagnostics only and must not be treated as the main comparison if the
prompt format was never trained. DeepSeek-Prover-V1.5's published RMaxTS result
(whole-proof-RL policy + search wrapper: 60.2% -> 63.5% on miniF2F) is a useful
external sanity-check reference for the Arm W optional hybrid cell before
trusting this study's own numbers.

All results are stratified by required-proof-length / difficulty bucket
(from the frozen §26 assignment). The predicted result is a
difficulty-dependent crossover, not a uniform ranking: outcome-only
arms (W, W+SC) are expected to match or beat the search arms on short
proofs, where direct sampling already succeeds often enough to get
nonzero reward, and to lag increasingly on long, compositional proofs,
where whole-proof reward is exactly zero until the model can nearly solve the
whole thing. T-step can still emit local step positives when search proves
subgoals, and Mix tests whether those local rows complement whole-proof
training instead of replacing it.

## 30. Hygiene Defaults for the Curated Pool

Any autoformalized statement entering this study's pool must already
have passed Extension B's standard promotion gate plus the negation
check (`try_negation`, §3.5.1 / concern G5) before being added: attempt
the negation, and retire or relabel any statement that proves false or
that double-proves (both the statement and its negation succeed,
indicating a vacuous/inconsistent hypothesis set) before promotion to
this study's frozen pool. This is a pool-construction requirement
applied once, upstream of Extension D, not a variable under test here.
Extension D's arms are compared on training algorithm; statement-level
contamination tolerance is a separate, already-settled question and
should not be allowed to vary uncontrolled across arms by accident.

## 31. Outcome Variables

```
whole-proof pass@K per generation/training/verifier budget (W, W+SC, Mix)
interactive/tree solved@budget per ledger unit (T-step, T-noval, Mix)
compute-to-asymptote (shift) vs. final asymptote, per arm/mode
macro-tactic call rate per arm (covariate for K-alignment, not an outcome)
step valid-rate and proof-progress rate for lineage-A policies
value AUC / calibration error (T-step and Mix only when value labels are trained)
step-HER multiplier: proved step rows per root witness step row
optional rendered-HER candidate/verified multiplier (artifact path only)
```

## 32. Scope

Run the full 5-arm x difficulty-stratified matrix at a smaller model
size than the production §5.2 base model, given compute constraints;
confirm the headline crossover (Arm W vs. T-step/Mix, on the longest
difficulty bucket) at full scale only for the cell(s) that matter most
once the smaller-scale results are in. Two to three seeds on headline
cells; single-seed acceptable for diagnostic arms (W+SC, T-noval) when they are
used to explain the topline rather than establish it.

This Part does not modify Stage 1's checkpoint, Stage 2-4's mechanics,
or the production pipeline's own replay buffer and exit criteria in
any way. It is a separate study that reads the same Stage 1 checkpoint
and the same hygiene-passed pool, and writes to its own buffers.

---

## References

**Systems and Infrastructure**

[1] Harmonic. "Running Lean at Scale." Engineering Blog, Sep 2025.
    https://harmonic.fun/news/lean-at-scale/
    → Source for REPL service v0-v3 design, inverted backend connection
      pattern, global queueing, autoscaling, and state compression.

[2] Kimina Lean Server. project-numina/kimina-lean-server, 2025.
    https://github.com/project-numina/kimina-lean-server
    Technical report: arXiv:2504.21230
    → Source for REPL worker pool, header/body split, LRU header reuse,
      batch verification, and infotree extraction.

[3] Lean REPL. leanprover-community/repl.
    https://github.com/leanprover-community/repl
    → Underlying REPL used by Kimina. Relevant for whole-file verification
      and possible future direct REPL proof-state work.

[3a] Pantograph / PyPantograph. stanford-centaur/PyPantograph.
     https://github.com/stanford-centaur/PyPantograph
     → Source for tactic-level goal_start, load_sorry, goal_tactic,
       goal_save, and goal_load used by the v0 Env Backend worker.

[4] Slime. THUDM, 2025.
    https://github.com/THUDM/slime
    → RL post-training framework connecting Megatron training, SGLang rollout,
      custom data generation, data buffer, and weight synchronization.

[5] Qwen3.6. QwenLM/Qwen3.6, 2026.
    https://github.com/QwenLM/Qwen3.6
    Model: Qwen/Qwen3.6-27B on Hugging Face.
    → Main actor model candidate. Dense 27B, Apache 2.0, released Apr 2026,
      SGLang/vLLM/Transformers-compatible. LeanFoundry uses shorter text-only
      rollout contexts by default.

**Datasets and Lean Tooling**

[6] Yang et al. "LeanDojo: Theorem Proving with Retrieval-Augmented
    Language Models." NeurIPS 2023. arXiv:2306.15626.
    → Primary data/tooling foundation: theorem tracing, proof states, tactics,
      premises, benchmark splits, and ReProver baseline.

[7] LeanDojo-v2. "A Comprehensive Library for AI-Assisted Theorem Proving
    in Lean." NeurIPS Mathematical Reasoning and AI, 2025.
    https://leandojo.org/leandojo.html
    → Updated Lean 4 library for repository tracing, lifelong dataset
      management, agents, fine-tuning, GRPO, retrieval, and eval/deployment.

[8] LeanTree. "Accelerating White-Box Proof Search with Factorized States
    in Lean 4." arXiv:2507.14722, 2025.
    Tool: https://github.com/Kripner/leantree
    Dataset: https://huggingface.co/datasets/ufal/leantree
    → Prior for factorized intermediate proof states, metavariable-coupling
      checks, branch parallelism, proof-tree data, and white-box Lean
      proof-state tooling.

[8a] cat-searcher/minif2f-lean4. MiniF2F Lean 4 JSONL dataset.
     https://huggingface.co/datasets/cat-searcher/minif2f-lean4
     → Public MiniF2F Lean 4 row shape used by the built-in
       `minif2f_lean4_jsonl` benchmark adapter.

[8b] ChristianZ97/PutnamBench-lean4. PutnamBench Lean 4 JSONL dataset.
     https://huggingface.co/datasets/ChristianZ97/PutnamBench-lean4
     → Public PutnamBench Lean 4 row shape used by the built-in
       `putnambench_lean4_jsonl` benchmark adapter.

[8c] Goedel-LM/MathOlympiadBench. MathOlympiadBench Lean 4 JSONL dataset.
     https://huggingface.co/datasets/Goedel-LM/MathOlympiadBench
     → Public MathOlympiadBench row shape used by the built-in
       `matholympiadbench_lean4_jsonl` benchmark adapter.

[8d] UDACA/proofnet-lean4. ProofNet Lean 4 JSONL dataset.
     https://huggingface.co/datasets/UDACA/proofnet-lean4
     → Public ProofNet Lean 4 row shape used by the built-in
       `proofnet_lean4_jsonl` benchmark adapter.

[9] Lean Copilot. "Towards Large Language Models as Copilots for Theorem
    Proving in Lean." arXiv:2404.12534, 2024/2025.
    → Lean-native LLM inference framework for tactic suggestion, proof search,
      and premise selection.

[10] Loogle. nomeata/loogle.
     https://github.com/nomeata/loogle
     → Mathlib search tool. Not used as a core training-time tool. If later
       retrieval experiments are conducted, the index must be built from the
       same Mathlib commit as the env_profile.

**Algorithms, Provers, and Models**

[11] Harmonic. "Aristotle: IMO-level Automated Theorem Proving."
     arXiv:2510.01346, 2025.
     → Source for MCGS, AND/OR hardest-child priority, Expert Iteration,
       HER, value labels, state-equivalence caveats, TTT, and autoformalization.

[12] DeepMind. "Olympiad-level formal mathematical reasoning with
     reinforcement learning." Nature, 2025.
     → AlphaProof/AlphaGeometry formal reasoning system; 2024 IMO silver-level
       result and AlphaZero-style RL over Lean proof search.

[12a] Lample et al. "HyperTree Proof Search for Neural Theorem Proving."
      arXiv:2205.11491, 2022.
      → Direct prior for policy/value-guided proof search, search-generated
        training traces, and step-level proof-state/action learning.

[13] ByteDance Seed. "BFS-Prover: Scalable Best-First Tree Search for
     LLM-based Automatic Theorem Proving." arXiv:2502.03438, 2025.
     → Best-first tree search, self-filtering Expert Iteration, DPO from
       compiler feedback, and MiniF2F results.

[14] ByteDance Seed. "BFS-Prover-V2: Scaling up Multi-Turn Off-Policy RL
     and Multi-Agent Tree Search for LLM Step-Provers." 2025.
     https://github.com/ByteDance-Seed/BFS-Prover-V2
     → Open step-level prover system with multi-stage EI, adaptive tactic
       filtering, periodic retraining, and planner-enhanced inference search.

[15] Moonshot AI. "Kimina-Prover Preview: Towards Large Formal Reasoning
     Models with Reinforcement Learning." arXiv:2504.11354, 2025.
     → Whole-proof formal reasoning pattern, Kimina Lean Server release, and
       RL results without MCTS/value/process reward in the public recipe.

[16] project-numina/kimina-prover-rl.
     https://github.com/project-numina/kimina-prover-rl
     → Open RL pipeline around Kimina-style verifier rewards and long-context
       formal reasoning; useful baseline but not MCGS runtime infra.

[17] Lin et al. "Goedel-Prover-V2: Scaling Formal Theorem Proving with
     Scaffolded Data Synthesis and Self-Correction." arXiv:2508.03613, 2025.
     → Three SFT formats, pass-rate bucketing, self-correction, GRPO recipe,
       checkpoint averaging, and Goedel-Formalizer-V2 design.

[18] Xin et al. "DeepSeek-Prover-V1.5: Harnessing Proof Assistant Feedback
     for Reinforcement Learning and Monte-Carlo Tree Search." arXiv:2408.08152,
     2024.
     → RLPAF, intermediate-success filtering for GRPO, and RMaxTS-style search.

[19] Xin et al. "DeepSeek-Prover-V2." arXiv:2504.21801, 2025.
     → Subgoal decomposition, recursive proof synthesis, structure consistency
       reward, and two-phase EI/RL pipeline.

[20] Kripner. nanoproof, 2026.
     https://github.com/Kripner/nanoproof
     → Minimal open AlphaProof/HyperTree Proof Search-style implementation
       using LeanTree server, MCTS prover, evaluation, and distributed RL loop.

[21] InternLM2.5-StepProver. "Advancing Automated Theorem Proving via
     Critic-Guided Search." arXiv:2410.15700, 2024/2025.
     → Step prover with critic-guided search and expert iteration.

[22] MPS-Prover. "Advancing Stepwise Theorem Proving by Multi-Perspective
     Search and Data Curation." arXiv:2505.10962, 2025.
     → Multi-perspective tree search, learned critics, heuristic diversity,
       and post-training data curation.

[23] StepFun-Prover Preview. "Let's Think and Verify Step by Step."
     arXiv:2507.20199, 2025.
     → Tool-integrated reasoning model and RL framework; reports 70% pass@1
       on miniF2F-test with the 32B preview model.

[24] Leanabell-Prover-V2. "Verifier-integrated Reasoning for Formal Theorem
     Proving via Reinforcement Learning." arXiv:2507.08649, 2025.
     → Verifier-integrated CoT/RL with multi-turn Lean feedback.

[25] Seed-Prover 1.5. "Mastering Undergraduate-Level Theorem Proving via
     Learning from Experience." arXiv:2512.17260, 2025.
     → Large-scale agentic RL and test-time scaling; reports strong PutnamBench
       and Putnam 2025 results.

[26] Prover Agent. "An Agent-based Framework for Formal Mathematical Proofs."
     arXiv:2506.19923, 2025.
     → Agentic framework coordinating informal reasoning, a formal prover,
       Lean feedback, and auxiliary lemma generation.

[27] Polu & Han. "Generative Language Modeling for Automated Theorem
     Proving." arXiv:2009.03393, 2020.
     → Original Expert Iteration formulation for neural theorem proving.

[28] Shao et al. "DeepSeekMath." arXiv:2402.03300, 2024.
     → Source for GRPO used in Stage 4.

[29] Ma et al. "OProver: A Unified Framework for Agentic Formal Theorem
     Proving." arXiv:2605.17283, 2026.
     → Recent whole-proof/agentic Lean 4 baseline using retrieved verified
       proofs, repair trajectories, SFT, and RL over unresolved hard cases.

[30] Leang et al. "Pythagoras-Prover: Advancing Efficient Formal Proving via
     Augmented Lean Formalisation." arXiv:2606.12594, 2026.
     → Recent compute-efficient open Lean prover family with autoregressive
       and diffusion-style proof generation plus augmented formalization data.

---

# Appendix: Aristotle Algorithm Reference

This appendix documents the Aristotle algorithm as understood from the paper
and subsequent analysis. It serves as the authoritative algorithmic reference
for LeanFoundry's MCGS implementation. Where LeanFoundry deviates or extends,
deviations are noted explicitly.

---

## A.1 States and Actions

**State**: a tuple of (goal expressions, local context expressions, local
variable names). Two states are equivalent iff all three match exactly.
Variable names are part of the key — `hP : P ⊢ Q` and `h1 : P ⊢ Q` are
different states. This is pragmatic: renaming would require expensive
normalization.

**Action**: a text string of one or more Lean tactics, optionally prefixed
with inline natural-language comments. Actions are deduplicated by the state
transitions they produce, not by text equality.

**State splitting rule**: after an action produces multiple goals, split into
independent states only if no goal contains metavariables. If metavariables
are present, bundle all goals as one state — the metavariable value chosen for
one goal affects the other. Goals from explicit `sorry` placeholders are always
split and never permitted to have metavariables.

When states are deduplicated across proof paths, the hypertree becomes a
hypergraph. LeanFoundry gates graph merging behind a correctness acceptance
test (see concern A1). In v0.1–v0.2, tree search only.

---

## A.2 AND/OR Structure

- **State (OR node)**: proved if ANY action succeeds.
- **Action (AND node)**: succeeds only if ALL child states are proved.

The MCTS iteration cycle is strictly sequential within one theorem:
select → expand → backpropagate → repeat.

**UCB** governs action selection at the current state:
```
UCB(a) = value_estimate(a) + c * prior(a) * sqrt(parent_visits) / (1 + action_visits)
```
Prior is empirical frequency of the action in policy samples, NOT sequence
log-probability (log-prob biases against actions with multiple equivalent
textual representations).

**LCB** governs AND-child selection: among the AND-children of the selected
action, descend into the one with the lowest lower confidence bound — the
hardest, most uncertain subgoal. Rationale: the bottleneck determines whether
the action can ever succeed. Budget flows primarily to the hardest child. The
easier child receives budget only when the harder one is proved or when a
fresh iteration selects a completely different action from the root.

LCB and UCB are independent mechanisms operating at different levels. LCB
selects which AND-child to descend into at the parent action level. UCB
selects which action to try at the state level.

---

## A.3 Negation Pruning

For each single-goal state `⊢ P`, a synthetic action is added to the pool:
prove `¬P` in the same local context. This action competes under normal UCB
selection and receives a full sub-search across potentially many iterations.
It is NOT a one-step check.

If `¬P` is proved: state is marked DISPROVED. "Dead" propagates upward through
all parent AND-nodes. Any AND-node with a DISPROVED child is eliminated from
its parent OR-node.

If `¬P` is not proved: the action accumulates visit count, UCB score declines,
search moves on naturally.

LeanFoundry: implemented as `try_negation=False` flag in expansion (see G5).

---

## A.4 Parallelism

**Within one theorem**: MCTS iterations are strictly sequential. The only
parallelism is outside the selected state's worker lease. N candidate tactics
are generated together for the selected state, but Env Backend receives them as
one proof-state expansion item. One worker loads that state once and evaluates
the tactic candidates internally. The backend manager must not flatten those
tactics into separate jobs.

**Across theorems**: independent MCGS instances. No shared state, no
coordination. Trivially parallel.

**Cross-theorem batching**: when many theorems are searched concurrently,
policy and Env Backend calls arrive in bursty patterns. The full Slime custom
rollout owns the search orchestration; its EnvClient microbatches proof-state
expansion items into `/exec/step_batch` calls, like Kimina batches many
independent code-check items in one `/check` request. Design parameters are the
microbatch window, max items per request, and backpressure policy (see R1).

---

## A.5 Trajectory Representation

A proof with AND-splits is a tree, not a sequence:

```python
@dataclass
class TacticNode:
    state: FactorizedProofState
    tactic: str
    children: list["TacticNode"]  # AND-children after split; single for linear step

@dataclass
class ProofTree:
    roots: list[TacticNode]   # one solved initial backend state per root
    rendered_lean: str         # canonical text reconstructed from tactic history
```

Runtime search initialization has a synthetic wrapper above these roots:

```
synthetic root OR-state
  synthetic initialization AND-action
    real initial backend state 1
    real initial backend state 2
    ...
```

That wrapper is not training data. It exists only because `SearchTree` has one
root while `/exec/create_states` may return multiple initial states. Extraction
starts below the wrapper and turns each real initial state into one
`ProofTree.roots` entry by pairing the state with its proved action.

Three uses from one representation:
- `rendered_lean`: optional Path-B proof text for final verification
- Depth-first traversal: Path-A policy examples with `proof_prefix`
- Any proved subtree: future HER candidate (must pass `/exec/verify`)

The tree structure is required to reconstruct Lean's branching syntax
(`case inl =>`, `case inr =>`). LeanFoundry: stored as serialized TacticNode
tree in `trajectories.tactic_sequence` (see G3).

---

## A.6 Value Training

Three label types:

| State | Label | Weight | `disproved` |
|-------|-------|--------|-------------|
| On accepted-step proved Path-A path | 1 | 1.0 | False |
| Negation proved (DISPROVED) | 0 | 1.0 | True |
| Searched but not proved, ≥50 tactics tried | 0 | 0.25* | False |

*Weight 0.25 is a guess. Needs ablation (see R3).

In v0, runtime `OPEN` is not a durable resume state. A root that is still
`OPEN` when the configured attempt budget stops becomes the top-level
`EXHAUSTED`/unproved attempt outcome. That outcome is not theorem falsity, but
it may produce censored value-label data after the effort gate.

States searched with < min_effort tactics are excluded — too few attempts
to confidently label as negative.

Root-outcome interpretation:

- Runtime structural `PROVED` states can emit Path-A policy/value training data
  after accepted `/exec` steps and the sorry/admit guard. Top-level
  `SearchStatus.PROVED` and whole-proof artifacts still require the extracted
  `rendered_lean` to pass final `/exec/verify`.
- `DISPROVED` means a negation search proved falsity for the state being
  disproved. The original state receives a full-weight value-negative label.
  The tactics inside the negation proof can be positive policy data for the
  synthetic negation goal, not for the original goal.
- `EXHAUSTED`/unproved means the attempt stopped with the root still `OPEN`
  after spending its configured effort. This is a censored negative only; it may
  train value after the effort gate, but it is not policy data and not
  mathematical falsity.

---

## A.7 Policy Training

Each `(state, action)` pair in any found proof subgraph is a supervised example.
The action string includes hidden CoT tokens, inline comments, and formal
tactic text. Inline comments must be preserved — they are persistent memory
across the proof and the model must learn to produce them (see G4).

Hindsight Experience Replay has two surfaces in LeanFoundry. The primary
lineage-A surface multiplies examples by treating proved nodes as additional
local `(state, action)` examples; this does not require rendering. The optional
lineage-B artifact surface tries to render proved subtrees as standalone root
theorems and then re-verify them; Aristotle reports 10–50x amplification for
that style of subtree reuse, but LeanFoundry's default training path should not
depend on render verification.

---

## A.8 Outer Lemma Pipeline (Training Repo Concern)

The lemma decomposition loop is an algorithm-specific training recipe, not
an infrastructure component. It belongs in the training repo as a rollout
class. LeanFoundry's only required support is `TheoremSpec.initial_lean_block`
(see G1), which receives the sorry-initialized Lean block the training repo
constructs.

Pipeline (training repo):
1. LM generates informal proof of target theorem
2. LM decomposes into lemma chain (individually simple)
3. LM formalizes lemma statements to Lean 4 type signatures
4. Submit with `:= by sorry` to `EnvBackendClient.verify`; relay errors; correct
5. Build `initial_lean_block` with all sorry-d lemmas + main theorem
6. Pass to `SearchEngine` via `TheoremSpec(initial_lean_block=block)`
7. SearchEngine runs MCGS; lemma dependencies handled by Lean automatically
8. Read `ProofTree.roots` to determine proved/unproved initial states
9. If fails: annotate and revise decomposition; go to step 1

The informal proof context conditioning the policy during search is provided
by the training repo's prompt builder; the infra PolicyClient interface does
not need a dedicated field for it.

Both Aristotle-style (informal proof revision) and DeepSeek-Prover-V2-style
(structured subgoal decomposition) fit this interface — they differ only in
how the training repo builds the `initial_lean_block`.
