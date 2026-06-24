"""Deterministic ids and hashes for replay persistence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def stable_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for JSON-like data."""

    payload = _jsonable(value)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_id(kind: str, value: Any) -> str:
    """Return a deterministic namespaced id for durable rows."""

    return f"{kind}:{stable_hash(value)[:32]}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "stable_hash",
    "stable_id",
]
