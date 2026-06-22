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

### Core Verification And Data Spine

1. Test/dev environment is not runnable in this checkout.
   - Evidence: `pyproject.toml` and `uv.lock` point `lean-client` at
     `../kimina-lean-server/packages/lean-client`, which is missing locally, so
     `uv run --no-dev --with pytest pytest` fails before collection.
   - Impact: backend-facing contracts cannot be verified in this workspace.

2. Environment profiles are under-enforced relative to the design.
   - Design says every Lean execution is tied to a pinned env profile with
     Lean/Mathlib/header identity.
   - Code allows `EnvBackendConfig.env_profile="default"` and `EnvProfile`
     performs only light string/path validation.
   - Impact: the current schema/config surface does not yet prevent accidental
     env-profile mixing.

3. SQL/Pydantic consistency testing is too shallow for the stated contract.
   - Repo guidance says Pydantic models are source of truth and SQL must match.
   - Current test checks column names, not nullability, defaults, checks, or
     types.
   - Example: required `ATypeDataRecord.theorem_id` is nullable in SQL;
     required `FormalStatementStagingRecord.lean_statement` / `env_profile` are
     nullable in SQL.

4. Durable schema leaks a concrete backend name.
   - `verified_by_kimina` appears in SQL and Pydantic data records.
   - This conflicts with the boundary rule that concrete implementation names
     stay behind the `EnvBackend` adapter boundary.
   - Track whether to rename to backend-neutral language before the first
     stable migration is treated as durable API.

5. Replay persistence is schema/protocol-only.
   - Migrations and `ReplayStore` protocol exist, but there is no concrete
     SQLite implementation and no search-result-to-store writer.
   - This blocks the durable trajectory/value spine promised by the design.

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
