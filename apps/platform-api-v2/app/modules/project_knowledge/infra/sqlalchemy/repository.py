from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.project_knowledge.infra.sqlalchemy.models import ProjectKnowledgeSpaceRecord


class SqlAlchemyProjectKnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_project_id(self, project_id: UUID) -> ProjectKnowledgeSpaceRecord | None:
        stmt = select(ProjectKnowledgeSpaceRecord).where(
            ProjectKnowledgeSpaceRecord.project_id == project_id
        )
        return self.session.scalar(stmt)

    def create_space(
        self,
        *,
        project_id: UUID,
        provider: str,
        display_name: str,
        workspace_key: str,
        status: str,
        service_base_url: str,
        runtime_profile_json: dict,
    ) -> ProjectKnowledgeSpaceRecord:
        row = ProjectKnowledgeSpaceRecord(
            project_id=project_id,
            provider=provider,
            display_name=display_name,
            workspace_key=workspace_key,
            status=status,
            service_base_url=service_base_url,
            runtime_profile_json=runtime_profile_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def update_space(
        self,
        *,
        row: ProjectKnowledgeSpaceRecord,
        display_name: str | None,
        runtime_profile_json: dict | None,
    ) -> ProjectKnowledgeSpaceRecord:
        if display_name is not None:
            row.display_name = display_name
        if runtime_profile_json is not None:
            row.runtime_profile_json = runtime_profile_json
        self.session.flush()
        return row
