from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from app.core.context import get_current_request_context


def _normalize_log_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_log_value(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_normalize_log_value(item) for item in value if item is not None]
    return str(value)


def _build_context_fields() -> dict[str, Any]:
    try:
        context = get_current_request_context()
    except RuntimeError:
        return {}

    return {
        "request_id": context.request.request_id,
        "trace_id": context.request.trace_id,
        "method": context.request.method,
        "path": context.request.path,
        "tenant_id": context.tenant.tenant_id,
        "project_id": context.project.project_id,
        "actor_user_id": context.actor.user_id,
        "actor_subject": context.actor.subject,
        "actor_email": context.actor.email,
        "principal_type": context.actor.principal_type,
        "authentication_type": context.actor.authentication_type,
        "credential_id": context.actor.credential_id,
    }


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level).lower(),
        "logger": logger.name,
        "event": event,
    }
    payload.update(
        {
            key: value
            for key, value in _build_context_fields().items()
            if value is not None
        }
    )
    payload.update(
        {
            str(key): _normalize_log_value(value)
            for key, value in fields.items()
            if value is not None
        }
    )
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))
