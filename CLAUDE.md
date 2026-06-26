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
exhaustion emits no policy data. Deferred pieces remain graph/MCGS, negation
pruning, HER, real policy/value adapters, bonded value-label plumbing, and
richer proof rendering for split children that own multiple focused goals.

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
