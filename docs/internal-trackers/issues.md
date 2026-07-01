# LeanFoundry Issue Tracker

This file tracks design/code mismatches, stale design claims, and ambiguity
found during repo audits. Future-facing implementation plans belong in
[`todo.md`](todo.md); completed slices belong in
[`implementation-log.md`](implementation-log.md).

## 2026-06-22: Design Doc / Codebase Audit Pass

Coverage: `leanfoundry_system_design_v11.md` sections 1-32 plus Appendix A,
checked against the current codebase by local review and four read-only
subagent audits covering infrastructure/data, search, training/eval boundary,
and extensions.

### Coverage Matrix

Status values:
- `current`: design matches the current repo surface.
- `stale`: design text conflicts with current repo decisions.
- `future-only`: design is intentionally deferred roadmap.
- `needs-code`: design is current, but code is missing or incomplete.
- `needs-design`: code/repo decision exists, but design text needs updating.
- `needs-both`: both code and design need reconciliation.
- `training-repo`: belongs primarily to the separate training consumer.
- `external-data`: code surface exists, but validation needs live services or
  selected datasets outside this checkout.
- `external-stale-risk`: external facts may have changed and need fresh source
  verification before publication claims.

| Design section | Status | Evidence checked | Issue refs | Missing coverage / action |
|---|---|---|---|---|
| Project branding | current | `README.md`, `AGENTS.md`, package layout | - | Keep as infrastructure identity; no code issue found. |
| Open Questions / Concerns | current / future-only | schemas, proofsearch extraction/rendering, provenance | #6, #16-#18 | Resolved baseline items are recorded; optional rendered-HER/arbitrary rendering remains future. |
| System Landscape | current / external-stale-risk | primary-source refresh on 2026-06-30 | #29 | Core landscape claims were refreshed and 2026 baselines added; re-check before public-facing publication. |
| Extensions and Roadmap | current / future-only | package layout, extension code absence | #25-#28 | Core-vs-extension gates are explicit; extension components remain deferred. |
| System Architecture | current / training-repo | module layout, replay/eval/Slime adapter | #5, #19, #23, #25, #30 | Runnable infra baselines are separated from trainer/deployment ownership. |
| Design Principles | current / future-only | current code and trackers | #2, #5, #23, #30 | P3/P10 now state current durable/outbox guarantees separately from future checkpoint/resume. |
| §1 Environment Profiles | current | `EnvBackendConfig`, `EnvProfile`, eval loaders/runners, Slime runner | #2 | Low-level dev default is documented separately from training/eval ingress validation. |
| §2.1-2.7 Kimina `/exec` backend | current / external-data | `EnvBackend` protocol, `KiminaEnvBackend`, remote `lean-client` lock | #7, #9, #31 | LeanFoundry client boundary is current; backend server internals still require backend-side evidence. |
| §2.8 Validation Harness | current / external-data | search verification paths, tests, local live `/exec` e2e | #7, #31 | Harness API, latency summaries, and scripted live e2e are landed; run it over real backend trajectories before training. |
| §3.1-3.1.1 State structure / LeanTree | current / future-only | `FactorizedProofState`, expansion split logic | #10 | Current minimal state schema is separated from future LeanTree/MCGS identity research. |
| §3.2 AND/OR UCB selection | current | `_selection.py`, runtime-tree tests | #11 | Current local PUCT/hardest-child descent is the v0 contract. |
| §3.3 Expansion | current | `PolicyClient`, `_expansion.py`, action text storage | #12 | Policy request/history context is inference-only and wired. |
| §3.4 HER | current / future-only | `extract_training_artifacts`, `TrainingSample` schema | #17 | Step-level extraction and Path-B render diagnostics are landed; standalone rendered-HER reverify remains future. |
| §3.5 Value data | current / future-tuning | `ValueLabel`, extraction logic, TODO | #17 | Node-local censored negatives and disproved/root/internal semantics are landed; weight/effort gates still need ablation. |
| §3.5.1 Negation pruning | current | config/provenance helper, expansion path | #16 | Persistent negation action and nested synthetic proof subtrees are landed. |
| §3.6 Supported algorithms | current / future-only | `SearchAlgorithm`, `build_engine` | #14, #32 | Direct/self-correct/tree/best-first are implemented; tactic beam, optimistic/RMaxTS, MCGS, AND/OR MCGS are enum-only/future. |
| §3.7 Search roadmap | current / future-only | implementation log, factory, TODO | #14, #19, #32 | Roadmap is rebased around implemented direct/self-correct/tree wedges and deferred algorithms. |
| §4.1 A-type data | current | `ATypeDataRecord`, SQL migration | #3, #8 | Schema nullability, backend-neutral verification naming, and examples are aligned. |
| §4.2 B-type data | current | `TheoremRecord`, SQL migration | #2, #3 | Env/split/profile invariants are enforced at ingress where LeanFoundry owns the boundary. |
| §4.3 Trajectories/value labels | current / future-only | `TrajectoryRecord`, `TrainingArtifacts`, SQL | #5, #8, #17, #33 | Replay/failure/eval artifacts and extraction semantics have baselines; rendered-HER remains future Path-B. |
| §4.4 Formalizer output | current / future-only | staging schema, promotion gate, draft loop, formalizer/judge/dedup contracts | #26 | Staging header, draft/retry orchestration, HTTP formalizer contract, statement check, semantic judge contract, exact dedup hash, embedding dedup contract, difficulty mapping, and deterministic promotion gate landed; real models/services and live corpora remain future. |
| §5 Hardware / Qwen / Phase -1 | training-repo | `leanfoundry/slime`, pyproject deps | #20, #24 | Keep hardware/model/profiling in training repo; infra only exposes metrics/artifacts. |
| §6 Data for each stage | current / training-repo | replay protocol, extraction artifacts, Slime sample conversion | #5, #19, #20, #36, #38 | Stage data recipe is training-repo; infra durable artifacts and training-row/Sample conversion baselines are landed. |
| §7 Training pipeline | training-repo / future-only | `leanfoundry/slime`, `proofsearch`, replay protocols | #19, #20, #22 | Stage loops not implemented here; keep consumer-facing interfaces stable. |
| §8 Metrics | current / training-repo | eval protocol, schemas | #23, #24 | Infra metrics/artifacts have a local baseline; training progression/W&B metrics stay training-repo owned. |
| §8.5 Evaluation protocol | current / future-only | `EvalRunner`, `EvalArtifactManifest` | #23, #34 | Benchmark manifests, pass@k, solved@budget, contamination checks, source loaders, MiniF2F adapter, row-adapter extension point, and artifact writers landed; additional dataset adapters remain future. |
| §9 Known risks | current / future-tuning | TODO SearchConfig exclusions, code surface | #24, #35 | Risk ownership and the max-tree/pruning stance are explicit; empirical tuning remains. |
| §10 Repo boundary/release | current | README, AGENTS, policy/env APIs | #4, #9, #20-#22 | `lean_client` schema/client boundary, optional Slime adapter, and rollout pseudocode are aligned. |
| §§11-16 Extension A | current / future-only | scaleout contracts | #25 | Router autoscale, binary framing, pure scheduling, reference TCP service, router-backed EnvBackend adapter, and portable-state contracts landed; production hardening, state export/import, distributed replay, and deployment actions remain future. |
| §§17-20 Extension B | current / future-only | staging schema, promotion gate, draft loop, formalizer/judge/dedup contracts | #26 | Local deterministic formalization pipeline contracts landed; concrete model checkpoints, deployed indexes/services, calibration, and live corpus runs remain future. |
| §§21-24 Extension C / TTT | current / future-only | TTT protocols, trace schemas, orchestration loop, promotion gate, trace replay | #27 | TTT contract, callback-driven orchestration loop, local promotion decision gate, and promoted-trace replay writes landed; MCGS/per-problem search source and concrete trainer reload remain future. |
| §§25-32 Extension D | current / training-repo | ablation plan schemas/helpers | #28 | Frozen curriculum, arms, hard ledger, and crossed eval contract landed; actual training execution and live meter enforcement remain external. |
| Appendix A Aristotle reference | current / reference | current search/extraction code | #10-#17, #32 | Appendix remains reference material; graph/global semantics are explicitly deferred. |

