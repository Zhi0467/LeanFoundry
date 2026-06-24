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
  Markovian state and the history-conditional root-to-state tactic prefix.
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
