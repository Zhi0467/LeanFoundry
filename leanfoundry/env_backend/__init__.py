"""Lean execution backend abstractions."""

from leanfoundry.env_backend.base import EnvBackend, EnvBackendConfig
from leanfoundry.env_backend.kimina_backend import KiminaEnvBackend


def make_env_backend(config: EnvBackendConfig) -> EnvBackend:
    """Build the default Lean execution backend for one config."""

    return KiminaEnvBackend(config)


__all__ = [
    "EnvBackend",
    "EnvBackendConfig",
    "make_env_backend",
]
