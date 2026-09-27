from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI, Request

from platform_api.core.context import (
    build_request_context,
    reset_current_request_context,
    set_current_request_context,
)
from platform_api.core.errors.handlers import unexpected_error_response
from platform_api.core.observability import log_event, metrics_registry

logger = logging.getLogger(__name__)


def register_request_context_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        context = build_request_context(request)
        token = set_current_request_context(context)
        request.state.request_id = context.request.request_id
        request.state.platform_context = context

        try:
            try:
                response = await call_next(request)
            except Exception as exc:  # noqa: BLE001 - HTTP boundary must convert unexpected errors.
                response = unexpected_error_response(request, exc)
            current_context = request.state.platform_context
            duration_ms = round(
                (perf_counter() - current_context.request.started_at) * 1000, 2
            )
            metrics_registry.record_http_request(
                method=current_context.request.method,
                path=current_context.request.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            log_event(
                logger,
                "http.request.completed",
                method=current_context.request.method,
                path=current_context.request.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["x-request-id"] = current_context.request.request_id
            response.headers["x-trace-id"] = current_context.request.trace_id
            return response
        finally:
            reset_current_request_context(token)
