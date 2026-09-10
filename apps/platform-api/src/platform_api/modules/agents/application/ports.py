from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from platform_api.core.context.models import ActorContext


@dataclass(frozen=True, slots=True)
class StoredAssistantAggregate:
    id: UUID
    project_id: UUID
    name: str
    description: str
    graph_id: str
    status: str
    context: dict[str, Any]
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime | None
    updated_at: datetime | None


class AssistantParameterSchemaProviderProtocol(Protocol):
    async def build_schema(
        self,
        graph_id: str,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> dict[str, Any]: ...
