# CLAUDE.md

Agent guidance for this repo lives in **[AGENTS.md](AGENTS.md)** — read it first.
It covers what LeanFoundry is, the current architecture decisions (v0 is AND/OR
**tree** search, not graph/MCGS; lean_client owns the `/exec` schema), and the
maintainer's working preferences.

**Keep AGENTS.md and this file current as you learn** — prefer updating them over
re-deriving context. Keep both concise.

Inherited global rules still apply: descriptive variable names; `uv` +
`pyproject.toml` for deps; separate utilities from entry points and public from
private functions; ask before pushing to GitHub.
