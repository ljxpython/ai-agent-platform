from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.core.db.base import Base


class RunRequestRecord(Base):
    """Submission audit and idempotency; execution state belongs to Agent Server."""

    __tablename__ = "run_requests"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "thread_id", "idempotency_key", name="uq_run_requests_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    agent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    context_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    interrupt_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submission_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="submitted"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now(), onupdate=func.now()
    )
