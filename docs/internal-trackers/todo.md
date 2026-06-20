# LeanFoundry Internal Todo

## Completed Scaffold

1. Layout the project and define the first reviewable schema/interface scaffold.
2. Add plain-language field descriptions to core schema/config models.
3. Add initial SQL migration comments explaining the durable tables.

## Env Backend Interface: Resolved Decisions

These supersede the earlier "mirror the /exec schema inside LeanFoundry"
approach. Goal: one schema, no redundant copy to maintain.

1. Deleted `leanfoundry/schemas/exec.py`.
   - The Lean `/exec` wire types (states, steps, verify, limits) are owned by
     the `lean-client` package and imported from `lean_client.exec_models`
     directly. LeanFoundry no longer keeps its own copy.
   - The old copy had already drifted (it was missing `goal_id`/`auto_resume`
     on the step item).

2. `EnvBackend` protocol speaks `lean_client` wire types and exposes `step()`,
   not `step_batch()`.
   - `step()` is the coalesced hot path: the `lean-client` batcher aggregates
     concurrent per-state `step()` calls across theorem searches into one
     `/exec/step_batch` HTTP request. This is the cross-theorem batching that
     R1 in the design is about.
   - `step_batch()` bypassed that coalescer, so exposing it as the primary
     expansion call was wrong.

3. `lean-client` promoted from dev-only to a runtime dependency.
   - Consequence accepted on purpose: the CI promise "tests pass without the
     sibling `kimina-lean-server` checkout" no longer holds; we prefer that
     over maintaining a duplicate wire schema.
   - Coupling boundary: search transitively imports `lean_client.exec_models`
     (the wire schema), but NOT the transport. Only `kimina_backend.py`
     constructs `AsyncLeanExecBackend`.

## FactorizedProofState: Simplified to Tree-Search Node (applied 2026-06-19)

Reasoning (not version-gating): the search is tree search — every reached state
is its own node. Node merging (sharing one node between two separately-reached
states) is an optional optimization, not a correctness requirement. It is sound
only with a state-identity key that captures everything affecting future tactic
behavior, including the parts Lean does not print. Printed-text keys are
incomplete, so merging on them can silently reuse a proof that does not apply.
There is no reliable cheap "merge-eligible" test. So the choice is binary: build
and validate a complete key, or do not merge. Not merging is legitimate and may
be permanent. Until/unless a complete key exists, all merge-identity fields are
simply unnecessary, not "deferred".

Unifying principle: a node stores its goals + the token to resume them. It does
NOT store how it was assembled. Anything used only to BUILD the node is consumed
at expansion time and discarded.

1. Fields with no consumer in tree search:
   - `theorem_header_options_hash` (a state-identity key component; merge only)
   - `tactic_history_hash` (a merge opt-out; see 2)
   - `metavariable_coupling_groups` (transient split input, not state; see 4)
   - `local_context_by_component` (redundant; see 3)

2. `tactic_history_hash` is a merge OPT-OUT, not an identity.
   - It exists to force "never merge this state" for tactics whose effect is
     not captured by the printed goals (e.g. `aesop`/`simp_all`), by poisoning
     the key so it cannot collide. It is not how same-state is detected.
   - It only has meaning once merging exists, which it does not. Drop it now.

3. Redundancy: a goal's hypotheses are stored twice.
   - `GoalComponent.hypotheses` AND
     `FactorizedProofState.local_context_by_component[id].entries`.
   - Keep one (on `GoalComponent`, next to the goal it belongs to).

4. Coupling and goal-naming are both consumed at expansion, not stored.
   - When the backend returns a multi-goal state it also reports which goals are
     metavariable-coupled (as positions, on the wire response). The expansion
     step reads that to decide bundling (coupled goals stay in one node,
     independent goals may split off), then discards it. Every later step gets
     fresh goals + fresh coupling from the backend, so the old coupling is never
     re-read. Lean enforces the live coupling behind the token meanwhile. So
     `metavariable_coupling_groups` should not be on the stored state.
   - A goal is referenced by its position in the state's goal list. A stable
     text id would only help when tracking one goal as the list shifts, or when
     the same goal appears in two places at once — neither happens here (states
     are frozen snapshots; goals are not shared).