### Core Verification And Data Spine

1. Test/dev environment is runnable from the remote `lean-client` lock.
   - Resolved: `pyproject.toml` and `uv.lock` now source `lean-client` from the
     pinned GitHub repository instead of a missing sibling checkout.
   - Current evidence: `uv run --no-dev --with pytest pytest` collects and
     passes in this workspace.

2. Environment profiles are enforced at training/eval ingress.
   - Design says every training/eval Lean execution is tied to a pinned env
     profile with Lean/Mathlib/header identity.
   - Landed: `env_profiles.py` rejects default profiles at replay/training
     ingress, validates theorem headers against optional `EnvProfile`
     registries, and rejects mixed theorem batches unless explicit routing is
     enabled.
   - Landed: benchmark loaders and eval runners accept profile registries, and
     the Slime training backend builder requires an explicit non-default
     profile.
   - Resolved design boundary: `EnvBackendConfig.env_profile="default"`
     remains deliberately available for direct local/dev client construction,
     while training/eval ingress requires explicit non-default profiles.

3. SQL/Pydantic consistency testing covers the current direct contract.
   - Repo guidance says Pydantic models are source of truth and SQL must match.
   - Resolved: the initial migration test now checks column presence,
     nullability, SQL defaults, SQLite type affinity, and representative SQL
     `CHECK` constraints for direct model-backed fields.
   - Keep extending the test when new durable model constraints are added.

