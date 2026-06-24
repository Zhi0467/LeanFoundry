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
- `external-stale-risk`: external facts may have changed and need fresh source
  verification before publication claims.

| Design section | Status | Evidence checked | Issue refs | Missing coverage / action |
|---|---|---|---|---|
| Project branding | current | `README.md`, `AGENTS.md`, package layout | - | Keep as infrastructure identity; no code issue found. |
| Open Questions / Concerns | stale / needs-both | schemas, proofsearch extraction/rendering, provenance | #6, #16-#18 | Remove resolved G1-G4 text; keep HER/rendering/policy-context/negation residuals. |
| System Landscape | external-stale-risk | local docs only | #29 | External system claims need web/source refresh before public-facing publication. |
| Extensions and Roadmap | needs-design | package layout, extension code absence | #25-#28 | Mark core vs extension gates more sharply; avoid implying extension components exist. |
| System Architecture | needs-both | module layout, replay/eval/rl_engine protocols | #5, #19, #23, #25, #30 | Single-machine diagram includes trainer/inference/data/eval pieces that are mostly protocols or training-repo work. |
| Design Principles | needs-both | current code and trackers | #2, #5, #23, #30 | P3/P10 durable spine/preemptibility are design goals, not implemented guarantees. |
| §1 Environment Profiles | needs-code | `EnvBackendConfig`, `EnvProfile`, theorem/artifact schemas | #2 | Replace ambiguous defaults; validate profile/header/hash identity. |
| §2.1-2.7 Kimina `/exec` backend | needs-both | `EnvBackend` protocol, `KiminaEnvBackend`, remote `lean-client` lock | #7, #9, #31 | Client protocol exists; server mode/state store/scheduler behavior are not proven by this checkout. |
| §2.8 Validation Harness | stale / needs-code | search verification paths, tests | #7, #31 | Use `/exec/verify`; build replay/latency/cache validation harness. |
| §3.1-3.1.1 State structure / LeanTree | needs-design | `FactorizedProofState`, expansion split logic | #10 | Separate current minimal state schema from future LeanTree/MCGS identity research. |
| §3.2 AND/OR UCB selection | needs-design | `_selection.py`, runtime-tree tests | #11 | Adopt current local PUCT/hardest-child as v0 or implement global-UCB/LCB later. |
| §3.3 Expansion | needs-code | `PolicyClient`, `_expansion.py`, action text storage | #12 | Add policy request/history context for tactic history and comments. |
| §3.4 HER | needs-code | `extract_training_artifacts`, `TrainingSample` schema | #17 | Add node-general subtree extraction and independent reverify. |
| §3.5 Value data | needs-code | `ValueLabel`, extraction logic, TODO | #17 | Make effort node-local; complete disproved/root/internal semantics. |
| §3.5.1 Negation pruning | future-only / needs-code | config/provenance helper, expansion path | #16 | Keep default off; wire only after DISPROVED prep and trace evidence. |
| §3.6 Supported algorithms | stale | `SearchAlgorithm`, `build_engine` | #14, #32 | Mark tactic beam, optimistic/RMaxTS, MCGS, AND/OR MCGS as enum-only/future. |
| §3.7 Search roadmap | needs-design | implementation log, factory, TODO | #14, #19, #32 | Rebase roadmap around implemented direct/self-correct/tree wedges and deferred algorithms. |
| §4.1 A-type data | needs-design | `ATypeDataRecord`, SQL migration | #3, #8 | Schema nullability and backend-neutral verification naming are fixed; design examples still need a de-stale pass. |
| §4.2 B-type data | needs-code | `TheoremRecord`, SQL migration | #2, #3 | Tighten env/split/profile invariants before data ingress. |
| §4.3 Trajectories/value labels | needs-code | `TrajectoryRecord`, `TrainingArtifacts`, SQL | #5, #8, #17, #33 | Add concrete store/writers and decide failure/eval/cleanup persistence. |
| §4.4 Formalizer output | future-only / needs-code | staging schema only | #26 | Staging table exists; pipeline/promotion/dedup/judge absent. |
| §5 Hardware / Qwen / Phase -1 | training-repo | `rl_engine` placeholder, pyproject deps | #20, #24 | Keep hardware/model/profiling in training repo; infra only exposes metrics/artifacts. |
| §6 Data for each stage | training-repo / needs-code | replay protocol, extraction artifacts | #5, #19, #20 | Stage data recipe is training-repo; infra must provide durable artifacts. |
| §7 Training pipeline | training-repo / future-only | `rl_engine`, `proofsearch`, replay protocols | #19, #20, #22 | Stage loops not implemented here; keep consumer-facing interfaces stable. |
| §8 Metrics | needs-code / training-repo | eval protocol, schemas | #23, #24 | Split infra metrics/artifacts from training progression/W&B metrics. |
| §8.5 Evaluation protocol | needs-code | `EvalRunner`, `EvalArtifactManifest` | #23, #34 | Add benchmark specs, pass@k, solved@budget, contamination checks, artifact writers. |
| §9 Known risks | needs-design | TODO SearchConfig exclusions, code surface | #24, #35 | Assign each risk to infra vs training; reconcile max-tree/pruning with current config stance. |
| §10 Repo boundary/release | needs-design | README, AGENTS, policy/env APIs | #4, #9, #20-#22 | Update `lean_client`, policy/value, rollout pseudocode, Docker/dev/versioning claims. |
| §§11-16 Extension A | future-only / needs-design | no router/store/state-portability code | #25 | Split router, state portability, distributed replay, and migration actions. |
| §§17-20 Extension B | future-only / needs-code | staging schema | #26 | Formalizer, semantic judge, dedup, promotion, difficulty estimation absent. |
| §§21-24 Extension C / TTT | future-only / stale | no TTT or reload interfaces | #27 | Do not claim MCGS/HER/reload already exist. |
| §§25-32 Extension D | future-only | direct/tree/best-first only | #28 | Add frozen curriculum, arms, budget ledger, crossed eval, outcome tracking later. |
| Appendix A Aristotle reference | needs-design | current search/extraction code | #10-#17, #32 | Mark as reference, not current behavior; explicitly defer global/graph semantics. |