5. Applied minimal `FactorizedProofState`:
   - `env_profile`, `goal_components` (each: target + hypotheses + pretty +
     optional Lean `name`/case-label, referenced by position), `pretty_state`,
     `state_token`, `serialized_lean_state` (optional escape hatch, design 2.3).
   - `GoalComponent` dropped `component_id` and `sibling_dependencies`; the
     `LocalContext` wrapper was deleted (hypotheses live on the goal).
   - Reintroduce a deliberately designed state-identity representation only if a
     sound merging engine is actually built.
   - Applied 2026-06-19: `leanfoundry/schemas/proof_state.py`,
     `schemas/__init__.py`, `tests/test_package_import.py`; design doc §3.1 and
     the v11.2 note.

## Immediate Guardrails

1. Schema/database consistency tests
   - Apply every SQL migration to an in-memory SQLite database.
   - Assert the expected tables and columns exist.
   - Assert critical constraints work, starting with:
     `state_value_labels.disproved => label = 0 and weight = 1.0`.
   - Keep an explicit expected-column map in tests until we choose a migration
     generator or ORM.

2. CI for schema/database consistency
   - Run tests and lint on pull requests and pushes.
   - CI must not require the sibling `kimina-lean-server` checkout.
   - Use `uv run --no-dev --with pytest pytest` for tests.
   - Use `uv run --no-dev --with flake8 flake8 leanfoundry tests` for lint.

## Design-Derived Search Budget Contract

The design docs make Lean tactic calls the primary MCTS/search budget. For MCTS
evaluation, the docs explicitly say pass@k is the wrong metric and report
`solved@budget` over tactic-call budgets such as 50, 100, 250, 500, 1000, and
2000. The TTT pseudocode also passes `budget=config.search_budget` to
`mcgs_search`; in this infra scaffold that is represented as
`SearchConfig.max_tactic_calls`.

SearchConfig should therefore contain only design-backed search-level controls
for now:

1. `max_tactic_calls`
   - hard cap on Lean tactic attempts for one theorem search.
   - primary stop condition and the x-axis for solved@budget curves.

2. `tactics_per_expansion`
   - number of policy tactic candidates requested when expanding one selected
     proof state.
   - design examples use `n_tactics=8`.
   - the backend still enforces `/exec/limits.max_tactics_per_step_item`.

3. `try_negation`
   - enables the design's optional synthetic negation action for single-goal
     states.
   - default remains false and should be gated from `TheoremSpec.source`.
   - when enabled, the synthetic action consumes budget like any other tactic
     attempt.

4. `min_censored_negative_effort`
   - design value-label gate: only states with at least 50 tactics tried become
     censored-negative labels.
   - not a search stop condition.

5. `censored_negative_weight`
   - current design guess is 0.25.
   - this is a value-training knob, not a graph traversal budget.

6. `value_mode`
   - bonded/unbonded value-client behavior from `canonical_search.md`.
   - not a budget, but needed by the search engine to know whether LeanFoundry
     owns value-label emission/training responsibilities.

### Explicitly Not in SearchConfig Yet

Do not add these as first-class search config fields until the design docs or
profiling data justify them:

1. Wall-clock cap per theorem
   - the docs mention a 10s direct-sampling budget in Stage 2 and verifier wall
     time in the Extension D compute ledger.
   - they do not define wall-clock as the MCTS search stop condition.
   - backend per-request timeouts already live in `/exec` request/config fields.

2. Max tree nodes
   - useful engineering guardrail, but not currently specified by the design.
   - if memory pressure appears, add it as a measured runtime safety cap.

3. Max depth
   - average proof depth is an evaluation metric.
   - the design does not specify depth as a search stop condition.

4. Max expansions
   - expansion count is derivable from tactic-call budget and
     `tactics_per_expansion`.
   - add only if an algorithm needs it independently.

5. Per-state action cap
   - UCB soft termination is the design mechanism for routing budget away from
     exhausted states.
   - add a hard per-state cap only after traces show repeated waste.

6. Outer decomposition/revision budgets
   - `canonical_search.md` explicitly marks this as ambiguous.
   - this belongs to training-repo rollout orchestration, not the infra
     `SearchConfig`, unless the design is updated.

## Next: Runtime AND/OR Search Tree