4. Durable schema leaks a concrete backend name.
   - Resolved for the initial schema: the SQL and Pydantic data records now use
     `verified_by_backend`.
   - Keep future durable fields backend-neutral before treating migrations as a
     stable API.

5. Replay persistence has a concrete Path-A implementation.
   - Resolved for the baseline: `SQLiteReplayStore` and
     `persist_search_result(...)` write theorem, trajectory, policy-example,
     value-label, verified A-type, and attempt-lifecycle rows.
   - Landed after Path-A: cleanup attempts now preserve deferred item ids, and
     cancellation unwind can persist cancel failures/statuses through
     `attempt_lifecycle_outbox` when a replay store is present.
   - Landed after Path-A: lifecycle reconciliation retries pending cleanup and
     cancel rows, marks terminal deleted/drained/cleaned/orphaned outcomes, and
     direct-search active verifier cancellations persist to replay.
   - Landed after Path-A: lifecycle reconciliation has a bounded/infinite
     scheduler helper and warning/critical operator alerts.
   - Landed after Path-A: `leanfoundry-reconcile-lifecycle` /
     `python -m leanfoundry.replay.lifecycle_cli` gives cron and service
     supervisors a runnable reconciliation hook with JSON diagnostics and
     optional alert-based nonzero exit codes.
   - Landed after Path-A: extraction failures persist to the replay store with
     deterministic ids.
   - Landed after Path-A: SQLite migrations use an ordered registry with
     v4/v5/v6/v7-to-current upgrade coverage. Stable-schema release governance
     is documented in `docs/design/schema_release_governance.md`. Still open
     beyond Path-A: site-specific pager/metrics integration.

### Stale Or Ambiguous Design Text

6. Open Questions G1-G4 have current baselines plus Path-B residuals.
   - Implemented: `TheoremSpec.initial_lean_block`, `TheoremSpec.source`,
     `ValueLabel.disproved`, value label `weight`, `TacticNode`, and full
     sampled tactic text preservation.
   - Landed after the audit: policy prompt history/comment context is wired as
     inference-only `PolicyContext`, downstream training conversion has
     `to_training_rows(...)` plus the Slime `Sample` adapter, and step-level
     proved-node extraction is current.
   - Still open: optional rendered-HER artifacts and arbitrary tree rendering
     correctness.

7. §2.8 validation harness has a reusable API baseline.
   - Current search acceptance uses `/exec/verify` through `verify_one`.
   - Resolved design text: Extension B statement checks use lean-client's
     legacy REPL `api_check` route, while search-path proof acceptance uses
     `/exec/verify`.
   - Landed: `validate_backend_case(...)` replays tree-shaped tactic
     trajectories through an injected `EnvBackend`, including focused
     `goal_group` child replays after goal-coupling splits, then verifies the
     supplied complete proof through `/exec/verify`.
   - Landed: `leanfoundry-validate-backend` /
     `python -m leanfoundry.env_backend.validation_cli` loads
     `BackendValidationCase` JSON/JSONL, enforces one `env_profile` per run,
     prints JSON diagnostics, and exits nonzero on failed reports.
   - Landed after the CLI: validation reports now include create/replay/verify
     and total elapsed seconds, and the CLI summary includes aggregate latency
     totals/means for live backend sweeps.
   - Landed live smoke: `tests/test_e2e_search.py` passed against a local
     one-worker Kimina `/exec` server on `http://127.0.0.1:8017` with
     `LEANFOUNDRY_E2E=1`.
   - Remaining gap: run the validation CLI against actual LeanDojo/LeanTree
     trajectories and interpret latency/cache behavior with backend telemetry.

8. §4 data-store examples are current for the implemented schema.
   - Resolved: trajectory text now says `tactic_sequence` stores serialized
     `ProofTree` JSON, not a flat tactic list.
   - Resolved: the `state_value_labels` SQL example includes `weight` and
     `disproved`, and the surrounding text describes current `try_negation`
     semantics.

9. §10 `lean_client` boundary is aligned.
   - Current contract allows importing `lean_client.exec_models` directly; only
     `kimina_backend.py` constructs `AsyncLeanExecBackend`.
   - Resolved: design now distinguishes shared wire-schema imports from
     concrete backend construction.

10. §3.1.1 and Appendix A are separated from current runtime behavior.
    - Earlier drafts referenced coupling groups / tactic-history hash as
      `FactorizedProofState` semantics, but the current state schema is minimal
      and stores only current open goals plus resume token.
    - Appendix Aristotle text remains reference material for graph/global
      variants; current code dedupes tactic text and splits by backend
      `sibling_dep` coupling groups.
    - Resolved: the current state schema and future graph/MCGS identity
      research path are called out separately.

