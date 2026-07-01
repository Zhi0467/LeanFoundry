# LeanFoundry Implementation Log

This file records completed implementation slices and review follow-ups. Keep
future-facing plans in [`todo.md`](todo.md).

## 2026-06-19: Scaffold And Backend Contract

- Added the first schema/interface scaffold and plain-language field
  descriptions.
- Added the initial SQL migration comments and schema/database guardrails.
- Removed the local `/exec` schema mirror. LeanFoundry now imports
  `lean_client.exec_models`; `lean-client` owns the wire schema.
- Updated `EnvBackend` to expose the coalesced `step(...)` hot path instead of a
  primary `step_batch(...)` API.
- Promoted `lean-client` from dev-only to runtime dependency. Only
  `kimina_backend.py` constructs the transport.

## 2026-06-19: FactorizedProofState Simplification

- Reduced `FactorizedProofState` to a tree-search node representation:
  `env_profile`, `goal_components`, `pretty_state`, `state_token`, and optional
  `serialized_lean_state`.
- Removed merge-identity fields from the state model because v0 is tree search,
  not graph search.
- Kept hypotheses on `GoalComponent` and removed the redundant local-context
  wrapper.
- Updated the design doc with the v11.2 tree-search note.

## 2026-06-19: Runtime Tree Slice

- Added private runtime tree classes in `_tree.py`: OR `StateNode`, AND
  `ActionNode`, status propagation, parent/child links, visit/value counters,
  node ids, and a tree-level tactic-call counter.
- Added `_budgets.py` for deterministic tactic-call accounting.
- Added `_selection.py` helpers for empirical priors, prior/value PUCT action
  selection, and value-free hardest-child selection.
- Added tests for AND/OR invariants, budget accounting, full tactic text
  preservation, and deterministic selection.

## 2026-06-20: Expansion Slice

- Added `_expansion.py` to sample one policy batch, call one
  `EnvBackend.step(...)`, account for executed tactics, and attach actions plus
  child states.
- Converted backend `ExecGoalInfo` into `GoalComponent` /
  `FactorizedProofState`.
- Mapped step statuses into runtime tree mutations or operational outcomes.
- Added tests for policy/backend single-call behavior, duplicate prior counting,
  already-tried tactic skipping, goal conversion, error handling, operational
  statuses, and budget exhaustion.

## 2026-06-20: Backprop Slice

- Added `_backprop.py` for visit-count propagation from executed actions up to
  the root.
- Kept status propagation inside `SearchTree` mutation methods.
- Added tests for direct action backprop, ancestor path accounting, and
  expansion-batch visit accounting.

## 2026-06-20: Goal Focus Contract

- Verified live that `auto_resume` is not exact group focus.
- Standardized split-goal resume on backend `goal_group`.
- Backend commit `27dac09` added `ExecStepBatchItem.goal_group` and raw
  `goal.continue` group resume.
- LeanFoundry added `EnvBackend.step(..., goal_group)` and
  `StateNode.focus`.
- Expansion now groups goals by transitive closure of `sibling_dep`, creates one
  child per coupling group, and resumes split children through `goal_group`.

## 2026-06-21: First Concrete Search-Engine Slice

- Added direct whole-proof search in `direct.py` with `DIRECT` and
  `SELF_CORRECT`.
- Added concrete AND/OR tree search in `and_or.py`.
- Added `SelectionStrategy`, `PuctSelection`, and `BestFirstSelection`.
- Added async value evaluation and AND/OR-aware value backup.
- Added solved-tree extraction and final verification through `/exec/verify`.
- Added `build_engine(config)` and `run_search_batch(...)`.
- Added tests covering direct/self-correct, PUCT tree, best-first tree with fake
  values, operational aborts, factory dispatch, and the batch driver.

## 2026-06-21: Review Follow-Ups

- Fixed coupled multi-goal extraction by rejecting unsupported split children
  with multiple focused goals instead of rendering misleading Lean.
- Made `SearchConfig()` default to `PUCT_TREE`, since `TACTIC_BEAM` is still
  unimplemented.
- Split direct whole-proof budget from tree tactic-call budget with
  `max_direct_candidates` and `direct_candidates_per_round`.
- Exposed tree-selection hyperparameters:
  `puct_exploration_weight` and `best_first_missing_value_score`.
- Refined expansion operational-status handling:
  `invalid_state_token` and `cancelled` poison the expansion; all-overloaded
  surfaces retryable backpressure; mixed overloaded plus executed statuses are a
  backend protocol violation.
- Split shared helpers into `_common.py`, direct-only helpers into
  `_direct_utils.py`, tree initialization into `_tree_init.py`, and tree
  utilities into `_and_or_utils.py`.
- Confirmed `lean_client.verify_one` delegates to `/exec/verify` and does not
  create state-store entries, so direct search does not call cleanup.

Validation for this slice:

- `uv run --no-dev --with pytest pytest` passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` passed.
- `git diff --check` passed.

## 2026-06-21: Synthetic Initialization Layer Clarification

- Renamed and documented the runtime tree's synthetic initialization action.
- Clarified that `ProofTree` extraction skips the synthetic root/action layer
  and starts from the real backend-created initial states.

## 2026-06-21: Retry And Terminal-State Decisions

- Recorded v0 operational semantics for mixed overloaded/executed step results,
  all-overloaded retry/backoff, and invalid state tokens.
- Recorded training semantics for runtime `PROVED`, semantic `DISPROVED`, and
  root-`OPEN`-at-stop unproved outcomes.
- Expanded the tracker/design text to preserve the reasoning details:
  operational backpressure is not search evidence, runtime `OPEN` remains the
  unresolved tree status, and top-level `EXHAUSTED`/unproved outcomes are
  effort-gated censored negatives.
- Recorded follow-up review constraints: wire existing lean-client overload
  retry knobs through backend config, expose concrete cleanup/cancel response
  types before checked lifecycle handling, and define an explicit training
  artifact envelope before policy/value extraction.
- Kept extraction/rendering active because renderer correctness remains
  unresolved beyond narrow verified fixtures.

## 2026-06-21: Operational, Extraction, And Lifecycle Slice

- Added `EnvBackendConfig.max_overloaded_retries` and
  `overload_backoff_seconds`, forwarding them through `KiminaEnvBackend` to
  lean-client without adding a LeanFoundry search-loop retry path.
- Made mixed `overloaded` plus executed step results a structured backend
  protocol `ERROR`: executed tactic attempts are charged, partial action
  children are discarded, and all-overloaded remains an operational error with
  zero tactic budget.
- Added the explicit `TrainingArtifacts` envelope with proof candidates,
  positive policy examples, value labels, extraction/rendering failures, and
  diagnostics. `SearchResult` now carries this envelope separately from scalar
  diagnostics.
- Added `ExtractionContext` and value-label extraction for verified proved
  paths, semantic disproved states, and root-runtime-`OPEN` unproved attempts.
  Proof/policy/proved-value artifacts are gated on final `/exec/verify`.
- Kept the current proof rendering canonical and narrow while making rendering
  failures explicit; `sorry` replacement now skips line comments, nested block
  comments, and strings.
- Added `SearchAttemptContext` with runner-owned `attempt_id`,
  `search_item_id`, `verify_item_id`, and cleanup knobs. `run_search_batch(...)`
  allocates contexts for normal callers and accepts explicit contexts for
  runners/tests.
- Split tree lifecycle ids: tree `create_states`, `step`, and cleanup use
  `search_item_id`; final `/exec/verify` uses `verify_item_id`. Direct search
  verifier attempts use `f"{verify_item_id}:{k}"` and do not call cleanup.
- Added checked cleanup with bounded retries for `deferred` backend cleanup
  responses. Cancelled runner tasks call `cancel([search_item_id])`, then retry
  cleanup.

Validation for this slice:

- `python3 -m py_compile` passed for touched modules and tests.
- `git diff --check` passed.
- `uv run --no-dev --with pytest pytest ...` is blocked in this workspace
  because the editable dependency
  `../kimina-lean-server/packages/lean-client` is missing.

## 2026-06-22 — Audit fixes for the lifecycle/artifacts slice

A multi-agent review of the point 1-4 work surfaced correctness bugs the slice
tests masked. Root cause: the full suite was not runnable in the authoring
workspace, so green came from `py_compile`, not pytest, and the backend-facing
paths were tested against fabricated response shapes.

- `cleanup_search_state` read `response.deferred` / `response.deleted`, neither
  of which exists on `ExecCleanupResponse` (`deleted_items:
  list[ExecCleanupResult]`, per-item `status`). Against the real backend the
  deferred-retry never fired and `cleanup_deleted` was always `0`. Rewrote it to
  iterate the typed model (`status == "deferred"` retried, `status == "deleted"`
  counted) and removed the `getattr` reflection helpers. The cleanup/cancel test
  fakes returned fabricated `SimpleNamespace` shapes that hid this; they now
  return real `ExecCleanupResponse` / `ExecCancelResponse`.
- `initialize_search_tree` attached initial states one at a time, so an
  already-closed hole arriving before an open one flipped the synthetic action
  to terminal mid-loop (uncaught `ValueError`). Added
  `SearchTree.add_child_states` (attach all, refresh once) and used it.
- Proved-tree extraction could raise a bare `ValueError` (lexer miss, zero-goal
  state) and crash the attempt; the engine now degrades any extraction failure
  to a clean `ERROR` result, and `_render_lean_with_proofs` raises
  `UnsupportedProofExtraction`.
- `_line_indent_before` returned `""` for a `sorry` preceded by a bullet/tactic,
  de-indenting multi-line scripts to column 0; it now uses the sorry's column.
- Fixed the three `mypy` errors the slice introduced (`label: Literal[0, 1]`,
  `Mapping` diagnostics, `_refresh_action_value` None-narrowing).

Validation: `uv run --no-dev --with pytest pytest` -> 63 passed; `flake8` clean;
`mypy` clean on the touched modules; `git diff --check` clean.

Deferred (unreachable in v0, belongs to later slices): the DISPROVED extraction
branch labels the wrong state and would report `EXHAUSTED` (negation slice); the
driver's `asyncio.gather` has no per-theorem isolation (runner slice).

## 2026-06-22 — Runner isolation and best-effort lifecycle

Pulled the two reachable-today defects out of the lifecycle-hardening TODO after
re-reading the code; the rest of that section stays future work.

- `run_search_batch(...)` now isolates non-cancellation failures per theorem.
  `run_one` catches a stray policy/backend exception and returns that theorem's
  `SearchResult(ERROR, operational_status="runner_exception")` via
  `_runner_error_result`, instead of letting a bare `asyncio.gather(...)`
  propagate the first exception and orphan the still-running siblings.
  `CancelledError` still unwinds the whole gather.
- Cleanup is now best-effort everywhere it could mask the primary outcome.
  `cleanup_search_state_best_effort` runs cleanup, returns its diagnostics, and
  on failure returns a `cleanup_failed` diagnostic instead of raising. The tree
  engine's `finish(...)` and its outer `except` both use it, so a cleanup
  transport error can no longer discard an already computed `PROVED` result or
  mask the original exception. The driver's cancellation path uses
  `cancel_search_state_best_effort` + `cleanup_search_state_best_effort` so a
  failed cancel/cleanup cannot replace the propagating `CancelledError`.
- Reworded the TODO `DISPROVED` item: the branch already labels the real initial
  state, so the real gaps are the `EXHAUSTED` misreport (a disproved root never
  yields `SearchStatus.DISPROVED`) and missing disproved-internal-node coverage.
  Both stay gated behind `try_negation`.
- Tests: per-theorem isolation (one theorem raises, sibling still proves);
  cleanup failure preserves a `PROVED` result with a `cleanup_failed`
  diagnostic; cleanup failure during an unexpected error still propagates the
  original exception.

Known residual (still in TODO): cancellation covers only `search_item_id`, not
`verify_item_id`/`verify_item_id:k`, and a cancel failure during unwind is
swallowed without a runner event. (The two cleanup-diagnostic residuals noted
here — `cleanup_failed` dropped on the unexpected-exception path and overstated
`cleanup_attempts` — were resolved in the next entry.)

Validation: `uv run --no-dev --with pytest pytest` -> all pass; `flake8` clean;
`mypy` clean on the touched modules; `git diff --check` clean.

## 2026-06-23: Remote lean-client Source

- Switched the `lean-client` uv source from the sibling local checkout to
  `https://github.com/Zhi0467/kimina-lean-server.git`, subdirectory
  `packages/lean-client`, so clean checkouts and CI no longer depend on local
  repo state.
- Documented the remote source and lock-refresh command in `README.md`.
- Added a README section showing how a training repo should depend on
  LeanFoundry, inject policy/value/backend clients, and avoid importing Lean
  server internals.
- Updated CI to check the lockfile and run tests/lint against locked remote
  sources.

Validation:

- `uv lock --check` passed.
- `uv sync --group dev --reinstall-package lean-client` rebuilt `lean-client`
  from the locked GitHub source.
- `uv run --isolated --locked --no-dev --with pytest pytest` passed: 66 tests.
- `uv run --isolated --locked --no-dev --with flake8 flake8 leanfoundry tests`
  passed.
- `git diff --check` passed.

## 2026-06-23: Resolve lifecycle diagnostic residuals

Closed the two cleanup-diagnostic residuals from the runner-isolation entry and
tightened the engine contract so the fix is structural, not patched in.

- `cleanup_search_state(...)` is now best-effort itself: a backend/transport
  exception is captured into the returned `CleanupReport` as `failed` with the
  actual attempt count, instead of raised. `cleanup_attempts` is now accurate on
  failure (no longer overstated as `cleanup_max_attempts`), and the redundant
  `cleanup_search_state_best_effort` wrapper was removed. `cleanup_failed`
  appears in diagnostics only when cleanup actually failed.
