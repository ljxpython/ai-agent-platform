from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from platform_api.modules.agents.application.ports import StoredAssistantAggregate
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord


def _to_aggregate(
    agent: AgentRecord,
) -> StoredAssistantAggregate:
    return StoredAssistantAggregate(
        id=agent.id,
        project_id=agent.project_id,
        name=agent.name,
        description=agent.description,
        graph_id=agent.graph_id,
        status=agent.status,
        context=dict(agent.context),
        created_by=agent.created_by,
        updated_by=agent.updated_by,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


class SqlAlchemyAssistantsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _get_agent(self, assistant_id: UUID) -> AgentRecord | None:
        return self.session.get(AgentRecord, assistant_id)

    def list_project_assistants(
        self,
        *,
        project_id: UUID,
        limit: int,
        offset: int,
        query: str | None,
        graph_id: str | None,
    ) -> tuple[list[StoredAssistantAggregate], int]:
        base_stmt = select(AgentRecord).where(AgentRecord.project_id == project_id)
        if query and query.strip():
            normalized = f"%{query.strip().lower()}%"
            base_stmt = base_stmt.where(
                func.lower(AgentRecord.name).like(normalized)
                | func.lower(AgentRecord.description).like(normalized)
                | func.lower(AgentRecord.graph_id).like(normalized)
            )
        if graph_id and graph_id.strip():
            base_stmt = base_stmt.where(AgentRecord.graph_id == graph_id.strip())

        stmt = (
            base_stmt.order_by(desc(AgentRecord.created_at), desc(AgentRecord.id))
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        rows = list(self.session.scalars(stmt).all())
        total = int(self.session.scalar(count_stmt) or 0)
        return [_to_aggregate(agent) for agent in rows], total

    def get_assistant_by_id(
        self, assistant_id: UUID
    ) -> StoredAssistantAggregate | None:
        stmt = select(AgentRecord).where(AgentRecord.id == assistant_id)
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return _to_aggregate(row)

    def get_by_project_and_graph_id(
        self,
        *,
        project_id: UUID,
        graph_id: str,
    ) -> StoredAssistantAggregate | None:
        stmt = (
            select(AgentRecord)
            .where(
                AgentRecord.project_id == project_id,
                AgentRecord.graph_id == graph_id,
            )
            .limit(1)
        )
        row = self.session.scalar(stmt)
        if row is None:
            return None
        return _to_aggregate(row)

    def create_assistant(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
        graph_id: str,
        context: dict,
        actor_user_id: UUID,
    ) -> StoredAssistantAggregate:
        now = datetime.now(UTC)
        record = AgentRecord(
            project_id=project_id,
            name=name,
            description=description,
            graph_id=graph_id,
            created_at=now,
            context=context,
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )
        self.session.add(record)
        self.session.flush()
        return _to_aggregate(record)

    def update_assistant_runtime_fields(
        self,
        *,
        assistant_id: UUID,
        graph_id: str,
        name: str,
        description: str,
    ) -> StoredAssistantAggregate:
        record = self._get_agent(assistant_id)
        if record is None:
            raise ValueError("assistant_not_found")
        record.graph_id = graph_id
        record.name = name
        record.description = description
        self.session.flush()
        return _to_aggregate(record)

    def update_assistant_configuration(
        self,
        *,
        assistant_id: UUID,
        status: str,
        context: dict,
        actor_user_id: UUID,
    ) -> StoredAssistantAggregate:
        record = self._get_agent(assistant_id)
        if record is None:
            raise ValueError("assistant_not_found")
        record.status = status
        record.context = context
        record.updated_by = actor_user_id
        record.updated_at = datetime.now(UTC)
        self.session.flush()
        return _to_aggregate(record)

    def delete_assistant(self, *, assistant_id: UUID) -> None:
        record = self._get_agent(assistant_id)
        if record is None:
            return
        self.session.delete(record)
        self.session.flush()
