"""Observe each model-handler failure without introducing recovery behavior."""

from __future__ import annotations

import time
from collections.abc import Mapping
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langgraph.config import get_config

from runtime_service.observability.diagnostics import log_diagnostic
from runtime_service.observability.errors import is_control_flow, model_error_fields
from runtime_service.observability.langfuse import record_diagnostic_event
from runtime_service.runtime.errors import RuntimePrivacyError


class ModelErrorMiddleware(AgentMiddleware):
    def __init__(self, metadata: Mapping, *, scope: str = "primary") -> None:
        super().__init__()
        self._metadata = dict(metadata)
        self._scope = scope

    def _record(self, request: ModelRequest, exc: Exception, started: float) -> None:
        try:
            config = get_config()
            namespace = (config.get("metadata") or {}).get(
                "langgraph_checkpoint_ns", ""
            )
        except RuntimeError:
            namespace = ""
        model = getattr(request.model, "model_name", None) or getattr(
            request.model, "model", None
        )
        fields = {
            **self._metadata,
            **model_error_fields(exc),
            "model_id": model,
            "scope": self._scope,
            "namespace": namespace.split("|") if isinstance(namespace, str) else [],
            "model_call_id": str(uuid4()),
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
        }
        log_diagnostic("runtime.model_call.failed", fields)
        record_diagnostic_event("runtime.model_call.failed", fields)

    async def awrap_model_call(self, request: ModelRequest, handler):
        started = time.monotonic()
        try:
            return await handler(request)
        except Exception as exc:
            if not isinstance(exc, RuntimePrivacyError) and not is_control_flow(exc):
                try:
                    self._record(request, exc, started)
                except Exception:  # Keep the original exception and traceback.
                    pass
            raise


__all__ = ["ModelErrorMiddleware"]
