# LeanFoundry Internal Todo

This file is future-facing: active implementation plans, unresolved design
questions, and remaining work.

Historical implementation notes live in
[`implementation-log.md`](implementation-log.md).

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
   - Every accepted tree proof still requires final `verify_one` /
     `/exec/verify`.

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
   - Runtime `PROVED` becomes proof/policy/value training data only after final
     `/exec/verify` accepts the rendered proof. Without final verification it is
     only structural search state.
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

## SearchConfig Contract

Tree search and direct whole-proof search use different budget units.

1. `max_tactic_calls`
   - Hard cap on Lean tactic attempts for one tree-search theorem.
   - Primary stop condition and solved@budget x-axis.

2. `tactics_per_expansion`
   - Number of policy tactic candidates requested for one selected state.
   - Backend limits still cap the concrete step item width.

3. `max_direct_candidates`
   - Hard cap on whole-proof candidates verified by `DIRECT` or
     `SELF_CORRECT`.
   - This is a direct pass@k-style budget, not a tactic-call budget.

4. `direct_candidates_per_round`
   - Whole-proof candidates sampled per self-correction feedback round.
   - Total direct verifier attempts are still capped by
     `max_direct_candidates`.

5. `puct_exploration_weight`
   - PUCT exploration multiplier for high-prior, under-visited actions.

6. `best_first_missing_value_score`
   - Score assigned by `BEST_FIRST` to unvalued open leaf states.
   - Default is `0.0`, preserving the value-free fallback.

7. `try_negation`
   - Optional synthetic negation search for single-goal states.
   - Default remains false.

8. `min_censored_negative_effort`
   - Value-label emission gate, not a search stop condition.

9. `censored_negative_weight`
   - Training weight for searched-but-unproved states.

10. `value_mode`
    - Bonded/unbonded label-emission behavior.

## Not in SearchConfig Yet

Do not add these as first-class search config fields until the design docs,
traces, or profiling justify them:

1. Wall-clock cap per theorem.
2. Max tree nodes.
3. Max depth.
4. Max expansions.
5. Per-state action cap.
6. Outer decomposition/revision budgets.

Backend per-request timeouts belong to the `/exec` request/config layer, not to
tree-search semantics.

## Active Next Work

1. Lifecycle hardening
   - Per-theorem failure isolation and best-effort cleanup/cancel that never
     mask the primary outcome have landed (see implementation-log). Remaining:
   - Track all active backend item ids per attempt, not only the static
     `search_item_id`. Cancellation currently covers only tree search state; it
     must also cover the tree final `verify_item_id` and direct candidate
     verifier ids such as `verify_item_id:k`. While unwinding a cancellation
     there is no result to attach to, so a cancel failure is currently
     swallowed without a runner event; give it an observable sink.
   - Preserve cleanup-failure diagnostics on unexpected tree exceptions that
     are later wrapped by `run_search_batch(...)` as `runner_exception`. The
     tree engine currently calls best-effort cleanup on the outer exception
     path, but discards the returned `cleanup_failed` diagnostic before the
     driver turns the original error into a `SearchResult`.
   - Make cleanup diagnostics precise on transport/backend exceptions.
     `cleanup_search_state_best_effort(...)` currently reports
     `cleanup_attempts=cleanup_max_attempts` even when cleanup failed on the
     first call; report actual attempted calls or add a distinct field for
     planned retry capacity.
   - Add a durable deferred-cleanup outbox or attempt-lifecycle table for item
     ids still `deferred` after bounded retries. Track retry count, last
     status/error, next retry time, and whether the item is search-state or
     verifier work.
   - Reject duplicate runner-provided `attempt_id`, `search_item_id`, and
     `verify_item_id` values before launching concurrent attempts, with a test
     proving duplicate ids fail before any backend call.

