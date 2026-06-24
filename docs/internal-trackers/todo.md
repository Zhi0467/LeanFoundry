# LeanFoundry Internal Todo

This file is future-facing: active implementation plans, unresolved design
questions, and remaining work. It has four parts: settled **Current Contracts**,
the **SearchConfig** reference, the **Current Path-A Baseline**, and the
**Roadmap** of everything after it.

Historical implementation notes live in
[`implementation-log.md`](implementation-log.md). Concrete design-doc/code
mismatches are tracked in [`issues.md`](issues.md).

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
   - Whole-proof artifacts still require final `verify_one` / `/exec/verify`;
     per-node training data does not (see Contract 7).

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
   - Per-node policy/value training data is gated on per-step backend
     acceptance, not on whole-proof `/exec/verify`. Every tactic edge in the
     tree was executed by Lean during search (a real `ExecStepResult`), and
     coupling groups are metavariable-closed, so the per-node `(state, tactic)`
     and `(state, outcome)` tuples are verifier-grounded per step. The minimum
     soundness requirement is that a `complete` step is a genuine closure
     (sorry/admit-free). Whole-proof `/exec/verify` is demoted to an optional
     artifact gate plus a sampled soundness audit; it is not the data gate.
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

## SearchConfig

Tree search and direct whole-proof search use different budget units.

1. `max_tactic_calls` — hard cap on Lean tactic attempts for one tree-search
   theorem. Primary stop condition and solved@budget x-axis.
2. `tactics_per_expansion` — policy tactic candidates per selected state. Backend
   limits still cap the concrete step item width.
3. `max_direct_candidates` — hard cap on whole-proof candidates for `DIRECT` /
   `SELF_CORRECT`. A pass@k-style budget, not a tactic-call budget.
4. `direct_candidates_per_round` — whole-proof candidates per self-correction
   round; still capped by `max_direct_candidates`.
5. `puct_exploration_weight` — PUCT exploration multiplier for high-prior,
   under-visited actions.
6. `best_first_missing_value_score` — score `BEST_FIRST` assigns to unvalued open
   leaves. Default `0.0` preserves the value-free fallback.
7. `try_negation` — optional synthetic negation search for single-goal states.
   Default false.
8. `min_censored_negative_effort` — value-label emission gate, not a stop
   condition.
9. `censored_negative_weight` — training weight for searched-but-unproved states.
10. `value_mode` — bonded/unbonded label-emission behavior.

Not first-class config fields until design docs, traces, or profiling justify
them: wall-clock cap per theorem, max tree nodes, max depth, max expansions,
per-state action cap, outer decomposition/revision budgets. Backend per-request
timeouts belong to the `/exec` request/config layer, not tree-search semantics.

## Current Path-A Baseline

The training baseline is per-node extraction, decoupled from whole-proof
rendering (AlphaZero-style per-state training: observation = Lean proof state,
target = the tactic, value = verifier-grounded outcome). Whole proofs are a
deliverable (Path B), not a data gate.

Records emitted per completed attempt (proved or not):
- PolicyExample positives from proved subtrees. Store BOTH formulations on one
  record: `state` (Markovian observation) and `proof_prefix` (the root->state
  tactic path = history-conditional context, walked from `parent_action`). The
  target stays the single proved `tactic` string. Visit counts and failed
  siblings remain in the tree for future RL/weighting, but are not the target.
- ValueLabel per explored state: proved=1, disproved=full-weight-0,
  explored-unproved=censored-negative. Effort is node-local.

Minimum rendering: none of the branching kind. State text is the backend's
per-goal pretty; `proof_prefix` is a concatenation of tactics along a single
root->node path (linear, always succeeds). No bullets, focus, or whole-tree
collapse is ever needed for training data.

