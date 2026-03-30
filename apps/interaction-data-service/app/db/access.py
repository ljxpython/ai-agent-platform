from __future__ import annotations

import uuid
from datetime import datetime

from app.db.models import TestCaseDocument, TestCaseRecord
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def create_test_case_document(
    session: Session,
    *,
    project_id: uuid.UUID,
    batch_id: str | None,
    idempotency_key: str | None,
    filename: str,
    content_type: str,
    storage_path: str | None,
    source_kind: str,
    parse_status: str,
    summary_for_model: str,
    parsed_text: str | None,
    structured_data: dict | None,
    provenance: dict,
    confidence: float | None,
    error: dict | None,
) -> TestCaseDocument:
    normalized_batch_id = batch_id.strip() if isinstance(batch_id, str) and batch_id.strip() else None
    normalized_idempotency_key = (
        idempotency_key.strip()
        if isinstance(idempotency_key, str) and idempotency_key.strip()
        else None
    )
    if normalized_idempotency_key is not None:
        existing_stmt = select(TestCaseDocument).where(
            TestCaseDocument.project_id == project_id,
            TestCaseDocument.idempotency_key == normalized_idempotency_key,
        )
        if normalized_batch_id is None:
            existing_stmt = existing_stmt.where(TestCaseDocument.batch_id.is_(None))
        else:
            existing_stmt = existing_stmt.where(TestCaseDocument.batch_id == normalized_batch_id)
        existing = session.scalar(existing_stmt)
        if existing is not None:
            if normalized_batch_id is not None and not existing.batch_id:
                existing.batch_id = normalized_batch_id
            if storage_path is not None:
                existing.storage_path = storage_path
            if parse_status == "parsed" or existing.parse_status == "unprocessed":
                existing.parse_status = parse_status
            if summary_for_model:
                existing.summary_for_model = summary_for_model
            if parsed_text:
                existing.parsed_text = parsed_text
            if structured_data is not None:
                existing.structured_data = structured_data
            if provenance:
                existing.provenance = provenance
            if confidence is not None:
                existing.confidence = confidence
            if error is not None:
                existing.error = error
            elif parse_status == "parsed":
                existing.error = None
            session.flush()
            return existing

    row = TestCaseDocument(
        project_id=project_id,
        batch_id=normalized_batch_id,
        idempotency_key=normalized_idempotency_key,
        filename=filename,
        content_type=content_type,
        storage_path=storage_path,
        source_kind=source_kind,
        parse_status=parse_status,
        summary_for_model=summary_for_model,
        parsed_text=parsed_text,
        structured_data=structured_data,
        provenance=provenance,
        confidence=confidence,
        error=error,
    )
    session.add(row)
    session.flush()
    return row