v0 is AND/OR **tree** search: one node per reached state, no state merging (see
v11.2 design note). "AND/OR" describes the structure (a state is OR over its
candidate actions; an action is AND over the subgoals it spawns) and is
orthogonal to tree-vs-graph, which is only about whether identical states
reached by different paths are merged. They are not.

Goal: implement the live search tree used by `SearchEngine` at runtime. This is
not the same object as `ProofTree`/`TacticNode`. The runtime tree keeps failed
branches, open branches, visit counts, priors, values, dead/disproved states,
and operational state-token metadata. `ProofTree` is only the solved projection
written to trajectories and HER data.

### Applied First Slice (2026-06-19)

Implemented the private runtime-tree foundation without the live engine:

- `leanfoundry/proofsearch/_tree.py`: mutable OR `StateNode` and AND
  `ActionNode` classes, status propagation, parent/child links, visit/value
  counters, tactic-call counter, and node ids suitable for backend step calls.
  Follow-up review removed unwired per-node tactic counters and aligned state
  ids to `"<search_id>:<counter>"`, so lean-client's default
  `item_id_from_node_id` derives `search_id`.
- `leanfoundry/proofsearch/_budgets.py`: deterministic tactic-call accounting
  helpers. Budget unit is one backend step result, including errored attempts
  and any future synthetic actions. Keep budget mutation through these helpers;
  do not add a second write path on `SearchTree`.
- `leanfoundry/proofsearch/_selection.py`: empirical action priors from
  duplicate policy samples, prior-only PUCT/UCB action selection, and
  value-free hardest-child selection.
- `tests/test_runtime_tree.py`: AND/OR invariants, open-is-not-false behavior,
  budget accounting, empirical prior preservation of full tactic text, and
  deterministic selection.

Still deferred after this slice: `_expansion.py`, `_extract.py`, concrete
`and_or.py` `SearchEngine`, final `/exec/verify`, value labels, negation
pruning, and HER.

### Applied Second Slice (2026-06-20)

Implemented private expansion helpers without the concrete engine:

- `leanfoundry/proofsearch/_expansion.py`: samples one policy batch for one
  frontier state, computes empirical action priors from duplicate samples,
  skips already-tried tactic strings, calls one `EnvBackend.step(...)`, unwraps
  `ExecStepBatchResult.results` for tactic-call accounting, and attaches
  `ActionNode`s plus child `StateNode`s.
- Converts wire `ExecGoalInfo` into `GoalComponent`/`FactorizedProofState`.
  Follow-up review resolved that v0 must NOT split a returned multi-goal state:
  the backend returns one whole-state token and `EnvBackend.step(...)` does not
  expose focused goal stepping, so split child nodes would not resume soundly.
  For now one `open` step result becomes one child state containing all returned
  goals. Revisit metavariable-coupled bundling only with a focused-step protocol.
- Step statuses map to runtime tree or operational signals: `complete` proves
  the action structurally; `open` with goals creates one whole-state child;
  `open` with no goals is treated as structurally proved; `error` marks the
  action dead and counts as a Lean tactic attempt; `invalid_state_token`,
  `overloaded`, and `cancelled` surface on `ExpansionOutcome`/the state
  failure message and do not count against `max_tactic_calls`.
  The engine still must run final `verify_one` before returning
  `SearchStatus.PROVED`.
- `tests/test_expansion.py`: policy/backend single-call behavior, duplicate
  prior counting, already-tried tactic skipping, full tactic text preservation,
  goal conversion, v0 whole-state child construction, error handling,
  operational-status handling, and budget exhaustion.

Still deferred after this slice: `_extract.py`, concrete `and_or.py`
`SearchEngine`, final `/exec/verify`, value labels, negation pruning, HER, and
any protocol change needed for focused expansion of split independent goals.
The engine loop must not ignore `ExpansionOutcome.operational_status`: because
`invalid_state_token`, `overloaded`, and `cancelled` do not consume tactic
budget, blindly re-selecting the same state can livelock. Handle these by
re-deriving the token, retrying with backoff, cancelling, or aborting the
theorem according to the resume model.

### Applied Third Slice (2026-06-20)

Implemented private value-free backpropagation helpers without the concrete
engine:

