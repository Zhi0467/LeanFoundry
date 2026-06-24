# LeanFoundry

LeanFoundry is a standalone infrastructure project for Lean proof search,
replay, and evaluation.

This checkout is currently a scaffold for the v11 architecture. The copied
LeanDojo-v2 source has been removed; external datasets and runtimes should live
behind LeanFoundry-owned interfaces rather than in core runtime code.

## Using LeanFoundry From a Training Repo

A training repo should depend on LeanFoundry as a package and keep model
serving, data loading, scheduling, and training loops in the training repo:

```toml
[project]
dependencies = [
    "leanfoundry",
]

[tool.uv.sources]
leanfoundry = { git = "https://github.com/Zhi0467/LeanFoundry.git", branch = "main" }
```

The training repo supplies concrete `PolicyClient` and optional `ValueClient`
implementations, chooses a `SearchConfig`, and passes an `EnvBackend`.
LeanFoundry owns proof search, verification, artifact extraction, and stable
schemas. Kimina owns Lean execution through `lean-client`; training code should
not import Lean server internals directly unless it is implementing a new
backend adapter.

Run the Lean execution server as a separate process. For local development, the
published Docker image is the simplest path:

```sh
docker pull zzzzhi/kimina-lean-server:latest
docker run --rm \
  --name kimina-lean-server \
  -p 8000:8000 \
  zzzzhi/kimina-lean-server:latest

curl -fsS http://127.0.0.1:8000/exec/limits
```

Use an immutable image tag from the kimina repo for reproducible jobs. The
Python client below connects to that already-running server URL; it does not
launch the server in-process.

```python
from leanfoundry.env_backend import EnvBackendConfig
from leanfoundry.env_backend.kimina_backend import KiminaEnvBackend
from leanfoundry.proofsearch import (
    SearchAlgorithm,
    SearchConfig,
    run_search_batch,
)
from leanfoundry.schemas import TheoremSpec


async def search_theorems(policy_client, value_client=None):
    env_backend = KiminaEnvBackend(
        EnvBackendConfig(
            api_url="http://127.0.0.1:8000",
            env_profile="default",
        )
    )
    await env_backend.connect()
    try:
        return await run_search_batch(
            [
                TheoremSpec(
                    lean_statement=(
                        "theorem add_zero_nat (n : Nat) : n + 0 = n := by "
                        "sorry"
                    ),
                    header="",
                    env_profile="default",
                    source="train",
                    theorem_name="add_zero_nat",
                )
            ],
            policy_client=policy_client,
            value_client=value_client,
            env_backend=env_backend,
            config=SearchConfig(
                algorithm=SearchAlgorithm.PUCT_TREE,
                max_tactic_calls=100,
            ),
        )
    finally:
        await env_backend.close()
```

## Development

```sh
uv sync --group dev
uv run --no-dev --with pytest pytest
uv run --no-dev --with flake8 flake8 leanfoundry tests
```

The Lean execution backend client is the `lean-client` package from
`https://github.com/Zhi0467/kimina-lean-server.git`, subdirectory
`packages/lean-client`, locked in `uv.lock`. This keeps clean checkouts and CI
independent of any sibling local `kimina-lean-server` checkout. To refresh after
upstream client changes:

```sh
uv lock --upgrade-package lean-client
uv sync --group dev
```

LeanFoundry uses lean-client's `/exec` wire types directly (no local mirror);
only the concrete backend *client* is isolated to the `EnvBackend` adapter
(`kimina_backend.py`).

Agent/contributor guidance lives in `AGENTS.md`.

## Design Docs

- `docs/design/leanfoundry_system_design_v11.md`
- `docs/design/canonical_search.md`
