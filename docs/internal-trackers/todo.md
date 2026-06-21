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

1. Richer proof rendering
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
   - Add real Lean fixtures before changing renderer behavior: linear proof,
     multiple initial states, constructor bullets, cases/induction with named
     tags, tagless/inaccessible goals forcing the positional fallback,
     multi-line and nested-`by` tactic text, contiguous and non-contiguous
     coupled groups, and coupled multi-goal rejection until identity-based
     focusing lands.
   - Optional sharper oracle: re-run each rendered subtree from its parent
     `state_token` and check it reaches the recorded child state.

2. Real policy/value adapters
   - Add concrete `PolicyClient` / `ValueClient` adapters behind the existing
     protocols.
   - Keep Slime/SGLang specifics behind the adapter boundary.

3. Bonded value mode and labels
   - Add the bonded `wrap(policy_client) -> value_client` factory when the model
     side is ready.
   - Emit `state_value_labels` only when LeanFoundry owns bonded labels.
   - Keep unbonded value clients label-free.

4. Negation pruning
   - Implement `try_negation` as a provenance-gated search behavior.
   - Synthetic negation attempts must count against `max_tactic_calls`.
   - Disproved labels are full-weight zero labels.

5. HER extraction
   - Extract and re-verify subproofs from solved trees.
   - Keep HER tree-shaped, not a flat tactic sequence.

6. Durable results and resume
   - Ensure finished trajectories/proofs are written to SQLite as they land.
   - Defer partial search-tree checkpointing until per-theorem budgets are large
     enough that losing in-flight compute hurts.

7. Graph/MCGS
   - Deferred until a complete state-identity fingerprint exists.
   - Do not optimize for graph merging before proving the tree path.
