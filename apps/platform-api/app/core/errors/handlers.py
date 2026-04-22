from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors.base import PlatformApiError
from app.core.errors.payload import build_error_payload, build_error_response

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _validation_details(exc: RequestValidationError) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for item in exc.errors():
        details.append(
            {
                "loc": list(item.get("loc", ())),
                "message": item.get("msg", "Invalid request"),
                "type": item.get("type", "validation_error"),
            }
        )
    return details


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
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_payload(request_id=_request_id(request)),
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
        return JSONResponse(
            status_code=500,
            content=build_error_payload(
                code="internal_server_error",
                message="Internal server error",
                request_id=_request_id(request),
            ),
        )
