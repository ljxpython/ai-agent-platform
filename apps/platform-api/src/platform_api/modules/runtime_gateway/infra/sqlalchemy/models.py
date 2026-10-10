from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.core.db.base import Base


class ThreadAccessRecord(Base):
    """Authoritative Platform ACL; no business role policy is stored in Runtime."""

    __tablename__ = "thread_access"
    thread_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_user_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="private"
    )
    shared_actions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    project_actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    takeovers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    provisioning_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ready"
    )
    reserved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


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
    origin_ref: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )
    parent_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    interrupt_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submission_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="submitted"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=func.now(),
    )


class RunCompletionOriginRecord(Base):
    """Platform ownership for a generic runtime terminal callback."""

    __tablename__ = "run_completion_origins"
    origin_ref: Mapped[str] = mapped_column(String(128), primary_key=True)
    runtime_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default"
    )
    source_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="submission"
    )
    source_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    thread_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="reuse"
    )
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    agent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=func.now(),
    )


class RunCompletionEventRecord(Base):
    """Idempotent, safe terminal event accepted from the runtime."""

    __tablename__ = "run_completion_events"
    __table_args__ = (
        UniqueConstraint("runtime_id", "run_id", name="uq_run_completion_event_run"),
        Index(
            "ix_run_completion_feed",
            "project_id",
            "recipient_user_id",
            "accepted_at",
            "event_id",
        ),
    )
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    runtime_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default"
    )
    origin_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_key: Mapped[str] = mapped_column(String(128), nullable=False)
    recipient_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detail_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    dedup_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    body_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class RunCompletionReceiptRecord(Base):
    """Per-actor read receipt for private completion feed items."""

    __tablename__ = "run_completion_receipts"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "actor_user_id", name="uq_run_completion_receipt_actor"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
