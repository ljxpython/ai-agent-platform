from __future__ import annotations

from typing import Any

from app.api.management.common import require_project_role
from app.api.management.schemas import (
    CreateTestCaseRecordRequest,
    UpdateTestCaseRecordRequest,
)
from app.db.access import parse_uuid
from app.services.interaction_data_service import InteractionDataService
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(tags=["management-testcase"])


def _parse_project_id(project_id: str):
    project_uuid = parse_uuid(project_id)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    return project_uuid


def _cleanup_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _payload_to_dict(payload: Any) -> dict[str, Any]:
    return payload.model_dump(exclude_none=True) if hasattr(payload, "model_dump") else dict(payload)


@router.get("/projects/{project_id}/testcase/overview")
async def get_testcase_overview(request: Request, project_id: str) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor", "executor"})
    service = InteractionDataService(request)
    return await service.get_overview(project_id)


@router.get("/projects/{project_id}/testcase/batches")
async def list_testcase_batches(
    request: Request,
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor", "executor"})
    service = InteractionDataService(request)
    return await service.list_batches(project_id, limit=limit, offset=offset)


@router.get("/projects/{project_id}/testcase/cases")
async def list_testcase_cases(
    request: Request,
    project_id: str,
    status: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor", "executor"})
    service = InteractionDataService(request)
    return await service.list_cases(
        project_id,
        status=_cleanup_optional_text(status),
        batch_id=_cleanup_optional_text(batch_id),
        query=_cleanup_optional_text(query),
        limit=limit,
        offset=offset,
    )


@router.get("/projects/{project_id}/testcase/cases/{case_id}")
async def get_testcase_case(request: Request, project_id: str, case_id: str) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor", "executor"})
    service = InteractionDataService(request)
    return await service.get_case(project_id, case_id)


@router.post("/projects/{project_id}/testcase/cases")
async def create_testcase_case(
    request: Request,
    project_id: str,
    payload: CreateTestCaseRecordRequest,
) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor"})
    service = InteractionDataService(request)
    return await service.create_case(project_id, _payload_to_dict(payload))


@router.patch("/projects/{project_id}/testcase/cases/{case_id}")
async def update_testcase_case(
    request: Request,
    project_id: str,
    case_id: str,
    payload: UpdateTestCaseRecordRequest,
) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor"})
    service = InteractionDataService(request)
    return await service.update_case(project_id, case_id, _payload_to_dict(payload))


@router.delete("/projects/{project_id}/testcase/cases/{case_id}")
async def delete_testcase_case(request: Request, project_id: str, case_id: str) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor"})
    service = InteractionDataService(request)
    return await service.delete_case(project_id, case_id)


@router.get("/projects/{project_id}/testcase/documents")
async def list_testcase_documents(
    request: Request,
    project_id: str,
    batch_id: str | None = Query(default=None),
    parse_status: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor", "executor"})
    service = InteractionDataService(request)
    return await service.list_documents(
        project_id,
        batch_id=_cleanup_optional_text(batch_id),
        parse_status=_cleanup_optional_text(parse_status),
        query=_cleanup_optional_text(query),
        limit=limit,
        offset=offset,
    )


@router.get("/projects/{project_id}/testcase/documents/{document_id}")
async def get_testcase_document(
    request: Request,
    project_id: str,
    document_id: str,
) -> dict[str, Any]:
    project_uuid = _parse_project_id(project_id)
    require_project_role(request, project_uuid, allowed_roles={"admin", "editor", "executor"})
    service = InteractionDataService(request)
    return await service.get_document(project_id, document_id)
