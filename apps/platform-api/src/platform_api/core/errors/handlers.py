from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from platform_api.core.errors.base import PlatformApiError
from platform_api.core.errors.payload import (
    build_error_response,
    safe_error_headers,
    safe_validation_details,
)

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _validation_details(exc: RequestValidationError) -> list[dict[str, object]]:
    return safe_validation_details(exc.errors())


def _http_exception_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "not_authenticated",
        403: "forbidden",
        404: "route_not_found",
        405: "method_not_allowed",
    }.get(status_code, "http_error")


def _http_exception_message(exc: StarletteHTTPException) -> str:
    if exc.status_code in {404, 405}:
        return {
            404: "Route not found",
            405: "Method not allowed",
        }[exc.status_code]
    if isinstance(exc.detail, str) and exc.detail.strip():
        return exc.detail.strip()
    return {
        400: "Bad request",
        401: "Authentication required",
        403: "Permission denied",
        404: "Route not found",
        405: "Method not allowed",
    }.get(exc.status_code, "HTTP error")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PlatformApiError)
    async def handle_platform_api_error(
        request: Request,
        exc: PlatformApiError,
    ) -> JSONResponse:
        return build_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=_request_id(request),
            details=exc.details,
            extra=exc.extra,
            headers=safe_error_headers(
                exc.status_code,
                getattr(exc, "headers", None),
                platform=not hasattr(exc, "upstream_status_code"),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return build_error_response(
            status_code=422,
            code="validation_failed",
            message="Validation failed",
            request_id=_request_id(request),
            details=_validation_details(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return build_error_response(
            status_code=exc.status_code,
            code=_http_exception_code(exc.status_code),
            message=_http_exception_message(exc),
            request_id=_request_id(request),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return unexpected_error_response(request, exc)


def unexpected_error_response(request: Request, exc: Exception) -> JSONResponse:
    location = exc.__traceback__
    while location and location.tb_next:
        location = location.tb_next
    logger.error(
        "unhandled_exception request_id=%s type=%s location=%s:%s",
        _request_id(request),
        type(exc).__name__,
        location.tb_frame.f_code.co_filename if location else "unknown",
        location.tb_lineno if location else 0,
    )
    return build_error_response(
        status_code=500,
        code="internal_server_error",
        message="Internal server error",
        request_id=_request_id(request),
    )