def list_test_case_documents(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    batch_id: str | None,
    parse_status: str | None,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[TestCaseDocument], int]:
    base_stmt = select(TestCaseDocument)
    if project_id is not None:
        base_stmt = base_stmt.where(TestCaseDocument.project_id == project_id)
    if isinstance(batch_id, str) and batch_id.strip():
        base_stmt = base_stmt.where(TestCaseDocument.batch_id == batch_id.strip())
    if isinstance(parse_status, str) and parse_status.strip():
        base_stmt = base_stmt.where(TestCaseDocument.parse_status == parse_status.strip())
    if isinstance(query, str) and query.strip():
        pattern = f"%{query.strip()}%"
        base_stmt = base_stmt.where(
            or_(
                TestCaseDocument.filename.ilike(pattern),
                TestCaseDocument.summary_for_model.ilike(pattern),
            )
        )
    stmt = base_stmt.order_by(desc(TestCaseDocument.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def get_test_case_document(
    session: Session, document_id: uuid.UUID
) -> TestCaseDocument | None:
    return session.get(TestCaseDocument, document_id)


def create_test_case(
    session: Session,
    *,
    project_id: uuid.UUID,
    batch_id: str | None,
    case_id: str | None,
    title: str,
    description: str,
    status: str,
    module_name: str | None,
    priority: str | None,
    source_document_ids: list[str],
    content_json: dict,
) -> TestCaseRecord:
    row = TestCaseRecord(
        project_id=project_id,
        batch_id=batch_id,
        case_id=case_id,
        title=title,
        description=description,
        status=status,
        module_name=module_name,
        priority=priority,
        source_document_ids=source_document_ids,
        content_json=content_json,
    )
    session.add(row)
    session.flush()
    return row


def list_test_cases(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    status: str | None,
    batch_id: str | None,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[TestCaseRecord], int]:
    base_stmt = select(TestCaseRecord)
    if project_id is not None:
        base_stmt = base_stmt.where(TestCaseRecord.project_id == project_id)
    if isinstance(status, str) and status.strip():
        base_stmt = base_stmt.where(TestCaseRecord.status == status.strip())
    if isinstance(batch_id, str) and batch_id.strip():
        base_stmt = base_stmt.where(TestCaseRecord.batch_id == batch_id.strip())
    if isinstance(query, str) and query.strip():
        pattern = f"%{query.strip()}%"
        base_stmt = base_stmt.where(
            or_(
                TestCaseRecord.title.ilike(pattern),
                TestCaseRecord.description.ilike(pattern),
                TestCaseRecord.module_name.ilike(pattern),
                TestCaseRecord.case_id.ilike(pattern),
            )
        )
    stmt = base_stmt.order_by(desc(TestCaseRecord.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def get_test_case(session: Session, test_case_id: uuid.UUID) -> TestCaseRecord | None:
    return session.get(TestCaseRecord, test_case_id)


def update_test_case(
    session: Session,
    row: TestCaseRecord,
    *,
    title: str | None,
    description: str | None,
    status: str | None,
    module_name: str | None,
    priority: str | None,
    source_document_ids: list[str] | None,
    content_json: dict | None,
) -> TestCaseRecord:
    if title is not None:
        row.title = title
    if description is not None:
        row.description = description
    if status is not None:
        row.status = status
    if module_name is not None:
        row.module_name = module_name
    if priority is not None:
        row.priority = priority
    if source_document_ids is not None:
        row.source_document_ids = source_document_ids
    if content_json is not None:
        row.content_json = content_json
    session.flush()
    return row


def delete_test_case(session: Session, row: TestCaseRecord) -> None:
    session.delete(row)
    session.flush()


def get_test_case_overview(
    session: Session,
    *,
    project_id: uuid.UUID | None,
) -> dict[str, object]:
    documents_stmt = select(func.count()).select_from(TestCaseDocument)
    parsed_stmt = select(func.count()).select_from(TestCaseDocument).where(
        TestCaseDocument.parse_status == "parsed"
    )
    failed_stmt = select(func.count()).select_from(TestCaseDocument).where(
        TestCaseDocument.parse_status == "failed"
    )
    cases_stmt = select(func.count()).select_from(TestCaseRecord)
    latest_document_stmt = select(TestCaseDocument).order_by(
        desc(TestCaseDocument.created_at),
        desc(TestCaseDocument.id),
    )
    latest_case_stmt = select(TestCaseRecord).order_by(
        desc(TestCaseRecord.updated_at),
        desc(TestCaseRecord.id),
    )

    if project_id is not None:
        documents_stmt = documents_stmt.where(TestCaseDocument.project_id == project_id)
        parsed_stmt = parsed_stmt.where(TestCaseDocument.project_id == project_id)
        failed_stmt = failed_stmt.where(TestCaseDocument.project_id == project_id)
        cases_stmt = cases_stmt.where(TestCaseRecord.project_id == project_id)
        latest_document_stmt = latest_document_stmt.where(TestCaseDocument.project_id == project_id)
        latest_case_stmt = latest_case_stmt.where(TestCaseRecord.project_id == project_id)

    latest_document = session.scalar(latest_document_stmt.limit(1))
    latest_case = session.scalar(latest_case_stmt.limit(1))
    latest_batch_id: str | None = None
    latest_activity_at: datetime | None = None

    if latest_document is not None:
        latest_batch_id = latest_document.batch_id
        latest_activity_at = latest_document.created_at
    if latest_case is not None and (
        latest_activity_at is None or latest_case.updated_at >= latest_activity_at
    ):
        latest_batch_id = latest_case.batch_id
        latest_activity_at = latest_case.updated_at

    return {
        "documents_total": int(session.scalar(documents_stmt) or 0),
        "parsed_documents_total": int(session.scalar(parsed_stmt) or 0),
        "failed_documents_total": int(session.scalar(failed_stmt) or 0),
        "test_cases_total": int(session.scalar(cases_stmt) or 0),
        "latest_batch_id": latest_batch_id,
        "latest_activity_at": latest_activity_at,
    }


def list_test_case_batches(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, object]], int]:
    documents_stmt = (
        select(
            TestCaseDocument.batch_id,
            func.count().label("documents_count"),
            func.max(TestCaseDocument.created_at).label("latest_document_at"),
        )
        .where(TestCaseDocument.batch_id.is_not(None))
        .group_by(TestCaseDocument.batch_id)
    )
    parse_summary_stmt = (
        select(
            TestCaseDocument.batch_id,
            TestCaseDocument.parse_status,
            func.count().label("status_count"),
        )
        .where(TestCaseDocument.batch_id.is_not(None))
        .group_by(TestCaseDocument.batch_id, TestCaseDocument.parse_status)
    )
    cases_stmt = (
        select(
            TestCaseRecord.batch_id,
            func.count().label("test_cases_count"),
            func.max(TestCaseRecord.updated_at).label("latest_case_at"),
        )
        .where(TestCaseRecord.batch_id.is_not(None))
        .group_by(TestCaseRecord.batch_id)
    )

    if project_id is not None:
        documents_stmt = documents_stmt.where(TestCaseDocument.project_id == project_id)
        parse_summary_stmt = parse_summary_stmt.where(TestCaseDocument.project_id == project_id)
        cases_stmt = cases_stmt.where(TestCaseRecord.project_id == project_id)

    batches: dict[str, dict[str, object]] = {}
    for row in session.execute(documents_stmt):
        batch_id = str(row.batch_id or "").strip()
        if not batch_id:
            continue
        batches[batch_id] = {
            "batch_id": batch_id,
            "documents_count": int(row.documents_count or 0),
            "test_cases_count": 0,
            "latest_created_at": row.latest_document_at,
            "parse_status_summary": {},
        }

    for row in session.execute(parse_summary_stmt):
        batch_id = str(row.batch_id or "").strip()
        if not batch_id:
            continue
        entry = batches.setdefault(
            batch_id,
            {
                "batch_id": batch_id,
                "documents_count": 0,
                "test_cases_count": 0,
                "latest_created_at": None,
                "parse_status_summary": {},
            },
        )
        summary = entry["parse_status_summary"]
        if isinstance(summary, dict):
            summary[str(row.parse_status)] = int(row.status_count or 0)

    for row in session.execute(cases_stmt):
        batch_id = str(row.batch_id or "").strip()
        if not batch_id:
            continue
        entry = batches.setdefault(
            batch_id,
            {
                "batch_id": batch_id,
                "documents_count": 0,
                "test_cases_count": 0,
                "latest_created_at": None,
                "parse_status_summary": {},
            },
        )
        entry["test_cases_count"] = int(row.test_cases_count or 0)
        latest_created_at = entry.get("latest_created_at")
        latest_case_at = row.latest_case_at
        if latest_case_at is not None and (
            latest_created_at is None or latest_case_at >= latest_created_at
        ):
            entry["latest_created_at"] = latest_case_at

    ordered = sorted(
        batches.values(),
        key=lambda item: (
            item.get("latest_created_at") is not None,
            item.get("latest_created_at").isoformat()
            if item.get("latest_created_at") is not None
            else "",
            item.get("batch_id") or "",
        ),
        reverse=True,
    )
    total = len(ordered)
    return ordered[offset : offset + limit], total
