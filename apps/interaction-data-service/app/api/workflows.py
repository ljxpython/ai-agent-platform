from __future__ import annotations

from app.db.access import (
    create_requirement_document,
    create_review_report,
    create_usecase_workflow,
    create_usecase_workflow_snapshot,
    get_usecase_workflow,
    list_usecase_workflows,
    list_workflow_snapshots,
    mark_workflow_approved,
    parse_uuid,
    persist_workflow_as_use_case,
)
from app.db.session import session_scope
from app.schemas.workflows import (
    CreateRequirementDocumentRequest,
    CreateWorkflowRequest,
    CreateWorkflowReviewRequest,
    CreateWorkflowSnapshotRequest,
)
from fastapi import APIRouter, HTTPException, Query, Request

from .common import require_db_session_factory

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _serialize_workflow(row) -> dict[str, object]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "title": row.title,
        "summary": row.summary,
        "status": row.status,
        "latest_snapshot_id": str(row.latest_snapshot_id) if row.latest_snapshot_id else None,
        "persistable": row.persistable == "true",
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_snapshot(row) -> dict[str, object]:
    return {
        "id": str(row.id),
        "workflow_id": str(row.workflow_id),
        "version": row.version,
        "status": row.status,
        "review_summary": row.review_summary,
        "deficiency_count": row.deficiency_count,
        "payload_json": row.payload_json,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/documents")
async def create_document(request: Request, payload: CreateRequirementDocumentRequest):
    project_id = parse_uuid(payload.project_id)
    if project_id is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = create_requirement_document(
            session,
            project_id=project_id,
            filename=payload.filename,
            content_type=payload.content_type,
            storage_path=payload.storage_path,
        )
        return {"id": str(row.id), "project_id": str(row.project_id), "filename": row.filename}


@router.post("")
async def create_workflow(request: Request, payload: CreateWorkflowRequest):
    project_id = parse_uuid(payload.project_id)
    requirement_document_id = (
        parse_uuid(payload.requirement_document_id) if payload.requirement_document_id else None
    )
    if project_id is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = create_usecase_workflow(
            session,
            project_id=project_id,
            title=payload.title,
            summary=payload.summary,
            requirement_document_id=requirement_document_id,
            workflow_type=payload.workflow_type,
            agent_key=payload.agent_key,
            metadata_json=payload.metadata_json,
        )
        return _serialize_workflow(row)


@router.get("")
async def list_workflows(
    request: Request,
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    project_uuid = parse_uuid(project_id) if project_id else None
    if project_id and project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        rows, total = list_usecase_workflows(
            session,
            project_id=project_uuid,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {"items": [_serialize_workflow(row) for row in rows], "total": total}


@router.get("/{workflow_id}")
async def get_workflow(request: Request, workflow_id: str):
    workflow_uuid = parse_uuid(workflow_id)
    if workflow_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_workflow_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_usecase_workflow(session, workflow_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="workflow_not_found")
        return _serialize_workflow(row)


@router.get("/{workflow_id}/snapshots")
async def get_workflow_snapshots(request: Request, workflow_id: str):
    workflow_uuid = parse_uuid(workflow_id)
    if workflow_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_workflow_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_usecase_workflow(session, workflow_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="workflow_not_found")
        snapshots = list_workflow_snapshots(session, workflow_uuid)
        return {"items": [_serialize_snapshot(item) for item in snapshots], "total": len(snapshots)}


@router.post("/{workflow_id}/snapshots")
async def create_snapshot(request: Request, workflow_id: str, payload: CreateWorkflowSnapshotRequest):
    workflow_uuid = parse_uuid(workflow_id)
    if workflow_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_workflow_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        workflow = get_usecase_workflow(session, workflow_uuid)
        if workflow is None:
            raise HTTPException(status_code=404, detail="workflow_not_found")
        row = create_usecase_workflow_snapshot(
            session,
            workflow=workflow,
            status=payload.status,
            review_summary=payload.review_summary,
            deficiency_count=payload.deficiency_count,
            persistable=payload.persistable,
            payload_json=payload.payload_json,
        )
        return _serialize_snapshot(row)


@router.post("/{workflow_id}/review")
async def create_review(request: Request, workflow_id: str, payload: CreateWorkflowReviewRequest):
    workflow_uuid = parse_uuid(workflow_id)
    snapshot_uuid = parse_uuid(payload.snapshot_id)
    if workflow_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_workflow_id")
    if snapshot_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_snapshot_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        workflow = get_usecase_workflow(session, workflow_uuid)
        if workflow is None:
            raise HTTPException(status_code=404, detail="workflow_not_found")
        row = create_review_report(
            session,
            workflow_id=workflow_uuid,
            snapshot_id=snapshot_uuid,
            summary=payload.summary,
            payload_json=payload.payload_json,
        )
        workflow.status = "reviewed"
        session.flush()
        return {"id": str(row.id), "status": row.status, "summary": row.summary}


@router.post("/{workflow_id}/approve")
async def approve_workflow(request: Request, workflow_id: str):
    workflow_uuid = parse_uuid(workflow_id)
    if workflow_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_workflow_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        workflow = get_usecase_workflow(session, workflow_uuid)
        if workflow is None:
            raise HTTPException(status_code=404, detail="workflow_not_found")
        row = mark_workflow_approved(session, workflow)
        return _serialize_workflow(row)


@router.post("/{workflow_id}/persist")
async def persist_workflow(request: Request, workflow_id: str):
    workflow_uuid = parse_uuid(workflow_id)
    if workflow_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_workflow_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        workflow = get_usecase_workflow(session, workflow_uuid)
        if workflow is None:
            raise HTTPException(status_code=404, detail="workflow_not_found")
        if workflow.status != "approved_for_persistence":
            raise HTTPException(status_code=409, detail="workflow_not_ready_for_persist")
        try:
            row = persist_workflow_as_use_case(session, workflow)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "workflow": _serialize_workflow(workflow),
            "use_case": {
                "id": str(row.id),
                "project_id": str(row.project_id),
                "workflow_id": str(row.workflow_id) if row.workflow_id else None,
                "snapshot_id": str(row.snapshot_id) if row.snapshot_id else None,
                "title": row.title,
                "description": row.description,
                "status": row.status,
                "content_json": row.content_json,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            },
        }