- The tree engine is now total: its unexpected-exception path returns an ERROR
  `SearchResult` (`operational_status="unexpected_error"`, the primary
  `failure_message`, and cleanup diagnostics) instead of re-raising. A cleanup
  failure during an unexpected error is therefore preserved on the result as
  `cleanup_failed` rather than discarded and rebuilt as a driver-level
  `runner_exception`. `CancelledError` still propagates.
- The driver's `except Exception` net now mainly covers direct search (no search
  state) and any genuine engine bug; per-theorem isolation is unchanged.
- Tests updated: the two "engine raises on unexpected/limits error" tests now
  assert ERROR results; the cleanup-failure-during-unexpected-error test asserts
  the result carries both `failure_message` and `cleanup_failed`.

Still open (TODO point 2): cancellation covers only `search_item_id`, and a
cancel failure during unwind is swallowed without a runner event.

Validation: `uv run --no-dev --with pytest pytest` -> 66 passed; `flake8` clean;
`mypy` clean on `leanfoundry/proofsearch/`; `git diff --check` clean.

## 2026-06-23: Refresh lean-client after kimina update

- Inspected kimina commits `7dba5cc1..310e6c13`. The `lean-client`
  consumer-facing backend signatures and `/exec` Pydantic models used by
  LeanFoundry did not change.
- Refreshed `uv.lock` to kimina commit `310e6c13`.
- Updated the design doc's scheduler/config note for kimina's new
  resource-sized server launch defaults: worker count is CPU plus
  memory-bounded, and in-flight/queued caps are derived from worker count. The
  LeanFoundry runtime contract remains `/exec/limits`.
- Updated `README.md` to show the downstream Docker server launch path
  (`docker pull`, `docker run`, `/exec/limits`) before the client usage example.

Validation:

- `uv lock --check` passed.
- `uv sync --group dev --reinstall-package lean-client` rebuilt `lean-client`
  from the locked GitHub source.
- `uv run --isolated --locked --no-dev --with pytest pytest` passed: 66 tests.
- `uv run --isolated --locked --no-dev --with flake8 flake8 leanfoundry tests`
  passed.
- `uv run --locked --no-dev --with mypy mypy leanfoundry/proofsearch` passed.
- `git diff --check` passed.

## 2026-06-24: Path-A schema baseline

- Added `PolicyExample.proof_prefix` so one policy row carries both the
  Markovian state and the root-to-state tactic prefix as provenance / optional
  prompt context.
- Relaxed `TrainingSample.whole_proof` to optional because per-node Path-A data
  does not require a rendered whole proof.
- Renamed the durable A-type proof verification flag from `verified_by_kimina`
  to backend-neutral `verified_by_backend` in Pydantic and SQL.
- Tightened the initial-migration consistency tests beyond column presence:
  required Pydantic fields must be non-null in SQL, non-null model defaults must
  have SQL defaults, and store-derived required SQL fields are explicit.
- Updated the design and tracker notes to record the Path-A contract: per-node
  policy/value examples are grounded by accepted `/exec` steps plus the
  sorry/admit guard, while final `/exec/verify` is an artifact gate and sampled
  audit path rather than the training-data gate.

Validation: `uv run --no-dev --with pytest pytest
tests/test_schema_database_consistency.py` -> 6 passed.

## 2026-06-24: Path-A soundness and render-free extraction

- Added a shared Lean token scanner for exact tokens outside comments and
  strings, and used it to mark tactics containing `sorry` or `admit` as DEAD at
  expansion attach-time. A backend `complete` response for a placeholder tactic
  can no longer prove a search action.
- Changed tree-search training extraction to walk the runtime solved tree
  directly. Positive `PolicyExample` rows now come from the proved action at
  each runtime state and carry a linear `proof_prefix`; bonded proved
  `ValueLabel` rows use node-local subtree effort from runtime visits.
- Decoupled Path-A artifacts from optional whole-proof rendering and
  verification. Rendering failures and final verifier rejections remain visible
  in `TrainingArtifacts.failures` and result diagnostics, but they no longer
  erase per-node policy/value data from a structurally solved tree.
- Kept whole-proof `ProofTree` artifacts verifier-status-bearing: accepted
  rendered proofs are proof candidates; rejected rendered proofs are retained on
  `SearchResult.proof_tree` with `verified=False` and a verification failure.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_expansion.py
  tests/test_extraction.py tests/test_search_engines.py` -> 42 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch
  tests/test_expansion.py tests/test_extraction.py tests/test_search_engines.py`
  passed.

## 2026-06-24: Path-A SQLite replay store and writer

- Added a concrete `SQLiteReplayStore` that applies the initial migration on a
  fresh database and persists theorem records, verified A-type proof rows,
  per-state policy examples, value labels, and trajectory records.
- Added a `policy_examples` table for the Path-A policy rows; state hashes and
  row ids are deterministic content hashes so repeated writes are idempotent.
- Added `persist_search_result(...)`, which writes a theorem attempt into the
  replay store and returns the `SearchResult` with replay diagnostics
  (`replay_trajectories`, `replay_policy_examples`, `replay_value_labels`,
  `replay_a_type_data`, and `replay_theorem_id`).
- Wired `run_search_batch(..., replay_store=..., model_version=...)` to
  stream-write each attempt after search completes. Replay write failures are
  reported in result diagnostics as `replay_write_failed` without masking the
  primary search outcome.
- Added driver coverage proving a solved tree-search attempt writes theorem,
  trajectory, policy, value, and A-type rows to SQLite.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_schema_database_consistency.py
  tests/test_package_import.py tests/test_search_engines.py` -> 33 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/replay
  leanfoundry/proofsearch/driver.py tests/test_schema_database_consistency.py
  tests/test_search_engines.py` passed.

## 2026-06-24: Subagent review fixes for Path-A and lifecycle

- Restored the top-level result contract: tree-search `SearchStatus.PROVED`
  again means the rendered whole-proof artifact passed final `/exec/verify`.
  Rendering failures and verifier rejections now return ERROR/CANCELLED as
  appropriate, while preserving Path-A policy/value artifacts and failure
  diagnostics.
- Made the placeholder guard conservative for interpolated strings such as
  `s!"{(by sorry : Nat)}"`; exact `sorry`/`admit` tokens inside interpolated
  strings now mark the action DEAD.
- Prevented initially complete synthetic initialization from emitting synthetic
  policy/value rows.
- Added SQLite schema versioning plus `0002_policy_examples.sql` so existing
  replay databases get the Path-A policy table.
- Made one replay attempt write atomic, made theorem identity immutable on id
  conflicts, let SQLite timestamp defaults fire, and persisted runner-level
  exception results when replay is enabled.
- Rejected duplicate runner-provided `attempt_id`, `search_item_id`, or
  `verify_item_id` before backend calls.
- Expanded cancellation coverage: tree cancellation now includes
  `verify_item_id`, and direct search cancels the active `verify_item_id:k`
  when cancellation lands during final verification.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_replay_store.py
  tests/test_search_engines.py tests/test_expansion.py` -> 46 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/replay
  leanfoundry/proofsearch tests/test_replay_store.py tests/test_search_engines.py
  tests/test_expansion.py` passed.

## 2026-06-24: Design de-stale pass after Path-A

- Added a v11.12 design note recording that Path-A core is implemented and that
  top-level `SearchStatus.PROVED` remains final-verify accepted, while Path-A
  policy/value artifacts are per-step grounded.
- Marked the `initial_lean_block`, value-label representation, and
  `TacticNode` trajectory gaps as resolved baseline work.
- Updated §3.2 to make local root-to-leaf PUCT plus the implemented
  hardest-child heuristic the v0 contract, with global highest-UCB/LCB left as
  reference/future material.
- Updated the best-first section to match the implemented
  value/missing-score/goal-count/visit/stable-order heuristic.
- Updated Appendix A value-label wording so accepted-step Path-A training data
  is distinct from top-level whole-proof verification acceptance.

Validation: docs-only; `git diff --check` included in the final verification
for this checkpoint.

## 2026-06-24: Schema consistency checks beyond column names

- Expanded the SQL/Pydantic consistency guard to cover SQLite type affinity and
  durable CHECK constraints, not just column names, nullability, and defaults.
- Aligned the initial schema with locally enforceable Pydantic record
  constraints: non-empty theorem statement, non-empty environment
  profile/source, non-negative policy/value depths and effort, bounded staging
  judge score, value-label domain, and disproved-negative invariants.
- Added the same non-negative policy depth constraint to the incremental
  `policy_examples` migration used by pre-Path-A databases.

Validation: included in the next checkpoint verification.

## 2026-06-26: Path-A review follow-ups

- Updated `AGENTS.md` and `CLAUDE.md` to state the landed Path-A contract:
  whole-proof candidates/A-type rows require final `/exec/verify`, while
  policy/proved-value artifacts are per-step grounded.
- Added durable theorem verifier metadata (`theorem_name`, JSON
  `allowed_axioms`) to the initial schema plus a `0003` migration, and made
  theorem identity validation include those fields.
- Documented the synchronous-transaction invariant in the replay writer and the
  fail-closed interpolated-string behavior in the Lean token scanner.
- Cleaned an incidental `ExtractionFailure` import path in the tree engine.

Validation: included in the next checkpoint verification.

## 2026-06-24: Design de-stale completion pass

- Updated the validation harness and training flow to use `/exec/verify` for
  search-path proof acceptance, while leaving REPL `/verify` only for
  Extension-B statement checks.
- Replaced stale current-path MCGS/MCTS/HER wording with the landed
  direct/self-correct/tree-search Path-A baseline, and marked beam,
  graph/MCGS, node-general HER, richer rendering, and TTT support as deferred.
- Refreshed §4 SQL examples to match the current migrations, including
  `policy_examples`, `proof_prefix`, value-label `weight`, and
  `verified_by_backend`.
- Narrowed the repository boundary section to the actual package contents:
  `lean-client` only at the EnvBackend adapter boundary, proofsearch direct/tree
  engines, replay SQLite store/writer, eval protocol stubs, and optional Slime
  integration through the training extra.

Validation: docs-only; included in the next checkpoint verification.

## 2026-06-24: DISPROVED status and value-label prep

- Mapped an explicitly `DISPROVED` runtime root to top-level
  `SearchStatus.DISPROVED` instead of falling through to `EXHAUSTED`.
- Extracted full-weight `ValueLabel(label=0, disproved=True)` rows for every
  explicitly disproved runtime state in proved, disproved, and open attempts.
- Added regression coverage for internal disproved-node extraction and the
  explicit-disproved-root engine path. This does not implement negation
  pruning; it only makes existing DISPROVED certificates observable and
  trainable.

Validation: included in the next checkpoint verification.

## 2026-06-26: e2e tier and mutation baseline

- Added `tests/test_e2e_search.py`: the first tests that drive a real theorem
  through `run_search_batch` against a live kimina-lean-server. They assert the
  Path-A contract that a runtime tree reaching `proved` is equivalent to final
  `/exec/verify` acceptance -- the divergence a faked backend cannot catch,
  especially on `constructor` split-child rendering. Opt-in via `LEANFOUNDRY_E2E=1`
  plus `LEANFOUNDRY_E2E_API_URL`; registered an `e2e` pytest marker so the default
  suite stays hermetic (the tests skip when unset). The policy is a fixed
  closing-tactic stub because the backend contract, not the model, is under test.
- Ran a mutmut 3.6 baseline over `leanfoundry/proofsearch/*` (config in
  `setup.cfg [mutmut]`; reproduce with
  `uv run --with mutmut --with pytest mutmut run`). Result: 2088 mutants, 1465
  killed + 12 timeout caught, 576 survived, 35 uncovered -- about a 71% catch
  rate. Survivors concentrate in the Path-A and orchestration code (`and_or` 91,
  `direct` 85, `extraction` 64, `_extract` 59, `_lean_tokens` 45); `_lean_tokens.py`
  still has no dedicated test. These are the highest-value targets for follow-up
  unit coverage.

Validation: full suite green (86 passed, 2 e2e skipped); e2e not executed here
(no live backend in this environment); `git diff --check` clean.

## 2026-06-27: Lean token scanner and backprop coverage

- Added dedicated `_lean_tokens.py` coverage for first-token positions, Lean
  identifier boundaries, line comments, nested block comments, escaped regular
  strings, fail-closed interpolated strings, longest-match behavior, and the
  proof-placeholder helper used by expansion. This directly targets the mutmut
  hotspot identified in the mutation baseline.
- Added `_backprop.py` regression coverage for value/visit semantics that the
  mutation run exposed: default no-value updates, explicit value backups,
  repeated visit accumulation, ancestor propagation, OR max backups, AND
  product backups, proved/disproved terminal values, and root propagation.

Validation:

- `uv run --no-dev --with pytest pytest` -> 113 passed, 2 e2e skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` passed.
- `git diff --check` passed.
- Live E2E against local Docker kimina-lean-server:
  `LEANFOUNDRY_E2E=1 LEANFOUNDRY_E2E_API_URL=http://127.0.0.1:8000
  uv run --no-dev --with pytest pytest tests/test_e2e_search.py` -> 2 passed.
- Full mutmut rerun:
  `uv run --with mutmut --with pytest mutmut run` -> 2088 mutants,
  1511 killed + 14 timeout-caught, 528 survived, 35 uncovered. The scanner
  hotspot now has 14 survived mutants, down from 45 in the prior baseline;
  targeted `_backprop.py` mutation coverage now kills all 50 mutants there.

## 2026-06-27: Streaming e2e expansion

- Expanded the live e2e tier while keeping the existing `run_search_batch(...)`
  driver and EnvBackend boundary. The concurrent tree-search case now
  synchronizes policy responses across three theorem searches and records
  lean-client's internal batcher call sizes, proving the existing
  `EnvBackend.step(...)` -> `AsyncLeanExecBackend.step(...)` streaming
  microbatch path coalesces into a multi-item `/exec/step_batch` call.
- Expanded coverage from two tree smoke cases to seven backend-contract cases:
  single-tactic tree, split tree, nested split tree, concurrent microbatch
  coalescing, direct whole-proof success, direct verifier rejection, and
  self-correct feedback followed by success.

Validation:

- `uv run --no-dev --with pytest pytest` -> 114 passed, 7 e2e skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` passed.
- Live E2E against local Docker kimina-lean-server:
  `LEANFOUNDRY_E2E=1 LEANFOUNDRY_E2E_API_URL=http://127.0.0.1:8000
  uv run --no-dev --with pytest pytest tests/test_e2e_search.py -q` ->
  7 passed.

