from __future__ import annotations

import json
import logging
import re
from typing import Any

from langgraph.config import get_config

from runtime_service.observability.context import get_current_trace_context

_context_metrics = logging.getLogger("runtime_service.context_metrics")
_context_metrics.setLevel(logging.INFO)
_context_metrics.propagate = False
if not _context_metrics.handlers:
    _context_metrics.addHandler(logging.StreamHandler())

_CORRELATION_KEYS = ("project_id", "thread_id", "platform_trace_id", "request_id")


def _safe_scalar_id(value: Any) -> str | None:
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value)
        else None
    )


def log_context_metric(fields: dict[str, Any]) -> None:
    """Private counters must be visible even when the host configures only structlog."""
    try:
        try:
            config = get_config()
        except RuntimeError:
            config = {}
        metadata = config.get("metadata") or {}
        identity: dict[str, Any] = {
            "run_id": metadata.get("run_id"),
            "checkpoint_ns": str(metadata.get("langgraph_checkpoint_ns", ""))[:1024],
        }
        for key in _CORRELATION_KEYS:
            value = _safe_scalar_id(metadata.get(key))
            if value:
                identity[key] = value
        _context_metrics.info(
            json.dumps({**identity, **fields}, ensure_ascii=True, separators=(",", ":"))
        )
    except Exception:
        pass  # Diagnostics cannot replace the execution result.


class RuntimeTraceLogFilter(logging.Filter):
    """Enriches all standard logging.LogRecord with service, trace_id, and span_id."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = "runtime-service"  # type: ignore[attr-defined]
        record.trace_id = ""  # type: ignore[attr-defined]
        record.span_id = ""  # type: ignore[attr-defined]
        ctx = get_current_trace_context()
        if ctx:
            record.trace_id = ctx.trace_id  # type: ignore[attr-defined]
            record.span_id = ctx.span_id  # type: ignore[attr-defined]
        return True


def format_log_line(message: str, *, extra: dict[str, Any] | None = None) -> str:
    ctx = get_current_trace_context()
    trace_id = ctx.trace_id if ctx else "-"
    span_id = ctx.span_id if ctx else "-"
    prefix = f"[runtime-service][trace_id={trace_id}][span_id={span_id}]"
    if extra:
        extra_str = " ".join(f"{k}={v}" for k, v in extra.items())
        return f"{prefix} {message} ({extra_str})"
    return f"{prefix} {message}"
