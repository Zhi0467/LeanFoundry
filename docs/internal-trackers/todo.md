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

## Holistic Design Completion Map

This map is the high-level path from the design doc to an implementation plan.
Concrete mismatches and stale claims are tracked in [`issues.md`](issues.md).

1. Make the core verifiable and backend-neutral.
   - Keep the remote `lean-client` lock refreshed when the GitHub source
     changes.
   - Tighten env-profile contracts before relying on any generated data:
     replace ambiguous defaults, validate profile/header identity, and make
     every theorem/artifact carry the selected profile consistently.
   - Strengthen SQL/Pydantic consistency tests beyond column names: nullability,
     defaults, checks, and type affinity must match the strict Pydantic source
     of truth.
   - Remove backend-specific names from durable schemas before migrations are
     treated as stable public API.

2. Finish the minimal durable and evaluable single-machine spine.
   - Implement a concrete SQLite `ReplayStore` over the existing migration.
   - Decide the artifact persistence shape before writing code: tables vs
     artifact files, deterministic ids, content hashes, search-attempt records,
     extraction failures, cleanup outbox rows, and eval manifests.
   - Add artifact-to-store writers for finished proofs, trajectories, value
     labels, extraction failures, and eval manifests.
   - Add the fixed-model eval path needed to measure the baseline: direct
     pass@k, self-correct pass@k, tree-search solved@budget, and throughput
     artifact writing.
   - Keep live search-tree checkpointing deferred until replay/resume is
     explicitly designed; persist solved projections and scalar attempt records
     first.

3. Settle current search semantics before adding graph search.
   - Make current local root-to-leaf PUCT plus current hardest-child heuristic
     the v0 baseline contract, and explicitly defer global-UCB / LCB
     hardest-child semantics to later algorithm work.
   - Add a policy-context contract for tactic history and inline comment memory;
     current `PolicyClient.sample_tactics(...)` receives only state objects.
   - Split direct search serving from pass@k evaluation: `SearchEngine.search`
     may stop at first proof, but eval needs all-attempt verification and
     pass@k artifacts.
   - Keep graph/MCGS behind the state-identity gate. The implemented baseline is
     AND/OR tree search.

4. Complete extraction and rendering before treating search output as training
   data.
   - Finish lifecycle residuals, node-local value effort, `DISPROVED` status and
     label semantics, multiple-proved-action handling, node-general HER, failure
     classification, and renderer diagnostics.
   - Broaden proof rendering only with real Lean fixtures and oracle checks; the
     current renderer is intentionally narrow and fail-closed.

5. Build the infra-owned adapter surface after the persistent/evaluable loop.
   - Add a generic reference `PolicyClient` / `ValueClient` adapter only after
     the policy-context contract is stable.
   - Update design/API docs to match current `PolicyClient` / `ValueClient`
     separation and `run_search_batch(...)` signature.
   - Keep Slime, SGLang, Megatron, model choice, W&B, optimizer, and stage
     configs as training-repo responsibilities. LeanFoundry owns protocols and
     stable artifacts, not the recipe.

6. Treat extensions as gated work, not hidden core requirements.
   - Extension A starts after the single-machine spine is measured and replay is
     durable; it needs router/state-portability/replay-store adapter work, not
     just URL changes.
   - Extension B starts after core contamination rules and eval splits are
     stable; current code has staging schemas only.
   - Extension C / TTT starts after HER, adapter reload semantics, and
     per-problem trace persistence exist.
   - Extension D starts after Stage 1-style baselines and eval harnesses exist;
     it needs frozen-curriculum, budget-ledger, per-arm storage, and crossed
     eval infrastructure.

## Active Next Work

1. Core design/code alignment
   - Replace ambiguous env-profile defaults with an explicit pinned profile or a
     required configuration path; validate header/hash/profile identity at data
     ingress.
   - Expand schema consistency tests to cover nullability, defaults, checks, and
     type affinity, not just column names.
   - Rename durable backend-specific fields such as `verified_by_kimina` before
     the initial migration is treated as stable.
   - Update the design doc in a separate pass for stale G1-G4, §2.8 `/verify`,
     §4 store examples, §10 `lean_client` boundary, §3.6 supported algorithms,
     Part II training scope, and extension status wording.

2. Lifecycle hardening
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
   - Reject duplicate runner-provided `attempt_id`, `search_item_id`, and
     `verify_item_id` values before launching concurrent attempts, with a test
     proving duplicate ids fail before any backend call.

