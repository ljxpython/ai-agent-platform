from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors.base import PlatformApiError

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PlatformApiError)
    async def handle_platform_api_error(
        request: Request,
        exc: PlatformApiError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_payload(request_id=_request_id(request)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception request_id=%s method=%s path=%s",
            _request_id(request),
            request.method,
            request.url.path,
            exc_info=exc,
        )
        payload = {
            "error": {
                "code": "internal_server_error",
                "message": "Internal server error",
                "details": [],
            }
        }
        request_id = _request_id(request)
        if request_id:
            payload["request_id"] = request_id
        return JSONResponse(status_code=500, content=payload)