- `leanfoundry/proofsearch/_backprop.py`: increments visit counts from an
  evaluated `ActionNode` through parent actions/states back to the root.
  Follow-up review made backprop visits-only: status propagation stays owned by
  the `SearchTree` mutation methods (`mark_action_proved`, `mark_action_dead`,
  `add_child_state`, `mark_state_disproved`).
- `backpropagate_actions(...)` handles one expansion batch by backpropagating
  each executed action. This matches the current expansion shape where one
  selected state can execute several tactic candidates in one backend step.
  Deliberate visit semantics: N executed tactics mean N visits to the frontier
  and each ancestor, preserving `state.visit_count == sum(action.visit_count)`.
- Still no value estimates, value-label emission, negation labels, or censored
  negatives. Those remain gated on a value model, bonded mode, and negation
  pruning.
- `tests/test_backprop.py`: direct action backprop, ancestor path accounting,
  and expansion-batch accounting.

Still deferred after this slice: `_extract.py`, concrete `and_or.py`
`SearchEngine`, final `/exec/verify`, value labels, negation pruning, HER,
focused goal stepping, and checkpoint/resume.

### Invariants

1. A `StateNode` is an OR node:
   - it is proved if any outgoing `ActionNode` is proved.
   - it is disproved only when negation pruning proves the logical negation.
   - it stays open when unresolved under the current tactic-call budget.

2. An `ActionNode` is an AND node:
   - it represents one tactic/action from one state.
   - it is proved only if all child `StateNode`s are proved.
   - it is dead if any child is disproved.
   - it has zero children when the tactic closes the goal.

3. Runtime tree state is operational:
   - it stores visits, priors, values, backend state tokens, parent/child links,
     failure messages, and tactic-call counters.
   - it is not the durable replay representation.

4. `ProofTree` extraction is one-way:
   - solved runtime tree slice -> tree-shaped `ProofTree`.
   - HER and SFT consume the extracted tree, not the mutable runtime tree.

### Module Plan

1. `leanfoundry/proofsearch/_tree.py`
   - private runtime tree classes: `SearchTree`, `StateNode`, `ActionNode`.
   - enums for state-node and action-node status.
   - parent/child links for AND/OR propagation.
   - per-node `FactorizedProofState`, `state_token`, depth, and counters.
   - per-action tactic text, prior, value estimate, visit count, and children.
   - tree-level tactic-call counter for `max_tactic_calls`.

2. `leanfoundry/proofsearch/_budgets.py`
   - central budget checks against `SearchConfig.max_tactic_calls`.
   - deterministic tactic-call accounting so solved@budget tests reproduce
     exact stop points.
   - include synthetic negation actions in tactic-call accounting.
   - do not add wall-clock/node/depth hard stops yet.

3. `leanfoundry/proofsearch/_selection.py`
   - UCB/PUCT action selection over OR choices.
   - hardest-child selection by lower-confidence bound for AND children.
   - skip terminal/dead/proved/disproved nodes.
   - explicit fallback when value estimates are missing, per
     `canonical_search.md`.

4. `leanfoundry/proofsearch/_expansion.py`
   - call `PolicyClient.sample_tactics`.
   - one selected state -> one `EnvBackend.step(node_id, state_token, tactics)`
     call (lean_client coalesces across searches; do not batch here).
   - convert wire `GoalInfo` -> `GoalComponent`/`FactorizedProofState`, and make
     the metavariable bundling decision (see B3).
   - convert each step result into one `ActionNode` and its child `StateNode`s.
   - preserve full tactic/action text, including inline comments.
   - increment tactic-call counters from backend results (see R5).

5. `leanfoundry/proofsearch/_backprop.py`
   - update visits, values, proved/disproved status, and action status.
   - propagate proved upward: an OR state is proved if any action succeeds.
   - propagate dead/disproved upward: an AND node dies if any child is disproved.
   - emit value-label candidates for proved, censored-negative, and disproved
     states.

6. `leanfoundry/proofsearch/_extract.py`
   - extract the solved slice of `SearchTree`.
   - render that solved slice into `ProofTree`.
   - support one root per initial sorry goal.
   - keep HER extraction tree-shaped, not flat.

7. `leanfoundry/proofsearch/and_or.py`
   - concrete AND/OR tree-search `SearchEngine` (no state merging), under a new
     `SearchAlgorithm.AND_OR_TREE` value (added with the engine; MCGS deferred).
   - owns the iteration loop, tactic-call budget checks, expansion, backprop,
     final verification, extraction, and `SearchResult`.

