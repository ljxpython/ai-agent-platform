from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.context.models import ActorContext
from app.modules.operations.application.ports import (
    OperationDispatcherProtocol,
    OperationExecutorProtocol,
    StoredOperation,
)

_ACTOR_SNAPSHOT_KEY = "actor_snapshot"


class DatabasePollingOperationDispatcher(OperationDispatcherProtocol):
    async def dispatch(self, *, operation: StoredOperation) -> None:
        # Database polling worker claims submitted rows directly.
        _ = operation


class OperationExecutorRegistry:
    def __init__(self, executors: list[OperationExecutorProtocol] | tuple[OperationExecutorProtocol, ...]) -> None:
        self._executors = {executor.kind: executor for executor in executors}

    def supported_kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._executors))

    def get(self, kind: str) -> OperationExecutorProtocol | None:
        return self._executors.get(kind)


def with_actor_snapshot(*, metadata: Mapping[str, Any], actor: ActorContext) -> dict[str, Any]:
    enriched = dict(metadata)
    enriched[_ACTOR_SNAPSHOT_KEY] = {
        "user_id": actor.user_id,
        "subject": actor.subject,
        "email": actor.email,
        "platform_roles": list(actor.platform_roles),
        "project_roles": {
            project_id: list(roles)
            for project_id, roles in actor.project_roles.items()
        },
    }
    return enriched


def actor_from_operation(operation: StoredOperation) -> ActorContext:
    snapshot = operation.metadata.get(_ACTOR_SNAPSHOT_KEY)
    if isinstance(snapshot, dict):
        project_roles = snapshot.get("project_roles")
        return ActorContext(
            user_id=_clean(snapshot.get("user_id")),
            subject=_clean(snapshot.get("subject")),
            email=_clean(snapshot.get("email")),
            platform_roles=_normalize_roles(snapshot.get("platform_roles")),
            project_roles=_normalize_project_roles(project_roles),
        )
    return ActorContext(user_id=operation.requested_by, subject=operation.requested_by)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_roles(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _normalize_project_roles(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, tuple[str, ...]] = {}
    for project_id, roles in value.items():
        cleaned_project_id = _clean(project_id)
        if not cleaned_project_id:
            continue
        normalized[cleaned_project_id] = _normalize_roles(roles)
    return normalized