### Search Behavior Gaps

11. Selection semantics are aligned for v0.
    - Resolved: §3.2 now documents the implemented local root-to-leaf PUCT
      descent and structural hardest-child heuristic.
    - Appendix A remains reference material for future graph/global variants.

12. Policy prompt history/comment context has an inference-only baseline.
    - Landed: `PolicyClient.sample_tactics(...)` accepts `PolicyContext`,
      expansion derives `proof_prefix` from parent runtime actions, and the
      default HTTP tactic prompt can include that prefix as Lean comments.
    - This remains prompt context only: it does not mutate
      `FactorizedProofState` and is not a separate history-conditional training
      target.

13. Direct search pass@k semantics and verifier transport are aligned.
    - Landed: `DIRECT` samples one candidate pool up to
      `max_direct_candidates`, verifies every returned candidate through
      `EnvBackend.verify(...)`,
      records every `DirectVerificationAttempt`, returns the first accepted
      proof as the top-level proof, and stores every accepted verified proof in
      `TrainingArtifacts.proof_candidates`.
    - Landed: `FixedModelEvalRunner` derives pass@k from accepted verifier
      candidate indices, so later rejected candidates do not erase an earlier
      pass@k success.
    - `SELF_CORRECT` intentionally keeps sequential `verify_one` calls because
      each next prompt depends on previous verifier feedback.

14. Supported-algorithm wording is ahead of code.
    - Implemented: direct, self-correct, PUCT tree / `AND_OR_TREE` alias, and
      best-first.
    - Enum-only/future: tactic beam, optimistic/RMaxTS, MCGS, AND/OR MCGS.
    - Design currently says LeanFoundry "supports" all modes.

15. Best-first design text is aligned for v0.
    - Resolved: the design now describes the implemented value/missing-score,
      goal-count, visit, and deterministic tie-order heuristic.

16. Negation pruning has a conservative baseline, not full Aristotle search.
    - Landed: `try_negation` is provenance-gated, eligible single-goal states
      can render a simple synthetic negated theorem, backend-stepped negation
      tactics count against `max_tactic_calls`, and a complete negation marks
      the state/root `DISPROVED`.
    - Landed: negation attempts are recorded in
      `TrainingArtifacts.negation_attempts` and persisted durably in
      `negation_attempts`.
    - Landed: local definitions/`let` entries in negation contexts are handled
      by typed abstraction; unsupported names and empty types still fail
      closed.
    - Landed: negation is now a persistent synthetic action that normal
      selection can revisit for additional tactic batches; ordinary failures
      keep the action open, while repeated policy outputs fail closed.
    - Landed: the synthetic action now owns the negated-theorem proof state as
      a child subtree; open subgoals inside that proof are searched by the
      normal AND/OR tree, and proved tactics inside that subtree train the
      synthetic negation goal rather than the original false state.

17. Node-general proved-node extraction remains partial.
    - Landed baseline: lineage-A step extraction now emits policy positives
      from every proved runtime action, including multiple proved actions at
      one state and proved internal subtrees under an unproved root. Bonded
      proved-value labels are emitted for every proved runtime state.
    - Whole-proof candidates remain canonical and verifier-gated.
      Action-level Path-B render diagnostics now count render candidates,
      structurally renderable candidates, unsupported candidates, and verified
      top-level artifacts. Standalone rendered-HER subproof verification is
      still optional/future Path-B work.
    - Censored negatives use node-local `visit_count` over open real states,
      not attempt-level budget alone. Remaining work is empirical tuning of
      `min_censored_negative_effort` and `censored_negative_weight`.
    - Disproved-root top-level status and internal disproved-node labels exist
      for manually marked runtime states and conservative synthetic negation
      checks.

18. Proof rendering is intentionally narrow.
    - Current renderer is verified-gated and fail-closed, but it is still
      positional, has limited real-Lean fixture coverage, and cannot reconstruct
      arbitrary focused goal groups.
    - Landed: extraction diagnostics now expose the narrow renderer's
      action-level candidate/support boundary without treating it as training
      data.
    - Missing design contract: `GoalComponent` currently carries order/name, not
      a stable goal identity that would let the renderer safely reconstruct
      arbitrary non-contiguous focused groups.

### Training, Eval, And Repo Boundary

19. Part II Stage 3 wording is partly ahead of current implementation.
    - Current core is AND/OR tree search with Path-A step extraction,
      step-level HER extraction, baseline HTTP policy/value clients, eval
      runner wiring, persistent negation action retries, and a Slime rollout
      adapter.
    - Graph/MCGS, rendered-HER artifacts, and live full-stack training
      execution remain deferred.

