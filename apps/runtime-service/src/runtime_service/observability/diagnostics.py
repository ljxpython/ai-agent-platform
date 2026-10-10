"""Safe local diagnostic events and deterministic Run-to-trace association."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.runtime.errors import WORKSPACE_ERROR_CODES

logger = logging.getLogger(__name__)
_FIELDS = frozenset(
    {
        "graph_id",
        "run_id",
        "thread_id",
        "tenant_id",
        "project_id",
        "request_id",
        "platform_trace_id",
        "model_id",
        "callback_run_id",
        "model_call_id",
        "scope",
        "namespace",
        "code",
        "error_type",
        "provider_status",
        "duration_ms",
        "outcome",
        "error_code",
        "phase",
        "ordinal",
        "started_at",
        "ended_at",
        "factory_id",
        "budget_scope",
        "limit",
        "used",
        "remaining",
        "component",
        "unit",
        "role",
        "attempts",
        "backend",
        "command_state",
        "retry_wait_ms",
        "plan_id",
        "revision",
        "content_hash",
        "actor_id",
        "decision",
    }
)


def uuid_string(value: Any) -> str | None:
    try:
        return str(UUID(str(value))) if value is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def diagnostic_metadata(
    config: Mapping[str, Any], graph_id: str, facts: VerifiedDelegation
) -> dict[str, Any]:
    metadata = config.get("metadata") or {}
    configurable = config.get("configurable") or {}
    return {
        "graph_id": graph_id,
        "run_id": uuid_string(metadata.get("run_id")),
        "thread_id": uuid_string(
            facts.scope.thread_id or configurable.get("thread_id")
        ),
        "tenant_id": facts.principal.tenant_id,
        "project_id": facts.principal.project_id,
        "request_id": facts.request_id,
        "platform_trace_id": facts.platform_trace_id,
    }


def trace_id_for(metadata: Mapping[str, Any]) -> str | None:
    values = [metadata.get(key) for key in ("tenant_id", "project_id", "run_id")]
    if not all(isinstance(value, str) and value for value in values) or not uuid_string(
        values[2]
    ):
        return None
    seed = "runtime:v1:" + ":".join(values)
    return hashlib.sha256(seed.encode()).digest()[:16].hex()


def safe_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in fields.items():
        if key not in _FIELDS or value is None:
            continue
        if key == "namespace" and isinstance(value, (list, tuple)):
            result[key] = [
                part
                for part in value[:8]
                if isinstance(part, str)
                and re.fullmatch(r"[\w:.-]{1,128}", part, flags=re.ASCII)
            ]
        elif (
            isinstance(value, str)
            and len(value) <= 256
            and not any(c in value for c in ("\n", "\r", "/", "\\"))
        ):
            result[key] = value
        elif type(value) in (int, float) and math.isfinite(value) and value >= 0:
            result[key] = value
    return result


def workspace_execution_fields(fields: Mapping[str, Any]) -> dict[str, Any] | None:
    """Validate only the execution summary; identity comes from the callback."""
    for key, allowed in (
        ("backend", {"docker"}),
        ("phase", {"start", "execute", "cleanup"}),
        ("outcome", {"recovered", "failed", "cancelled"}),
        ("command_state", {"not_started", "started", "unknown"}),
    ):
        if not isinstance(fields.get(key), str) or fields[key] not in allowed:
            return None
    attempts = fields.get("attempts")
    wait = fields.get("retry_wait_ms")
    if type(attempts) is not int or not 1 <= attempts <= 4:
        return None
    if type(wait) not in (int, float) or not math.isfinite(wait) or wait < 0:
        return None
    code = fields.get("code")
    if code is not None and (
        not isinstance(code, str) or code not in WORKSPACE_ERROR_CODES
    ):
        return None
    duration = fields.get("duration_ms")
    return {
        **{
            key: fields[key] for key in ("backend", "phase", "outcome", "command_state")
        },
        "attempts": attempts,
        "retry_wait_ms": wait,
        "code": code,
        "duration_ms": duration
        if type(duration) in (int, float) and math.isfinite(duration) and duration >= 0
        else None,
    }


def log_diagnostic(event: str, fields: Mapping[str, Any]) -> None:
    try:
        payload = {"schema_version": 1, "event": event, **safe_fields(fields)}
        logger.info(
            json.dumps(
                payload, ensure_ascii=True, allow_nan=False, separators=(",", ":")
            )
        )
    except Exception:  # Diagnostics cannot replace the execution result.
        return


__all__ = [
    "diagnostic_metadata",
    "log_diagnostic",
    "safe_fields",
    "trace_id_for",
    "uuid_string",
]
