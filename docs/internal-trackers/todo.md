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

1. Operational retry policy
   - Wire lean-client's existing all-overloaded retry/backoff knobs through
     `EnvBackendConfig` / `KiminaEnvBackend` instead of adding a second
     LeanFoundry search-loop retry path. Existing knob names are
     `max_overloaded_retries` and `overload_backoff_seconds`.
   - Those client-side overload retries stay outside `max_tactic_calls` and
     outside value-label effort accounting, because no Lean tactic ran.
   - If all-overloaded is still returned after the client/backend retry layer is
     exhausted, return an operational error for backpressure. Do not report
     `EXHAUSTED`, because search did not spend proof-search effort; it hit an
     infrastructure capacity failure.
   - Mixed `overloaded` plus executed statuses remains an immediate backend
     protocol failure after charging the executed tactic attempts. Do not attach
     partial action children from that step item.
   - `invalid_state_token` remains immediate v0 failure; do not rederive tokens
     or restart theorem search until durable replay/resume exists.
   - Tests for this slice: config fields are forwarded into
     `AsyncLeanExecBackend.connect(...)`; all-overloaded after client retries
     returns an operational `ERROR` with zero tactic budget and no proof/value
     artifacts; mixed overloaded/executed still charges executed tactic attempts
     and fails the theorem attempt.

2. Runtime `OPEN` and unproved attempt outcomes
   - Keep runtime OR-state statuses as `OPEN | PROVED | DISPROVED` in v0. A dead
     attached tactic/action is only evidence that this tactic failed; it is not
     evidence that the state is false or that the LM action space is closed.
   - Do not add runtime `EXHAUSTED` until durable resume or a finite per-state
     action source gives `OPEN` and `EXHAUSTED` different runtime behavior.
   - Root `PROVED`: after final `/exec/verify`, emit proof data, positive policy
     data from the solved `ProofTree`, and value label `1` for proved states.
   - Root `DISPROVED`: emit full-weight value-negative data for the disproved
     state. Do not train the original-goal policy on this as a successful tactic;
     only the synthetic negation sub-search is positive policy data for the
     negation goal.
   - Root runtime `OPEN` at attempt stop becomes the top-level
     `EXHAUSTED`/unproved result. It may emit censored-negative value labels only
     after `min_censored_negative_effort`; it emits no policy data and is not
     mathematical falsity.

3. Training artifact extraction and proof rendering
   - Treat extraction as training-data extraction, not just solved-proof
     projection. The extractor must cover policy and value artifacts for
     verified `PROVED`, semantic `DISPROVED`, and root-`OPEN`-at-stop
     `EXHAUSTED`/unproved outcomes.
   - Define an explicit extraction output contract before implementing artifact
     emission. A likely shape is a `TrainingArtifacts`/`ExtractionResult` object
     containing verified proof candidates, policy examples, value labels,
     rendering/extraction failures, and small diagnostics. Do not overload
     `ProofTree` or `SearchResult.diagnostics` to carry all training artifacts.
   - Pass an extraction context instead of hidden globals: theorem id/env profile,
     search config, attempt ids, verification status, model version when known,
     and the effort counters needed for censored-negative gates.
   - The current `extract_proof_tree(...)` is only a first proved-proof
     projection used before final verification. It skips the synthetic
     initialization layer and projects each real initial backend state plus its
     first proved action into `ProofTree.roots`.
   - Do not assume only one proved action can exist at a state. The outer search
     loop stops after the root is structurally proved, but an expansion sends a
     batch of tactics and attaches all executed results before the loop can stop;
     multiple distinct tactics in that batch can prove the same OR state. Decide
     whether training emits one canonical proof, all proved alternatives from the
     final expansion, or a capped set.
   - Add value-label extraction separately from proof-tree extraction:
     verified proved paths -> label 1; disproved states -> full-weight label 0
     with `disproved=true`; root-`OPEN`-at-stop unproved attempts ->
     effort-gated censored label 0.
   - Make extraction node-general, not root-only. It must project and render
     the subtree rooted at an arbitrary state as a standalone proof of that
     state's goals, because HER extraction (later in this section) re-verifies
     extracted subproofs through the same path. Designing it root-only forces a
     rewrite.
   - Rendering is the unresolved half. The current linear-concatenation /
     bullet renderer is a narrow heuristic, not a general compiler from proof
     tree to valid Lean; positional rendering is a dead end, not a heuristic to
     refine. The remaining bullets are the rendering plan.
   - Decide the source of truth first. Either LeanFoundry reconstructs surface
     focusing from the tree, or the backend (which holds the elaborated proof)
     returns the tactic script / proof term and LeanFoundry assembles from
     backend-provided pieces. `/exec/verify` stays the acceptance gate either
     way. This fork bounds how much rendering complexity LeanFoundry owns;
     resolve it before building the renderer.
   - If LeanFoundry renders, render by goal identity, mirroring how search
     focuses. Search focuses arbitrary goal subsets by id through
     `goal.continue`; surface Lean has no primitive for focusing an arbitrary,
     possibly non-contiguous subset together. Expansion already produces a
     non-contiguous coupled group (`focus (0, 2)` with independent goal `1`
     between, see `tests/test_expansion.py`), which positional `·` and
     bullet-free sequencing cannot express at all.
     - Prefer `case <tag> =>` focusing on the goal's case tag.
     - Gather a non-contiguous coupled subset with `on_goal` / `pick_goal` /
       `rotate`.
     - Fall back to positional `·` only for tagless single-goal splits.
     - Render a coupled multi-goal child as one contiguous block over its
       gathered goals; never re-split it internally. This is what replaces the
       current `UnsupportedProofExtraction` guard.
   - Thread initial-block holes structurally, not by regex. The `\bsorry\b`
     substitution rewrites `sorry` inside comments and strings and silently
     corrupts otherwise-valid proofs. Initial backend states map 1:1 to holes
     in source order; thread each root proof to its hole by backend hole
     identity/position, or a Lean-aware scan that skips comments and strings.
   - Measure rendering coverage as a distinct outcome. A proved tree we could
     not render is neither a search nor a verify error; emit a distinct
     extraction/rendering-failure signal and track its rate. Because the
     training-semantics contract gates all `PROVED` training artifacts
     (including tactic-policy pairs) on the rendered proof passing
     `/exec/verify`, rendering coverage directly bounds training-data yield.
   - Add real Lean fixtures before changing behavior: linear proof, multiple
     initial states, constructor bullets, cases/induction with named tags,
     tagless/inaccessible goals forcing the positional fallback, multi-line and
     nested-`by` tactic text, comments/strings containing `sorry`, contiguous
     and non-contiguous coupled groups, and coupled multi-goal rejection until
     identity-based focusing lands.
   - Optional sharper oracle: re-run each rendered subtree from its parent
     `state_token` and check it reaches the recorded child state, so a
     rendering bug localizes to one node instead of failing the whole proof
     opaquely.
   - Keep final `/exec/verify` as the acceptance gate.

