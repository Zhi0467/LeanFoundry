# AGENTS.md

Guidance for agents working in LeanFoundry. **Keep this file and `CLAUDE.md`
current as the repo and its decisions evolve** — prefer updating them over
re-deriving context next time. Keep both concise.

## What this is

LeanFoundry is a distributed Lean proof-search runtime — stateless tactic
execution, verification, search orchestration, trajectory capture, and
evaluation — for training theorem-proving agents. It is **infrastructure**:
model-, training-, and algorithm-agnostic. The training repo is a separate
consumer that plugs in via stable interfaces.

## Current state (read before designing anything)

- v0 search is AND/OR **tree** search — NOT graph search / MCGS. States reached
  by different paths are **not merged** (sound merging needs a complete
  state-identity fingerprint, which is hard and deferred, maybe permanently).
  See the design doc's v11.2 note and §3.1.
- The Lean `/exec` wire schema is owned by the `lean-client` package.
  LeanFoundry imports `lean_client.exec_models` directly — there is **no
  mirror**. Search uses `EnvBackend.step()` (the coalesced hot path); only
  `leanfoundry/env_backend/kimina_backend.py` constructs the lean_client client.
- Durable spine = SQLite (`leanfoundry/schemas/migrations/`). The Python
  Pydantic models are the **source of truth**; the SQL must match them (a test
  enforces this).
- Schemas are strict and minimal: `extra="forbid"`, `frozen=True`. Store only
  what is read, not how it was produced.
- Expansion splits goals by metavariable coupling: independent subgoals become
  separate AND children resumed via the backend's `goal_group` focus (verified
  live; `auto_resume` is NOT group focus); coupled goals stay bundled.
- The first concrete search-engine loop slice is implemented across TWO wedges
  behind the `SearchEngine` Protocol and `build_engine(config)`: direct
  whole-proof search (`direct.py`: `sample_proofs` -> verify; direct +
  completion-with-feedback) and AND/OR tree search (`and_or.py`). The tree wedge
  takes a pluggable `SelectionStrategy` (PUCT, best-first) — NEVER inline a
  selection criterion. Clients (policy/value/env) are INJECTED into `search()` by
  a composition root, never built by the engine; `value_mode` is a label-emission
  flag, not a value source. Value backup uses product over AND children and max
  over OR actions; final `/exec/verify` is still required. Direct whole-proof
  search uses `max_direct_candidates` / `direct_candidates_per_round`; tree
  search uses `max_tactic_calls` plus selector knobs
  `puct_exploration_weight` / `best_first_missing_value_score`. Deferred:
  graph/MCGS, negation pruning, HER, real model adapters, bonded value
  factory/labels, and richer proof rendering for split children that own
  multiple focused goals. Search attempts now receive runner-owned
  `SearchAttemptContext` ids: tree state uses `search_item_id`, final verify
  uses `verify_item_id`, direct verifier attempts use `verify_item_id:k`, and
  checked cleanup/cancel is runner lifecycle work. Training extraction returns a
  `TrainingArtifacts` envelope; proof/policy/proved-value artifacts require
  final `/exec/verify` acceptance, while root-runtime-`OPEN` exhaustion emits no
  policy data and only effort-gated censored value labels in bonded mode.

## How to work here (maintainer's standing preferences)

- **Read first, reason, don't treat docs as dogma.** Before answering a design
  question, read `docs/design/` and the actual `lean-client` package from the
  GitHub source pinned in `uv.lock` (a local sibling checkout is convenience,
  not truth). Reason from first principles.
- **No redundancy, no mirrors, no "just in case" fallbacks.** Crystal clear over
  defensive; minimal over complete.
- **Explain at the runtime level** — what data flows and what a thing is *for* —
  not field-by-field detail.
- **Persist decisions in the repo, not just chat.** The design doc
  (`docs/design/leanfoundry_system_design_v11.md`) is mutable: edit it
  surgically with a dated `> **v11.x (date):**` note plus the minimal local
  change — never a rewrite. Mirror future work into
  `docs/internal-trackers/todo.md` and completed slice notes into
  `docs/internal-trackers/implementation-log.md`.
- Descriptive variable names. Separate utilities from entry points; keep public
  and private functions in different files.
- Deps via `uv` + `pyproject.toml`. Tests: `uv run --no-dev --with pytest
  pytest`. Lint: `flake8` (79 cols).
- Operational rules and conversation-derived working preferences live here and
  in `CLAUDE.md`, not in internal tracker docs. When a discussion changes how
  agents should work in this repo, update these files. For each new slice: edit
  `todo.md` before implementation when planning changes are needed; keep
  implementation notes in `implementation-log.md`; run targeted tests, full
  tests, lint, and `git diff --check`; leave `todo.md` focused on unresolved or
  future work.
- Git: **commit directly to `main`** — do not create a feature branch unless
  asked. Still **ask before any `git push`**.

## Where things are

- System design: `docs/design/leanfoundry_system_design_v11.md`.
- Algorithm reference: `docs/design/canonical_search.md` (Aristotle + analysis).
- Future-facing plan: `docs/internal-trackers/todo.md`.
- Completed slice log: `docs/internal-trackers/implementation-log.md`.
- Schemas: `leanfoundry/schemas/`. Interfaces: `env_backend/`, `policy/`,
  `proofsearch/`, `rl_engine/`.
- Next slice: richer proof rendering or real policy/value adapters, depending
  on the tracker.