## 2026-06-30: Slime pin + compat-test harness (unblocks the in-repo adapter)

Cleared issue #20, the gate in front of the in-repo Slime adapter (design
v11.13). No adapter code yet; this only makes the dependency deterministic and
drift-detecting.

- Pinned `slime` to commit `a897e1f40357fdf3b148f1eb4ce26e1aeccfcd2c` in
  `[tool.uv.sources]` (was tracking `main`) and re-locked. The resolved commit
  was unchanged, so the `uv.lock` diff is just the 2-line rev annotation;
  `uv lock --check` is clean. Commented the `[training]` extra to say bump
  deliberately + re-run compat tests, never track main.
- Added `tests/test_slime_compat.py` plus a `slime` pytest marker. The tests
  `importorskip("slime")`, so the default hermetic suite skips them; they run
  under the `[training]` extra on a CUDA box
  (`uv run --extra training pytest -m slime`). Assertions are grounded in the
  pinned `slime/utils/types.py`: `Sample` is an importable dataclass, it still
  carries the fields the adapter reads/writes
  (`prompt/tokens/response/response_length/reward/label/loss_mask/status/metadata`),
  and `append_response_tokens` keeps its keyword-only `trainable` parameter
  (load-bearing for tactic-span loss masking). The runtime `data_buffer`/`args`
  surfaces are deferred to the adapter slice's own tests.

Validation:

- `uv lock --check` clean.
- `uv run --no-dev --with pytest pytest tests/test_slime_compat.py -v` -> 1
  skipped (no slime in the hermetic env).
- `uv run --no-dev --with pytest pytest -q` -> 113 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 tests/test_slime_compat.py` clean.
- `git diff --check` clean.

## 2026-06-30: Training-target docs correction and Slime adapter handoff spec

Rewrote the training-data framing after the lineage-A/lineage-B clarification:
tree search emits step-level `(state, tactic)` samples, direct rollout emits the
model's own whole proofs, and rendering a whole proof from the search tree is
never a data gate.

- Added `docs/design/slime_adapter_spec.md` as the end-to-end implementation
  handoff for the Phase 2 reference clients and Phase 3 in-repo Slime adapter.
  The spec states the exact module layout, LeanFoundry APIs to call, pinned Slime
  surfaces to confirm, sample conversion rules, and tests required before the
  adapter is considered done.
- Updated `docs/design/leanfoundry_system_design_v11.md` and
  `docs/internal-trackers/todo.md` around v11.14, the Slime adapter plan, and the
  training-data model: two generation modes map to two targets; hybrid inference
  is not a third target; `proof_prefix` is provenance/context, not a
  history-conditional target; and `loss_mask` is only for self-correction or
  spans within a single response.
- Replaced the old Extension D "search-as-discovery vs shaped-credit" framing
  with a frozen training-target study: W, W+SC, T-step, T-noval, and Mix. The
  target comparison is now whole-proof lineage B versus search-generated
  step-policy lineage A versus mixed data, with target-appropriate eval modes.
- Split HER language into lineage-A step HER (proved-node reuse, no rendering or
  reverify) and optional lineage-B rendered-HER artifacts (render + `/exec/verify`
  before A-type insertion). Updated metrics to `step_her_multiplier` and
  render-candidate/verified multipliers.
- Tightened the Slime grouping contract: direct/self-correct groups stay fixed
  for GRPO-style objectives, while tree-step mode returns one ragged group per
  theorem search and sets shared `Sample.rollout_id` on sibling step samples.

Validation:

- `git diff --check` clean.

## 2026-06-30: Full training-adapter contract tightening

Converted the follow-up design clarifications into explicit implementation
requirements rather than leaving them as open chat context.

- Updated `docs/design/slime_adapter_spec.md` to cover the full adapter contract,
  not only the first runnable Slime loop. The spec now says LeanFoundry owns
  theorem metadata validation, token construction, `response_length`,
  `loss_mask`, reward/status, and `lf_kind` metadata for the Slime samples the
  trainer consumes.
- Grounded the tree objective in the step-prover literature: tree search emits
  lineage-A `(proof_state, tactic)` rows for EI/SFT by default; whole-proof and
  self-correction are separate lineage-B targets. Ragged tree groups must not be
  forced through fixed-size GRPO unless the trainer explicitly supports them.
- Added full-implementation requirements for self-correction trace artifacts,
  bonded and unbonded value clients, numeric-head and natural-language boxed/JSON
  value parsing, negation-backed `DISPROVED` labels, and fail-fast env-profile
  consistency.
- Mirrored the same requirements into the design doc and future-facing tracker,
  and opened issue-tracker entries for the missing code surfaces:
  self-correct traces, value-client modes, and Slime token/env validation.
- Updated `AGENTS.md` and `CLAUDE.md` so future agents do not reintroduce the
  tree-rendering data path or move Slime Sample construction into the training
  repo.

## 2026-06-30: Phase 2 reference clients and row conversion

Landed the Slime-free reference surfaces that Phase 1 eval and Phase 3 adapter
work build on. This is not the Slime adapter yet.

- Added `leanfoundry/policy/http_client.py` with `HTTPPolicyClient` and
  `HTTPValueClient`. The policy client posts JSON generation requests and
  returns `list[list[str]]`; the value client returns validated scores in
  `[0, 1]` from either numeric-head/JSON payloads or natural-language text ending
  in a boxed/JSON scalar.
- Added `leanfoundry/proofsearch/to_rows.py` with framework-neutral
  `TrainingRow` / `TrainingSegment` and `to_training_rows(...)` for current
  direct whole-proof and tree step examples. Self-correct rows remain blocked on
  persisting a real self-correct trace artifact.
- Added `make_env_backend(config)` so future composition roots do not reach into
  `env_backend.kimina_backend`.
- Exported the new public helpers and added hermetic tests for HTTP client
  payload/parse behavior, whole-proof/tactic row conversion, default backend
  construction, and core-import Slime cleanliness.

Validation so far:

- `uv run --no-dev --with pytest pytest tests/test_http_clients.py
  tests/test_to_rows.py tests/test_env_backend.py tests/test_package_import.py
  -q` -> 17 passed.

## 2026-06-30: Phase 3 Slime adapter baseline

Landed the in-repo pull-shaped adapter package under `leanfoundry/slime/` and
removed the abandoned push-shaped `leanfoundry/rl_engine/` package.

- Added lazy `leanfoundry.slime.generate_rollout`, `SGLangPolicyClient`,
  `SlimeRolloutRunner`, row-to-Slime `Sample` conversion, and the
  `rollout.py` composition root. The adapter builds/injects env, policy, and
  value clients, pulls theorem records from a Slime data source, runs
  `run_search_batch(...)`, converts results through `to_training_rows(...)`, and
  returns `RolloutFnTrainOutput` / `RolloutFnEvalOutput`.
- Added fail-fast theorem metadata handling for non-default `env_profile`,
  required `header`, mixed-profile batches, and theorem/backend profile
  disagreement.
- Built Slime `Sample`s by direct prompt+response token construction with
  aligned `response_length` and `loss_mask`, because accepted training rows do
  not necessarily carry SGLang rollout logprobs.
- Added default-suite tests with fake Slime modules for token/loss-mask
  conversion, theorem metadata validation, grouped/callable data-source input,
  tokenizer loading from `args.hf_checkpoint`, `RolloutFnEvalOutput`, and async
  rollout orchestration.

Known remaining gaps:

- The adapter has not been run under the real `[training]` extra against pinned
  Slime/SGLang or a live Lean backend in this slice.
- Production tokenizer/processor and data-source edge cases still need live
  SGLang/Slime/Lean smoke coverage before a real training run.

Validation so far:

- `uv run --no-dev --with pytest pytest tests/test_slime_adapter.py -q` -> 6
  passed.
- `uv run --no-dev --with pytest pytest tests/test_package_import.py -q` -> 6
  passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py -q` -> 3
  passed after installing the pinned Slime extra.

## 2026-06-30: Env-profile ingress enforcement baseline

Started Phase 1 data-integrity hardening by enforcing pinned env profiles where
training/replay data enters durable or online training paths.

- Added `leanfoundry/env_profiles.py` with `header_hash(...)`,
  `validate_theorem_env_profile(...)`, and
  `validate_theorem_batch_env_profiles(...)`.
- Wired the validators into the Slime runner, replay writer, and SQLite theorem
  insertion path. These now reject default env profiles at training/replay
  ingress, reject mixed batches unless explicit routing is enabled, and can
  validate theorem headers against an `EnvProfile` registry.
- Kept `EnvBackendConfig.env_profile="default"` for local/dev backend
  compatibility; this is a documented remaining weakness, not a claim that every
  execution path is profile-strict.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_env_profiles.py
  tests/test_replay_store.py tests/test_slime_adapter.py -q` -> 16 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/env_profiles.py
  leanfoundry/slime/runner.py leanfoundry/replay/writer.py
  leanfoundry/replay/sqlite_store.py tests/test_env_profiles.py
  tests/test_replay_store.py tests/test_slime_adapter.py` -> passed.

## 2026-06-30: Fixed-model eval runner baseline

Added the first concrete infrastructure-owned eval runner.

- Added `FixedModelEvalRunner`, which validates benchmark env profiles, calls
  `run_search_batch(...)`, and returns an `EvalArtifactManifest`.
- Direct and self-correct modes report pass@k from the accepted verifier attempt
  index; tree modes report solved@budget for the configured tactic-call budget.
  The manifest also records status counts, proved rate, elapsed seconds, and
  theorem throughput.
- Updated the `EvalRunner` protocol to accept `env_backend` and optional
  `value_client`, matching the actual search driver contract.

Known remaining gaps:

- This is not a benchmark loader, artifact writer, or report generator.
- Direct eval still stops on the first accepted proof, so binary pass@k rates are
  available but per-candidate eval artifacts are not.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_eval_runner.py
  tests/test_env_profiles.py -q` -> 8 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals
  tests/test_eval_runner.py leanfoundry/env_profiles.py
  tests/test_env_profiles.py` -> passed.

## 2026-06-30: Benchmark manifest schema

Added the pre-loader benchmark manifest surface required by the eval roadmap.

- Added `BenchmarkManifest` and `BenchmarkCompatibility` to the public schemas.
  The manifest records benchmark source, split, env profile, compatibility
  status, contamination policy, fixed held-out assignment id, dataset commit, and
  optional expected theorem count.
- Kept this to schema and validation tests only; benchmark loaders and artifact
  writers remain future work.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_benchmark_manifest.py
  tests/test_package_import.py tests/test_schema_database_consistency.py -q` ->
  17 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/schemas/eval.py
  leanfoundry/schemas/__init__.py tests/test_benchmark_manifest.py` -> passed.

## 2026-06-30: Attempt lifecycle outbox baseline

Closed the durable cleanup/cancel observability part of Phase 1 without adding
a reconciliation worker yet.

- Added `AttemptLifecycleRecord` and the SQLite
  `attempt_lifecycle_outbox` table. Fresh databases include the table in
  `0001_initial.sql`; existing databases upgrade through
  `0004_attempt_lifecycle_outbox.sql` and `PRAGMA user_version = 4`.
- `cleanup_search_state(...)` now preserves the concrete item ids still
  deferred after bounded cleanup attempts, plus the configured cleanup attempt
  cap.
- Best-effort cancel now returns a `CancelReport` with item statuses or
  transport failure details. `run_search_batch(...)` persists a cancelled
  attempt result when cancellation happens under a replay store, then re-raises
  `CancelledError` as before.
- `persist_search_result(...)` converts cleanup/cancel diagnostics into stable
  attempt-lifecycle rows. Terminal cancel statuses are marked terminal; deferred
  cleanup and failed cancel rows remain non-terminal for future reconciliation.

Known remaining gaps:

- There is no backend reconciliation/retry worker yet; the table is the durable
  sink/outbox.
- Direct search still cancels an active `verify_item_id:k` inside the direct
  engine, but that active verifier id is not propagated into replay diagnostics
  on task cancellation.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_schema_database_consistency.py
  tests/test_replay_store.py tests/test_search_engines.py -q` -> 47 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/_lifecycle.py
  leanfoundry/proofsearch/driver.py leanfoundry/replay leanfoundry/schemas
  tests/test_schema_database_consistency.py tests/test_replay_store.py
  tests/test_search_engines.py` -> passed.

## 2026-06-30: Step-level extraction hardening baseline

Aligned extraction with the per-step training-data contract.

- Policy extraction now emits a positive `PolicyExample` for every proved
  runtime action, including multiple proved actions at the same state and
  proved internal subtrees below an unproved root.
- Bonded proved-value extraction now labels every proved runtime state, not
  only states on the canonical solved root witness.
- Whole-proof candidates remain canonical and final-verifier-gated; this change
  does not attempt rendered-HER subproof verification.
- Split proof-artifact failures into `unsupported`, `rendering`, and
  `verification` kinds while preserving base extraction diagnostics.

Known remaining gaps:

