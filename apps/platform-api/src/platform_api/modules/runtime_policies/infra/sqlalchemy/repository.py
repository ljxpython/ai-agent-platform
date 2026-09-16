from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import asc, desc, select, update
from sqlalchemy.orm import Session

from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)
from platform_api.modules.runtime_policies.infra.sqlalchemy.models import (
    ProjectGraphPolicyRecord,
    ProjectModelPolicyRecord,
    ProjectToolPolicyRecord,
)


class SqlAlchemyRuntimePolicyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_graph_policies(self, *, project_id: UUID) -> list[ProjectGraphPolicyRecord]:
        stmt = (
            select(ProjectGraphPolicyRecord)
            .where(ProjectGraphPolicyRecord.project_id == project_id)
            .order_by(asc(ProjectGraphPolicyRecord.display_order), asc(ProjectGraphPolicyRecord.updated_at))
        )
        return list(self.session.scalars(stmt).all())

    def upsert_graph_policy(
        self,
        *,
        project_id: UUID,
        graph_catalog_id: UUID,
        is_enabled: bool,
        display_order: int | None,
        note: str | None,
        updated_by: str | None,
    ) -> ProjectGraphPolicyRecord:
        stmt = select(ProjectGraphPolicyRecord).where(
            ProjectGraphPolicyRecord.project_id == project_id,
            ProjectGraphPolicyRecord.graph_catalog_id == graph_catalog_id,
        )
        row = self.session.scalar(stmt)
        if row is None:
            row = ProjectGraphPolicyRecord(project_id=project_id, graph_catalog_id=graph_catalog_id)
            self.session.add(row)
        row.is_enabled = is_enabled
        row.display_order = display_order
        row.note = note
        row.updated_by = updated_by
        self.session.flush()
        return row

    def list_tool_policies(self, *, project_id: UUID) -> list[ProjectToolPolicyRecord]:
        stmt = (
            select(ProjectToolPolicyRecord)
            .where(ProjectToolPolicyRecord.project_id == project_id)
            .order_by(asc(ProjectToolPolicyRecord.display_order), asc(ProjectToolPolicyRecord.updated_at))
        )
        return list(self.session.scalars(stmt).all())

    def upsert_tool_policy(
        self,
        *,
        project_id: UUID,
        tool_catalog_id: UUID,
        is_enabled: bool,
        display_order: int | None,
        note: str | None,
        updated_by: str | None,
    ) -> ProjectToolPolicyRecord:
        stmt = select(ProjectToolPolicyRecord).where(
            ProjectToolPolicyRecord.project_id == project_id,
            ProjectToolPolicyRecord.tool_catalog_id == tool_catalog_id,
        )
        row = self.session.scalar(stmt)
        if row is None:
            row = ProjectToolPolicyRecord(project_id=project_id, tool_catalog_id=tool_catalog_id)
            self.session.add(row)
        row.is_enabled = is_enabled
        row.display_order = display_order
        row.note = note
        row.updated_by = updated_by
        self.session.flush()
        return row

    def list_model_policies(self, *, project_id: UUID) -> list[ProjectModelPolicyRecord]:
        stmt = (
            select(ProjectModelPolicyRecord)
            .where(ProjectModelPolicyRecord.project_id == project_id)
            .order_by(desc(ProjectModelPolicyRecord.is_default_for_project), asc(ProjectModelPolicyRecord.updated_at))
        )
        return list(self.session.scalars(stmt).all())

    def get_default_model_id(self, *, project_id: UUID) -> str | None:
        model_id = self.session.scalar(
            select(RuntimeCatalogModelRecord.id).join(
                ProjectModelPolicyRecord,
                ProjectModelPolicyRecord.model_catalog_id == RuntimeCatalogModelRecord.id,
            ).where(
                ProjectModelPolicyRecord.project_id == project_id,
                ProjectModelPolicyRecord.is_enabled.is_(True),
                ProjectModelPolicyRecord.is_default_for_project.is_(True),
                RuntimeCatalogModelRecord.enabled.is_(True),
            )
        )
        if model_id:
            return str(model_id)
        # Fallback 1: 若未显式标记 is_default_for_project，取该项目已启用的首个模型策略
        fallback_project_model = self.session.scalar(
            select(RuntimeCatalogModelRecord.id).join(
                ProjectModelPolicyRecord,
                ProjectModelPolicyRecord.model_catalog_id == RuntimeCatalogModelRecord.id,
            ).where(
                ProjectModelPolicyRecord.project_id == project_id,
                ProjectModelPolicyRecord.is_enabled.is_(True),
                RuntimeCatalogModelRecord.enabled.is_(True),
            ).order_by(asc(ProjectModelPolicyRecord.updated_at))
        )
        if fallback_project_model:
            return str(fallback_project_model)
        # Fallback 2: 若项目无任何 policy 记录，取全局已启用的首个模型
        disabled_subq = select(ProjectModelPolicyRecord.model_catalog_id).where(
            ProjectModelPolicyRecord.project_id == project_id,
            ProjectModelPolicyRecord.is_enabled.is_(False),
        )
        fallback_global = self.session.scalar(
            select(RuntimeCatalogModelRecord.id).where(
                RuntimeCatalogModelRecord.enabled.is_(True),
                RuntimeCatalogModelRecord.id.not_in(disabled_subq),
            ).order_by(asc(RuntimeCatalogModelRecord.created_at))
        )
        return str(fallback_global) if fallback_global else None

    def upsert_model_policy(
        self,
        *,
        project_id: UUID,
        model_catalog_id: UUID,
        is_enabled: bool,
        is_default_for_project: bool,
        temperature_default: Decimal | None,
        note: str | None,
        updated_by: str | None,
    ) -> ProjectModelPolicyRecord:
        stmt = select(ProjectModelPolicyRecord).where(
            ProjectModelPolicyRecord.project_id == project_id,
            ProjectModelPolicyRecord.model_catalog_id == model_catalog_id,
        )
        row = self.session.scalar(stmt)
        if row is None:
            row = ProjectModelPolicyRecord(project_id=project_id, model_catalog_id=model_catalog_id)
            self.session.add(row)
        if is_default_for_project:
            self.session.execute(
                update(ProjectModelPolicyRecord)
                .where(
                    ProjectModelPolicyRecord.project_id == project_id,
                    ProjectModelPolicyRecord.model_catalog_id != model_catalog_id,
                    ProjectModelPolicyRecord.is_default_for_project.is_(True),
                )
                .values(is_default_for_project=False)
            )
        row.is_enabled = is_enabled
        row.is_default_for_project = is_default_for_project
        row.temperature_default = temperature_default
        row.note = note
        row.updated_by = updated_by
        self.session.flush()
        return row
