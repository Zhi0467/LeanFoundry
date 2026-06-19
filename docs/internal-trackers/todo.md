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

1. Should `max_tactic_calls` be renamed to `search_budget` to match the design
   pseudocode, or is the more explicit name clearer?
2. RESOLVED: per-call timeouts ride on lean_client's step item (its
   `TimeoutConfig`); defaults live in `EnvBackendConfig`. No LeanFoundry copy.
3. Should value-mode handling be split into a dedicated config before any
   concrete `SearchEngine` implementation?
4. Should runtime tree checkpoint/resume be v0 or explicitly deferred?
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