20. Slime integration is no longer placeholder-only, but still needs live
    training-extra validation.
    - The push-shaped `rl_engine` placeholder has been removed.
    - `leanfoundry/slime/` now provides the pull-shaped rollout entrypoint,
      runner hooks, SGLang policy client, and row-to-Sample conversion.
    - Pinned Slime API-compat tests pass under `[training]`.
   - Landed: `tests/test_slime_live.py` is an opt-in live smoke that drives
     real `async_generate_rollout` through pinned Slime, SGLang, a Lean
     backend, and the configured tokenizer checkpoint.
   - Landed adjacent evidence: the Lean backend side of live e2e passed through
     `tests/test_e2e_search.py` against a local Kimina `/exec` server.
   - Remaining gap: execute that smoke against actual services before a real
     training run; default rollout tests still use fake Slime modules.

21. Policy/value API examples in §10 are current.
    - Resolved: the design now separates `PolicyClient` and `ValueClient`.
    - Resolved: `sample_proofs(...)` and `sample_tactics(...)` return
      `list[list[str]]`, one candidate list per prompt/state.

22. Slime rollout pseudocode is aligned with the current adapter.
    - Resolved for the baseline: `leanfoundry/slime/rollout.py`, `samples.py`,
      and `runner.py` call `run_search_batch(...)` with explicit clients/backend
      and convert results through `to_training_rows(...)`.
    - Resolved in fake coverage: grouped/callable data-source inputs,
      tokenizer loading from `args.hf_checkpoint`, and eval output.
    - Landed: the long-form design now uses the current pull-shaped
      `SlimeRolloutRunner` / `async_generate_rollout` structure instead of
      obsolete push-shaped pseudocode.
    - Remaining gap: run the harness in a configured live environment.

23. Evaluation has a runnable manifest/artifact baseline.
    - Landed: `FixedModelEvalRunner` produces `EvalArtifactManifest` with
      pass@k for direct/self-correct, solved@budget for tree modes, status
      counts, and throughput metrics.
    - Landed: benchmark JSONL loading validates `BenchmarkManifest`
      compatibility, env profile, and theorem count; runner artifact writing
      materializes manifest/results/benchmark/report files with content hashes.
    - Landed: direct/self-correct verifier attempts are recorded as
      `DirectVerificationAttempt` artifacts and serialized in eval results.
    - Landed: mode coverage now includes direct pass@k, self-correct pass@k,
      and state-token solved@budget for PUCT, best-first, and `AND_OR_TREE`.
    - Landed: `load_benchmark_source(...)` loads manifest sources from local
      paths, `file://`, HTTP(S), and explicit Hugging Face file URIs.
    - Landed: `BenchmarkManifest.row_format` plus `BenchmarkRowAdapter`
      provides the extension point for benchmark-specific row transforms.
    - Landed: built-in `MINIF2F_LEAN4_ROW_FORMAT` /
      `make_minif2f_lean4_row_adapter(...)` adapts MiniF2F Lean4 JSONL rows
      into `TheoremSpec`s using the manifest env profile and split.
    - Landed: built-in `PUTNAMBENCH_LEAN4_ROW_FORMAT` /
      `make_putnambench_lean4_row_adapter(...)` adapts PutnamBench Lean4 JSONL
      rows into `TheoremSpec`s using the registered env-profile header and
      split.
    - Landed: built-in `MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT` /
      `make_matholympiadbench_lean4_row_adapter(...)` adapts
      MathOlympiadBench Lean4 JSONL rows into `TheoremSpec`s using per-row
      headers and split.
    - Landed: built-in `PROOFNET_LEAN4_ROW_FORMAT` /
      `make_proofnet_lean4_row_adapter(...)` adapts ProofNet Lean4 JSONL rows
      by explicitly filling public statements ending at `:=` with `by sorry`
      and rejecting non-placeholder statements.
    - Still open: additional public-benchmark adapters, only after choosing
      datasets whose native rows are not already LeanFoundry theorem JSONL.

24. Risk ownership is mixed.
    - Infra-owned risks: env-profile verification, search memory, replay,
      renderer, eval artifacts, backend throughput.
    - Training-repo risks: GRPO reward hacking details, KL policy, weight sync,
      optimizer/model fit, W&B/reporting.

### Extensions