2. Extraction and training-artifact hardening
   - Fix `DISPROVED` artifact semantics before enabling `try_negation`. The
     branch already labels the real initial state (not the synthetic root), so
     the two real gaps are: (1) a disproved root falls through to the top-level
     `EXHAUSTED` branch in `and_or.py`, so `SearchStatus.DISPROVED` is never
     produced even though the enum exists — map a disproved root to a disproved
     top-level outcome; and (2) the disproved value-label branch scans only the
     real initial states, so a disproved internal state emits no full-weight
     `ValueLabel(label=0, disproved=True)` — walk the tree for disproved nodes,
     not just the initial layer.
   - Make censored-negative effort node-local. Store or compute tactics tried
     below each `StateNode`, and use that value for censored-negative
     eligibility instead of applying the whole attempt budget to every open real
     initial state.
   - Decide and implement multiple-proved-action extraction: either emit every
     independently rendered and verified proved action as a separate proof
     candidate with derived policy/value artifacts, or explicitly keep
     canonical-first-only extraction and record skipped proved alternatives as a
     non-training diagnostic.
   - Add node-general HER extraction. Iterate proved subtree roots from the
     runtime tree, build subtree `TrainingSample` / `ProofTree` candidates,
     render each candidate, reverify under the same `env_profile`, and emit
     diagnostics for `her_candidate_multiplier`, `her_verified_multiplier`, and
     discarded failures.
   - Split extraction failure kinds in emitted artifacts: use `unsupported` for
     known unsupported tree shapes, `rendering` for renderer/compiler failures,
     and `verification` for final `/exec/verify` rejection.
   - Preserve base extraction diagnostics on all failure envelopes, including
     rendering failures, so root runtime status, search budget, proved action
     count, and proved alternatives remain visible.

3. Richer proof rendering
   - Current extraction emits a canonical proof candidate and explicit
     `TrainingArtifacts`; `extract_proof_tree(...)` remains a narrow renderer
     used before final `/exec/verify`.
   - Decide the source of truth before broadening rendering. Either LeanFoundry
     reconstructs surface focusing from the tree, or the backend returns tactic
     scripts/proof terms and LeanFoundry assembles backend-provided pieces.
     `/exec/verify` stays the acceptance gate either way.
   - If LeanFoundry renders, render by goal identity, mirroring how search
     focuses. Search focuses arbitrary goal subsets through `goal.continue`;
     surface Lean has no primitive for focusing an arbitrary, possibly
     non-contiguous subset together.
   - Prefer `case <tag> =>` for named goals; gather non-contiguous coupled
     subsets with `on_goal` / `pick_goal` / `rotate`; fall back to positional
     `·` only for tagless single-goal splits.
   - Render a coupled multi-goal child as one contiguous block over its gathered
     goals; never re-split it internally. This is what replaces the current
     `UnsupportedProofExtraction` guard.
   - Add a renderer invariant test that counts real `sorry` placeholders in
     `initial_lean_block`, rejects proof-script/placeholder cardinality
     mismatch, and fails if an inserted proof consumes a later placeholder.
   - Add real Lean fixtures before changing renderer behavior: linear proof,
     multiple initial states whose proofs would fail if swapped, constructor
     bullets, cases/induction with named tags, tagless/inaccessible goals
     forcing the positional fallback, multi-line and nested-`by` tactic text,
     model-emitted bullets, contiguous and non-contiguous coupled groups, and
     coupled multi-goal rejection until identity-based focusing lands.
   - Keep rejecting split children whose `focus` owns multiple goals until the
     renderer can reconstruct that exact focused group in surface Lean and the
     result is verified by a real Lean fixture.
   - Add an oracle test that re-runs each rendered subtree from its parent
     `state_token` and checks it reaches the recorded child focus/state for at
     least one independent split and one coupled-group case.

4. Real policy/value adapters
   - Add concrete `PolicyClient` / `ValueClient` adapters behind the existing
     protocols.
   - Keep Slime/SGLang specifics behind the adapter boundary.

5. Bonded value mode and labels
   - Add the bonded `wrap(policy_client) -> value_client` factory when the model
     side is ready.
   - Emit `state_value_labels` only when LeanFoundry owns bonded labels.
   - Keep unbonded value clients label-free.

6. Negation pruning
   - Implement `try_negation` as a provenance-gated search behavior.
   - Synthetic negation attempts must count against `max_tactic_calls`.
   - Disproved labels are full-weight zero labels.

7. Durable results and resume
   - Ensure finished trajectories/proofs are written to SQLite as they land.
   - Defer partial search-tree checkpointing until per-theorem budgets are large
     enough that losing in-flight compute hurts.

8. Graph/MCGS
   - Deferred until a complete state-identity fingerprint exists.
   - Do not optimize for graph merging before proving the tree path.