### Core Verification And Data Spine

1. Test/dev environment is runnable from the remote `lean-client` lock.
   - Resolved: `pyproject.toml` and `uv.lock` now source `lean-client` from the
     pinned GitHub repository instead of a missing sibling checkout.
   - Current evidence: `uv run --no-dev --with pytest pytest` collects and
     passes in this workspace.

2. Environment profiles are under-enforced relative to the design.
   - Design says every Lean execution is tied to a pinned env profile with
     Lean/Mathlib/header identity.
   - Code allows `EnvBackendConfig.env_profile="default"` and `EnvProfile`
     performs only light string/path validation.
   - Impact: the current schema/config surface does not yet prevent accidental
     env-profile mixing.

3. SQL/Pydantic consistency testing is still narrower than the full contract.
   - Repo guidance says Pydantic models are source of truth and SQL must match.
   - Resolved: the initial migration test now checks column presence,
     nullability, and SQL defaults for direct model-backed fields, and the
     concrete nullability examples found in the audit are fixed.
   - Still open: checks and type affinity are not yet compared against Pydantic
     constraints.

4. Durable schema leaks a concrete backend name.
   - Resolved for the initial schema: the SQL and Pydantic data records now use
     `verified_by_backend`.
   - Keep future durable fields backend-neutral before treating migrations as a
     stable API.

5. Replay persistence has a concrete Path-A implementation.
   - Resolved for the baseline: `SQLiteReplayStore` and
     `persist_search_result(...)` write theorem, trajectory, policy-example,
     value-label, and verified A-type rows.
   - Still open beyond Path-A: richer failure persistence, cleanup outbox,
     eval artifact writers, and compatibility/versioned migration policy.

### Stale Or Ambiguous Design Text

6. Open Questions G1-G4 are stale or partly stale.
   - Implemented: `TheoremSpec.initial_lean_block`, `TheoremSpec.source`,
     `ValueLabel.disproved`, value label `weight`, `TacticNode`, and full
     sampled tactic text preservation.
   - Still open: HER extraction, tree rendering correctness, policy prompt
     history/comment context, and downstream training conversion.

7. §2.8 validation harness still says final proof verification through
   legacy `/verify`.
   - Current search acceptance uses `/exec/verify` through `verify_one`.
   - The design should distinguish Extension B statement checks from search-path
     proof acceptance.

8. §4 data-store examples are partly stale.
   - The design still describes some tactic data as a flat JSON list, while the
     schema has `TacticNode` / `ProofTree`.
   - The design's `state_value_labels` SQL example omits `weight`, which now
     exists in code and migration.

