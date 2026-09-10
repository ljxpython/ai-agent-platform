from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def clean_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def ensure_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def payload_to_dict(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        value = payload.model_dump(exclude_none=True)
        if isinstance(value, dict):
            return dict(value)
    if isinstance(payload, Mapping):
        return dict(payload)
    return {}
