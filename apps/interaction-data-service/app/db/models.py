from __future__ import annotations

import uuid
from datetime import datetime

from app.db.base import Base
from sqlalchemy import DateTime, Float, JSON, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


JSON_FIELD = JSONB().with_variant(JSON(), "sqlite")


class TestCaseDocument(Base):
    __tablename__ = "test_case_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="upload")
    parse_status: Mapped[str] = mapped_column(String(64), nullable=False, default="parsed")
    summary_for_model: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_data: Mapped[dict | None] = mapped_column(JSON_FIELD, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSON_FIELD, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON_FIELD, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TestCaseRecord(Base):
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    module_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_document_ids: Mapped[list[str]] = mapped_column(JSON_FIELD, nullable=False, default=list)
    content_json: Mapped[dict] = mapped_column(JSON_FIELD, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
