# CLAUDE.md

Agent guidance for this repo lives in **[AGENTS.md](AGENTS.md)** — read it first.
It covers what LeanFoundry is, the current architecture decisions (v0 is AND/OR
**tree** search, not graph/MCGS; lean_client owns the `/exec` schema), and the
maintainer's working preferences.

The first concrete search-engine loop slice is implemented — two wedges (direct
whole-proof `direct.py`; AND/OR tree `and_or.py` with a pluggable
`SelectionStrategy`) behind one `build_engine(config)` factory.
`docs/internal-trackers/implementation-log.md` records what landed:
direct/self-correct, PUCT and best-first tree pegs, fake-tested value evaluation
and AND/OR backup, extraction plus final verify, and the concurrent driver.
`docs/internal-trackers/todo.md` is future-facing. Direct whole-proof search uses
`max_direct_candidates` / `direct_candidates_per_round`; tree search uses
`max_tactic_calls` plus selector knobs `puct_exploration_weight` /
`best_first_missing_value_score`. `SearchAttemptContext` is runner-owned:
tree search state uses `search_item_id`, final verify uses `verify_item_id`,
direct verifier candidates use `verify_item_id:k`, and checked cleanup/cancel
belongs to the runner lifecycle. Training extraction emits a `TrainingArtifacts`
envelope; whole-proof candidates/A-type rows require final `/exec/verify`
acceptance, while Path-A policy/proved-value artifacts are per-step grounded and
can survive Path-B rendering or verification failure. Unproved root-open
exhaustion emits no policy data. Value serving, bonded value-label emission,
provenance-gated negation-backed `DISPROVED`, durable negation attempts, and
nested persistent negation proof search have runnable baselines. Deferred
pieces remain graph/MCGS, benchmark-specific remote adapters/deployment wiring,
and richer Path-B proof rendering for split children that own multiple focused
goals.

Training adapter correction: tree search emits lineage-A step rows
`(proof_state, tactic)`; direct/self-correct emits lineage-B whole-proof rows.
Do not render a whole proof from the tree as the training-data path. The
authoritative adapter handoff is `docs/design/slime_adapter_spec.md`: LeanFoundry
owns Slime Sample token/loss-mask construction, env-profile validation,
self-correct trace rows, value-client modes, and negation-backed DISPROVED
semantics. Use Slime `append_response_tokens(...)` when rows carry rollout
log-probs; verifier-grounded LeanFoundry rows without SGLang log-probs use the
explicit `leanfoundry_verified_without_rollout_logprobs` construction path. The
tiny real-SGLang tree EI smoke proves this local sample contract plus one local
optimizer step, not full Slime/Megatron trainer acceptance or weight sync.
Downstream Slime launches should pass
`leanfoundry.slime.add_leanfoundry_arguments` to Slime's parser hook instead of
duplicating LeanFoundry-owned args.

Extensions A-D are not current `main` implementation. A full pre-split snapshot
is preserved on `extensions/codex-full`, but those components need fresh design
review and live e2e before any future mainline claim. Keep the two-branch
separation: do not merge `extensions/codex-full` wholesale into `main`; future
extension work must cherry-pick or re-implement reviewed pieces onto current
`main`.

**Keep AGENTS.md and this file current as you learn** — prefer updating them over
re-deriving context. Keep both concise.

Inherited global rules still apply: descriptive variable names; `uv` +
`pyproject.toml` for deps; separate utilities from entry points and public from
private functions; ask before pushing to GitHub.
The `lean-client` source of truth is the GitHub source pinned in `uv.lock`;
local sibling checkouts are only convenience copies.

Operational rules and conversation-derived working preferences belong in
`AGENTS.md` and this file, not in internal tracker docs. When a discussion
changes how agents should work in this repo, update these files. Keep `todo.md`
future-facing; put completed slice notes in
`docs/internal-trackers/implementation-log.md`; validate changes with targeted
tests, full tests, lint, and `git diff --check`.

Do not claim a runtime path is done unless its live e2e has actually run and
passed in the relevant environment. Hermetic/fake tests, skipped e2e tests,
compat imports, and docs checklists are not completion evidence.
