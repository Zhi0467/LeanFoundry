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