- Rendered-HER artifacts are still a future Path-B stream.
- Censored-negative effort is still based on existing runtime visit counts; no
  separate node-local failed-action accounting was added in this slice.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_extraction.py
  tests/test_search_engines.py tests/test_to_rows.py tests/test_slime_adapter.py
  -q` -> 41 passed.
- `uv run --no-dev --with flake8 flake8
  leanfoundry/proofsearch/extraction.py leanfoundry/proofsearch/and_or.py
  tests/test_extraction.py tests/test_search_engines.py` -> passed.

## 2026-06-30: Value serving and conservative negation baseline

Closed the runnable Phase 5 baseline while leaving full Aristotle-style
negation search explicit as future work.

- `HTTPValueClient` already supports natural-language boxed/JSON scalar parsing
  and numeric-head/JSON scalar parsing; added Slime runner coverage for bonded
  value clients against the SGLang router and unbonded clients against a
  separate endpoint.
- Added `_negation.py`, a conservative synthetic-negation check for tree search.
  When `try_negation` is enabled and theorem provenance allows it, an eligible
  single-goal state renders a simple `¬ target` theorem through the backend,
  samples tactics for that negation state, charges completed Lean attempts
  against `max_tactic_calls`, and marks the original state/root `DISPROVED` if a
  negation tactic completes.
- The negation proof tactics are not emitted as policy positives for the
  original state. Disproved value labels flow through the existing
  `disproved=True`, full-weight extraction path.

Known remaining gaps:

- This is one checked negation expansion, not a persistent UCB-competing
  negation sub-search. Durable one-shot proof-attempt artifacts landed later in
  the negation artifact slice below.
- Local context rendering is intentionally conservative and skips unsupported
  binders/let-bindings instead of guessing Lean code.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_search_engines.py
  tests/test_http_clients.py tests/test_slime_adapter.py
  tests/test_package_import.py -q` -> 49 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/_negation.py
  leanfoundry/proofsearch/_expansion.py leanfoundry/proofsearch/and_or.py
  leanfoundry/slime/runner.py tests/test_search_engines.py
  tests/test_slime_adapter.py tests/test_http_clients.py` -> passed.

## 2026-06-30: Policy-context prompt baseline

Landed the optional inference-context path without changing the training target
or proof-state schema.

- Added `PolicyContext` to the policy protocol. `sample_tactics(...)` can now
  receive one context object per proof state.
- Expansion derives `PolicyContext.proof_prefix` from parent runtime actions,
  preserving inline comments in sampled tactics.
- `HTTPPolicyClient`'s default tactic prompt includes non-empty proof prefixes
  as Lean comments before the current Markov proof state. Slime runner hooks
  accept the same optional context.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_expansion.py
  tests/test_http_clients.py tests/test_search_engines.py
  tests/test_slime_adapter.py tests/test_package_import.py -q` -> 68 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/policy
  leanfoundry/proofsearch/_expansion.py leanfoundry/proofsearch/_negation.py
  leanfoundry/slime/runner.py tests/test_expansion.py
  tests/test_http_clients.py tests/test_search_engines.py
  tests/test_slime_adapter.py tests/test_e2e_search.py` -> passed.

## 2026-06-30: Benchmark loader and eval artifact writer

Closed the manifest-backed local benchmark/eval artifact residual.

- Added `leanfoundry/evals/io.py` with `load_benchmark_jsonl(...)`,
  `validate_benchmark_theorems(...)`, `write_eval_artifacts(...)`, and
  `render_eval_report(...)`.
- JSONL benchmark loading rejects incompatible manifests, validates theorem
  env profiles against the `BenchmarkManifest`, and enforces expected theorem
  count when present.
- `FixedModelEvalRunner.run(...)` accepts an optional `benchmark_manifest` and
  optional `artifact_dir`. When an artifact directory is provided, it writes
  `eval_manifest.json`, `results.jsonl`, `benchmark.jsonl`, and `report.md`.
  The manifest/returned metrics record content hashes for the materialized
  result, benchmark, and report files.

Known remaining gaps:

- This is a local JSONL loader/writer, not a benchmark-specific remote dataset
  adapter.
- Direct/self-correct pass@k rates are derived from the accepted attempt index.
  Per-candidate verifier artifacts landed later in the direct verifier attempt
  trace slice below.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_eval_io.py
  tests/test_eval_runner.py tests/test_benchmark_manifest.py -q` -> 11 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals tests/test_eval_io.py
  tests/test_eval_runner.py tests/test_benchmark_manifest.py` -> passed.

## 2026-06-30: Lifecycle reconciliation and direct cancel replay

Closed the remaining concrete lifecycle observability residuals.

- Added `get_pending_attempt_lifecycle_records(...)` to the replay protocol and
  SQLite store.
- Added `reconcile_attempt_lifecycle(...)`, which retries pending cleanup/cancel
  outbox rows against the backend and persists updated statuses. Cleanup rows
  can become `deleted`, stay `deferred`, become `failed`, or become terminal
  `orphaned` after the recorded retry cap. Cancel rows become
  `cancelling`, `drained`, `cleaned`, or `failed`.
- Direct search now raises cancellation with diagnostics after cancelling the
  active `verify_item_id:k`; `run_search_batch(...)` persists those diagnostics
  as cancel lifecycle rows when a replay store is present.

Known remaining gaps:

- Reconciliation is a callable helper, not a background scheduler or operator
  alerting loop.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_replay_store.py
  tests/test_search_engines.py -q` -> 44 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/replay
  leanfoundry/proofsearch/_lifecycle.py leanfoundry/proofsearch/direct.py
  leanfoundry/proofsearch/driver.py tests/test_replay_store.py
  tests/test_search_engines.py` -> passed.

## 2026-06-30: Self-correct trace rows

Closed the self-correction training-row residual for accepted corrections.

- Added `SelfCorrectTurn` and `SelfCorrectTrace` schemas under
  `TrainingArtifacts`.
- `DirectSearchEngine(self_correct=True)` now records rejected proof attempts,
  rendered verifier feedback, corrected proof attempts, per-turn verifier
  statuses, verifier item ids, and accepted/final status.
- `to_training_rows(...)` now emits `kind="self_correct"` rows for accepted
  corrections. The row prompt contains the theorem, previous failed proof, and
  verifier feedback; the response is the accepted correction and is trainable.

Known remaining gap:

- Failed-correction negative rows remain a training-objective choice and are not
  emitted by default.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_to_rows.py
  tests/test_search_engines.py tests/test_slime_adapter.py
  tests/test_package_import.py -q` -> 47 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/direct.py
  leanfoundry/proofsearch/to_rows.py leanfoundry/schemas/trajectory.py
  leanfoundry/schemas/__init__.py tests/test_to_rows.py
  tests/test_search_engines.py` -> passed.

## 2026-06-30: Direct verifier attempt traces

Closed the direct/self-correct all-attempt eval-provenance residual.

- Added `DirectVerificationAttempt` and
  `TrainingArtifacts.direct_verification_attempts`.
- `DirectSearchEngine` now records every verifier attempt before termination,
  including rejected, accepted, cancelled, and overloaded verifier statuses.
  Accepted whole-proof and self-correct rows remain the only training-row
  sources; rejected candidates are eval provenance only.
- `FixedModelEvalRunner` counts recorded direct verifier attempts in manifest
  metrics, while `write_eval_artifacts(...)` serializes the full traces in
  `results.jsonl`.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_search_engines.py
  tests/test_eval_runner.py tests/test_to_rows.py -q` -> 42 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/direct.py
  leanfoundry/evals/runner.py leanfoundry/schemas/trajectory.py
  leanfoundry/schemas/__init__.py tests/test_search_engines.py
  tests/test_eval_runner.py` -> passed.

## 2026-06-30: Lifecycle scheduler and alerts

Closed the core lifecycle scheduling residual while keeping deployment wiring
outside the library.

- Added `reconcile_attempt_lifecycle_periodically(...)`, which runs bounded or
  infinite reconciliation passes with configurable interval, limit, sleep
  function, and optional alert sink.
- Added `LifecycleOperatorAlert` and `LifecycleSchedulerReport`. Failed rows
  emit warning alerts; orphaned cleanup rows emit critical alerts. The
  scheduler report aggregates reconciliation diagnostics across passes.
- Deployment choices such as cron, supervisor integration, metrics export, and
  paging destinations remain outside core LeanFoundry.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_replay_store.py -q` -> 12
  passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/replay/lifecycle.py
  leanfoundry/replay/__init__.py tests/test_replay_store.py` -> passed.

## 2026-06-30: Eval env-profile registry wiring

Closed the concrete env-profile manifest wiring residual for eval/training
ingress.

- `load_benchmark_jsonl(...)`, `validate_benchmark_theorems(...)`, and
  `FixedModelEvalRunner.run(...)` accept optional `EnvProfile` registries and
  validate theorem headers against the pinned profile metadata.
- `SlimeRolloutRunner.build_env_backend(...)` now requires an explicit
  non-default `lean_env_profile` / `env_profile` for training rollouts. The
  lower-level `EnvBackendConfig` default remains available for direct dev/test
  client construction.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_slime_adapter.py
  tests/test_eval_io.py tests/test_eval_runner.py tests/test_env_profiles.py
  -q` -> 22 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/slime/runner.py
  leanfoundry/evals/io.py leanfoundry/evals/runner.py
  tests/test_slime_adapter.py tests/test_eval_io.py tests/test_eval_runner.py`
  -> passed.

## 2026-06-30: Durable extraction-failure records

Closed the concrete replay failure-persistence residual.

- Added `ExtractionFailureRecord` and the `extraction_failures` SQLite table
  with a v5 migration.
- Added `ReplayStore.put_extraction_failures(...)` and a SQLite implementation.
- `persist_search_result(...)` now writes `TrainingArtifacts.failures` with
  deterministic ids and reports `replay_extraction_failures` in diagnostics.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_replay_store.py
  tests/test_schema_database_consistency.py -q` -> 21 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/replay/base.py
  leanfoundry/replay/sqlite_store.py leanfoundry/replay/writer.py
  leanfoundry/schemas/records.py leanfoundry/schemas/__init__.py
  tests/test_replay_store.py tests/test_schema_database_consistency.py`
  -> passed.

## 2026-06-30: Durable negation proof-attempt artifacts

Closed the durable negation diagnostics/artifacts residual while keeping the
full Aristotle-style persistent negation sub-search separate.

- Added `NegationTacticAttempt` and `NegationAttempt` under
  `TrainingArtifacts.negation_attempts`.
- `maybe_apply_negation(...)` now records unsupported, initialization,
  policy-empty, not-proved, proved, and operational-abort negation outcomes.
  The artifact includes source state/node, rendered synthetic theorem,
  negation backend state, tactic attempts/statuses/messages, charged tactic
  count, proved flag, and proved tactic.
- Added `NegationAttemptRecord` plus the `negation_attempts` SQLite table in
  schema v6, and wired `persist_search_result(...)` to store attempts with
  deterministic ids and `replay_negation_attempts` diagnostics.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_search_engines.py
  tests/test_replay_store.py tests/test_schema_database_consistency.py -q`
  -> 56 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/_negation.py
  leanfoundry/proofsearch/_expansion.py leanfoundry/proofsearch/and_or.py
  leanfoundry/replay/base.py leanfoundry/replay/sqlite_store.py
  leanfoundry/replay/writer.py leanfoundry/schemas/trajectory.py
  leanfoundry/schemas/records.py leanfoundry/schemas/__init__.py
  tests/test_search_engines.py tests/test_replay_store.py
  tests/test_schema_database_consistency.py` -> passed.

## 2026-06-30: Negation local-definition rendering

Closed the common local-context rendering residual for the one-shot synthetic
negation baseline while preserving fail-closed behavior.

- `_hypothesis_binder(...)` now accepts local definitions/`let` entries by
  abstracting them to ordinary typed theorem parameters. This intentionally
  drops the defining value; a proved negation for every value of the parameter
  is stronger than the original state-under-definition and therefore remains a
  sound `DISPROVED` certificate.
- Entries with missing names, invalid Lean binder identifiers, or empty types
  still return `unsupported` and emit the durable negation-attempt artifact
  rather than guessing surface syntax.
- Added tree-search coverage proving the rendered synthetic theorem contains
  the typed binder, omits the local definition value, and records the rendered
  theorem in `TrainingArtifacts.negation_attempts`.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_search_engines.py -q`
  -> 35 passed.
- `uv run --no-dev --with pytest pytest -q` -> 175 passed, 7 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py -q`
  -> 3 passed.
- `git diff --check` -> passed.

## 2026-06-30: Persistent negation action retries

Advanced the negation baseline from one-shot checking to selected retries while
leaving nested multi-step negation proof search explicit as future work.

- Added live-search metadata on `ActionNode` for the synthetic negation action:
  rendered theorem, theorem name, backend negation state, and tactics already
  tried on that negation state.
- `maybe_apply_negation(...)` now initializes the synthetic action once, then
  advances an already-open negation action when selection returns to that
  source state. Ordinary failed negation tactics leave the action open for a
  later selected retry; repeated policy outputs fail closed instead of looping.
- Each retry emits a durable `NegationAttempt` with a distinct step item id,
  tactic statuses/messages, charged tactic count, and proved/not-proved status.
  Proved negation still marks the source state/root `DISPROVED` and does not
  emit policy positives for the original state.
- Added tree-search coverage where the first negation tactic fails, the same
  backend negation state is reused, the second retry proves the negation, and
  the attempt artifacts record `not_proved` then `proved`.

Remaining gap:

- If a negation tactic returns an open subgoal state, LeanFoundry records that
  batch as `not_proved` and retries the synthetic negation root later; it does
  not yet insert that open negation subgoal into a nested AND/OR subtree.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_search_engines.py -q`
  -> 36 passed.
