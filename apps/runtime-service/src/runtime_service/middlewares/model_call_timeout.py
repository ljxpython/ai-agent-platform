"""Single async model-call timeout middleware."""

from __future__ import annotations

import asyncio
import math
import os

from langchain.agents.middleware import AgentMiddleware, ModelRequest

DEFAULT_MODEL_CALL_TIMEOUT_SECONDS = 600.0


def resolve_model_call_timeout_seconds(default: float = DEFAULT_MODEL_CALL_TIMEOUT_SECONDS) -> float:
    raw = os.getenv("AGENT_MODEL_CALL_TIMEOUT_SECONDS", "").strip()
    if raw:
        try:
            parsed = float(raw)
            if math.isfinite(parsed) and parsed > 0:
                return parsed
        except ValueError:
            pass
    return float(default)


class ModelCallTimeoutMiddleware(AgentMiddleware):
    """Cancel a provider call after a bounded wall-clock duration."""

    def __init__(self, timeout_seconds: float | None = None) -> None:
        super().__init__()
        resolved = resolve_model_call_timeout_seconds() if timeout_seconds is None else timeout_seconds
        if isinstance(resolved, bool) or not math.isfinite(resolved) or resolved <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        self.timeout_seconds = float(resolved)

    async def awrap_model_call(self, request: ModelRequest, handler):
        async with asyncio.timeout(self.timeout_seconds):
            return await handler(request)


__all__ = [
    "DEFAULT_MODEL_CALL_TIMEOUT_SECONDS",
    "ModelCallTimeoutMiddleware",
    "resolve_model_call_timeout_seconds",
]
