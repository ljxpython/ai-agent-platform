from __future__ import annotations

import mimetypes
from collections.abc import Mapping
from urllib.parse import quote

from app.api.common import require_db_session_factory
from app.db.access import (
    create_test_case_document,
    get_test_case_document,
    list_test_cases_for_document,
    list_test_case_documents,
    parse_uuid,
)
from app.db.session import session_scope
from app.schemas.test_case_service import (
    TestCaseDocumentAssetResponse,
    CreateTestCaseDocumentRequest,
    TestCaseDocumentListResponse,
    TestCaseDocumentRelationsResponse,
    TestCaseDocumentResponse,
)
from app.services.document_assets import (
    resolve_document_asset_path,
    write_document_asset,
)
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/documents", tags=["test-case-service"])


def _build_content_disposition(*, filename: str, inline: bool) -> str:
    disposition = "inline" if inline else "attachment"
    fallback_name = "document.pdf"
    encoded = quote((filename or fallback_name).strip() or fallback_name)
    return (
        f"{disposition}; filename=\"{fallback_name}\"; "
        f"filename*=UTF-8''{encoded}"
    )


def _serialize_document(row) -> dict[str, object]:
    content_type = _resolve_content_type_from_document_row(row)
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "batch_id": row.batch_id,
        "idempotency_key": row.idempotency_key,
        "filename": row.filename,
        "content_type": content_type,
        "storage_path": _resolve_storage_path_from_document_row(row) or None,
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


def _serialize_related_case(row) -> dict[str, object]:
    return {
        "id": str(row.id),
        "case_id": row.case_id,
        "title": row.title,
        "status": row.status,
        "batch_id": row.batch_id,
    }


def _runtime_meta_from_document(document: Mapping[str, object]) -> dict[str, object]:
    provenance = document.get("provenance")
    if not isinstance(provenance, Mapping):
        return {}
    runtime_meta = provenance.get("runtime")
    if not isinstance(runtime_meta, Mapping):
        return {}
    return {str(key): value for key, value in runtime_meta.items()}


def _resolve_storage_path_from_document_row(row) -> str:
    storage_path = (row.storage_path or "").strip()
    if storage_path:
        return storage_path
    asset_meta = _resolve_asset_meta_from_document_row(row)
    if not isinstance(asset_meta, Mapping):
        return ""
    asset_storage_path = asset_meta.get("storage_path")
    if asset_storage_path is None:
        return ""
    return str(asset_storage_path).strip()


def _resolve_asset_meta_from_document_row(row) -> Mapping[str, object]:
    provenance = row.provenance if isinstance(row.provenance, Mapping) else {}
    asset_meta = provenance.get("asset")
    if not isinstance(asset_meta, Mapping):
        return {}
    return asset_meta


def _resolve_content_type_from_document_row(row) -> str:
    content_type = (row.content_type or "").strip()
    if content_type:
        return content_type

    asset_meta = _resolve_asset_meta_from_document_row(row)
    for key in ("content_type", "mime_type"):
        value = asset_meta.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized

    provenance = row.provenance if isinstance(row.provenance, Mapping) else {}
    for key in ("mime_type", "content_type"):
        value = provenance.get(key)
        if value is None:
            continue
        normalized = str(value).strip()
        if normalized:
            return normalized

    guessed, _ = mimetypes.guess_type((row.filename or "").strip())
    return guessed or "application/octet-stream"


@router.post("/assets", response_model=TestCaseDocumentAssetResponse)
async def create_document_asset(
    request: Request,
    project_id: str = Form(...),
    batch_id: str | None = Form(default=None),
    idempotency_key: str | None = Form(default=None),
    filename: str | None = Form(default=None),
    content_type: str | None = Form(default=None),
    file: UploadFile = File(...),
):
    if parse_uuid(project_id) is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="empty_document_asset")
    effective_filename = (filename or file.filename or "document").strip() or "document"
    effective_content_type = (
        (content_type or file.content_type or "application/octet-stream").strip()
        or "application/octet-stream"
    )
    asset_key = (idempotency_key or effective_filename).strip() or "document"
    stored = write_document_asset(
        root_dir=request.app.state.document_asset_root,
        project_id=project_id,
        batch_id=batch_id,
        asset_key=asset_key,
        filename=effective_filename,
        content_type=effective_content_type,
        payload=payload,
    )
    return stored


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
    limit: int = Query(50, ge=1, le=500),
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


@router.get("/{document_id}/relations", response_model=TestCaseDocumentRelationsResponse)
async def get_document_relations(request: Request, document_id: str):
    document_uuid = parse_uuid(document_id)
    if document_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_document_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_test_case_document(session, document_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        document_payload = _serialize_document(row)
        related_cases = list_test_cases_for_document(
            session,
            project_id=row.project_id,
            document_id=document_id,
        )
        return {
            "document": document_payload,
            "runtime_meta": _runtime_meta_from_document(document_payload),
            "related_cases": [_serialize_related_case(item) for item in related_cases],
            "related_cases_count": len(related_cases),
        }


def _build_document_asset_response(
    request: Request,
    *,
    document_id: str,
    inline: bool,
) -> FileResponse:
    document_uuid = parse_uuid(document_id)
    if document_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_document_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_test_case_document(session, document_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        storage_path = _resolve_storage_path_from_document_row(row)
        if not storage_path:
            raise HTTPException(status_code=404, detail="document_asset_not_found")
        try:
            asset_path = resolve_document_asset_path(
                request.app.state.document_asset_root,
                storage_path,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="document_asset_not_found") from exc
        response = FileResponse(
            asset_path,
            media_type=row.content_type or "application/octet-stream",
            filename=row.filename,
        )
        response.headers["Content-Disposition"] = _build_content_disposition(
            filename=row.filename,
            inline=inline,
        )
        return response


@router.get("/{document_id}/preview")
async def preview_document_asset(request: Request, document_id: str):
    return _build_document_asset_response(
        request,
        document_id=document_id,
        inline=True,
    )


@router.get("/{document_id}/download")
async def download_document_asset(request: Request, document_id: str):
    return _build_document_asset_response(
        request,
        document_id=document_id,
        inline=False,
    )


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