### Test Plan

1. Tree invariants
   - OR node is proved when one action is proved.
   - AND node is proved only when all children are proved.
   - AND node is dead when any child is disproved.
   - unresolved states remain open rather than becoming false.

2. Budget behavior
   - search stops at `max_tactic_calls`.
   - synthetic negation attempts count against `max_tactic_calls`.
   - `min_censored_negative_effort` gates value-label emission, not search
     termination.

3. Expansion behavior
   - one selected state produces one `EnvBackend.step` call.
   - tactic candidates are not flattened into separate backend jobs.
   - inline comments survive in tactic/action text.

4. Extraction behavior
   - solved tree slice extracts to tree-shaped `ProofTree`.
   - failed/dead branches are not included in `ProofTree`.
   - branching proofs keep child order and nested structure.

5. Schema/database behavior
   - migrations apply cleanly to SQLite.
   - migration columns match expected durable table contracts.
   - value-label constraints reject invalid disproved positives.

### Review Decisions Before Coding Runtime Tree

1. RESOLVED: keep `max_tactic_calls` (clearer than `search_budget`).
2. RESOLVED: per-call timeouts ride on lean_client's step item (its
   `TimeoutConfig`); defaults live in `EnvBackendConfig`. No LeanFoundry copy.
3. RESOLVED: keep `value_mode` on `SearchConfig`; do not split it into a
   dedicated config.
4. RESOLVED: yes, but as increment 2 (after the core loop proves a theorem).
   Keep the runtime-tree node types serializable from the start (plain data:
   state, tactic text, stats, token, status) so checkpoint is a clean add, not
   a retrofit (P10). Checkpoint at the iteration boundary — the per-theorem loop
   is sequential, so that point is quiescent (no in-flight `step()`), which is
   why streaming `step()` needs no journal. Checkpoint = tree structure +
   per-node `state_token` + stats + budget counter (incremented at backprop, not
   submit, so a re-derived expansion never double-counts).
   - Two layers: the runtime tree (search process) vs the backend state blobs
     (the token is just a handle). v0 resume target = search-process death;
     tokens are still live on the backend within `state_ttl`, so reload + go.
   - Backend death kills all tokens (signalled by `invalid_state_token`):
     re-derive a dead state by replaying its tactic path from the root, or
     restart the theorem. Blob persistence (`serialized_lean_state` / durable
     token store) for backend-death survival is a later multi-node concern.
   - Do NOT use `step_batch_resumable`/the journal on the search hot path; a lost
     expansion is just re-selected next iteration (idempotent at search level).
5. Should any hard tree-growth cap be added only after first traces, or do we
   want a conservative safety cap despite it not being in the design?
6. RESOLVED: focus on tree search; MCGS/graph deferred. Add an `AND_OR_TREE`
   `SearchAlgorithm` value when the engine lands; leave `MCGS`/`AND_OR_MCGS` as
   unimplemented future values. Do not build graph merging now.

### Bugs and Recommendations (plan review 2026-06-19)

Corrections to the plan above:

B1. `_tree.py` must NOT store `state_token` separately on `StateNode` — it is
    already inside the node's `FactorizedProofState`. Read it from there.
B2. `_expansion.py` calls `EnvBackend.step(node_id, state_token, tactics)` (the
    coalesced hot path), not a `StepBatchItem` — that type no longer exists in
    LeanFoundry; lean_client assembles the HTTP batches. (Bullets fixed above.)
B3. `_expansion.py` was missing the two conversions that ARE the state model:
    (a) wire `GoalInfo` -> `GoalComponent`/`FactorizedProofState`; (b) the
    metavariable bundling decision — read each returned goal's coupling
    (positions), put coupled goals in ONE child `StateNode`, split independent
    goals into their own. Coupling is consumed here, never stored.
    Superseded for v0 by the second implementation slice: without a focused
    `EnvBackend.step(..., goal_id=...)` protocol, split child nodes cannot
    resume soundly. v0 keeps one whole-state child per open backend result and
    defers metavariable-aware splitting until focused stepping exists.
B4. `_backprop.py` value-label emission is bonded-mode only. In unbonded mode
    LeanFoundry writes no `state_value_labels`. Gate on `value_mode == "bonded"`.

