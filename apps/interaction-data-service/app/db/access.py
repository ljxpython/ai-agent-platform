from __future__ import annotations

import uuid

from app.db.models import (
    RequirementDocument,
    UseCase,
    UsecaseReviewReport,
    UsecaseWorkflow,
    UsecaseWorkflowSnapshot,
)
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def create_requirement_document(
    session: Session,
    *,
    project_id: uuid.UUID,
    filename: str,
    content_type: str,
    storage_path: str | None,
) -> RequirementDocument:
    row = RequirementDocument(
        project_id=project_id,
        filename=filename,
        content_type=content_type,
        storage_path=storage_path,
    )
    session.add(row)
    session.flush()
    return row


def create_usecase_workflow(
    session: Session,
    *,
    project_id: uuid.UUID,
    title: str,
    summary: str,
    requirement_document_id: uuid.UUID | None,
    workflow_type: str,
    agent_key: str,
    metadata_json: dict,
) -> UsecaseWorkflow:
    row = UsecaseWorkflow(
        project_id=project_id,
        title=title,
        summary=summary,
        requirement_document_id=requirement_document_id,
        workflow_type=workflow_type,
        agent_key=agent_key,
        metadata_json=metadata_json,
    )
    session.add(row)
    session.flush()
    return row


def list_usecase_workflows(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[UsecaseWorkflow], int]:
    base_stmt = select(UsecaseWorkflow)
    if project_id is not None:
        base_stmt = base_stmt.where(UsecaseWorkflow.project_id == project_id)
    if isinstance(status, str) and status.strip():
        base_stmt = base_stmt.where(UsecaseWorkflow.status == status.strip())
    stmt = base_stmt.order_by(desc(UsecaseWorkflow.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def get_usecase_workflow(session: Session, workflow_id: uuid.UUID) -> UsecaseWorkflow | None:
    return session.get(UsecaseWorkflow, workflow_id)


def next_snapshot_version(session: Session, workflow_id: uuid.UUID) -> int:
    stmt = select(func.max(UsecaseWorkflowSnapshot.version)).where(
        UsecaseWorkflowSnapshot.workflow_id == workflow_id
    )
    latest = session.scalar(stmt)
    return int(latest or 0) + 1


def create_usecase_workflow_snapshot(
    session: Session,
    *,
    workflow: UsecaseWorkflow,
    status: str,
    review_summary: str,
    deficiency_count: int,
    persistable: bool,
    payload_json: dict,
) -> UsecaseWorkflowSnapshot:
    row = UsecaseWorkflowSnapshot(
        workflow_id=workflow.id,
        version=next_snapshot_version(session, workflow.id),
        status=status,
        review_summary=review_summary,
        deficiency_count=deficiency_count,
        payload_json=payload_json,
    )
    session.add(row)
    session.flush()
    workflow.latest_snapshot_id = row.id
    workflow.status = status
    workflow.persistable = "true" if persistable else "false"
    session.flush()
    return row


def list_workflow_snapshots(
    session: Session, workflow_id: uuid.UUID
) -> list[UsecaseWorkflowSnapshot]:
    stmt = (
        select(UsecaseWorkflowSnapshot)
        .where(UsecaseWorkflowSnapshot.workflow_id == workflow_id)
        .order_by(desc(UsecaseWorkflowSnapshot.version))
    )
    return list(session.scalars(stmt).all())


def create_review_report(
    session: Session,
    *,
    workflow_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    summary: str,
    payload_json: dict,
) -> UsecaseReviewReport:
    row = UsecaseReviewReport(
        workflow_id=workflow_id,
        snapshot_id=snapshot_id,
        summary=summary,
        payload_json=payload_json,
    )
    session.add(row)
    session.flush()
    return row


def mark_workflow_approved(session: Session, workflow: UsecaseWorkflow) -> UsecaseWorkflow:
    workflow.status = "approved_for_persistence"
    workflow.persistable = "true"
    session.flush()
    return workflow


def create_use_case(
    session: Session,
    *,
    project_id: uuid.UUID,
    title: str,
    description: str,
    status: str,
    workflow_id: uuid.UUID | None,
    snapshot_id: uuid.UUID | None,
    content_json: dict,
) -> UseCase:
    row = UseCase(
        project_id=project_id,
        title=title,
        description=description,
        status=status,
        workflow_id=workflow_id,
        snapshot_id=snapshot_id,
        content_json=content_json,
    )
    session.add(row)
    session.flush()
    return row


def persist_workflow_as_use_case(
    session: Session, workflow: UsecaseWorkflow
) -> UseCase:
    if workflow.latest_snapshot_id is None:
        raise ValueError("workflow_has_no_snapshot")

    snapshot = session.get(UsecaseWorkflowSnapshot, workflow.latest_snapshot_id)
    if snapshot is None:
        raise ValueError("workflow_snapshot_not_found")

    payload = snapshot.payload_json or {}
    title = str(payload.get("title") or workflow.title).strip() or workflow.title
    description = str(payload.get("description") or workflow.summary).strip()

    row = create_use_case(
        session,
        project_id=workflow.project_id,
        title=title,
        description=description,
        status="active",
        workflow_id=workflow.id,
        snapshot_id=snapshot.id,
        content_json=payload,
    )
    workflow.status = "persisted"
    session.flush()
    return row


def list_use_cases(
    session: Session,
    *,
    project_id: uuid.UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[UseCase], int]:
    base_stmt = select(UseCase)
    if project_id is not None:
        base_stmt = base_stmt.where(UseCase.project_id == project_id)
    if isinstance(status, str) and status.strip():
        base_stmt = base_stmt.where(UseCase.status == status.strip())
    stmt = base_stmt.order_by(desc(UseCase.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def get_use_case(session: Session, use_case_id: uuid.UUID) -> UseCase | None:
    return session.get(UseCase, use_case_id)


def update_use_case(
    session: Session,
    row: UseCase,
    *,
    title: str | None,
    description: str | None,
    status: str | None,
    content_json: dict | None,
) -> UseCase:
    if title is not None:
        row.title = title
    if description is not None:
        row.description = description
    if status is not None:
        row.status = status
    if content_json is not None:
        row.content_json = content_json
    session.flush()
    return row


def delete_use_case(session: Session, row: UseCase) -> None:
    session.delete(row)
    session.flush()