- `uv run --no-dev --with pytest pytest tests/test_runtime_tree.py
  tests/test_backprop.py -q` -> 31 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/_negation.py
  leanfoundry/proofsearch/_expansion.py leanfoundry/proofsearch/_tree.py
  tests/test_search_engines.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 176 passed, 7 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py -q`
  -> 3 passed.
- `git diff --check` -> passed.

## 2026-06-30: Extraction/value/negation tracker de-stale

Updated stale audit/tracker wording after the current extraction, value-label,
eval, and negation baselines:

- Marked expansion policy context, node-general step extraction, value-label
  semantics, and persistent negation action retries as current in
  `issues.md`.
- Replaced the stale claim that censored negatives use attempt-level effort;
  extraction now gates them by each open runtime state's `visit_count`.
- Updated the design module map so `proofsearch/` no longer lists
  node-general proved-node extraction or basic negation pruning as deferred,
  and `evals/` reflects the local JSONL/eval artifact baseline.
- Corrected Extension C / architecture tracker entries so node-general
  extraction, replay, eval, and Slime-adapter baselines are no longer described
  as absent.
- Marked SQL/Pydantic consistency testing current for column, nullability,
  default, type-affinity, and representative `CHECK` coverage.
- Removed stale "still open" wording for policy prompt context, downstream row
  conversion, and step-level proved-node extraction.
- Refreshed the §10 `PolicyClient` / `ValueClient` API snippet so policy
  sampling returns per-input candidate batches and value estimation is a
  separate protocol.
- Marked §4 data-store examples current after aligning the remaining negation
  wording with `try_negation` and the current `state_value_labels` shape.
- Updated the coverage matrix for §4 and §8 so data-store, replay/value,
  benchmark manifest, pass@k/solved@budget, contamination, and eval artifact
  baselines are marked current with remote/rendered extensions left future.
- Tightened remaining matrix labels for open questions, supported algorithms,
  search roadmap, and Extension C so they distinguish current baselines from
  deliberately future work.
- Renamed the G1-G4 issue heading to reflect current baselines plus Path-B
  residuals rather than stale open questions.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_replay_store.py
  tests/test_schema_database_consistency.py` -> 27 passed.
- `git diff --check` -> passed.

## 2026-06-30: Localized unsupported extraction failures

Closed the small Phase 4 localization residual for unsupported renderer
failures.

- `UnsupportedProofExtraction` now carries an optional structured `node_id`.
- The split-coupled-goal renderer rejection attaches the problematic runtime
  child node id to that exception.
- `AndOrSearchEngine` copies the structured node id into
  `ExtractionFailure.node_id`, so replay/debug consumers do not need to parse
  it from the message text.
- Extended the coupled-goal extraction regression to assert the recorded node id.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_search_engines.py -q`
  -> 37 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/_extract.py
  leanfoundry/proofsearch/and_or.py tests/test_search_engines.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 177 passed, 7 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py -q`
  -> 3 passed.
- `git diff --check` -> passed.

## 2026-06-30: Nested negation proof subtrees

Closed the remaining local Phase 5 negation-search gap: open subgoals inside a
synthetic negation proof now use the normal AND/OR tree instead of a separate
one-off retry loop.

- Added runtime metadata for negation contexts and actions that disprove their
  parent when their child subtree is proved.
- Synthetic negation initialization now attaches the backend-created negated
  theorem state as a child of the synthetic action. Tactics inside that child
  state are sampled and expanded by the normal tree path, including open
  subgoals.
- When the negation child subtree is proved, the source state is marked
  `DISPROVED`; the synthetic action itself is not emitted as a policy positive
  for the original state.
- Policy examples inside the negation subtree are preserved as positives for
  the synthetic negation proof states, with proof prefixes skipping the internal
  negation sentinel.
- Added focused coverage for a negation proof that opens a subgoal, proves the
  subgoal, records a durable `NegationAttempt`, and emits only negation-state
  policy positives plus the original state's full-weight disproved value label.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_search_engines.py -q`
  -> 37 passed.
- `uv run --no-dev --with pytest pytest tests/test_runtime_tree.py
  tests/test_backprop.py -q` -> 31 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/_negation.py
  leanfoundry/proofsearch/_expansion.py leanfoundry/proofsearch/_tree.py
  leanfoundry/proofsearch/and_or.py leanfoundry/proofsearch/extraction.py
  tests/test_search_engines.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 177 passed, 7 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py -q`
  -> 3 passed.
- `git diff --check` -> passed.

## 2026-06-30: Schema release governance

Closed the release-policy residual left after the ordered SQLite migration
registry.

- Added `docs/design/schema_release_governance.md`, covering released-migration
  immutability, append-only migration rules, Pydantic-first schema changes,
  required upgrade/schema-consistency tests, destructive-change handling, and
  eval-manifest compatibility.
- Linked the policy from the v11.31 design note, the future-facing todo, the
  issue tracker, and `AGENTS.md`.

Validation:

- `git diff --check` -> passed.

## 2026-06-30: Ordered SQLite migration registry

Closed the concrete migration-discipline residual for the current replay spine.

- Replaced the one-off SQLite migration ladder with an ordered `MIGRATIONS`
  registry. Future migrations append `(version, path)` entries and bump
  `SCHEMA_VERSION` automatically from the last registry entry.
- Kept the existing guarded v3 theorem-verifier migration behavior for DBs that
  already have those columns.
- Added explicit v4 -> v6 and v5 -> v6 upgrade tests so the current
  extraction-failure and negation-attempt tables are covered for existing DBs.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_replay_store.py
  tests/test_schema_database_consistency.py -q` -> 24 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/replay/sqlite_store.py
  tests/test_replay_store.py tests/test_schema_database_consistency.py`
  -> passed.

## 2026-06-30: Direct pass@k candidate pool verification

Closed the direct-search pass@k semantic gap left after verifier-attempt
provenance landed.

- Plain `DIRECT` search now verifies the full sampled whole-proof candidate
  pool up to `max_direct_candidates` before returning a successful result,
  unless a terminal backend status aborts the run.
- The top-level `SearchResult.proof_tree` remains the first accepted proof, but
  `TrainingArtifacts.proof_candidates` keeps every accepted verified candidate
  so whole-proof training rows can include all positives from the pool.
- `TrainingArtifacts.direct_verification_attempts` records accepted and
  rejected candidates across the whole pool.
- `SELF_CORRECT` keeps its feedback-loop semantics and still stops on the first
  accepted correction.
- Fixed-model eval pass@k now reads accepted verifier candidate indices from
  `direct_verification_attempts`, not total verifier attempts.

Validation:

- `uv run --no-dev --with pytest pytest
  tests/test_search_engines.py::test_direct_engine_accepts_first_verified_candidate
  tests/test_search_engines.py::test_direct_engine_verifies_full_candidate_pool_after_success
  tests/test_search_engines.py::test_self_correct_feeds_back_verifier_message
  -q` -> 3 passed.
- `uv run --no-dev --with pytest pytest
  tests/test_eval_runner.py::test_fixed_eval_runner_reports_pass_at_k -q`
  -> 1 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/proofsearch/direct.py
  leanfoundry/evals/runner.py tests/test_search_engines.py
  tests/test_eval_runner.py` -> passed.

## 2026-06-30: Opt-in Slime live-stack rollout smoke

Closed the missing test-harness side of the Phase 3 live-validation gap.

- Added `tests/test_slime_live.py`, an opt-in `slime` + `e2e` smoke that uses
  the real `leanfoundry.slime.async_generate_rollout` entrypoint under the
  pinned Slime package.
- The smoke requires `LEANFOUNDRY_SLIME_E2E=1`, a live Lean API URL/profile, a
  live SGLang router address, and an HF checkpoint for tokenizer loading.
- It runs one direct whole-proof theorem through the SGLang policy client,
  Kimina verifier backend, and Slime row-to-sample output path. Lean verifier
  rejection is allowed; plumbing errors, cancelled runs, and operational search
  errors fail the smoke.
- Default hermetic runs and `[training]` runs without live service env vars skip
  the test cleanly.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_slime_live.py -q`
  -> 1 skipped.
- `uv run --extra training pytest -m "slime and e2e"
  tests/test_slime_live.py -q` -> 1 skipped.
- `uv run --no-dev --with flake8 flake8 tests/test_slime_live.py` -> passed.

## 2026-06-30: Lifecycle reconciliation CLI

Closed the local deployment-hook gap for the attempt-lifecycle outbox.

- Added `leanfoundry/replay/lifecycle_cli.py`, runnable as
  `python -m leanfoundry.replay.lifecycle_cli`.
- Added the `leanfoundry-reconcile-lifecycle` console script. It opens a SQLite
  replay DB, connects to the configured Lean backend, runs bounded or infinite
  lifecycle reconciliation passes, prints aggregate JSON diagnostics, emits
  warning/critical alert JSON to stderr, and can exit nonzero on alerts for
  cron/systemd usage.
- Kept reconciliation semantics in `reconcile_attempt_lifecycle_periodically`;
  the CLI is only operator wiring.
- Fixed an import-order circularity where importing `leanfoundry.replay` before
  `leanfoundry.proofsearch` could recurse through
  `replay.writer -> proofsearch.__init__ -> driver -> replay`. The writer now
  avoids a runtime `SearchResult` import and treats search results
  structurally.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_lifecycle_cli.py -q`
  -> 2 passed.
- `uv run --no-dev --with pytest pytest tests/test_package_import.py -q`
  -> 6 passed.
- `uv run --no-dev --with flake8 flake8
  leanfoundry/replay/lifecycle_cli.py leanfoundry/replay/writer.py
  tests/test_lifecycle_cli.py` -> passed.

## 2026-06-30: Eval mode coverage expansion

Closed the local "richer mode coverage" part of the eval tracker gap.

- Added self-correct pass@k coverage that verifies `SELF_CORRECT` maps to
  `EvalMode.SELF_CORRECT`, raises `max_direct_candidates` to the largest
  requested k, counts direct verifier attempts, and computes pass@k from the
  accepted verifier candidate index.
- Expanded solved@budget coverage across the implemented state-token modes:
  PUCT tree, best-first, and the `AND_OR_TREE` alias.
- The remaining eval gap is benchmark-specific remote dataset adapters beyond
  the local JSONL/manifest loader.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_eval_runner.py -q`
  -> 8 passed.
- `uv run --no-dev --with flake8 flake8 tests/test_eval_runner.py
  leanfoundry/evals/runner.py` -> passed.

## 2026-06-30: Optional failed self-correct negatives

Closed the self-correction negative-objective tracker item without changing
default training rows.

- Added `include_failed_self_correct_negatives` to `to_training_rows(...)`.
  When enabled, rejected self-correct turns become reward-0
  `kind="self_correct"` rows with
  `self_correct_objective="failed_negative"` metadata.
- Accepted self-correct corrections are unchanged and still emit reward-1 rows.
- Wired the Slime rollout arg `lf_include_failed_self_correct_negatives` so
  training can opt in per run. The default remains off.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_to_rows.py
  tests/test_slime_adapter.py -q` -> 13 passed.
- `uv run --no-dev --with flake8 flake8
  leanfoundry/proofsearch/to_rows.py leanfoundry/slime/rollout.py
  tests/test_to_rows.py tests/test_slime_adapter.py` -> passed.

## 2026-06-30: Manifest-source benchmark loader

Closed the generic remote-source part of the eval benchmark loader gap.

- Added `load_benchmark_source(...)`, which loads theorem JSONL from the source
  recorded in `BenchmarkManifest.source`.
- Supported source forms: local paths, `file://` URIs, HTTP(S) JSONL URLs, and
  explicit Hugging Face file URIs (`hf://repo` or `hf://org/repo` with
  `?path=...` and optional `revision=...`).
- Reused the existing compatibility, env-profile, and theorem-count validation
  after loading. The existing `load_benchmark_jsonl(...)` path remains for
  callers that already have a concrete local file.
- Remaining eval-loader work is benchmark-specific schema transforms for remote
  sources that are not already LeanFoundry theorem JSONL.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_eval_io.py -q`
  -> 9 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals/io.py
  leanfoundry/evals/__init__.py tests/test_eval_io.py` -> passed.

## 2026-06-30: Benchmark row-format adapters

Closed the generic schema-transform hook for benchmark loading.

- Added `BenchmarkManifest.row_format`, defaulting to serialized
  LeanFoundry `TheoremSpec` JSONL.
- Added `BenchmarkRowAdapter` support to `load_benchmark_source(...)` and
  `load_benchmark_jsonl(...)`; non-default row formats must provide an
  explicit adapter at load time.
- Kept public benchmark transforms out of the core theorem schema. Concrete
  adapters can be added only for selected datasets that need them.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_eval_io.py
  tests/test_benchmark_manifest.py -q` -> 14 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals/io.py
  leanfoundry/evals/__init__.py leanfoundry/schemas/eval.py
  tests/test_eval_io.py tests/test_benchmark_manifest.py` -> passed.

## 2026-06-30: Design boundary reconciliation

Closed the local design-doc drift around current-vs-future system boundaries.

- Added a v11.38 note documenting the current core implementation and explicit
  deferred work: graph/MCGS, tactic beam, optimistic/RMaxTS, richer Path-B
  rendering, and Extensions A-D.
- Updated the long-form design text for current step extraction, conservative
  negation, env-profile ingress, `lean_client.exec_models` ownership, optional
  Slime rollout integration, P3/P10 durable/preemptibility guarantees, and
  current Slime rollout pseudocode.
- Updated the issue tracker so resolved design mismatches are no longer listed
  as open, while external live smoke, backend validation harness execution,
  concrete public-benchmark adapters, and deferred extensions remain explicit.

## 2026-06-30: Backend validation harness baseline

Closed the local §2.8 harness API gap.

- Added `leanfoundry.env_backend.validation` with
  `BackendValidationCase`, `BackendReplayStep`, `BackendValidationReport`, and
  `validate_backend_case(...)`.
- The harness initializes a theorem through `/exec/create_states`, replays
  tree-shaped tactic trajectories through an injected `EnvBackend`, preserves
  LeanFoundry's goal-coupling split into focused `goal_group` child replays,
  and verifies the supplied complete proof through `/exec/verify`.