Scope the FIRST slice small; add the rest as later increments:

R1. No value model first. `search()` takes `value_client: ValueClient | None`;
    build prior-only tree search (PUCT explore term + final verify). So the
    "value missing" path in `_selection.py` is the DEFAULT, not an edge case:
    UCB uses prior + visits; LCB hardest-child needs a value-free heuristic
    (e.g. most-open-subgoals) until a value model exists.
R2. No negation pruning first. `try_negation` stays in config but the engine
    ignores it (design R4 defers it). Removes DISPROVED handling, synthetic
    actions, and disproved labels from the first slice.
R3. No HER first. `_extract.py` emits only the main `ProofTree` (one root per
    sorry). HER subproof extraction + re-verification is a later increment.

Correctness details to pin down before coding:

R4. PUCT prior = empirical frequency of an action among policy samples, not
    log-prob (design 3.2). `sample_tactics` returns raw strings; compute the
    prior from duplicate multiplicity — do NOT dedupe before counting.
R5. Budget unit = one tactic string executed = one `StepResult`. Expanding N
    candidates costs N against `max_tactic_calls`; errored attempts still count
    (they ran in Lean). Define this once in `_budgets.py`.
R6. Lifecycle: `and_or.py` must `cleanup()` backend state at end of search
    (bounded `max_state_store_bytes`). Define a `node_id` scheme
    (e.g. `"<search_id>:<counter>"`) compatible with the batcher's
    `item_id_from_node_id` grouping.
R7. Determinism: thread a sampling seed and a fixed selection tie-break so the
    budget tests reproduce exact stop points.
R8. PROVED requires a final `verify_one(...)` on assembled `rendered_lean` — a
    "complete" stepped state is not a certificate (design 2.5/2.7). Rendering
    needs `GoalComponent.name` (case labels) for branching syntax.

### Process and Resume Model (2026-06-19)

Process model (v0): ONE search process runs all theorem searches concurrently as
async tasks, sharing one `EnvBackend` client whose batcher coalesces their
`step()` calls into `/exec/step_batch` requests. Multi-process fan-out needs a
cross-process dispatcher (design R1 / Extension A) — deferred. Revisit when the
single orchestrator's own CPU (selection/backprop/serialization) saturates or one
event loop can no longer keep the backend/inference busy.

Three resume levels, distinct layers:
1. Durable spine (Data Buffer, P3): finished proofs/trajectories are written to
   SQLite as found, so a crash never loses RESULTS. Essential, cheap — this is
   the actual preemptibility guarantee.
2. Search-tree checkpoint (fine, per-theorem): partial in-flight tree + per-node
   `state_token` + stats + budget counter. Only saves RE-COMPUTE of in-flight
   theorems; an optimization, not a correctness need (re-running an unfinished
   search is deterministic with a seed). Keep the tree serializable from day one.
3. Trainer checkpoint (coarse): weights + optimizer + train step. Separate layer,
   training-repo concern; not infra-search's job.

OPEN: does v0 build level 2, or rely on level 1 + re-running in-flight theorems on
resume? Recommendation: level 1 first; add level 2 only when per-theorem budgets
are large enough that losing in-flight compute hurts.

Crash vs pause is an ORCHESTRATION concern; the infra resume path is the same for
both — re-run unfinished theorems from the spine (optionally skipped by level 2):
- Crash (unexpected exit): supervisor backoff-retry auto-restarts. Restart is fast
  (< `state_ttl`), so the backend is up and tokens are still live → cheap resume.
- Pause that frees resources (backend torn down): all tokens die (= backend
  death); re-run in-flight on resume. Results already safe in the spine.
- Keep-alive ping only helps the narrow "pause search but keep backend warm,
  briefly" case (pins state, bounded by `max_state_store_bytes`). Not worth
  building in v0; revisit if that scenario is real.
The search engine exposes primitives only (checkpoint, resume, graceful drain,
cleanup); the supervisor / training repo owns the retry-vs-hold policy.

## Goal Focus: Verified Backend Verdict + Revised Plan (2026-06-20)

Investigated live against the kimina/Pantograph backend
(`(∃ n : Nat, n = n) ∧ True`). Supersedes the `goal_id/auto_resume` focus idea in
B3 and the second slice's whole-state deferral.

