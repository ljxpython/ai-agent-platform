from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import Base


class ProjectKnowledgeSpaceRecord(Base):
    __tablename__ = 'project_knowledge_spaces'
    __table_args__ = (
        UniqueConstraint('project_id', name='uq_project_knowledge_spaces_project'),
        UniqueConstraint('workspace_key', name='uq_project_knowledge_spaces_workspace'),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default='lightrag')
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    workspace_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active')
    service_base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    runtime_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
