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
  enforces this). Stable-schema release rules live in
  `docs/design/schema_release_governance.md`.
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
  `puct_exploration_weight` / `best_first_missing_value_score`. Value serving,
  bonded label emission, provenance-gated negation-backed `DISPROVED`, durable
  negation attempts, and nested persistent negation proof search have runnable
  baselines. Deferred: graph/MCGS, benchmark-specific remote
  adapters/deployment wiring, and richer Path-B proof rendering for split
  children that own multiple focused goals. Search attempts now receive
  runner-owned
  `SearchAttemptContext` ids: tree state uses `search_item_id`, final verify
  uses `verify_item_id`, direct verifier attempts use `verify_item_id:k`, and
  checked cleanup/cancel is runner lifecycle work. Training extraction returns a
  `TrainingArtifacts` envelope; whole-proof candidates/A-type rows require
  final `/exec/verify` acceptance, while Path-A policy/proved-value artifacts
  are per-step grounded and can survive Path-B rendering or verification
  failure. Root-runtime-`OPEN` exhaustion emits no policy data and only
  effort-gated censored value labels in bonded mode.
- Training adapter contract (v11.15): tree search training data is lineage-A
  step-level `(proof_state, tactic)` data; direct/self-correct is lineage-B
  whole-proof data. Do NOT render a whole proof from the tree as the data path.
  The in-repo Slime adapter spec is `docs/design/slime_adapter_spec.md`;
  LeanFoundry owns Sample token/loss-mask construction, env-profile validation,
  self-correct trace rows, value-client modes (bonded/unbonded and numeric/NL
  scalar), and negation-backed DISPROVED semantics. Slime
  `append_response_tokens(...)` is used when rows carry rollout log-probs;
  verifier-grounded LeanFoundry rows without SGLang log-probs use the explicit
  `leanfoundry_verified_without_rollout_logprobs` construction path. Tree rows
  use Slime compact fanout nesting (`list[list[list[Sample]]]`) with shared
  per-search `Sample.rollout_id`; the default downstream objective is
  EI/SFT (`loss_type=sft_loss`), not fixed-width GRPO. The tiny real-SGLang
  tree EI smoke proves this local sample contract plus one local optimizer
  step, not full Slime/Megatron trainer acceptance or weight sync.
  Downstream Slime launches should use
  `leanfoundry.slime.add_leanfoundry_arguments` for LeanFoundry-owned args
  instead of duplicating the adapter flag list.
- Extensions A-D are not current `main` implementation. A full pre-split
  snapshot is preserved on `extensions/codex-full`, but those components need
  fresh design review and live e2e before any future mainline claim. Keep the
  two-branch separation: do not merge `extensions/codex-full` wholesale into
  `main`; future extension work must cherry-pick or re-implement reviewed
  pieces onto current `main`.

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
- Do not claim a runtime path is done unless its live e2e has actually run and
  passed in the relevant environment. Hermetic tests, fake transports, skipped
  e2e tests, import-only compat checks, and docs/checklists are not completion
  evidence. If the live Lean/SGLang/Slime services are absent, say the path is
  not e2e-proven and do not mark it complete.
- Git: **commit directly to `main`** — do not create a feature branch unless
  asked. Still **ask before any `git push`**.

## Where things are

- System design: `docs/design/leanfoundry_system_design_v11.md`.
- Algorithm reference: `docs/design/canonical_search.md` (Aristotle + analysis).
- Future-facing plan: `docs/internal-trackers/todo.md`.
- Completed slice log: `docs/internal-trackers/implementation-log.md`.
- Schemas: `leanfoundry/schemas/`. Interfaces: `env_backend/`, `policy/`,
  `proofsearch/`, `slime/` (training extra only).
- Next slice: follow `docs/internal-trackers/todo.md`; shortest runnable
  training path is Phase 2 reference clients -> Phase 3 Slime adapter, while
  value serving/negation are required for the full Aristotle-like loop.
