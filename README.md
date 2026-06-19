# LeanFoundry

LeanFoundry is a standalone infrastructure project for Lean proof search,
replay, and evaluation.

This checkout is currently a scaffold for the v11 architecture. The copied
LeanDojo-v2 source has been removed; external datasets and runtimes should live
behind LeanFoundry-owned interfaces rather than in core runtime code.

## Development

```sh
uv sync --group dev
uv run pytest
```

The Lean execution backend client comes from a sibling `kimina-lean-server`
checkout via the `lean-client` dependency. LeanFoundry uses lean-client's
`/exec` wire types directly (no local mirror); only the concrete backend
*client* is isolated to the `EnvBackend` adapter (`kimina_backend.py`).

Agent/contributor guidance lives in `AGENTS.md`.

## Design Docs

- `docs/design/leanfoundry_system_design_v11.md`
- `docs/design/canonical_search.md`