Verdict:
- `auto_resume=True` = Pantograph `Site.prefer` (keeps ALL other in-scope goals —
  drags unrelated siblings); `auto_resume=False` = `Site.focus` (suspends ALL
  siblings incl. coupled). Neither is group focus. The earlier "auto_resume drags
  only coupled siblings" assumption is FALSE.
- Group focus works via Pantograph `GoalState.resume(goals)` = raw `goal.continue`
  with internal `Goal.id`s. Verified: `[0,1]` → exact coupled cluster; `[2]` →
  independent goal; both solved independently. Goal order is stable across
  save/load, so public goal indices are a valid handle.
- PyPantograph bug: `goal_resume_async` sends `goal.name` not `goal.id`
  (`pantograph/server.py:329`, `pantograph/expr.py:57`). Use raw `goal.continue`.

Revised contract (replaces the inference about focused stepping):
1. Backend (kimina-lean-server, one commit — now a SERVER feature, not a client
   pass-through): add `goal_group: list[int]` to `ExecStepBatchItem` (mutually
   exclusive with `goal_id/auto_resume`); the worker validates indices (non-empty,
   unique, in-range), maps them to `Goal.id`, calls raw `goal.continue`, then runs
   tactics with plain `Site()`; thread `goal_group` through `submit_step` /
   `AsyncLeanExecBackend.step`.
2. LeanFoundry: `EnvBackend.step(..., goal_group: tuple[int,...] | None = None)`.
   Standardize on `goal_group` ONLY — never thread `goal_id/auto_resume`
   (a singleton tuple focuses an independent goal; `auto_resume` is a footgun).
   `StateNode.focus = tuple[int,...] | None` on the private runtime node
   (root focus None).
3. Expansion: group returned goals by transitive closure of `sibling_dep`; one
   child per group, each storing the shared result token + its focus index tuple.
   The conservative "independent-only split, clusters whole-state" fallback is NO
   LONGER needed — full split is sound. `focus` indices and `goal_components` must
   come from the SAME returned goal list.

Execution order: (1) backend `goal_group` feature, (2) LeanFoundry interface
reshape, (3) focused expansion round respecting caps (budget +
`max_tactics_per_step_item`, limits cached at connect) + `goal_group` + AND/OR
multi-child attach. Deferred (noted, not built): real `PolicyClient` impl — under
default Slime inference is vendored by Slime's rollout layer, not raw SGLang, so
the adapter is a Slime concern behind the Protocol; and the concurrency driver
(semaphore + `max_items_per_step_batch` / `max_in_flight_exec_requests`) that
composes single rounds.

Applied 2026-06-20:
1. kimina-lean-server commit `27dac09`: `ExecStepBatchItem.goal_group`, worker
   `goal.continue` group resume (raw, with `Goal.id`), threaded through
   `submit_step`/`step`/`step_node`. Verified live: `goal_group=[0,1]` resumes
   exactly the coupled cluster and excludes the independent goal.
2. LeanFoundry: `EnvBackend.step(..., goal_group)` + kimina forwarder (tuple ->
   list); `StateNode.focus: tuple[int, ...] | None` + `add_child_state(focus=)`.
3. `_expansion.py`: restored union-find split; `proof_states_from_goals` returns
   `ChildState(state, focus)` per coupling group. Optimization: a single group
   is the whole state and steps `focus=None` (no `goal.continue`); only an
   actual split (multiple groups) sets a focus. `expand_state` passes
   `goal_group=state_node.focus` and caps tactics by an optional cached
   `max_tactics_per_step_item`. Still deferred: PolicyClient impl + concurrency
   driver.

## Search Engine Loop: Design + Handoff Slice (2026-06-20)

The next slice is `and_or.py` (the concrete AND/OR tree-search `SearchEngine`)
plus a concurrent driver, value backup, final verification, and `_extract.py`.
This captures the design settled in discussion; build it pipeline-ready from the
start.

### Per-iteration loop (one search tree)

Four phases, run per selected node until budget exhausts or the root resolves,
then verify and extract:
1. select — `select_frontier_state(root)` (prior PUCT + value-free hardest child).
2. expand — `expand_state(...)`: `policy_client.sample_tactics` on the PARENT, one
   `EnvBackend.step(..., goal_group=node.focus)`, attach actions + split children.
   Status (proved/dead/disproved) propagates automatically inside the tree
   mutations — the loop does NOT call a separate status-backup site.
