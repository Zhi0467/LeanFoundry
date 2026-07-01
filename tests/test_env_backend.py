from __future__ import annotations

import asyncio

from lean_client.exec_models import ExecVerifyItem

from leanfoundry.env_backend import EnvBackendConfig, make_env_backend
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


def test_make_env_backend_returns_default_kimina_backend() -> None:
    config = EnvBackendConfig(
        api_url="http://lean",
        env_profile="mathlib",
    )

    backend = make_env_backend(config)

    assert isinstance(backend, KiminaEnvBackend)
    assert backend.config is config


def test_kimina_backend_forwards_exec_facade_methods() -> None:
    async def run() -> None:
        config = EnvBackendConfig(
            api_url="http://lean",
            env_profile="mathlib",
        )
        backend = KiminaEnvBackend(config)
        connected = RecordingExecBackend()
        backend._backend = connected

        verify_items = [
            ExecVerifyItem(
                item_id="verify-batch",
                code="theorem t : True := by trivial",
                theorem_name="t",
            )
        ]

        assert await backend.limits() == "limits"
        assert await backend.create_states(
            "create-1",
            "theorem t : True := by sorry",
            env_profile="mathlib",
        ) == "create"
        assert await backend.step(
            "node-1",
            "state-token",
            ["intro h"],
            goal_group=(0, 2),
            timeout_ms=7000,
        ) == "step"
        assert await backend.verify_one(
            "verify-1",
            "theorem t : True := by trivial",
            "t",
            allowed_axioms=["Classical.choice"],
            env_profile="mathlib",
        ) == "verify_one"
        assert await backend.verify(
            verify_items,
            env_profile="mathlib",
        ) == "verify"
        assert await backend.cleanup(["item-1"]) == "cleanup"
        assert await backend.cancel(["item-2"]) == "cancel"
        assert await backend.stats() == "stats"
        await backend.close()

        assert connected.calls == [
            ("limits",),
            (
                "create_states",
                "create-1",
                "theorem t : True := by sorry",
                "mathlib",
            ),
            (
                "step",
                "node-1",
                "state-token",
                ["intro h"],
                7000,
                [0, 2],
            ),
            (
                "verify_one",
                "verify-1",
                "theorem t : True := by trivial",
                "t",
                ["Classical.choice"],
                "mathlib",
            ),
            ("verify", verify_items, "mathlib"),
            ("cleanup", ["item-1"]),
            ("cancel", ["item-2"]),
            ("stats",),
            ("aclose",),
        ]
        assert backend._backend is None

    asyncio.run(run())


class RecordingExecBackend:
    def __init__(self) -> None:
        self.calls = []

    async def limits(self):
        self.calls.append(("limits",))
        return "limits"

    async def create_states(self, item_id, code, *, env_profile=None):
        self.calls.append(("create_states", item_id, code, env_profile))
        return "create"

    async def step(
        self,
        node_id,
        state_token,
        tactics,
        *,
        timeout_ms=None,
        goal_group=None,
    ):
        self.calls.append(
            (
                "step",
                node_id,
                state_token,
                tactics,
                timeout_ms,
                goal_group,
            )
        )
        return "step"

    async def verify_one(
        self,
        item_id,
        code,
        theorem_name,
        *,
        allowed_axioms=None,
        env_profile=None,
    ):
        self.calls.append(
            (
                "verify_one",
                item_id,
                code,
                theorem_name,
                allowed_axioms,
                env_profile,
            )
        )
        return "verify_one"

    async def verify(self, items, *, env_profile=None):
        self.calls.append(("verify", items, env_profile))
        return "verify"

    async def cleanup(self, item_ids):
        self.calls.append(("cleanup", item_ids))
        return "cleanup"

    async def cancel(self, item_ids):
        self.calls.append(("cancel", item_ids))
        return "cancel"

    async def stats(self):
        self.calls.append(("stats",))
        return "stats"

    async def aclose(self):
        self.calls.append(("aclose",))
