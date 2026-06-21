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
`best_first_missing_value_score`. Deferred pieces remain graph/MCGS, negation
pruning, HER, real policy/value adapters, bonded value labels, and richer proof
rendering for split children that own multiple focused goals.

**Keep AGENTS.md and this file current as you learn** — prefer updating them over
re-deriving context. Keep both concise.

Inherited global rules still apply: descriptive variable names; `uv` +
`pyproject.toml` for deps; separate utilities from entry points and public from
private functions; ask before pushing to GitHub.
