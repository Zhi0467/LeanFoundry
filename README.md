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
checkout via the `lean-client` dev dependency. Runtime code imports only
LeanFoundry's `EnvBackend` protocol; the concrete `lean-client` import is
isolated to the backend adapter.

## Design Docs

- `docs/design/leanfoundry_system_design_v11.md`
- `docs/design/canonical_search.md`
