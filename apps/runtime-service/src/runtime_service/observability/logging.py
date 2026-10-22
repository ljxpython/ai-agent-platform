from __future__ import annotations

import logging
from typing import Any

from runtime_service.observability.context import get_current_trace_context


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