25. Extension A has local contracts but no deployed scale-out system.
    - Landed: `RouterMetrics`, `AutoscaleConfig`, `AutoscaleDecision`, and
      `plan_router_scale(...)` encode the queue-depth autoscaling formula.
    - Landed: `RouterCommand`, `RouterFrame`,
      `encode_router_frame(...)`, and `decode_router_frame(...)` encode the
      documented binary frame header with strict exact-frame decoding. Command
      payloads remain opaque until a router adapter owns their schemas.
    - Landed: `AsyncRouterService` provides a reference asyncio TCP service
      over those frames: backend `REGISTER`, client `REQUEST`, backend
      `FORWARD`, backend `RESPONSE`, client `DELIVER`, and disconnect requeue
      are covered locally with fake stream tests.
    - Landed: `RouterEnvBackend` and `RouterBackendWorker` carry lean-client
      `/exec` operations over the reference router for limits, create_states,
      one-state step_batch via `EnvBackend.step(...)`, verify, cleanup, cancel,
      and stats.
    - Landed: `leanfoundry-router` and `leanfoundry-router-worker` are stable
      local process entrypoints for launching the reference router and backend
      workers from an external supervisor.
    - Landed: `RouterServiceSnapshot` exposes local queue/backend/client
      diagnostics and assignment/delivery/requeue/drop counters; disconnected
      clients drop still-pending requests.
    - Landed: `RouterCommand.CANCEL`, `cancel_inflight_requests(...)`, and
      `RouterBackendWorker` task cancellation provide local protocol semantics
      for abandoned in-flight router work; late responses are dropped.
    - Landed: `leanfoundry.scaleout.health` derives `/healthz`, `/readyz`,
      and Prometheus-text `/metrics` endpoints from `RouterServiceSnapshot`,
      and `leanfoundry-router --health-port ...` can serve them.
    - Landed: `RouterState`, `register_backend(...)`,
      `enqueue_request(...)`, `complete_request(...)`, and
      `disconnect_backend(...)` encode deterministic FIFO scheduling,
      per-backend CPU-slot capacity, completion drain, duplicate-id rejection,
      and disconnect requeue for in-flight requests.
    - Landed: `PortableStateRef` records state snapshot codec, location, hash,
      sizes, and location-specific payload invariants.
    - Landed: `make_inline_state_ref(...)` and `decode_inline_state_ref(...)`
      implement RAW inline payload round-tripping with hash/size checks.
    - Landed: `make_file_state_ref(...)` and `decode_file_state_ref(...)`
      implement local `file://` URI payload writes/reads with payload-size,
      decoded SHA-256, and raw-size validation.
    - Landed: `decode_http_state_ref(...)` and `decode_uri_state_ref(...)`
      implement read-only `http://` / `https://` URI payload fetches with
      payload-size, codec, decoded SHA-256, and raw-size validation.
    - Landed: the `[scaleout]` extra installs `zstandard`; default installs
      still fail closed if ZSTD is requested, and focused tests cover real
      ZSTD inline/file round-trips under the extra.
    - Still missing: production router hardening/deployment, site-specific
      supervisor manifests and metrics/pager integration, backend state
      export/import, credentialed object-store clients and remote writes,
      Postgres store, Redis Streams store, distributed cleanup/cancel semantics,
      concrete backend/kernel abort guarantees, and deployment integration.
    - Design claim that "only URLs in configuration files change" is too strong;
      distributed cleanup/cancel, state portability, and replay-store semantics
      need explicit adapter work.

26. Extension B has local deterministic pipeline contracts only.
    - Landed: `formal_statements_staging` and
      `FormalStatementStagingRecord` preserve the Lean header/import block
      needed to produce `TheoremRecord.header`.
    - Landed: SQLite schema version 7 backfills the staging `header` column for
      existing DBs.
    - Landed: `evaluate_promotion(...)` checks syntax status, semantic judge
      score, dedup hash, and already-promoted state before building a
      `TheoremRecord`; rejection reasons are machine-readable.
    - Landed: exact local dedup hash helpers populate/check normalized
      statement/header/profile hashes before promotion.
    - Landed: `estimate_difficulty_from_quick_search(...)` maps a quick-search
      `SearchResult` to both a bucket and the numeric
      `difficulty_estimate: float` stored on theorem records.
    - Landed: `KiminaStatementVerifier` and
      `verify_staging_statement_code(...)` provide a local statement
      syntax/type-check wrapper and update `syntax_checked` from normalized
      lean-client `api_check` results.
    - Landed: `HTTPSemanticJudge` provides a local semantic-judge service
      contract, validates `[0, 1]` scores, and updates
      `semantic_judge_score`.
    - Landed: `run_formalization_draft_loop(...)` provides local draft/retry
      orchestration over injected formalizer and verifier protocols, carries
      verifier feedback between attempts, and emits accepted staging rows only
      after syntax acceptance.
    - Landed: `HTTPEmbeddingDeduplicator` provides a local embedding-dedup
      service contract, validates threshold-consistent duplicate/unique
      responses, and lets promotion optionally require a unique result.
    - Landed: `HTTPFormalizer` provides a local formalizer service/prompt
      contract, validates structured `lean_statement` responses, and passes
      verifier feedback through the draft payload.
    - Still missing: real formalizer/judge/embedding model checkpoints,
      deployed services/indexes, judge and embedding threshold calibration,
      running statement verifier/judge/dedup checks over real staged corpora,
      and running quick-search difficulty estimation on real model/backend
      results.