- Added hermetic tests proving split-goal replay uses `goal_group=(0,)` and
  `(1,)`, and that replay mismatches are reported without calling final
  verification.

Remaining external validation:

- Run the harness over actual LeanDojo/LeanTree trajectories against a live
  backend to measure replay correctness, cache behavior, and latency.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_backend_validation.py -q`
  -> 2 passed.
- `uv run --no-dev --with flake8 flake8
  leanfoundry/env_backend/validation.py tests/test_backend_validation.py`
  -> passed.

## 2026-06-30: Path-B render diagnostics

Closed the local accounting gap for optional rendered-HER / Path-B artifacts
without widening the proof renderer or changing the training-data gate.

- `extract_training_artifacts(...)` now emits action-level diagnostics:
  `path_b_render_candidates`, `path_b_renderable_candidates`,
  `path_b_unsupported_candidates`, and `path_b_verified_candidates`.
- The counters are derived from proved action subtrees. They distinguish what
  the existing narrow renderer can structurally represent from unsupported
  focused/coupled shapes, and count only the top-level verified artifact as
  verified.
- No new training rows are emitted, and no standalone subproof verification is
  attempted in core extraction.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_extraction.py
  tests/test_search_engines.py -q` -> 45 passed.
- `uv run --no-dev --with flake8 flake8
  leanfoundry/proofsearch/extraction.py tests/test_extraction.py` -> passed.

## 2026-06-30: Direct verifier batch transport

Closed the direct-search verifier transport optimization gap.

- Added `EnvBackend.verify(...)` to the protocol and wired
  `KiminaEnvBackend.verify(...)` to `AsyncLeanExecBackend.verify(...)`.
- Plain `DIRECT` search now builds one `ExecVerifyItem` per sampled candidate
  and submits the pass@k pool through `EnvBackend.verify(...)`, while preserving
  ordered `DirectVerificationAttempt` artifacts and existing terminal-status
  handling.
- `SELF_CORRECT` remains sequential by design because each correction prompt is
  conditioned on the previous verifier feedback.

Validation:

- `uv run --no-dev --with pytest pytest tests/test_search_engines.py
  tests/test_eval_runner.py -q` -> 46 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/env_backend/base.py
  leanfoundry/env_backend/kimina_backend.py leanfoundry/proofsearch/direct.py
  tests/test_search_engines.py` -> passed.

## 2026-06-30: Extension D ablation contract baseline

Closed the local contract gap for the controlled training-target ablation study
without adding optimizer or trainer code to LeanFoundry.

- Added schema models for frozen curricula, training-target arms, value serving
  mode declarations, hard generation/training/verifier ledger entries, crossed
  eval cells, and the top-level `AblationExperimentPlan`.
- Added `leanfoundry.evals.experiment_plan` helpers to materialize the standard
  W/W+SC/T-step/T-noval/Mix arms, complete per-arm/per-round ledgers, and native
  eval cells.
- The schema verifies frozen-assignment consistency, unique per-arm budget
  accounts, complete ledger coverage for every arm/round/meter cell, and rejects
  value serving or value metrics on `T-noval`.

Remaining external work:

- Build the frozen curriculum from a real pass@N sweep, run optimizer execution
  in the downstream training repo, enforce budget meters in deployment, and
  produce final outcome reports from real checkpoints.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_extension_d_plan.py`
  -> 6 passed.

## 2026-06-30: Extension C TTT contract baseline

Closed the local protocol/schema gap for future test-time training without
adding optimizer code. The generic orchestration loop landed later in
`2026-06-30: Generic TTT orchestration loop`.

- Added `leanfoundry.ttt` with framework-neutral `TTTAdapter` and
  `AdaptablePolicyClient` protocols.
- Added strict TTT schemas: `TTTConfig`, `TTTAdapterTrainingRequest`,
  `TTTAdapterTrainingResult`, `TTTRoundTrace`, `TTTSessionTrace`, and
  `TTTStageStatus`.
- The schemas keep main-replay promotion off by default, require non-empty
  per-problem training requests, validate adapter ids for successful
  train/reload stages, and reject duplicate round traces.

Remaining external/future work:

- Implement MCGS or another approved per-problem search source, trainer-side
  LoRA fine-tuning/reload, and any trace promotion gate needed before TTT
  traces enter main replay.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_ttt_contract.py`
  -> 9 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/schemas/ttt.py
  leanfoundry/ttt tests/test_ttt_contract.py leanfoundry/schemas/__init__.py`
  -> passed.

## 2026-06-30: Extension B promotion contract baseline

Closed the local promotion blocker for autoformalized staging records without
building the LLM formalizer, judge, or embedding dedup services.

- Added `FormalStatementStagingRecord.header` so staging records preserve the
  Lean import/options block required to become `TheoremRecord`s.
- Added SQLite migration `0007_formal_staging_header.sql` and bumped the replay
  store schema version to 7, with an upgrade test for legacy v6 rows.
- Added `leanfoundry.formalization.evaluate_promotion(...)` plus
  `PromotionGateConfig` and `PromotionDecision`. The gate requires syntax
  acceptance, semantic judge score, dedup hash, and not-yet-promoted status by
  default, then builds a `TheoremRecord` or returns rejection reasons.

Remaining future work:

- Implement the LLM draft/retry pipeline, statement verifier wrapper, semantic
  judge service, and embedding-similarity dedup service. Exact dedup hashing
  and quick-search difficulty mapping landed later in
  `2026-06-30: Formalization staging metadata helpers`.

Validation:

- `uv run --no-dev --with pytest pytest -q
  tests/test_formalization_promotion.py tests/test_schema_database_consistency.py
  tests/test_replay_store.py` -> 32 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/formalization
  leanfoundry/schemas/records.py leanfoundry/replay/sqlite_store.py
  tests/test_formalization_promotion.py tests/test_replay_store.py
  tests/test_schema_database_consistency.py` -> passed.

## 2026-06-30: Extension A scale-out contract baseline

Closed the local contract gap for future multi-machine scale-out without
building a router, distributed replay store, or state-transfer implementation.

- Added `leanfoundry.scaleout.autoscale` with `RouterMetrics`,
  `AutoscaleConfig`, `AutoscaleDecision`, and `plan_router_scale(...)`.
- Added `leanfoundry.scaleout.state_portability` with `PortableStateRef`,
  `StateSnapshotCodec`, and `StatePayloadLocation`.
- The autoscale helper implements the documented queue-depth formula as a pure
  decision function. `PortableStateRef` validates URI vs inline payload
  invariants and records codec/hash/size metadata plus compression ratio.

Remaining future work:

- Build the REPL router, router adapter, backend state export/import and
  compression, Postgres/Redis replay stores, distributed cleanup/cancel
  semantics, and deployment-specific autoscaler integration.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py`
  -> 7 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py` -> passed.

## 2026-06-30: Local audit boundary after extension contracts

Recorded the current implementation boundary in `todo.md` after the A/B/C/D
extension contracts and core Path-A/Slime/eval/replay baselines landed.

- The tracker now separates remaining items into live/external validation,
  dataset-specific adapters, deployment-specific wiring, downstream
  training-repo execution, and deliberately gated future algorithms.
- This is not a claim that those items are complete; it is the opposite. It
  prevents them from being mistaken for missing local code in the current core
  checkout.

Validation:

- `uv run --no-dev --with pytest pytest -q` -> 311 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py
  tests/test_slime_live.py -q` -> 3 passed, 1 skipped.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.

## 2026-06-30: Local live `/exec` e2e validation

Closed the local scripted Lean-backend e2e validation gap for the current
checkout.

- Started the sibling `kimina-lean-server` checkout in exec mode on
  `http://127.0.0.1:8017` with one Pantograph worker, one Lean process per env
  profile, one in-flight exec request, and a temporary state store under
  `/tmp/leanfoundry-kimina-state-8017`.
- Verified `/exec/limits` returned bounded caps, including
  `max_pantograph_workers=1`, `max_in_flight_exec_requests=1`, and
  `allow_unbounded_exec=false`.
- Ran the LeanFoundry live e2e harness through real `/exec/create_states`,
  `/exec/step_batch`, `/exec/verify`, and `/exec/cleanup` calls. This covers the
  scripted direct/tree/self-correct backend contract, not model quality.
- Shut the temporary server down cleanly after the run.

Remaining live work:

- Run `validate_backend_case(...)` over actual LeanDojo/LeanTree trajectories,
  measure live backend cache/latency behavior, and run the full
  Slime/SGLang/Lean smoke against actual model services.

Validation:

- `LEANFOUNDRY_E2E=1 LEANFOUNDRY_E2E_API_URL=http://127.0.0.1:8017
  LEANFOUNDRY_E2E_ENV_PROFILE=default uv run --no-dev --with pytest pytest -q
  tests/test_e2e_search.py` -> 7 passed.

## 2026-06-30: Backend validation CLI

Closed the local operator-runner gap for the §2.8 trajectory replay harness.

- Added `leanfoundry.env_backend.validation_cli` and the
  `leanfoundry-validate-backend` console script.
- The CLI accepts `BackendValidationCase` JSON or JSONL, derives or verifies a
  single `env_profile` for the run, connects once to the configured backend,
  replays every case through `validate_backend_case(...)`, prints JSON
  diagnostics, and exits nonzero when any report fails.
- This does not generate LeanDojo/LeanTree fixtures by itself; selected
  datasets still need adapters that materialize the existing
  `BackendValidationCase` schema before the real replay/caching/latency run.

Remaining live work:

- Run `leanfoundry-validate-backend` over actual LeanDojo/LeanTree validation
  case files against the target backend profile and record replay correctness,
  cache behavior, and latency.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_backend_validation.py`
  -> 4 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/env_backend/validation.py
  leanfoundry/env_backend/validation_cli.py tests/test_backend_validation.py`
  -> passed.

## 2026-06-30: Frozen pass@N curriculum helper

Closed the local construction gap for Extension D's frozen theorem-to-round
assignment.

- Added `build_frozen_curriculum_from_pass_sweep(...)` in
  `leanfoundry.evals.experiment_plan` and exported it from `leanfoundry.evals`.
- The helper consumes aligned `TheoremSpec` / `SearchResult` pairs from one
  direct whole-proof pass@N sweep, requires complete direct verifier-attempt
  evidence for candidates `1..N`, computes per-theorem accepted-candidate
  rates, assigns default `unsolved/hard/medium/easy` buckets, and rank-splits
  the fixed pool into training rounds.
- Weak evidence fails closed: missing attempts, duplicate candidate indices,
  missing theorem ids, and theorem-id mismatches raise before a curriculum is
  produced.

Remaining external/training work:

- Run the direct pass@N sweep on the chosen model and theorem pool, use this
  helper to freeze the curriculum, then execute optimizer/checkpoint/metering
  work in the downstream training/deployment stack.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_extension_d_plan.py`
  -> 9 passed.
- `uv run --no-dev --with flake8 flake8
  leanfoundry/evals/experiment_plan.py leanfoundry/evals/__init__.py
  tests/test_extension_d_plan.py` -> passed.

## 2026-06-30: Extension D budget guard helper

Closed the local hard-cap enforcement helper gap for Extension D.

- Added `leanfoundry.evals.budget` with `BudgetGuardDecision` and
  `check_budget_request(...)`.
- The helper evaluates one metered request against one `BudgetLedgerEntry`
  cell, verifies the request's `budget_account_id`, returns
  remaining-before/after diagnostics, refuses hard-cap overruns, and allows
  soft-cap overruns when `hard_cap=False`.
- This is not a distributed metering service. Durable usage counters,
  concurrency-safe decrement/reservation, and deployment integration remain the
  responsibility of the site-specific serving/training stack.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_extension_d_plan.py`
  -> 14 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals/budget.py
  leanfoundry/evals/__init__.py tests/test_extension_d_plan.py` -> passed.

## 2026-06-30: Generic TTT orchestration loop

Closed the local loop-control gap for Extension C without adding trainer or
MCGS-specific code.

- Added `leanfoundry.ttt.orchestrator` with `TTTRoundContext`,
  `TTTSearchRound`, `TTTSampleExtractor`, and `run_ttt_session(...)`.
- The loop alternates injected search, injected sample extraction,
  `TTTAdapter.fine_tune(...)`, adapter reload, and
  `AdaptablePolicyClient.with_adapter(...)`.
- The session trace records proved exits, insufficient-sample stops, training
  failures, reload failures, adapter ids, budgets, and sample counts. TTT traces
  are not promoted to main replay by this loop.
- Concrete LoRA optimizer execution/reload, MCGS or another selected
  per-problem search source, and any trace-promotion gate remain external or
  future work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_ttt_contract.py`
  -> 13 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/ttt
  tests/test_ttt_contract.py` -> passed.

## 2026-06-30: Formalization staging metadata helpers

Closed local Extension-B metadata gaps that do not require LLM or embedding
services.

- Added `leanfoundry.formalization.metadata` with exact normalized
  statement/header/env-profile dedup hashing.
- Added `staging_record_with_dedup_hash(...)` to populate or verify
  `FormalStatementStagingRecord.dedup_hash` before promotion.
- Added `estimate_difficulty_from_quick_search(...)`, which maps a quick-search
  `SearchResult` to an `easy/frontier/hard` bucket plus the numeric
  `difficulty_estimate` stored by `TheoremRecord`.
- These helpers do not replace semantic LLM judging, embedding-similarity dedup,
  statement verification wrappers, or the LLM draft/retry pipeline.

Validation:

- `uv run --no-dev --with pytest pytest -q
  tests/test_formalization_promotion.py` -> 11 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/formalization
  tests/test_formalization_promotion.py` -> passed.

## 2026-06-30: Inline portable state payload helpers

Closed a local Extension-A state-portability gap without implementing backend
state export/import or a router.

- Added `make_inline_state_ref(...)` and `decode_inline_state_ref(...)` to
  `leanfoundry.scaleout.state_portability`.
