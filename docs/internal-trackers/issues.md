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
- `off-main-snapshot`: implementation exists only on a preserved non-main
  branch and is not trusted current `main` implementation.

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
| §2.8 Validation Harness | current / external-data | search verification paths, tests, recovered local `/exec` e2e | #7, #31 | Harness API and Docker-backed local `/exec` e2e are current; run it over real backend trajectories before training. |
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
| §4.4 Formalizer output | current / future-only | staging schema, extension code absence | #26 | Core staging schema/header is current; promotion, draft/retry, formalizer, judge, dedup, and difficulty services are off-main snapshot/future work. |
| §5 Hardware / Qwen / Phase -1 | training-repo | `leanfoundry/slime`, pyproject deps | #20, #24 | Keep hardware/model/profiling in training repo; infra only exposes metrics/artifacts. |
| §6 Data for each stage | current / training-repo | replay protocol, extraction artifacts, Slime sample conversion | #5, #19, #20, #36, #38 | Stage data recipe is training-repo; Slime sample conversion still needs live e2e before completion claims. |
| §7 Training pipeline | training-repo / external-data | `leanfoundry/slime`, `proofsearch`, replay protocols | #19, #20, #22 | Stage loops require live Slime/SGLang/Lean e2e before any done claim. |
| §8 Metrics | current / training-repo | eval protocol, schemas | #23, #24 | Infra metrics/artifacts have a local baseline; training progression/W&B metrics stay training-repo owned. |
| §8.5 Evaluation protocol | current / future-only | `EvalRunner`, `EvalArtifactManifest` | #23, #34 | Benchmark manifests, pass@k, solved@budget, contamination checks, source loaders, MiniF2F adapter, row-adapter extension point, and artifact writers landed; additional dataset adapters remain future. |
| §9 Known risks | current / future-tuning | TODO SearchConfig exclusions, code surface | #24, #35 | Risk ownership and the max-tree/pruning stance are explicit; empirical tuning remains. |
| §10 Repo boundary/release | current | README, AGENTS, policy/env APIs | #4, #9, #20-#22 | `lean_client` schema/client boundary, optional Slime adapter, and rollout pseudocode are aligned. |
| §§11-16 Extension A | off-main-snapshot / future-only | `extensions/codex-full` branch | #25 | Implementation snapshot was moved off main; current main treats scaleout as future/deferred. |
| §§17-20 Extension B | off-main-snapshot / future-only | `extensions/codex-full` branch | #26 | Implementation snapshot was moved off main; current main treats formalization beyond core staging as future/deferred. |
| §§21-24 Extension C / TTT | off-main-snapshot / future-only | `extensions/codex-full` branch | #27 | Implementation snapshot was moved off main; current main treats TTT as future/deferred. |
| §§25-32 Extension D | off-main-snapshot / training-repo | `extensions/codex-full` branch | #28 | Implementation snapshot was moved off main; current main treats ablation execution as training-repo/future work. |
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
   - Resolved design boundary: search-path proof acceptance uses
     `/exec/verify`; future/off-main statement-check work is not search-path
     acceptance evidence.
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
   - Recovered local live smoke on 2026-07-01: Docker image
     `zzzzhi/kimina-lean-server:9820b9a` ran on
     `http://127.0.0.1:8017`, `/exec/limits` returned bounded caps, and
     `tests/test_e2e_search.py` passed with `7 passed`.
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
    - Pinned Slime API-compat tests can run under `[training]`, but they are not
      enough to call runtime rollout paths complete.
    - `tests/test_slime_live.py` is the opt-in live smoke for the real
      `async_generate_rollout` path through pinned Slime, SGLang, a Lean
      backend, and the configured tokenizer checkpoint.
    - Current 2026-07-01 local e2e evidence: `/exec` e2e passed against Docker
      Kimina on `http://127.0.0.1:8017`, and Slime adapter e2e passed direct,
      `puct_tree`, and `self_correct` with
      `LEANFOUNDRY_SLIME_E2E_LOCAL_GENERATOR=1`.
    - Landed after the failed live attempt: the live smoke now covers direct,
      `puct_tree`, and `self_correct`, requires emitted rows, and cleans up the
      backend in the same event loop. The local generator supplies a
      deterministic SGLang-compatible `/generate` endpoint and a temporary HF
      tokenizer, while the real pinned Slime package and live Lean backend are
      used.
    - Remaining gap: execute direct/tree/self-correct Slime e2e against actual
      deployed SGLang/Megatron services and run a trainer step before claiming
      training readiness.

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
    - Remaining gap: run the direct, tree, and self-correct rollout paths in a
      configured live environment. Until that passes, pseudocode alignment is
      not completion evidence.

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

25. Extension A is off-main snapshot / future work.
    - Current `main` has no `leanfoundry.scaleout` package, router CLI, router
      worker CLI, or `[scaleout]` optional extra.
    - The pre-split implementation snapshot is preserved on
      `extensions/codex-full`, but it is not trusted current implementation.
    - Any future scale-out re-import must start from current `main`, review the
      snapshot code against the current interfaces, and pass relevant live e2e.

26. Extension B is core staging plus off-main snapshot / future work.
    - Current `main` keeps the durable staging table/model, including
      `FormalStatementStagingRecord.header` and migration v7.
    - Current `main` has no `leanfoundry.formalization` service pipeline:
      promotion helpers, statement verifier, semantic judge, embedding dedup,
      HTTP formalizer, and draft/retry orchestration are off-main/future.
    - Any future autoformalization work needs live staged-corpus/backend
      evidence before it can be called done.

27. Extension C / TTT is off-main snapshot / future work.
    - Current `main` has no `leanfoundry.ttt` package, TTT schemas, TTT replay
      table, TTT adapter, or TTT orchestration loop.
    - The pre-split snapshot on `extensions/codex-full` is historical material,
      not current implementation.
    - Future TTT still needs an approved per-problem search source, a concrete
      trainer/reload adapter, and live end-to-end evidence.

28. Extension D is training-repo / future work.
    - Current `main` has no ablation-plan schemas, budget guard, SQLite budget
      meter, or `leanfoundry-budget-meter` CLI.
    - Actual pass@N sweeps, optimizer execution, checkpoint production,
      distributed metering, serving wrappers, and outcome reports belong to the
      downstream training/deployment stack unless explicitly reintroduced.

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
    - Landed after review: `samples.py` uses Slime's native
      `Sample.append_response_tokens(...)` when rows carry
      `slime_response_log_probs`, and uses an explicit
      `leanfoundry_verified_without_rollout_logprobs` fallback for verified
      search rows because the pinned Slime API rejects trainable appended tokens
      without rollout log-probabilities.
    - Landed: Slime runner theorem conversion and batch validation reject
      missing/default env profiles, mixed profile batches/runs, and
      theorem/backend profile mismatches unless explicit mixed routing is
      enabled.
    - An opt-in live full-stack rollout smoke exists for SGLang plus a Lean
      backend. The local deterministic-generator mode now proves
      tokenizer-backed Sample construction through real Slime and live Lean,
      but trainer acceptance is not done until the relevant real
      Slime/SGLang/Megatron e2e path passes.
