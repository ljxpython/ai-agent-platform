from __future__ import annotations

import re
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass

_TRACEPARENT_REGEX = re.compile(
    r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$", re.IGNORECASE
)


@dataclass(frozen=True, slots=True)
class RuntimeTraceContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    traceparent: str
    service: str = "runtime-service"


_CURRENT_TRACE_CONTEXT: ContextVar[RuntimeTraceContext | None] = ContextVar(
    "runtime_trace_context", default=None
)


def get_current_trace_context() -> RuntimeTraceContext | None:
    return _CURRENT_TRACE_CONTEXT.get()


def set_current_trace_context(
    ctx: RuntimeTraceContext,
) -> Token[RuntimeTraceContext | None]:
    return _CURRENT_TRACE_CONTEXT.set(ctx)


def reset_current_trace_context(token: Token[RuntimeTraceContext | None]) -> None:
    _CURRENT_TRACE_CONTEXT.reset(token)


def parse_or_create_traceparent(
    raw_traceparent: str | None,
    raw_trace_id: str | None = None,
    raw_request_id: str | None = None,
) -> RuntimeTraceContext:
    if raw_traceparent:
        match = _TRACEPARENT_REGEX.match(raw_traceparent.strip().lower())
        if match:
            trace_id = match.group(1)
            parent_span_id = match.group(2)
            span_id = uuid.uuid4().hex[:16]
            return RuntimeTraceContext(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                traceparent=f"00-{trace_id}-{span_id}-01",
            )

    candidate = (raw_trace_id or raw_request_id or "").strip().lower()
    if len(candidate) == 32 and all(c in "0123456789abcdef" for c in candidate):
        trace_id = candidate
    else:
        trace_id = uuid.uuid4().hex

    span_id = uuid.uuid4().hex[:16]
    return RuntimeTraceContext(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=None,
        traceparent=f"00-{trace_id}-{span_id}-01",
    )
