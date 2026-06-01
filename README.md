# LeanFoundry

LeanFoundry is a standalone infrastructure project for Lean proof search,
replay, and evaluation.

This checkout is currently a minimal package shell while the v9 architecture is
being prototyped. The copied LeanDojo-v2 source has been removed; future
LeanDojo use should live behind a data-source adapter rather than in core
runtime code.

## Development

```sh
uv sync --group dev
uv run pytest
```

The local development backend client is provided by the neighboring
`kimina-lean-server` checkout through the `kimina-client` dev dependency.

## Design Docs

- `docs/leanfoundry_system_design_v9.md`
- `docs/aristotle_algo.md`
