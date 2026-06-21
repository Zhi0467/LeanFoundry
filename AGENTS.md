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
- The search engine is the active slice, across TWO wedges behind the
  `SearchEngine` Protocol (a `build_engine(config)` factory dispatches on
  `config.algorithm`): a direct whole-proof wedge (`direct.py`: `sample_proofs` ->
  verify; direct + completion-with-feedback) and the AND/OR tree wedge
  (`and_or.py`). The tree wedge takes a pluggable `SelectionStrategy` (PUCT,
  best-first) — NEVER inline a selection criterion. Clients (policy/value/env) are
  INJECTED into `search()` by a composition root, never built by the engine;
  `value_mode` is a label-emission flag, not a value source. Policy/value are
  async streaming calls (SGLang continuous-batches — no manual batching); searches
  run concurrent + pipelined; value backup is AND/OR-aware (conjunction at AND
  nodes). First algorithms: direct completion, completion-with-feedback, PUCT,
  best-first; graph/MCGS deferred. See the tracker's "Search Engine Loop" section.

## How to work here (maintainer's standing preferences)

- **Read first, reason, don't treat docs as dogma.** Before answering a design
  question, read `docs/design/` and the actual backend at
  `../kimina-lean-server/packages/lean-client/`. Reason from first principles.
- **No redundancy, no mirrors, no "just in case" fallbacks.** Crystal clear over
  defensive; minimal over complete.
- **Explain at the runtime level** — what data flows and what a thing is *for* —
  not field-by-field detail.
- **Persist decisions in the repo, not just chat.** The design doc
  (`docs/design/leanfoundry_system_design_v11.md`) is mutable: edit it
  surgically with a dated `> **v11.x (date):**` note plus the minimal local
  change — never a rewrite. Mirror decisions into the plan/tracker
  (`docs/internal-trackers/todo.md`).
- Descriptive variable names. Separate utilities from entry points; keep public
  and private functions in different files.
- Deps via `uv` + `pyproject.toml`. Tests: `uv run --no-dev --with pytest
  pytest`. Lint: `flake8` (79 cols).
- Git: **commit directly to `main`** — do not create a feature branch unless
  asked. Still **ask before any `git push`**.

## Where things are

- System design: `docs/design/leanfoundry_system_design_v11.md`.
- Algorithm reference: `docs/design/canonical_search.md` (Aristotle + analysis).
- Plan and decision log: `docs/internal-trackers/todo.md`.
- Schemas: `leanfoundry/schemas/`. Interfaces: `env_backend/`, `policy/`,
  `proofsearch/`, `rl_engine/`.
- Next slice: the AND/OR engine loop + concurrent driver + verify + extraction —
  see the todo's "Search Engine Loop: Design + Handoff Slice" section (the full
  handoff spec). Earlier context: the "Next" and "Bugs and Recommendations"
  sections.
