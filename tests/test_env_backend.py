from __future__ import annotations

import asyncio

from leanfoundry.env_backend import EnvBackendConfig
from leanfoundry.env_backend.kimina_backend import KiminaEnvBackend


def test_kimina_backend_forwards_overload_retry_config(monkeypatch) -> None:
    connect_kwargs = {}

    class ConnectedBackend:
        async def aclose(self) -> None:
            pass

    async def fake_connect(api_url: str, **kwargs):
        connect_kwargs["api_url"] = api_url
        connect_kwargs.update(kwargs)
        return ConnectedBackend()

    monkeypatch.setattr(
        "leanfoundry.env_backend.kimina_backend.AsyncLeanExecBackend.connect",
        fake_connect,
    )

    backend = KiminaEnvBackend(
        EnvBackendConfig(
            api_url="http://lean",
            env_profile="mathlib",
            max_overloaded_retries=4,
            overload_backoff_seconds=0.25,
        )
    )

    asyncio.run(backend.connect())

    assert connect_kwargs["api_url"] == "http://lean"
    assert connect_kwargs["env_profile"] == "mathlib"
    assert connect_kwargs["max_overloaded_retries"] == 4
    assert connect_kwargs["overload_backoff_seconds"] == 0.25