27. Extension C / TTT has local orchestration but no concrete trainer/search source.
    - Landed: `leanfoundry.ttt.TTTAdapter`,
      `AdaptablePolicyClient.with_adapter(...)`, `TTTConfig`,
      `TTTAdapterTrainingRequest`, `TTTAdapterTrainingResult`,
      `TTTRoundTrace`, and `TTTSessionTrace`.
    - Landed: trace promotion to the main replay buffer is off by default, and
      per-round traces validate adapter/reload success semantics.
    - Landed: `run_ttt_session(...)` alternates injected search, sample
      extraction, adapter fine-tuning, reload, policy rebinding, and re-search
      while recording success/stop/failure traces.
    - Landed: `evaluate_ttt_trace_promotion(...)` provides the local opt-in
      promotion decision gate, including env-profile, trace-key dedup,
      failed-stage, solved-status, and successful-reload checks.
    - Landed: `TTTTraceReplayRecord`,
      `ReplayStore.put_ttt_trace_replay_records(...)`, SQLite
      `ttt_trace_replay`, and `persist_promoted_ttt_trace(...)` provide the
      explicit caller-owned replay write for promoted trace artifacts.
    - Still missing for TTT: MCGS or another approved per-problem search
      source and concrete trainer-side fine-tuning/reload implementation.

28. Extension D has a local experiment contract but no trainer.
    - Landed: `AblationExperimentPlan`, `FrozenCurriculumManifest`, the five
      standard training-target arms (W/W+SC/T-step/T-noval/Mix), per-arm
      replay/checkpoint namespaces, hard generation/training/verifier ledgers,
      `budget_account_id` consistency checks, and native crossed-eval cells.
    - Landed: no-value arms are schema-guarded from value serving and value
      AUC/calibration metrics.
    - Landed: `build_frozen_curriculum_from_pass_sweep(...)` constructs a
      deterministic frozen curriculum from complete direct pass@N verifier
      attempts, with fail-closed checks for missing candidate evidence and
      theorem-id mismatches.
    - Landed: `check_budget_request(...)` evaluates one request against one
      budget ledger cell, refuses wrong `budget_account_id`s and hard-cap
      overruns, and returns remaining-budget diagnostics.
    - Landed: `SQLiteBudgetMeterStore` provides local durable budget cells and
      atomic SQLite reservations over `check_budget_request(...)`, including
      existing-cell drift checks and concurrent local hard-cap serialization.
    - Landed: `leanfoundry-budget-meter` exposes local init/reserve/snapshot
      commands for JSON ledgers or plan-shaped budget objects and returns
      nonzero when a reservation is refused.
    - Still external: running the actual pass@N sweep on a selected model/pool,
      optimizer execution, checkpoint production, distributed metering services,
      worker-side live measurements, target-specific serving wrappers, and final
      outcome reports.

### Additional Coverage Findings

29. System Landscape external claims were refreshed on 2026-06-30.
    - Treat this section as background, not code contract.
    - Refreshed core claims from primary arXiv/project pages for the named
      prover/tooling systems used to justify the repo boundary.
    - Added 2026 OProver and Pythagoras-Prover baselines to avoid presenting an
      outdated "latest open prover" picture.
    - HTPS, LeanDojo/ReProver, BFS-Prover, and DeepSeek-Prover-V1.5 support the
      current framing that state-tactic search data is prior art, while the
      downstream experiment is a controlled comparison of step, whole-proof,
      self-correct, and mixed targets under shared infra.
    - Still external-stale-risk: before public release or citation-heavy docs,
      refresh claims about current open/closed systems and reported results from
      primary sources again.

30. Architecture and principles distinguish current modules from targets.
    - The single-machine diagram includes trainer, inference engine, SQLite data
      buffer, evaluation, and MCGS search as if they are all runnable pieces.
    - Current repo has concrete replay/eval/Slime-adapter baselines, but no
      concrete trainer process, inference service deployment, or MCGS engine.
    - Resolved: design principles now state current durable/outbox guarantees
      separately from future checkpoint/resume and deployment guarantees.

31. `/exec` server behavior is mostly outside this checkout's evidence surface.
    - Local evidence now covers the pinned `lean-client` package import and the
      `KiminaEnvBackend` pass-through boundary to `AsyncLeanExecBackend` for
      limits, create_states, step, verify_one, verify, cleanup, cancel, stats,
      close, and `goal_group` forwarding.
    - Still external-data: server limits, state-store behavior,
      cleanup/cancel/stats semantics, scheduler behavior, cache/latency, and
      kernel cancellation guarantees require live backend/server-side
      validation.
    - Keep server behavior claims in the design doc tied to backend-side tests,
      live validation reports, or imported lean-client contracts, not inferred
      from LeanFoundry alone.