3. Durable replay and eval spine
   - Decide the durable artifact shape before implementing writers: which data
     belongs in SQLite tables vs artifact files, deterministic id strategy,
     content hashes, failure persistence, and migration compatibility.
   - Implement concrete SQLite `ReplayStore` and write finished search artifacts
     into the durable tables as attempts land.
   - Add conversion from `TrainingArtifacts` to durable theorem/proof,
     trajectory, value-label, and failure records, preserving env profile,
     attempt ids, verifier status, and model version.
   - Add a durable deferred-cleanup outbox or attempt-lifecycle table for item
     ids still `deferred` after bounded retries. Track retry count, last
     status/error, next retry time, and whether the item is search-state or
     verifier work.
   - Implement infra-owned eval runners: direct pass@k, self-correct pass@k,
     tree-search solved@budget, artifact manifests, and throughput metrics.
   - Add benchmark/env-profile manifests before benchmark loaders: source,
     split, env profile, compatibility status, contamination policy, and fixed
     held-out assignment must be explicit.

4. Search semantics and policy context
   - Make current local root-to-leaf PUCT/hardest-child selection the v0
     baseline contract in design/API docs, and defer global highest-UCB action
     plus lower-confidence-bound hardest-child semantics to later algorithm
     work.
   - Add a prompt/history contract so tactic history and inline comments can
     reach `PolicyClient.sample_tactics(...)` without stuffing stale history into
     `FactorizedProofState`.
   - Reconcile best-first design text with implementation: either add
     policy-logprob/depth/novelty inputs or document the current
     value/missing-score/goal-count/visit heuristic.

5. Extraction and training-artifact hardening
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

6. Richer proof rendering
   - Current extraction emits a canonical proof candidate and explicit
     `TrainingArtifacts`; `extract_proof_tree(...)` remains a narrow renderer
     used before final `/exec/verify`.
   - Treat the current fail-closed renderer plus final `/exec/verify` as
     acceptable for the first persistent/evaluable tree baseline; do not broaden
     rendering ahead of the replay/eval spine.
   - Decide the source of truth before broadening rendering. Either LeanFoundry
     reconstructs surface focusing from the tree, or the backend returns tactic
     scripts/proof terms and LeanFoundry assembles backend-provided pieces.
     `/exec/verify` stays the acceptance gate either way.
   - Resolve the missing identity contract first: `GoalComponent` currently has
     order/name, not a stable goal identity that can safely reconstruct
     arbitrary focused groups in surface Lean.
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

7. Real policy/value adapters
   - Add generic reference `PolicyClient` / `ValueClient` adapters behind the
     existing protocols only after the policy-context contract is stable.
   - Keep Slime/SGLang/Megatron specifics in the training repo; the local
     `SlimeAdapter` remains a deferred boundary placeholder.
   - Update design examples so `PolicyClient`, `ValueClient`, and
     `run_search_batch(...)` match current public signatures.

8. Bonded value mode and labels
   - Add the bonded `wrap(policy_client) -> value_client` factory when the model
     side is ready.
   - Emit `state_value_labels` only when LeanFoundry owns bonded labels.
   - Keep unbonded value clients label-free.

9. Negation pruning
   - Keep runtime negation search deferred until autoformalized/decomposition
     work starts or Stage 3 traces show enough false-goal budget waste to justify
     it.
   - Preparatory work remains current: fix root/internal `DISPROVED` status and
     value-label semantics, and add trace metrics needed to evaluate R4.
   - When implemented, `try_negation` must be provenance-gated, count synthetic
     negation attempts against `max_tactic_calls`, and emit full-weight
     disproved zero labels.

10. Algorithm deferrals
   - Tactic beam and optimistic/RMaxTS are enum/design-family entries only; keep
     them off the core path until replay/eval proves the direct/tree/best-first
     baseline.
   - Deferred until a complete state-identity fingerprint exists.
   - Do not optimize for graph/MCGS merging before proving the AND/OR tree path.

11. Training-repo and extension handoff
   - Keep hardware/model/Slime/Megatron/SGLang/stage-config work in the training
     repo; LeanFoundry should expose protocols, durable artifacts, and eval
     manifests those workflows consume.
   - Extension A needs router adapter, state portability, distributed cleanup,
     and Postgres/Redis replay work after single-machine replay is solid.
   - Extension B needs formalizer draft/retry, statement verification, semantic
     judge, dedup, promotion, and difficulty-estimation workflows after core
     contamination rules are stable.
   - Extension C / TTT needs node-general HER, adapter reload semantics, and
     per-problem trace persistence before implementation.
   - Extension D needs frozen-curriculum materialization, per-arm stores,
     budget-ledger plumbing, and crossed-eval wrappers.