9. §10 overstates the `lean_client` boundary.
   - Current contract allows importing `lean_client.exec_models` directly; only
     `kimina_backend.py` constructs `AsyncLeanExecBackend`.
   - The design still reads as if `lean_client` appears only in the adapter.

10. §3.1.1 and Appendix A can be misread as current runtime behavior.
    - The design references coupling groups / tactic-history hash as
      `FactorizedProofState` semantics, but the current state schema is minimal
      and stores only current open goals plus resume token.
    - Appendix Aristotle text describes transition-based action dedup and
      all-metavariable multi-goal bundling; current code dedupes tactic text and
      splits by backend `sibling_dep` coupling groups.

### Search Behavior Gaps

11. Selection semantics differ from §3.2 / Appendix A.
    - Design describes global highest-UCB action selection plus LCB
      hardest-child descent.
    - Code performs local root-to-leaf PUCT descent and chooses the hardest
      child by open-goal count, visits, and stable tie order.
    - Decision needed: update design to make current v0 selection the contract,
      or implement the global-action / LCB semantics.

12. Policy prompt history/comment context is not represented at the API.
    - Design requires policy prompts to include full tactic history with inline
      comments.
    - Code preserves sampled tactic text in actions, but
      `PolicyClient.sample_tactics(...)` receives only the selected
      `FactorizedProofState`; expansion does not pass proof history.

13. Direct search is not the design's pass@k/batch-eval mode.
    - Design says direct whole-proof sampling verifies all attempts in batch and
      reports pass@k.
    - Code verifies sequentially and returns on the first accepted proof.
    - This may be fine for `SearchEngine.search(...)`, but eval needs a separate
      pass@k runner or a direct mode that returns all attempts.

14. Supported-algorithm wording is ahead of code.
    - Implemented: direct, self-correct, PUCT tree / `AND_OR_TREE` alias, and
      best-first.
    - Enum-only/future: tactic beam, optimistic/RMaxTS, MCGS, AND/OR MCGS.
    - Design currently says LeanFoundry "supports" all modes.

15. Best-first design text is stale.
    - Design says best-first combines policy logprob, value, depth, and novelty.
    - Code uses leaf value estimate, configured missing-value score, goal count,
      visits, and deterministic tie order.

16. Negation pruning is scaffolded but not wired.
    - Code has `SearchConfig.try_negation`, provenance helper, and
      `mark_state_disproved(...)`.
    - `AndOrSearchEngine` never applies provenance gating and expansion sends
      only sampled policy tactics.

17. HER and value-label extraction remain partial.
    - HER is described as proved-subtree extraction plus independent reverify,
      but current extraction emits only root proof candidates and derived
      policy/value artifacts.
    - Censored negatives use attempt-level budget and initial states, not
      node-local effort over failed nodes.
    - Disproved-root top-level status and internal disproved-node labels remain
      unresolved.

18. Proof rendering is intentionally narrow.
    - Current renderer is verified-gated and fail-closed, but it is still
      positional, has limited real-Lean fixture coverage, and cannot reconstruct
      arbitrary focused goal groups.
    - Missing design contract: `GoalComponent` currently carries order/name, not
      a stable goal identity that would let the renderer safely reconstruct
      arbitrary non-contiguous focused groups.

### Training, Eval, And Repo Boundary

19. Part II Stage 3 wording is ahead of current implementation.
    - The design presents Stage 3 as MCTS/MCGS plus HER plus value labels.
    - Current core is AND/OR tree search; graph/MCGS, node-general HER, real
      value adapters, and bonded labels remain deferred.

20. Slime integration is placeholder-only in this repo.
    - Design says "we use Slime" and specifies dependency/test behavior.
    - Code has `RLEngineBase` and `SlimeAdapter`, but every SlimeAdapter method
      raises `NotImplementedError`; `pyproject.toml` has no Slime dependency.

21. Policy/value API examples in §10 are stale.
    - Design puts `estimate_values(...)` on `PolicyClient` and shows
      `sample_proofs(...) -> list[str]`.
    - Code separates `PolicyClient` and `ValueClient`; `sample_proofs` returns
      `list[list[str]]`.