32. Tactic beam and optimistic/RMaxTS need explicit deferral.
    - They appear in the algorithm enum/design family, but no engine
      implementation exists.
    - Treat them like graph/MCGS: not on the core path until replay/eval proves
      the direct/tree/best-first baseline.

33. Durable artifact schema is underspecified.
    - `ReplayStore` covers theorem, A-type data, trajectory, value labels,
      extraction failures, and attempt-lifecycle outbox rows. Eval
      manifests/results are file artifacts with deterministic names and content
      hashes.
    - Landed: SQLite migrations use an ordered registry with legacy v4/v5
      upgrade coverage.
    - Landed: `docs/design/schema_release_governance.md` defines immutable
      released migrations, append-only migration rules, upgrade-test
      requirements, destructive-change handling, and eval-manifest governance.

34. Eval needs benchmark/env-profile manifests before loaders.
    - Landed: `BenchmarkManifest` carries source, split, env profile,
      compatibility status, contamination policy, fixed assignment id, dataset
      commit, and expected theorem count.
    - Landed: `load_benchmark_jsonl(...)` validates theorem rows against that
      manifest and optional `EnvProfile` registries, and
      `FixedModelEvalRunner.run(..., artifact_dir=..., env_profiles=...)`
      writes manifest-backed eval artifacts.
    - Landed: `load_benchmark_source(...)` dispatches manifest sources across
      local files, `file://`, HTTP(S), and Hugging Face file URIs.
    - Landed: `BenchmarkManifest.row_format` plus `BenchmarkRowAdapter`
      provides benchmark-specific row transforms without changing the core
      theorem schema.
    - Landed: built-in MiniF2F Lean4 JSONL row adapter for rows with
      `id`/`name`, `formal_statement`, `header`, optional informal text, and
      manifest-owned `env_profile`.
    - Landed: built-in PutnamBench Lean4 JSONL row adapter for rows with
      `problem_name`, `formal_statement`, optional informal text, and `split`;
      it derives the theorem header from the registered `EnvProfile`.
    - Landed: built-in MathOlympiadBench Lean4 JSONL row adapter for rows with
      `name`/`problem_id`, `formal_statement`, `header`, optional informal
      text, and `split`.
    - Landed: built-in ProofNet Lean4 JSONL row adapter for rows with `name`,
      `formal_statement`, `header`, optional informal text, and `split`; it
      explicitly initializes `:=` placeholders with `by sorry`.
    - Still open: additional adapters for selected public benchmarks whose
      native rows are not already LeanFoundry theorem JSONL.

35. Risk section records the max-tree/pruning stance.
    - Design and `todo.md` now agree that max tree nodes are not in
      `SearchConfig` until traces or profiling justify a semantic search budget
      or a separate operational guard.
    - Resolved design stance: max tree nodes remain out of `SearchConfig`
      until traces/profiling justify a semantic search budget or a separate
      operational guard.

36. Self-correction is executable and extractable for accepted corrections.
    - Landed: `SelfCorrectTrace` / `SelfCorrectTurn` persist failed proof
      attempts, Lean feedback, corrected attempts, per-turn verifier status, and
      verifier item ids.
    - Landed: `to_training_rows(...)` emits `kind="self_correct"` rows for
      accepted corrections using statement + previous failed proof + verifier
      feedback as prompt and the accepted correction as trainable response.
    - Landed: optional failed-correction negatives are available through
      `include_failed_self_correct_negatives=True` and the Slime rollout arg
      `lf_include_failed_self_correct_negatives`; default core rows remain
      accepted corrections only.

37. Value serving client modes need adapter wiring.
    - Baseline `HTTPValueClient` now supports numeric-head and natural-language
      boxed/JSON scalar parsing. It can point at a separate endpoint or the same
      checkpoint with a value prompt.
    - Landed: `SlimeRolloutRunner.build_value_client(...)` builds explicit
      bonded/unbonded value clients while `value_mode` still controls label
      emission.

38. Slime sample token construction and env-profile validation have a baseline.
    - Landed: LeanFoundry owns prompt/response tokenization, `response_length`,
      `loss_mask`, `lf_kind`, reward/status, and self-correct feedback masking
      in `leanfoundry/slime/samples.py`.
    - Landed: Slime runner theorem conversion and batch validation reject
      missing/default env profiles, mixed profile batches/runs, and
      theorem/backend profile mismatches unless explicit mixed routing is
      enabled.
   - Landed: an opt-in live full-stack rollout smoke exists for SGLang plus a
      Lean backend. The Lean-only live e2e passed against a local Kimina
      `/exec` server; still open: run the full Slime/SGLang/Lean smoke against
      actual services.
