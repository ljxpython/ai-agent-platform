"""Bounded provider classification; exception payloads never leave this module."""

from __future__ import annotations

import re
from asyncio import CancelledError
from collections.abc import Mapping
from typing import Any

from langchain_core.exceptions import (
    ContextOverflowError,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelNotFoundError,
    ModelPermissionDeniedError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from langgraph.errors import GraphBubbleUp

MODEL_ERROR_CODES = frozenset(
    {
        "provider_rate_limited",
        "provider_overloaded",
        "context_too_long",
        "model_unavailable",
        "provider_auth_failed",
        "provider_access_denied",
        "provider_timeout",
        "provider_unavailable",
        "model_call_failed",
    }
)
_CODES = {
    "rate_limit_error": "provider_rate_limited",
    "rate_limit_exceeded": "provider_rate_limited",
    "rate_limit": "provider_rate_limited",
    "overloaded_error": "provider_overloaded",
    "overloaded": "provider_overloaded",
    "context_length_exceeded": "context_too_long",
    "context_window_exceeded": "context_too_long",
    "model_not_found": "model_unavailable",
    "model_not_available": "model_unavailable",
    "authentication_error": "provider_auth_failed",
    "permission_error": "provider_access_denied",
}


def _attribute(exc: BaseException, name: str) -> Any:
    try:
        return getattr(exc, name, None)
    except Exception:
        return None


def is_control_flow(exc: BaseException) -> bool:
    return isinstance(
        exc, (CancelledError, GraphBubbleUp, KeyboardInterrupt, SystemExit)
    )


def error_type(exc: BaseException) -> str:
    name = type(exc).__name__
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,127}", name) else "Exception"


def _chain(exc: BaseException) -> list[BaseException]:
    result = []
    while isinstance(exc, BaseException) and len(result) < 3:
        if any(item is exc for item in result):
            break
        result.append(exc)
        exc = _attribute(exc, "__cause__") or _attribute(exc, "__context__")
    return result


def _provider_codes(exc: BaseException) -> list[str]:
    body = _attribute(exc, "body")
    if not isinstance(body, Mapping):
        return []
    nested = body.get("error")
    sources = [nested, body] if isinstance(nested, Mapping) else [body]
    return [
        value.lower()
        for source in sources
        for key in ("code", "type")
        if isinstance(value := source.get(key), str) and len(value) <= 128
    ]


def classify_exception(exc: BaseException) -> str | None:
    """Classify only model-handler errors, giving precise provider codes priority."""
    if is_control_flow(exc):
        return None
    chain = _chain(exc)
    for item in chain:
        for error_class, code in (
            (ModelRateLimitError, "provider_rate_limited"),
            (ModelTimeoutError, "provider_timeout"),
            (ModelConnectionError, "provider_unavailable"),
            (ContextOverflowError, "context_too_long"),
            (ModelAuthenticationError, "provider_auth_failed"),
            (ModelPermissionDeniedError, "provider_access_denied"),
            (ModelNotFoundError, "model_unavailable"),
        ):
            if isinstance(item, error_class):
                return code
    for item in chain:
        for code in _provider_codes(item):
            if code in _CODES:
                return _CODES[code]
    for item in chain:
        status = _attribute(item, "status_code")
        if type(status) is int:
            if status in {429, 529, 401, 403}:
                return {
                    429: "provider_rate_limited",
                    529: "provider_overloaded",
                    401: "provider_auth_failed",
                    403: "provider_access_denied",
                }[status]
            if 500 <= status <= 599:
                return "provider_unavailable"
        name = error_type(item)
        if isinstance(item, TimeoutError) or name in {
            "APITimeoutError",
            "ReadTimeout",
            "ConnectTimeout",
        }:
            return "provider_timeout"
        if isinstance(item, ConnectionError) or name == "APIConnectionError":
            return "provider_unavailable"
        by_type = {
            "RateLimitError": "provider_rate_limited",
            "AuthenticationError": "provider_auth_failed",
            "PermissionDeniedError": "provider_access_denied",
            "OpenAIModelNotFoundError": "model_unavailable",
        }
        if name in by_type:
            return by_type[name]
    for item in chain:
        try:
            text = str(item)[:2048].lower()
        except Exception:
            continue
        for phrase, code in _CODES.items():
            if phrase in text:
                return code
        if "maximum context length" in text or "context window is too long" in text:
            return "context_too_long"
    return "model_call_failed"


def model_error_fields(exc: BaseException) -> dict[str, Any]:
    status = _attribute(exc, "status_code")
    return {
        "code": classify_exception(exc),
        "error_type": error_type(exc),
        "provider_status": status
        if type(status) is int and 100 <= status <= 599
        else None,
    }


def execution_outcome(exc: BaseException | None) -> str:
    if exc is None:
        return "success"
    if isinstance(exc, CancelledError):
        return "cancelled"
    if isinstance(exc, GraphBubbleUp):
        return "interrupted"
    return "timeout" if isinstance(exc, (TimeoutError, ModelTimeoutError)) else "failed"


__all__ = [
    "MODEL_ERROR_CODES",
    "classify_exception",
    "error_type",
    "execution_outcome",
    "is_control_flow",
    "model_error_fields",
]
