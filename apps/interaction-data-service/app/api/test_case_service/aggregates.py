from __future__ import annotations

from app.api.common import require_db_session_factory
from app.db.access import get_test_case_overview, list_test_case_batches, parse_uuid
from app.db.session import session_scope
from app.schemas.test_case_service import (
    TestCaseBatchListResponse,
    TestCaseOverviewResponse,
)
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(tags=["test-case-service"])


@router.get("/overview", response_model=TestCaseOverviewResponse)
async def get_overview(
    request: Request,
    project_id: str | None = Query(None),
):
    project_uuid = parse_uuid(project_id) if project_id else None
    if project_id and project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        overview = get_test_case_overview(session, project_id=project_uuid)
        return {
            "project_id": project_id,
            "documents_total": overview["documents_total"],
            "parsed_documents_total": overview["parsed_documents_total"],
            "failed_documents_total": overview["failed_documents_total"],
            "test_cases_total": overview["test_cases_total"],
            "latest_batch_id": overview["latest_batch_id"],
            "latest_activity_at": (
                overview["latest_activity_at"].isoformat()
                if overview["latest_activity_at"] is not None
                else None
            ),
        }


@router.get("/batches", response_model=TestCaseBatchListResponse)
async def list_batches(
    request: Request,
    project_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    project_uuid = parse_uuid(project_id) if project_id else None
    if project_id and project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        rows, total = list_test_case_batches(
            session,
            project_id=project_uuid,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [
                {
                    "batch_id": str(item["batch_id"]),
                    "documents_count": int(item["documents_count"]),
                    "test_cases_count": int(item["test_cases_count"]),
                    "latest_created_at": (
                        item["latest_created_at"].isoformat()
                        if item.get("latest_created_at") is not None
                        else None
                    ),
                    "parse_status_summary": dict(item.get("parse_status_summary") or {}),
                }
                for item in rows
            ],
            "total": total,
        }