4. Runner-owned attempt lifecycle
   - Move backend item identity ownership out of individual engines and into the
     runner/composition root. The runner should allocate an `attempt_id` before
     starting `SearchEngine.search(...)`, then pass an attempt context or explicit
     ids into the engine. Engines should not hide the only cancellable backend id
     behind an internal `make_search_id(...)` call.
   - Update the `EnvBackend` protocol before checked lifecycle handling:
     `cleanup(...)` should return `ExecCleanupResponse` and `cancel(...)` should
     return `ExecCancelResponse`, not plain `object`. Tests and fakes should
     assert `deleted`/`deferred` cleanup and cancel status behavior through those
     concrete wire models.
   - Use separate lifecycle ids for search state and final verification. A
     concrete v0 shape is:
     `search_item_id = f"{attempt_id}:search"` and
     `verify_item_id = f"{attempt_id}:verify"`.
   - Tree search uses `search_item_id` for `/exec/create_states`,
     `/exec/step_batch`, and state-store cleanup. Final `/exec/verify` uses
     `verify_item_id`, so cancelling or cleaning the search item cannot poison
     final verification.
   - Direct whole-proof search has no search state-store item. Its verifier
     attempts should still derive stable item ids from the runner attempt id, for
     example `f"{attempt_id}:verify:{k}"`, so cancellation/observability is
     consistent across direct and tree engines.
   - Normal tree completion path:
     search awaits each backend step; if root is structurally `PROVED`, extract
     candidate proof artifacts; verify with `verify_item_id`; persist or hand off
     accepted training artifacts; then cleanup `search_item_id`.
   - Abandoned path:
     if the runner times out, is shut down, or cancels the Python search task
     while backend work may still be queued or running, call
     `cancel([search_item_id])`, then call `cleanup([search_item_id])` until the
     backend reports `deleted` or the runner records a deferred cleanup retry.
   - Cleanup must become a checked operation, not a fire-and-forget `finally`.
     `/exec/cleanup` can return `deferred` while work is in flight or state is
     pinned. The runner should retry with bounded backoff, and durable runners
     should record any still-deferred cleanup for later recovery.
   - Do not call `cancel([search_item_id])` on the normal proved path before
     final verification. In the current backend, `/exec/verify` uses the same
     lifecycle registry; if search and verify share an item id, cancel can make
     verify return `cancelled`. Separate search/verify ids avoid this class of
     bug.
   - Update `SearchEngine.search(...)` and `run_search_batch(...)` together. A
     likely interface is a small `SearchAttemptContext` carrying `attempt_id`,
     `search_item_id`, `verify_item_id`, and cleanup/cancel policy knobs. Keep
     `run_search_batch(...)` model/backend agnostic; it may allocate default
     contexts for simple callers.
   - Return attempt identity in `SearchResult` diagnostics or a first-class result
     field so logs, SQLite rows, backend stats, and recovery jobs can be joined
     without scraping generated node ids.
   - Tests for this slice:
     runner allocates ids and engines use them; tree verify uses a different item
     id from search; normal completion cleans search state after verification;
     cancelled runner task calls cancel then retries cleanup on `deferred`; direct
     search verifier ids derive from the attempt id and do not call search-state
     cleanup.

5. Real policy/value adapters
   - Add concrete `PolicyClient` / `ValueClient` adapters behind the existing
     protocols.
   - Keep Slime/SGLang specifics behind the adapter boundary.

6. Bonded value mode and labels
   - Add the bonded `wrap(policy_client) -> value_client` factory when the model
     side is ready.
   - Emit `state_value_labels` only when LeanFoundry owns bonded labels.
   - Keep unbonded value clients label-free.

7. Negation pruning
   - Implement `try_negation` as a provenance-gated search behavior.
   - Synthetic negation attempts must count against `max_tactic_calls`.
   - Disproved labels are full-weight zero labels.

8. HER extraction
   - Extract and re-verify subproofs from solved trees.
   - Keep HER tree-shaped, not a flat tactic sequence.

9. Durable results and resume
   - Ensure finished trajectories/proofs are written to SQLite as they land.
   - Defer partial search-tree checkpointing until per-theorem budgets are large
     enough that losing in-flight compute hurts.

10. Graph/MCGS
    - Deferred until a complete state-identity fingerprint exists.
    - Do not optimize for graph merging before proving the tree path.