22. Slime rollout pseudocode names APIs that do not exist.
    - Examples import/use `make_env_backend`, `samples_from_search_results`, and
      a different `run_search_batch(...)` signature.
    - Current env package exports only protocol/config, and `run_search_batch`
      requires explicit `policy_client`, `value_client`, and `env_backend`.

23. Evaluation is mostly aspirational.
    - Code has `EvalRunner` protocol and `EvalArtifactManifest` schema only.
    - Missing: benchmark loaders, pass@k implementation, solved@budget curves,
      artifact writers, report generation, and fixed-model eval runners.
    - Design says "Four modes" but currently lists only three modes.

24. Risk ownership is mixed.
    - Infra-owned risks: env-profile verification, search memory, replay,
      renderer, eval artifacts, backend throughput.
    - Training-repo risks: GRPO reward hacking details, KL policy, weight sync,
      optimizer/model fit, W&B/reporting.

### Extensions

25. Extension A is purely future-facing.
    - No router, router adapter, state compression/export/import layer,
      autoscaling metrics, Postgres store, or Redis Streams store exists.
    - Design claim that "only URLs in configuration files change" is too strong;
      distributed cleanup/cancel, state portability, and replay-store semantics
      need explicit adapter work.

26. Extension B has staging schema only.
    - `formal_statements_staging` exists in SQL/Pydantic.
    - Missing: LLM draft/retry pipeline, statement-verify wrapper, semantic
      judge, embedding dedup, promotion workflow, and difficulty estimator.
    - Design pseudocode returns string difficulty buckets, while schema stores
      `difficulty_estimate: float | None`.

27. Extension C / TTT overstates current support.
    - Design says LeanFoundry already has MCGS, HER extraction, and policy reload
      support for TTT.
    - Code has no MCGS implementation, node-general HER, `TTTAdapter`,
      `TTTConfig`, policy adapter reload semantics, or TTT loop.

28. Extension D has no experiment harness.
    - Missing: frozen-curriculum materializer, per-arm replay/checkpoint
      namespace, hard compute ledger, `budget_account_id` plumbing,
      crossed-eval wrappers, and S-full MCGS+HER arm.
    - Design lists value AUC/calibration for no-value/no-value-loss arms; clarify
      what value model is evaluated for each arm.

### Additional Coverage Findings

29. System Landscape contains external claims that were not live-verified.
    - Treat this section as background, not code contract.
    - Before public release or citation-heavy docs, refresh claims about current
      open/closed systems and reported results from primary sources.

30. Architecture and principles overstate current implemented modules.
    - The single-machine diagram includes trainer, inference engine, SQLite data
      buffer, evaluation, and MCGS search as if they are all runnable pieces.
    - Current repo has protocols/schemas for replay, eval, and RL integration,
      but no concrete trainer/inference/replay/eval implementation.
    - Design principles P3 and P10 should be read as targets: durable data spine
      and preemptible resume/checkpointing are not implemented guarantees yet.

31. `/exec` server behavior is mostly outside this checkout's evidence surface.
    - LeanFoundry client protocol and adapter exist, but the local missing
      `lean-client` checkout prevents verifying server limits, state-store,
      cleanup/cancel/stats, scheduler, and mode behavior here.
    - Keep server behavior claims in the design doc tied to backend-side tests or
      imported lean-client contracts, not inferred from LeanFoundry alone.

32. Tactic beam and optimistic/RMaxTS need explicit deferral.
    - They appear in the algorithm enum/design family, but no engine
      implementation exists.
    - Treat them like graph/MCGS: not on the core path until replay/eval proves
      the direct/tree/best-first baseline.

33. Durable artifact schema is underspecified.
    - `ReplayStore` covers theorem, A-type data, trajectory, and value labels,
      but not search-attempt records, extraction failures, cleanup outbox rows,
      or eval manifests.
    - Decide table vs artifact-file storage, deterministic ids, hashes, and
      failure persistence before implementing writers.

34. Eval needs benchmark/env-profile manifests before loaders.
    - `EvalArtifactManifest` has a benchmark string, but contamination rules need
      a concrete benchmark spec/manifest carrying source, split, env profile,
      compatibility status, and fixed held-out assignment.

35. Risk section has unresolved config tension.
    - Design risk mitigation proposes max tree size and pruning, while
      `todo.md` says max tree nodes are not in `SearchConfig` until design,
      traces, or profiling justify them.
    - Resolve whether tree memory protection is an operational guard outside
      `SearchConfig` or a future search budget knob.
