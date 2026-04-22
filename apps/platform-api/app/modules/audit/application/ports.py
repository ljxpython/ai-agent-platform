from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.modules.audit.domain import AuditPlane, AuditResult


@dataclass(frozen=True, slots=True)
class StoredAuditEvent:
    id: str
    request_id: str
    plane: AuditPlane
    action: str
    target_type: str | None
    target_id: str | None
    actor_user_id: str | None
    actor_subject: str | None
    tenant_id: str | None
    project_id: str | None
    result: AuditResult
    method: str
    path: str
    status_code: int
    duration_ms: int
    created_at: datetime
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AuditWriteCommand:
    request_id: str
    plane: AuditPlane
    action: str
    target_type: str | None
    target_id: str | None
    actor_user_id: str | None
    actor_subject: str | None
    tenant_id: str | None
    project_id: str | None
    result: AuditResult
    method: str
    path: str
    status_code: int
    duration_ms: int
    metadata: dict[str, Any]


class AuditRepositoryProtocol(Protocol):
    def create_event(self, command: AuditWriteCommand) -> None: ...

    def list_events(
        self,
        *,
        project_id: str | None,
        plane: str | None,
        action: str | None,
        target_type: str | None,
        target_id: str | None,
        actor_user_id: str | None,
        method: str | None,
        result: str | None,
        status_code: int | None,
        created_from: datetime | None,
        created_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[StoredAuditEvent], int]: ...