- RAW inline state bytes now round-trip through `PortableStateRef` with
  base64 payloads, SHA-256 metadata, raw-size metadata, and decode-time
  integrity checks.
- ZSTD remains an optional codec that requires an installed `zstandard`
  runtime. URI payload storage/fetching, Lean backend export/import, and router
  transport remain future/deployment work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py`
  -> 10 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py` -> passed.

## 2026-06-30: Pure router scheduler baseline

Closed the local Extension-A router-semantics gap without implementing the
TCP/binary router service or backend state transfer.

- Added `leanfoundry.scaleout.router` with immutable router-state transitions:
  `register_backend(...)`, `enqueue_request(...)`, `complete_request(...)`, and
  `disconnect_backend(...)`.
- The scheduler assigns queued requests FIFO to idle backend CPU slots, drains
  pending work after completions, rejects duplicate backend/request ids, and
  requeues in-flight requests when a backend disconnects.
- This is deliberately not the production REPL router. Socket framing, client
  connection tracking, backend adapters, state export/import, URI payload
  stores, distributed replay, and deployment autoscaler integration remain
  future/deployment work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py`
  -> 15 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py` -> passed.

## 2026-06-30: Binary router frame codec

Closed the local Extension-A framing gap without implementing the TCP router
service or router adapter.

- Added `leanfoundry.scaleout.protocol` with `RouterCommand`, `RouterFrame`,
  `encode_router_frame(...)`, and `decode_router_frame(...)`.
- The codec implements the documented
  `uint64 request_id | uint8 command | uint16 response_count | uint32 payload`
  frame in network byte order, treats payloads as opaque bytes, and rejects
  short frames, unknown command bytes, and length mismatches.
- Command-specific payload schemas, socket connection management, backend
  adapters, state transfer, distributed replay, and deployment integration
  remain future/deployment work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py`
  -> 21 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py` -> passed.

## 2026-06-30: Reference asyncio router service

Closed the local Extension-A TCP routing baseline without implementing the Lean
backend adapter or deployment hardening.

- Added `leanfoundry.scaleout.service` with `AsyncRouterService`,
  `RouterServiceConfig`, and `RouterBackendRegistration`.
- The service accepts backend `REGISTER` frames, client `REQUEST` frames,
  forwards assigned opaque payloads as `FORWARD`, converts backend `RESPONSE`
  frames into client `DELIVER`, and requeues in-flight requests when a backend
  stream disconnects.
- Backend registration is a small JSON payload inside the binary frame. Lean
  backend launch/adaptation, state export/import, URI payload transfer,
  production connection hardening, metrics, distributed replay, and autoscaler
  integration remain future/deployment work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py`
  -> 25 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py` -> passed.

## 2026-06-30: Local file URI state payload helpers

Closed the local Extension-A URI payload gap for filesystem-backed state refs
without implementing remote object-store adapters or Lean state export/import.

- Added `make_file_state_ref(...)` and `decode_file_state_ref(...)` to
  `leanfoundry.scaleout.state_portability`.
- `make_file_state_ref(...)` writes encoded state bytes to a local file and
  returns a `PortableStateRef(location=URI)` with a `file://` URI.
- `decode_file_state_ref(...)` accepts only `file://` refs, reads the payload,
  checks payload byte count, decodes according to the ref codec, and validates
  decoded SHA-256 plus raw size.
- Remote/object-store URI payload adapters, router payload transfer, and Lean
  backend export/import remain future/deployment work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py`
  -> 28 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py` -> passed.

## 2026-06-30: Router-backed EnvBackend adapter

Closed the local Extension-A adapter gap between LeanFoundry search/eval code
and the reference router, without implementing state export/import or
production deployment.

- Added `leanfoundry.scaleout.exec_adapter` with `RouterEnvBackend`,
  `RouterBackendWorker`, router exec payload schemas, and encode/decode
  helpers.
- `RouterEnvBackend` implements the normal `EnvBackend` protocol by sending
  lean-client `/exec` request models as JSON payloads inside router `REQUEST`
  frames and parsing returned response models from `DELIVER` frames.
- `RouterBackendWorker` connects as a router backend, decodes those operations,
  calls an injected concrete `EnvBackend`, and returns `RESPONSE` frames. The
  adapter covers limits, create_states, one-state step_batch via
  `EnvBackend.step(...)`, verify, cleanup, cancel, and stats.
- This preserves the existing scheduler unit: one proof-state expansion is one
  router request. Lean state export/import, remote payload movement, backend
  process supervision, distributed replay, and production deployment remain
  future/deployment work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py
  tests/test_scaleout_exec_adapter.py` -> 31 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py`
  -> passed.

## 2026-06-30: ZSTD scale-out optional extra

Closed the local optional-dependency gap for compressed portable state refs.

- Added the `[scaleout]` optional extra with `zstandard>=0.23.0`.
- Added focused coverage for `StateSnapshotCodec.ZSTD`: default installs
  assert the missing-extra path fails closed with a clear runtime error, while
  `uv run --extra scaleout` exercises real ZSTD inline and `file://` state-ref
  round-trips.
- Deployment still needs to decide whether router/backends install `[scaleout]`
  consistently; this only makes the package contract explicit and tested.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py
  tests/test_scaleout_exec_adapter.py` -> 32 passed.
- `uv run --extra scaleout --with pytest pytest -q
  tests/test_scaleout_contracts.py` -> 29 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py`
  -> passed.

## 2026-06-30: Reference router process entrypoints

Closed the local process-launch gap for the Extension-A reference router,
without adding site-specific supervisor manifests or production hardening.

- Added `leanfoundry.scaleout.router_cli` and the `leanfoundry-router`
  console script. It starts `AsyncRouterService` on a configured host/port.
- Added `leanfoundry.scaleout.worker_cli` and the
  `leanfoundry-router-worker` console script. It builds
  `RouterBackendWorker` around `make_env_backend(EnvBackendConfig(...))`.
- Focused tests cover parser/config construction and backend-factory
  injection without requiring a live Lean backend or a long-running service.
- Supervisor manifests, health checks, restart policy, metrics export,
  TLS/auth, and cluster autoscaler wiring remain deployment work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py
  tests/test_scaleout_exec_adapter.py tests/test_scaleout_cli.py`
  -> 35 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py
  tests/test_scaleout_cli.py` -> passed.

## 2026-06-30: Router health snapshot and pending-client cleanup

Closed a local hardening gap in the Extension-A reference router without adding
site-specific health endpoints or backend cancellation.

- Added `RouterServiceSnapshot` and `AsyncRouterService.snapshot()` with
  backend-slot, queue, client-request, stored-frame, assignment, delivery,
  requeue, and dropped-pending diagnostics.
- Added `drop_pending_requests(...)` to the pure router scheduler.
- Client disconnects now remove requests that are still pending in the queue.
  Requests already forwarded to a backend still run to completion and have
  their delivery discarded, because no backend cancellation protocol exists in
  the reference router yet.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py
  tests/test_scaleout_exec_adapter.py tests/test_scaleout_cli.py`
  -> 37 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py
  tests/test_scaleout_cli.py` -> passed.

## 2026-06-30: Formalization statement-check wrapper

Closed the local Extension-B statement-verifier wrapper gap without building
the LLM draft/retry loop or semantic judge.

- Added `leanfoundry.formalization.statement_verifier` with
  `StatementVerificationResult`, `verify_staging_statement_code(...)`,
  `verify_staging_statement(...)`, `KiminaStatementVerifier`, and
  `staging_record_with_syntax_result(...)`.
- The wrapper builds a Lean snippet with the staging row's header and a `sorry`
  body, calls lean-client's legacy REPL `api_check` route, and normalizes
  accepted/rejected/error outcomes for the staging `syntax_checked` gate.
- This is syntax/type checking only. It does not run the LLM draft/retry loop,
  semantic judge, embedding-similarity dedup, or live statement-check corpus.

Validation:

- `uv run --no-dev --with pytest pytest -q
  tests/test_formalization_promotion.py` -> 16 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/formalization
  tests/test_formalization_promotion.py` -> passed.

## 2026-06-30: Formalization semantic-judge contract

Closed the local Extension-B semantic-judge service contract gap without
building or calibrating a real judge model.

- Added `leanfoundry.formalization.semantic_judge` with `SemanticJudge`,
  `SemanticJudgeResult`, `HTTPSemanticJudge`,
  `parse_semantic_judge_response(...)`,
  `staging_record_with_semantic_judge_result(...)`, and payload helpers.
- The HTTP judge posts a staged informal/formal pair to a JSON endpoint and
  requires a numeric score in `[0, 1]`; promotion remains responsible for
  applying the threshold.
- This does not implement the LLM judge model, calibration corpus, deployment,
  embedding-similarity dedup, or live staged-corpus evaluation.

Validation:

- `uv run --no-dev --with pytest pytest -q
  tests/test_formalization_promotion.py` -> 21 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/formalization
  tests/test_formalization_promotion.py` -> passed.

## 2026-06-30: Formalization draft/retry orchestration

Closed the local Extension-B draft/retry orchestration gap without choosing or
deploying a concrete formalizer model.

- Added `leanfoundry.formalization.drafting` with `Formalizer`,
  `FormalizationDraftRequest`, attempt/result schemas, verifier feedback, and
  `run_formalization_draft_loop(...)`.
- The loop calls an injected formalizer, checks each generated Lean statement
  through the statement verifier wrapper, passes verifier messages into the
  next attempt, and returns a staging row only when syntax checking accepts.
- This slice did not yet implement a model adapter, prompt policy, formalizer
  service, real judge calibration, embedding-similarity dedup, or live
  staged-corpus evaluation; later 2026-06-30 slices added the formalizer and
  embedding-dedup service contracts.

Validation:

- `uv run --no-dev --with pytest pytest -q
  tests/test_formalization_promotion.py` -> 25 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/formalization
  tests/test_formalization_promotion.py` -> passed.

## 2026-06-30: Router health and metrics endpoint

Closed the local Extension-A health/metrics endpoint gap without claiming
production deployment integration.

- Added `leanfoundry.scaleout.health` with `RouterHealthReport`,
  `router_health_report(...)`, `router_metrics_text(...)`, and a minimal HTTP
  handler for `/healthz`, `/readyz`, and `/metrics`.
- `leanfoundry-router` now accepts `--health-host`, `--health-port`, and
  `--health-allow-zero-backends`; when enabled, it serves the side HTTP
  endpoint from the live `AsyncRouterService.snapshot()`.
- This is a reference supervisor hook only. It does not provide restart policy,
  service discovery, auth/TLS, pager wiring, cluster autoscaler integration,
  or backend cancellation for abandoned in-flight work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_health.py
  tests/test_scaleout_cli.py` -> 7 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_health.py tests/test_scaleout_cli.py` -> passed.

## 2026-06-30: HTTP state-ref payload reads

Closed the read-only remote URI payload gap for portable state refs without
claiming credentialed object-store writes or backend state export/import.

- Added `decode_http_state_ref(...)` for `http://` and `https://`
  `PortableStateRef(location=URI)` payloads.
- Added `decode_uri_state_ref(...)` as the supported URI dispatcher for
  `file://` and HTTP(S) refs.
- Both paths enforce `payload_size_bytes`, decode the configured state snapshot
  codec, and verify the decoded state SHA-256/raw-size invariants.
- This supports public or signed HTTP(S) object URLs. It does not implement
  S3/GCS/Azure SDK clients, credential management, remote writes, lifecycle
  policy, or backend state export/import.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py`
  -> 34 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py` -> passed.

## 2026-06-30: Router cancellation for abandoned in-flight work

Closed the local router/worker cancellation-semantics gap without claiming that
every concrete Lean backend can abort kernel execution instantly.

- Added `RouterCommand.CANCEL` as a router-to-backend frame.
- Added `cancel_inflight_requests(...)`, which removes abandoned in-flight
  requests from scheduler state, records request/backend cancellation
  assignments, and drains queued work into freed slots.
- `AsyncRouterService` now sends `CANCEL` frames when a client disconnects
  after assignment, tracks `cancelled_requests`, and drops late responses for
  already-cancelled request ids.
- `RouterBackendWorker` tracks one task per forwarded router request and
  cancels the corresponding task when it receives `CANCEL`.
- Concrete Lean process/kernel abort remains backend-owned; this is the local
  router protocol and worker-task cancellation contract.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_scaleout_contracts.py
  tests/test_scaleout_exec_adapter.py tests/test_scaleout_health.py`
  -> 44 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/scaleout
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py
  tests/test_scaleout_health.py` -> passed.

## 2026-06-30: Local durable budget-meter store

Closed the local durable budget-counter gap for Extension-D ablation plans
without claiming trainer integration or distributed metering deployment.

- Added `leanfoundry.evals.budget_store.SQLiteBudgetMeterStore`, backed by
  SQLite.
- `initialize_ledger(...)` creates one durable cell per
  arm/round/`BudgetLedgerMeter` and rejects drift if an existing cell's account,
  limit, unit, or hard-cap bit disagrees with the plan ledger.
- `reserve(...)` wraps `check_budget_request(...)` in a `BEGIN IMMEDIATE`
  transaction, updates usage only for allowed requests, preserves hard-cap
  refusals without spending, and supports soft-cap overrun when the ledger cell
  allows it.
- Tests cover normal reservations, account mismatch, hard-cap refusal,
  soft-cap overrun, existing-cell drift, and concurrent local hard-cap
  serialization.
- Distributed metering services, trainer-side request wiring, worker-side live
  measurements, and production DB deployment remain external.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_extension_d_plan.py`
  -> 20 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals
  tests/test_extension_d_plan.py` -> passed.

## 2026-06-30: Budget-meter CLI hook

Closed the local script-entrypoint gap for the SQLite budget meter without
building a distributed metering service.

- Added `leanfoundry.evals.budget_cli` and the `leanfoundry-budget-meter`
  console script.
