"""Minimal evidence receipts, not a second conversation or approval store."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.core.db.base import Base


class AssistantEvidenceRecord(Base):
    __tablename__ = "assistant_evidence"
    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
