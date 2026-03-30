from __future__ import annotations

from app.api.common import require_db_session_factory
from app.db.access import (
    create_test_case_document,
    get_test_case_document,
    list_test_case_documents,
    parse_uuid,
)
from app.db.session import session_scope
from app.schemas.test_case_service import (
    CreateTestCaseDocumentRequest,
    TestCaseDocumentListResponse,
    TestCaseDocumentResponse,
)
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/documents", tags=["test-case-service"])


def _serialize_document(row) -> dict[str, object]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "batch_id": row.batch_id,
        "idempotency_key": row.idempotency_key,
        "filename": row.filename,
        "content_type": row.content_type,
        "storage_path": row.storage_path,
        "source_kind": row.source_kind,
        "parse_status": row.parse_status,
        "summary_for_model": row.summary_for_model,
        "parsed_text": row.parsed_text,
        "structured_data": row.structured_data,
        "provenance": row.provenance,
        "confidence": row.confidence,
        "error": row.error,
        "created_at": row.created_at.isoformat(),
    }


@router.post("", response_model=TestCaseDocumentResponse)
async def create_document(request: Request, payload: CreateTestCaseDocumentRequest):
    project_id = parse_uuid(payload.project_id)
    if project_id is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = create_test_case_document(
            session,
            project_id=project_id,
            batch_id=payload.batch_id,
            idempotency_key=payload.idempotency_key,
            filename=payload.filename,
            content_type=payload.content_type,
            storage_path=payload.storage_path,
            source_kind=payload.source_kind,
            parse_status=payload.parse_status,
            summary_for_model=payload.summary_for_model,
            parsed_text=payload.parsed_text,
            structured_data=payload.structured_data,
            provenance=payload.provenance,
            confidence=payload.confidence,
            error=payload.error,
        )
        return _serialize_document(row)


@router.get("", response_model=TestCaseDocumentListResponse)
async def list_documents(
    request: Request,
    project_id: str | None = Query(None),
    batch_id: str | None = Query(None),
    parse_status: str | None = Query(None),
    query: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    project_uuid = parse_uuid(project_id) if project_id else None
    if project_id and project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        rows, total = list_test_case_documents(
            session,
            project_id=project_uuid,
            batch_id=batch_id,
            parse_status=parse_status,
            query=query,
            limit=limit,
            offset=offset,
        )
        return {"items": [_serialize_document(row) for row in rows], "total": total}


@router.get("/{document_id}", response_model=TestCaseDocumentResponse)
async def get_document(request: Request, document_id: str):
    document_uuid = parse_uuid(document_id)
    if document_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_document_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_test_case_document(session, document_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        return _serialize_document(row)
