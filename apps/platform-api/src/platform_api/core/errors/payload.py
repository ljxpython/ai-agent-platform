from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from email.utils import parsedate_to_datetime
from typing import Any

from fastapi.responses import JSONResponse

from platform_api.core.schemas import ErrorBody, ErrorResponse


def safe_validation_details(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    details = []
    for item in items[:20]:
        if not isinstance(item, Mapping):
            continue
        loc = item.get("loc")
        if not isinstance(loc, (list, tuple)):
            continue
        clean_loc = [
            part
            for part in loc[:16]
            if (isinstance(part, str) and len(part) <= 128)
            or (isinstance(part, int) and not isinstance(part, bool))
        ]
        kind = item.get("type")
        if not isinstance(kind, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", kind):
            kind = "validation_error"
        message = {
            "missing": "Field required",
            "extra_forbidden": "Extra field not permitted",
        }.get(kind, "Invalid value")
        details.append({"loc": clean_loc, "type": kind, "message": message})
    return details


def safe_error_headers(
    status_code: int, headers: Mapping[str, str] | None, *, platform: bool
) -> dict[str, str]:
    result = {}
    for key, value in (headers or {}).items():
        if not isinstance(value, str) or "\r" in value or "\n" in value:
            continue
        name = key.lower()
        if name == "retry-after" and status_code in (429, 503) and len(value) <= 128:
            try:
                valid = (value.isascii() and value.isdecimal()) or (
                    parsedate_to_datetime(value).tzinfo is not None
                )
            except (TypeError, ValueError, OverflowError):
                valid = False
            if valid:
                result["Retry-After"] = value
        elif name == "allow" and status_code == 405:
            methods = [part.strip() for part in value.split(",")]
            methods = [part for part in methods if re.fullmatch(r"[A-Z]+", part)]
            if methods:
                result["Allow"] = ", ".join(methods)
        elif (
            name == "www-authenticate"
            and platform
            and status_code == 401
            and len(value) <= 512
        ):
            result["WWW-Authenticate"] = value
    return result


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
        headers={
            **safe_error_headers(status_code, headers, platform=True),
            **({"x-request-id": request_id} if request_id else {}),
        },
    )