- `init` creates/verifies SQLite meter cells from either a JSON list of
  `BudgetLedgerEntry` objects or an object with a `budget_ledger` field.
- `reserve` atomically spends one cell through `SQLiteBudgetMeterStore` and
  exits nonzero when the budget guard refuses the request.
- `snapshot` prints the durable usage state for one arm/round/meter cell.
- This remains a local operator/script hook. Trainer-side request wiring,
  worker-side measurement collection, distributed metering services, and
  production DB deployment remain external.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_extension_d_plan.py`
  -> 22 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals
  tests/test_extension_d_plan.py` -> passed.

## 2026-06-30: TTT trace promotion decision gate

Closed the local TTT trace-promotion gate gap without writing promoted traces
to replay or implementing trainer-side LoRA/reload.

- Added `leanfoundry.ttt.promotion` with `TTTTracePromotionConfig`,
  `TTTTracePromotionDecision`, `ttt_trace_key(...)`, and
  `evaluate_ttt_trace_promotion(...)`.
- The default gate requires `TTTConfig.promote_traces_to_main_replay`, matches
  base checkpoint and trace namespace, optionally checks env profile, rejects
  caller-supplied duplicate trace keys, rejects failed stages, and promotes
  only solved sessions with at least one successful adapter reload.
- Passing decisions return a copy of the session trace with
  `promoted_to_main_replay=True`; replay-store writes remain caller-owned.
- MCGS/per-problem search sources and concrete trainer/reload implementation
  remain external.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_ttt_contract.py`
  -> 19 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/ttt
  tests/test_ttt_contract.py` -> passed.

## 2026-06-30: Embedding dedup service contract

Closed the local Extension-B embedding-dedup contract gap without claiming a
real embedding model, vector index, calibrated corpus threshold, or deployment.

- Added `leanfoundry.formalization.embedding_dedup` with
  `HTTPEmbeddingDeduplicator`, `EmbeddingDedupResult`, payload construction,
  and parser validation for threshold-consistent unique/duplicate responses.
- Added `PromotionGateConfig(require_embedding_unique=True)` so promotion can
  reject missing, errored, or duplicate embedding-dedup results when a caller
  has run the service.
- Kept `FormalStatementStagingRecord` unchanged; the current schema stores the
  exact normalized `dedup_hash`, while embedding-similarity decisions are a
  promotion-time gate owned by the caller.
- Real embedding model/index selection, calibration, deployed service wiring,
  and live staged-corpus dedup runs remain external/future work.

Validation:

- `uv run --no-dev --with pytest pytest -q
  tests/test_formalization_promotion.py` -> 30 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/formalization
  tests/test_formalization_promotion.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 316 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py
  tests/test_slime_live.py -q` -> 3 passed, 1 skipped.
- `uv run --extra scaleout --with pytest pytest -q
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py
  tests/test_scaleout_health.py` -> 44 passed.

## 2026-06-30: Backend validation latency reporting

Made the live backend validation CLI more useful for the remaining
external-data run without claiming that a real trajectory/caching sweep has
been executed.

- Added timing fields to `BackendValidationReport`: create latency, aggregate
  replay-step latency, verify latency, and total case latency.
- `validate_backend_case(...)` now measures those durations with an injectable
  monotonic clock, keeping the unit tests deterministic.
- `leanfoundry-validate-backend` JSON summaries now include aggregate latency
  totals and mean latency per case.
- Updated the validation harness docs/trackers so the remaining work is
  specifically real LeanDojo/LeanTree case material plus live backend cache
  interpretation.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_backend_validation.py`
  -> 4 passed.
- `uv run --no-dev --with flake8 flake8
  leanfoundry/env_backend/validation.py
  leanfoundry/env_backend/validation_cli.py tests/test_backend_validation.py`
  -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 336 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.

## 2026-06-30: Extension B HTTP formalizer contract

Closed the local formalizer service/prompt-contract gap without claiming a
deployed model or calibrated live corpus pipeline.

- Added `leanfoundry.formalization.formalizer` with `HTTPFormalizer`,
  `formalizer_payload(...)`, `default_formalizer_prompt(...)`, and
  `parse_formalizer_response(...)`.
- The payload carries the staging id, informal statement, env profile, header,
  attempt index, optional verifier feedback, and a structured response-format
  contract requiring `lean_statement`.
- The response parser accepts only a JSON object with a non-empty
  `lean_statement`, keeping free-text extraction out of the core contract.
- Updated Extension B docs and trackers to leave only real model checkpoints,
  deployed services/indexes, calibration, and live staged-corpus runs as
  future/external work.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_formalization_promotion.py`
  -> 33 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/formalization
  tests/test_formalization_promotion.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 336 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.

## 2026-06-30: PutnamBench Lean4 benchmark row adapter

Closed the second concrete public-benchmark adapter gap for eval loading.

- Added `PUTNAMBENCH_LEAN4_ROW_FORMAT` / `putnambench_lean4_jsonl` plus
  `adapt_putnambench_lean4_row(...)` and
  `make_putnambench_lean4_row_adapter(...)`.
- The adapter handles the public PutnamBench Lean4 JSONL row shape:
  `problem_name`, `formal_statement`, optional `informal_statement`, and
  `split`.
- Since those public rows have no per-row Lean header, the built-in loader path
  requires an `EnvProfile` registry entry for the manifest `env_profile` and
  uses that registered header.
- Full Lean blocks are preserved as `TheoremSpec.lean_statement`, including
  helper declarations before the theorem.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_eval_io.py
  tests/test_benchmark_manifest.py` -> 20 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals
  tests/test_eval_io.py tests/test_benchmark_manifest.py` -> passed.

## 2026-06-30: ProofNet Lean4 benchmark row adapter

Closed the ProofNet public-benchmark adapter gap with an explicit
theorem-initialization transform.

- Added `PROOFNET_LEAN4_ROW_FORMAT` / `proofnet_lean4_jsonl` plus
  `adapt_proofnet_lean4_row(...)` and
  `make_proofnet_lean4_row_adapter(...)`.
- The adapter handles the public ProofNet Lean4 row shape: `name`,
  `formal_statement`, `header`, optional `informal_prefix`, and `split`.
- Public rows end theorem statements at `:=`; the adapter only accepts that
  exact placeholder shape and fills it with `by sorry`. Non-placeholder
  statements fail closed instead of being rewritten.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_eval_io.py
  tests/test_benchmark_manifest.py` -> 25 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals
  tests/test_eval_io.py tests/test_benchmark_manifest.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 333 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.

## 2026-06-30: MathOlympiadBench Lean4 benchmark row adapter

Closed another concrete public-benchmark adapter gap for eval loading.

- Added `MATHOLYMPIADBENCH_LEAN4_ROW_FORMAT` /
  `matholympiadbench_lean4_jsonl` plus
  `adapt_matholympiadbench_lean4_row(...)` and
  `make_matholympiadbench_lean4_row_adapter(...)`.
- The adapter handles the public MathOlympiadBench JSONL row shape:
  `name`/`problem_id`, `formal_statement`, `header`, optional
  `informal_prefix`, and `split`.
- Full Lean blocks are preserved as `TheoremSpec.lean_statement`, including
  helper declarations before the theorem.
- ProofNet was inspected but left gated: public rows end theorem statements at
  `:=`, so supporting it should be a deliberate theorem-initialization
  transform, not an implicit loader rewrite.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_eval_io.py
  tests/test_benchmark_manifest.py` -> 22 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals
  tests/test_eval_io.py tests/test_benchmark_manifest.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 330 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.

## 2026-06-30: Tracker schema-version and stage-data cleanup

Cleaned up stale tracker/design wording after the promoted TTT trace replay
schema landed.

- Updated the Phase 1 durable-spine tracker to name the current SQLite replay
  schema as v8 and include TTT trace replay rows in the durable artifact set.
- Updated the issue matrix entry for §6 data-for-each-stage from
  `training-repo / needs-code` to `current / training-repo`, because durable
  replay artifacts, training rows, and Slime Sample construction now have local
  baselines; trainer execution remains downstream.
- Updated the older migration-registry design note to say v11.74 supersedes the
  current schema version to v8.

Validation:

- `git diff --check` -> passed.

## 2026-06-30: TTT promoted-trace replay writes

Closed the local Extension-C replay-write gap for promoted TTT traces without
claiming trainer-side LoRA/reload or a new per-problem search algorithm.

- Added `TTTTraceReplayRecord` as the durable promoted-trace artifact schema.
- Added SQLite schema version 8 with `ttt_trace_replay`, plus v7-to-v8 upgrade
  coverage and initial-schema consistency coverage.
- Added `ReplayStore.put_ttt_trace_replay_records(...)` and the
  `SQLiteReplayStore` implementation.
- Added `ttt_trace_replay_record_from_decision(...)` and
  `persist_promoted_ttt_trace(...)` so callers explicitly persist a promoted
  `TTTSessionTrace` plus its `TTTTracePromotionDecision`.
- Kept the write trace-only: it does not synthesize A-type proof rows,
  policy examples, or value labels from TTT traces.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_ttt_contract.py
  tests/test_replay_store.py tests/test_schema_database_consistency.py`
  -> 49 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/schemas/ttt.py
  leanfoundry/replay/base.py leanfoundry/replay/sqlite_store.py
  leanfoundry/ttt tests/test_ttt_contract.py tests/test_replay_store.py
  tests/test_schema_database_consistency.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 325 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py
  tests/test_slime_live.py -q` -> 3 passed, 1 skipped.
- `uv run --extra scaleout --with pytest pytest -q
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py
  tests/test_scaleout_health.py` -> 44 passed.

## 2026-06-30: Literature framing for training-data novelty

Corrected the docs around the question that motivated the training repo:
state-tactic search data is not new, and LeanFoundry should not frame it as if
it were.

- Added a v11.70 design note stating that HTPS, LeanDojo/ReProver, and
  BFS-Prover-style systems already use proof-state/tactic or search-distilled
  step data.
- Added HTPS to the system landscape and reference list.
- Updated `canonical_search.md` so the tree shape is required for whole-proof
  rendering/auditing and optional rendered-HER, not for Path-A step-policy
  training data.
- Tightened `slime_adapter_spec.md` around the actual downstream question:
  compare step rows, whole-proof rows, self-correction rows, and mixtures under
  fixed curriculum, env profile, verifier budget, and eval suite.

Validation:

- `git diff --check` -> passed.

## 2026-06-30: System landscape source refresh

Refreshed the external landscape docs from primary arXiv/project pages so the
repo boundary is not anchored to stale prover claims.

- Added OProver and Pythagoras-Prover to the system landscape and references as
  2026 open whole-proof / agentic baselines.
- Updated issue #29 from "not live-verified" to "refreshed on 2026-06-30 but
  still external-stale-risk."
- Kept the core conclusion narrow: LeanFoundry's role is reusable
  stateless-search/replay/eval infrastructure for controlled experiments, not
  being the latest prover checkpoint.

Validation:

- `git diff --check` -> passed.

## 2026-06-30: Lean-client adapter boundary regression

Strengthened the local `/exec` client-boundary evidence without claiming server
internals are verified in this checkout.

- Added `tests/test_env_backend.py::test_kimina_backend_forwards_exec_facade_methods`.
- The test wires a fake connected `AsyncLeanExecBackend`-shaped object into
  `KiminaEnvBackend` and checks pass-through for `limits`, `create_states`,
  `step`, `verify_one`, `verify`, `cleanup`, `cancel`, `stats`, and `close`.
- The test also pins the `goal_group` conversion from tuple to the lean-client
  list form.
- Updated issue #31 to remove the stale "missing lean-client checkout" rationale
  and keep the remaining server behavior under live/backend-side validation.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_env_backend.py`
  -> 3 passed.
- `uv run --no-dev --with flake8 flake8 tests/test_env_backend.py
  leanfoundry/env_backend` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 317 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py
  tests/test_slime_live.py -q` -> 3 passed, 1 skipped.
- `uv run --extra scaleout --with pytest pytest -q
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py
  tests/test_scaleout_health.py` -> 44 passed.

## 2026-06-30: MiniF2F Lean4 benchmark row adapter

Closed the first concrete public-benchmark adapter gap for eval loading without
claiming all benchmark formats are covered.

- Added `leanfoundry.evals.adapters` with `MINIF2F_LEAN4_ROW_FORMAT`,
  `adapt_minif2f_lean4_row(...)`, and
  `make_minif2f_lean4_row_adapter(...)`.
- `load_benchmark_source(...)` / `load_benchmark_jsonl(...)` now recognize
  `row_format="minif2f_lean4_jsonl"` and adapt MiniF2F Lean4 rows with
  `id`/`name`, `split`, `formal_statement`, `header`, and optional informal
  text into `TheoremSpec`s using the manifest env profile.
- Manifest/row split mismatches fail closed, and callers can still override the
  built-in adapter with an explicit row adapter mapping.
- Other public benchmark adapters remain future work until their native row
  formats and env-profile compatibility are selected.

Validation:

- `uv run --no-dev --with pytest pytest -q tests/test_eval_io.py
  tests/test_benchmark_manifest.py` -> 17 passed.
- `uv run --no-dev --with flake8 flake8 leanfoundry/evals
  tests/test_eval_io.py tests/test_benchmark_manifest.py` -> passed.
- `uv run --no-dev --with pytest pytest -q` -> 320 passed, 8 skipped.
- `uv run --no-dev --with flake8 flake8 leanfoundry tests` -> passed.
- `uv lock --check` -> passed.
- `git diff --check` -> passed.
- `uv run --extra training pytest -m slime tests/test_slime_compat.py
  tests/test_slime_live.py -q` -> 3 passed, 1 skipped.
- `uv run --extra scaleout --with pytest pytest -q
  tests/test_scaleout_contracts.py tests/test_scaleout_exec_adapter.py
  tests/test_scaleout_health.py` -> 44 passed.
