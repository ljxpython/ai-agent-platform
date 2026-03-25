from __future__ import annotations

from app.db.access import (
    create_use_case,
    delete_use_case,
    get_usecase_workflow,
    get_use_case,
    list_use_cases,
    parse_uuid,
    update_use_case,
)
from app.db.models import UsecaseWorkflowSnapshot
from app.db.session import session_scope
from app.schemas.usecases import CreateUseCaseRequest, UpdateUseCaseRequest
from fastapi import APIRouter, HTTPException, Query, Request

from app.api.common import require_db_session_factory

router = APIRouter(prefix="/use-cases", tags=["usecase-generation"])


def _serialize_use_case(row) -> dict[str, object]:
    return {
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
    }


@router.get("")
async def list_all_use_cases(
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
        rows, total = list_use_cases(
            session,
            project_id=project_uuid,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {"items": [_serialize_use_case(row) for row in rows], "total": total}


@router.post("")
async def create_new_use_case(request: Request, payload: CreateUseCaseRequest):
    project_uuid = parse_uuid(payload.project_id)
    workflow_uuid = parse_uuid(payload.workflow_id) if payload.workflow_id else None
    snapshot_uuid = parse_uuid(payload.snapshot_id) if payload.snapshot_id else None
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    if payload.workflow_id and workflow_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_workflow_id")
    if payload.snapshot_id and snapshot_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_snapshot_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        if workflow_uuid is not None and get_usecase_workflow(session, workflow_uuid) is None:
            raise HTTPException(status_code=404, detail="workflow_not_found")
        snapshot = None
        if snapshot_uuid is not None:
            snapshot = session.get(UsecaseWorkflowSnapshot, snapshot_uuid)
            if snapshot is None:
                raise HTTPException(status_code=404, detail="snapshot_not_found")
            if workflow_uuid is not None and snapshot.workflow_id != workflow_uuid:
                raise HTTPException(status_code=400, detail="snapshot_workflow_mismatch")
            if workflow_uuid is None:
                workflow_uuid = snapshot.workflow_id
        row = create_use_case(
            session,
            project_id=project_uuid,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            workflow_id=workflow_uuid,
            snapshot_id=snapshot_uuid,
            content_json=payload.content_json,
        )
        return _serialize_use_case(row)


@router.get("/{use_case_id}")
async def get_single_use_case(request: Request, use_case_id: str):
    use_case_uuid = parse_uuid(use_case_id)
    if use_case_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_use_case_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_use_case(session, use_case_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="use_case_not_found")
        return _serialize_use_case(row)


@router.patch("/{use_case_id}")
async def patch_use_case(request: Request, use_case_id: str, payload: UpdateUseCaseRequest):
    use_case_uuid = parse_uuid(use_case_id)
    if use_case_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_use_case_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_use_case(session, use_case_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="use_case_not_found")
        row = update_use_case(
            session,
            row,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            content_json=payload.content_json,
        )
        return _serialize_use_case(row)


@router.delete("/{use_case_id}")
async def remove_use_case(request: Request, use_case_id: str):
    use_case_uuid = parse_uuid(use_case_id)
    if use_case_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_use_case_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_use_case(session, use_case_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="use_case_not_found")
        delete_use_case(session, row)
        return {"ok": True}
