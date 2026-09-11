from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
import langgraph_sdk

from platform_api.core.errors import PlatformApiError, UpstreamServiceError

FORWARDED_HEADER_KEYS = ("x-request-id",)


def build_forward_headers(
    headers: Mapping[str, str | None],
    *,
    request_id: str | None = None,
) -> dict[str, str]:
    forwarded = {
        key: value
        for key in FORWARDED_HEADER_KEYS
        if (value := headers.get(key))
    }
    if "x-request-id" not in forwarded and request_id:
        forwarded["x-request-id"] = request_id
    return forwarded


def get_langgraph_client(
    *,
    base_url: str,
    api_key: str | None = None,
    forwarded_headers: Mapping[str, str] | None = None,
    timeout_seconds: float | None = None,
) -> Any:
    return langgraph_sdk.get_client(
        url=base_url,
        api_key=api_key if api_key else None,
        headers=dict(forwarded_headers or {}),
        timeout=timeout_seconds,
    )


def redact_runtime_private_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: redact_runtime_private_fields(item)
            for key, item in value.items()
            if not (str(key).startswith("_runtime_") or key in {"runtime_model_ref", "runtime_message_claim", "authorization_ref"})
        }
    if isinstance(value, list):
        return [redact_runtime_private_fields(item) for item in value]
    return value


def _runtime_upstream_message(detail: Any, *, fallback_code: str) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, Mapping):
        message = detail.get("message") or detail.get("detail")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return fallback_code.replace("_", " ")


def create_runtime_upstream_error(
    *,
    status_code: int,
    detail: Any,
    fallback_code: str,
    upstream_path: str | None = None,
) -> PlatformApiError:
    detail = redact_runtime_private_fields(detail)
    extra: dict[str, Any] = {
        "upstream": "langgraph",
        "upstream_status_code": status_code,
    }
    if upstream_path:
        extra["upstream_path"] = upstream_path
    if detail not in (None, ""):
        extra["upstream_detail"] = detail
    return PlatformApiError(
        code=fallback_code,
        status_code=status_code,
        message=_runtime_upstream_message(detail, fallback_code=fallback_code),
        extra=extra,
    )


def raise_runtime_upstream_error(exc: Exception, *, fallback_detail: str) -> None:
    if isinstance(exc, (PlatformApiError, UpstreamServiceError)):
        raise exc

    if isinstance(exc, httpx.TimeoutException):
        raise UpstreamServiceError(
            upstream="langgraph",
            status_code=504,
            code="langgraph_upstream_timeout",
            message="LangGraph upstream timed out",
        ) from exc

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        try:
            detail: Any = response.json()
        except Exception:
            detail = getattr(response, "text", None) or fallback_detail
        request = getattr(response, "request", None)
        url = getattr(request, "url", None)
        upstream_path = getattr(url, "path", None)
        raise create_runtime_upstream_error(
            status_code=status_code,
            detail=detail,
            fallback_code=fallback_detail,
            upstream_path=upstream_path,
        ) from exc

    message = str(exc).strip()
    if message.startswith("ValueError:"):
        detail = message.split(":", 1)[1].strip() or fallback_detail
        raise create_runtime_upstream_error(
            status_code=400,
            detail=detail,
            fallback_code=fallback_detail,
        ) from exc

    if isinstance(exc, httpx.HTTPError):
        raise UpstreamServiceError(
            upstream="langgraph",
            status_code=502,
            code="langgraph_upstream_unavailable",
            message="LangGraph upstream is unavailable",
        ) from exc

    raise UpstreamServiceError(
        upstream="langgraph",
        status_code=502,
        code="langgraph_upstream_unavailable",
        message="LangGraph upstream is unavailable",
    ) from exc