Minimum checking: per-step backend acceptance is the grounding (done during
search). The one hard requirement is sorry/admit-free `complete` steps. The
`/exec` step result exposes no sorry/axiom signal and a sorry-closed goal
reports `complete`, so reject `sorry`/`admit` (as Lean tokens, via the existing
lexer) at expansion attach-time by marking the action DEAD. The tree then can
never be proved through sorry, so extraction is sound by construction and search
never rewards sorry (reward-hack guard). No backend change. Axiom policy beyond
sorry (e.g. `native_decide`'s `ofReduceBool`) is out of scope; a `native_decide`
proof is real, and `/exec/verify`'s `allowed_axioms` covers it for Path B.

Storage (the durable buffer): concrete SQLite `ReplayStore` plus a writer that
turns `TrainingArtifacts` into durable rows (policy examples, value labels,
verified A-type proof rows, and one trajectory record) as attempts land.
Deterministic content-hash ids make writes idempotent; rows keep provenance through
`attempt_id`-derived trajectory ids, `theorem_id`, and `model_version`. This
durable store is a side archive for eval/HER/offline; it is NOT the online RL
conduit (Slime owns that, below).

Decisions:
- Policy target is the single proved `tactic` string (SFT / expert-iteration). A
  fixed-head visit-count distribution is an AlphaZero artifact for an enumerable
  action space; it does not map to an unbounded LLM tactic generator.
- Core extraction is algorithm-neutral. Whether the per-node data is consumed as
  EI positives or grouped for GRPO is the training side's choice; LeanFoundry
  does not bake grouping into core artifacts.

Slime adapter plan (read from THUDM/slime source; added as the CI-excluded
`training` optional extra; see `rl_engine/`):
- Integration is PULL, not push. Slime loads a function via
  `--rollout-function-path` and calls
  `generate_rollout(args, rollout_id, data_buffer, evaluation) -> list[list[Sample]]`
  (groups of `n_samples_per_prompt`). The loop is online on-policy batched: per
  `rollout_id`, generate fresh samples with current weights, train (GRPO/PPO via
  Megatron), sync weights to SGLang. So the existing
  `RLEngineBase.submit_samples(TrainingSample)` push contract is the wrong shape,
  and the old `TrainingSample` push contract does not fit Slime's per-rollout
  pull API; reshape the adapter around `generate_rollout`.
- Boundary: core stays algorithm-neutral and writes the durable `ReplayStore`.
  The Slime adapter (`generate_rollout`, imports slime) decides grouping and
  builds `Sample`s. Our search is the rollout; one search execution yields many
  samples sharing a `rollout_id`.
- `Sample` supports both formulations: Markovian -> one `Sample` per node
  (`prompt=state`, `response=tactic`, `reward=outcome`), siblings sharing
  `rollout_id`; history-conditional -> one trajectory `Sample` with the prefix
  in the prompt and `loss_mask`/`append_response_tokens(trainable=...)` marking
  model (tactic) vs environment (injected state) spans.
- Adapter steps: build a `PolicyClient` to Slime's SGLang endpoint from `args`;
  pull theorems; `run_search_batch`; algorithm-neutral extraction; convert to
  `Sample` groups; side-write the same artifacts to the durable `ReplayStore`;
  return `list[list[Sample]]`. Path-A core/store is landed; the adapter remains
  deferred until an explicit Slime commit pin and compatibility tests are chosen
  (#20).

## Roadmap (after Path-A)

Sequenced roughly in build order. Items the Path-A baseline already covers are
not repeated here.

1. Core alignment (verifiable, clean durable schema)
   - Enforce env profiles: replace ambiguous defaults with a pinned profile or a
     required config path; validate header/hash/profile identity at data ingress.

2. Durable spine + eval (beyond the Path-A store)
   - Decide durable artifact shape: tables vs files, deterministic ids, content
     hashes, failure persistence, migration compatibility.
   - Eval runners: direct pass@k, self-correct pass@k, tree solved@budget,
     throughput. Split direct serving (stop at first proof) from pass@k eval
     (all-attempt verification).
   - Benchmark/env-profile manifests before loaders: source, split, env profile,
     compatibility status, contamination policy, fixed held-out assignment.
   - Durable deferred-cleanup outbox / attempt-lifecycle table for ids still
     `deferred` after bounded retries (retry count, last status/error, next
     retry, search-state vs verifier work).

3. Lifecycle hardening (remaining)
   - Give cancel failures during unwind an observable sink. Cancellation is
     currently best-effort and intentionally does not mask `CancelledError`, but
     failures are swallowed without a runner event.

4. Search semantics + policy context
   - Policy history/comment contract (#12): let tactic history + inline comments
     reach `PolicyClient.sample_tactics(...)` without stuffing
     `FactorizedProofState`. This is the inference-time side of the Path-A
     `proof_prefix` (history-conditional formulation).

5. Extraction hardening (after the Path-A baseline)
   - Multiple-proved-action extraction: emit each independently verified proved
     action as its own candidate, or keep canonical-first and record skipped
     alternatives as a non-training diagnostic.
   - Node-general HER: iterate proved subtree roots, build subtree candidates,
     reverify under the same `env_profile`, emit her_candidate/verified metrics.
   - Split failure kinds (`unsupported` vs `rendering` vs `verification`) and
     preserve base extraction diagnostics on all failure envelopes.

6. Path-B richer rendering (deferred deliverable, never a data gate)
   - Whole-proof emission is a product deliverable. The robust route is
     backend-sourced: a future `/exec` proof-term/script capability the backend
     assembles from the closed proof. Do NOT build client-side whole-tree ->
     surface reconstruction; surface focusing (non-contiguous / jointly-coupled
     goal groups) has no faithful bullet encoding to re-derive, and the backend
     owns the only kernel-checked proof object.
   - If ever done client-side instead: resolve a stable goal identity first
     (`GoalComponent` has order/name, not identity); render by identity
     (`case <tag> =>`, `on_goal`/`pick_goal`/`rotate`, positional `·` only for
     tagless single splits); render coupled groups as one contiguous block; add
     real Lean fixtures (linear, swap-sensitive multi-state, named-tag
     cases/induction, tagless positional, nested-`by`, contiguous and
     non-contiguous coupled), a sorry-placeholder cardinality invariant, and a
     parent-`state_token` replay oracle. The current narrow `extract_proof_tree`
     stays only for direct/easy cases and the optional sampled audit.

7. Adapters, bonded value, negation
   - Reference `PolicyClient` / `ValueClient` adapters once the policy-context
     contract is stable; keep Slime/SGLang/Megatron in the training repo (the
     `generate_rollout` Slime adapter is sketched in the Path-A section).
   - Bonded value: `wrap(policy_client) -> value_client`; emit
     `state_value_labels` only when LeanFoundry owns bonded labels; keep unbonded
     value clients label-free.
   - Negation: deferred; remaining prep = trace metrics. When built,
     `try_negation` is provenance-gated, counts against `max_tactic_calls`, and
     emits full-weight disproved zero labels through the landed DISPROVED
     artifact path.

8. Deferred algorithms + extensions
   - Tactic beam, optimistic/RMaxTS, graph/MCGS: off the core path until
     replay/eval proves the direct/tree/best-first baseline; graph/MCGS also
     needs a complete state-identity fingerprint.
   - Extensions are gated work, not hidden core requirements: router / state
     portability / distributed replay (A); formalizer / judge / dedup /
     promotion (B); node-general HER + adapter reload + per-problem traces (C);
     frozen curriculum + per-arm stores + budget ledger + crossed eval (D).