3. evaluate (gated) — `value_client.estimate` on the NEW CHILD states; write each
   child's `value_estimate`. Skipped when there is no value source (value-free).
4. backprop — `backpropagate_actions` (visits) and, when values exist, the value
   backup folded into the SAME backward pass.

### Clients are injected, never constructed by the engine

`search(theorem, *, policy_client, value_client, env_backend, config)` receives
every client. The engine never constructs or connects one. The COMPOSITION ROOT
(a top-level runner / the training-repo rollout — the ultimate orchestration
level, deferred) builds + connects + injects + closes them; this is what keeps
the engine model/training-agnostic. Where each client is CALLED:
- policy: in expansion, on the PARENT (before the step).
- value: the evaluate step, on the CHILDREN (after the step, before backprop).
- backprop only READS `value_estimate`; it never calls a model.

### value_mode is a label-emission flag, not a client-construction directive

The value SOURCE is ALWAYS the injected `value_client`:
- value-free: `value_client=None` → skip evaluate → prior-only PUCT
  (`value_estimate` None → UCB exploit 0).
- unbonded: external `value_client` supplied by the training repo.
- bonded: a policy-backed `value_client` the root builds via a LeanFoundry factory
  `wrap(policy_client) -> value_client` (same checkpoint + value task token).
`value_mode` (in `SearchConfig`) controls ONLY whether LeanFoundry emits
`state_value_labels` (bonded → yes: proved=1 / censored-negative low-weight /
disproved full-weight; unbonded → no). The engine reads `value_mode` for label
emission and `value_client` for the scalar — orthogonal, both set consistently by
the root. The engine calls `value_client.estimate` uniformly and never knows a
bonded source is policy-backed.

### Throughput: async streaming, pipelined (NOT deferred)

Policy and value are async streaming calls to two clients; SGLang (Slime's
default inference) continuous-batches server-side, so the engine NEVER manually
batches — it fires concurrent single-item awaits and lets the server pack them.
Many theorem searches run as concurrent async tasks under an in-flight cap (the
driver).

Pipelining is built in from the start: each search is a coroutine doing
`expand -> await value -> backprop`; while one coroutine awaits its value call the
event loop runs others' expansions, so value computation overlaps expansion across
searches. No global "collect the whole frontier, then evaluate" barrier. The
simple form (await value before that node's backprop) already gives the overlap
via concurrency — do NOT build the harder two-phase "visit-backprop now,
value-backup when it lands late" variant; it is unnecessary.

### Value backup must be AND/OR-aware (footgun)

When the value backup lands, an AND action's value is a CONJUNCTION of its
children (product/min — you need ALL subgoals) and an OR state's value is a
DISJUNCTION (max/noisy-or over actions). This is NOT the AlphaZero running mean,
which is wrong at AND nodes (it would rate a branching tactic by the average of
its subgoals instead of the product). The status propagation already in
`_tree.py` is the {0, 1, unknown} shadow of exactly this combination rule.

### Slice scope

Build now: `and_or.py` loop (select / expand / evaluate-gated / backprop); the
concurrent driver (asyncio tasks + in-flight cap, limits cached at connect); the
gated async evaluate site + AND/OR value backup in `_backprop.py`;
operational-status handling (act on `ExpansionOutcome.operational_status` —
re-derive the token or abort; cannot rely on budget, since operational failures
cost 0 → livelock otherwise); final `verify_one` on the assembled proof (tree
PROVED is structural only); `_extract.py` (solved slice -> `ProofTree`). Test with
FAKE policy + value clients so the pipeline and value backup are exercised; the
value-free path (`value_client=None`) must also pass.

This revises R1 ("prior-only first"): the evaluate site + value-backup WIRING are
now in-slice so the pipeline is real and fake-tested; only the value-MODEL impl
(and the bonded factory) stay deferred. Value-free remains the gated default.

Deferred (stub/inject later): real SGLang/Slime PolicyClient/ValueClient impls;
the bonded `wrap(policy) -> value` factory; the runner / composition root; value
labels beyond the proved case; negation pruning; HER.
