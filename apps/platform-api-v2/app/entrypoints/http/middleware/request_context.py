from __future__ import annotations

from fastapi import FastAPI, Request

from app.core.context import (
    build_request_context,
    reset_current_request_context,
    set_current_request_context,
)


def register_request_context_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        context = build_request_context(request)
        token = set_current_request_context(context)
        request.state.request_id = context.request.request_id
        request.state.platform_context = context

        try:
            response = await call_next(request)
        finally:
            reset_current_request_context(token)

        current_context = request.state.platform_context
        response.headers["x-request-id"] = current_context.request.request_id
        return response
