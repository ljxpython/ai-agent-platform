from __future__ import annotations

from app.api.common import require_db_session_factory
from app.db.access import (
    create_test_case,
    delete_test_case,
    get_test_case,
    list_test_cases,
    parse_uuid,
    update_test_case,
)
from app.db.session import session_scope
from app.schemas.test_case_service import (
    CreateTestCaseRequest,
    TestCaseListResponse,
    TestCaseResponse,
    UpdateTestCaseRequest,
)
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/test-cases", tags=["test-case-service"])


def _serialize_test_case(row) -> dict[str, object]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "batch_id": row.batch_id,
        "case_id": row.case_id,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "module_name": row.module_name,
        "priority": row.priority,
        "source_document_ids": row.source_document_ids,
        "content_json": row.content_json,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("", response_model=TestCaseResponse)
async def create_one_test_case(request: Request, payload: CreateTestCaseRequest):
    project_id = parse_uuid(payload.project_id)
    if project_id is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = create_test_case(
            session,
            project_id=project_id,
            batch_id=payload.batch_id,
            case_id=payload.case_id,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            module_name=payload.module_name,
            priority=payload.priority,
            source_document_ids=payload.source_document_ids,
            content_json=payload.content_json,
        )
        return _serialize_test_case(row)


@router.get("", response_model=TestCaseListResponse)
async def list_all_test_cases(
    request: Request,
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    batch_id: str | None = Query(None),
    query: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    project_uuid = parse_uuid(project_id) if project_id else None
    if project_id and project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        rows, total = list_test_cases(
            session,
            project_id=project_uuid,
            status=status,
            batch_id=batch_id,
            query=query,
            limit=limit,
            offset=offset,
        )
        return {"items": [_serialize_test_case(row) for row in rows], "total": total}


@router.get("/{test_case_id}", response_model=TestCaseResponse)
async def get_single_test_case(request: Request, test_case_id: str):
    test_case_uuid = parse_uuid(test_case_id)
    if test_case_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_test_case_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_test_case(session, test_case_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="test_case_not_found")
        return _serialize_test_case(row)


@router.patch("/{test_case_id}", response_model=TestCaseResponse)
async def patch_test_case(request: Request, test_case_id: str, payload: UpdateTestCaseRequest):
    test_case_uuid = parse_uuid(test_case_id)
    if test_case_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_test_case_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_test_case(session, test_case_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="test_case_not_found")
        row = update_test_case(
            session,
            row,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            module_name=payload.module_name,
            priority=payload.priority,
            source_document_ids=payload.source_document_ids,
            content_json=payload.content_json,
        )
        return _serialize_test_case(row)


@router.delete("/{test_case_id}")
async def remove_test_case(request: Request, test_case_id: str):
    test_case_uuid = parse_uuid(test_case_id)
    if test_case_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_test_case_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_test_case(session, test_case_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="test_case_not_found")
        delete_test_case(session, row)
        return {"ok": True}
