from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi.responses import JSONResponse

from app.core.schemas import ErrorBody, ErrorResponse


def build_error_payload(
    *,
    code: str,
    message: str,
    request_id: str | None,
    details: Sequence[Mapping[str, Any]] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = ErrorResponse(
        request_id=request_id,
        error=ErrorBody(
            code=code,
            message=message,
            details=[dict(item) for item in details or ()],
            extra=dict(extra) if extra else None,
        ),
    )
    return payload.model_dump(exclude_none=True)


def build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str | None,
    details: Sequence[Mapping[str, Any]] | None = None,
    extra: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            code=code,
            message=message,
            request_id=request_id,
            details=details,
            extra=extra,
        ),
        headers=dict(headers or {}),
    )
