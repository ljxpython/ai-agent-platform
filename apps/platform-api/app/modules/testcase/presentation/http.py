from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import sessionmaker

from app.adapters.interaction_data import InteractionDataClient
from app.core.config import Settings
from app.core.context.models import ActorContext
from app.core.schemas import AckResponse
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.testcase.application import (
    CreateTestcaseCaseCommand,
    ExportTestcaseCasesQuery,
    ExportTestcaseDocumentsQuery,
    GetTestcaseBatchDetailQuery,
    ListTestcaseBatchesQuery,
    ListTestcaseCasesQuery,
    ListTestcaseDocumentsQuery,
    TestcaseService,
    UpdateTestcaseCaseCommand,
)
from app.modules.testcase.application.exporters import (
    build_case_export_content_disposition,
    build_document_export_content_disposition,
)
from app.modules.testcase.domain import (
    TestcaseBatchDetail,
    TestcaseBatchPage,
    TestcaseCase,
    TestcaseCasePage,
    TestcaseDocument,
    TestcaseDocumentPage,
    TestcaseDocumentRelations,
    TestcaseOverview,
    TestcaseRoleView,
)

router = APIRouter(prefix="/api/projects/{project_id}/testcase", tags=["testcase"])


def _bind_project_audit_scope(request: Request, project_id: str) -> None:
    request.state.audit_project_id = project_id


def get_testcase_service(request: Request) -> TestcaseService:
    settings: Settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    upstream = InteractionDataClient(
        base_url=settings.interaction_data_service_url,
        token=settings.interaction_data_service_token,
        timeout_seconds=settings.interaction_data_service_timeout_seconds,
        forwarded_headers={
            "x-request-id": str(getattr(request.state, "request_id", "") or "")
        },
    )
    return TestcaseService(
        session_factory=session_factory,
        upstream=upstream,
    )


@router.get("/overview", response_model=TestcaseOverview)
async def get_testcase_overview(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseOverview:
    _bind_project_audit_scope(request, project_id)
    return await service.get_overview(actor=actor, project_id=project_id)


@router.get("/role", response_model=TestcaseRoleView)
async def get_testcase_role(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseRoleView:
    _bind_project_audit_scope(request, project_id)
    return await service.get_role(actor=actor, project_id=project_id)


@router.get("/batches", response_model=TestcaseBatchPage)
async def list_testcase_batches(
    request: Request,
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseBatchPage:
    _bind_project_audit_scope(request, project_id)
    return await service.list_batches(
        actor=actor,
        project_id=project_id,
        query=ListTestcaseBatchesQuery(limit=limit, offset=offset),
    )


@router.get("/documents", response_model=TestcaseDocumentPage)
async def list_testcase_documents(
    request: Request,
    project_id: str,
    batch_id: str | None = Query(default=None),
    parse_status: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseDocumentPage:
    _bind_project_audit_scope(request, project_id)
    return await service.list_documents(
        actor=actor,
        project_id=project_id,
        query=ListTestcaseDocumentsQuery(
            batch_id=batch_id,
            parse_status=parse_status,
            query=query,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/documents/{document_id}/relations", response_model=TestcaseDocumentRelations)
async def get_testcase_document_relations(
    request: Request,
    project_id: str,
    document_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseDocumentRelations:
    _bind_project_audit_scope(request, project_id)
    return await service.get_document_relations(
        actor=actor,
        project_id=project_id,
        document_id=document_id,
    )


@router.get("/documents/export")
async def export_testcase_documents(
    request: Request,
    project_id: str,
    batch_id: str | None = Query(default=None),
    parse_status: str | None = Query(default=None),
    query: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> StreamingResponse:
    _bind_project_audit_scope(request, project_id)
    filename, media_type, payload = await service.export_documents(
        actor=actor,
        project_id=project_id,
        query=ExportTestcaseDocumentsQuery(
            batch_id=batch_id,
            parse_status=parse_status,
            query=query,
        ),
    )
    return StreamingResponse(
        BytesIO(payload),
        media_type=media_type,
        headers={"Content-Disposition": build_document_export_content_disposition(filename)},
    )


@router.get("/documents/{document_id}", response_model=TestcaseDocument)
async def get_testcase_document(
    request: Request,
    project_id: str,
    document_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseDocument:
    _bind_project_audit_scope(request, project_id)
    return await service.get_document(
        actor=actor,
        project_id=project_id,
        document_id=document_id,
    )


@router.get("/documents/{document_id}/preview")
async def preview_testcase_document(
    request: Request,
    project_id: str,
    document_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> StreamingResponse:
    _bind_project_audit_scope(request, project_id)
    payload, headers = await service.get_document_binary(
        actor=actor,
        project_id=project_id,
        document_id=document_id,
        inline=True,
    )
    response_headers: dict[str, str] = {}
    content_disposition = headers.get("content-disposition")
    if content_disposition:
        response_headers["Content-Disposition"] = content_disposition
    return StreamingResponse(
        BytesIO(payload),
        media_type=headers.get("content-type", "application/octet-stream"),
        headers=response_headers,
    )


@router.get("/documents/{document_id}/download")
async def download_testcase_document(
    request: Request,
    project_id: str,
    document_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> StreamingResponse:
    _bind_project_audit_scope(request, project_id)
    payload, headers = await service.get_document_binary(
        actor=actor,
        project_id=project_id,
        document_id=document_id,
        inline=False,
    )
    response_headers: dict[str, str] = {}
    content_disposition = headers.get("content-disposition")
    if content_disposition:
        response_headers["Content-Disposition"] = content_disposition
    return StreamingResponse(
        BytesIO(payload),
        media_type=headers.get("content-type", "application/octet-stream"),
        headers=response_headers,
    )


@router.get("/cases", response_model=TestcaseCasePage)
async def list_testcase_cases(
    request: Request,
    project_id: str,
    batch_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseCasePage:
    _bind_project_audit_scope(request, project_id)
    return await service.list_cases(
        actor=actor,
        project_id=project_id,
        query=ListTestcaseCasesQuery(
            batch_id=batch_id,
            status=status,
            query=query,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/cases/export")
async def export_testcase_cases(
    request: Request,
    project_id: str,
    batch_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    query: str | None = Query(default=None),
    columns: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> StreamingResponse:
    _bind_project_audit_scope(request, project_id)
    resolved_columns = tuple(
        item.strip() for item in (columns or "").split(",") if item.strip()
    )
    filename, media_type, payload = await service.export_cases(
        actor=actor,
        project_id=project_id,
        query=ExportTestcaseCasesQuery(
            batch_id=batch_id,
            status=status,
            query=query,
            columns=resolved_columns,
        ),
    )
    return StreamingResponse(
        BytesIO(payload),
        media_type=media_type,
        headers={"Content-Disposition": build_case_export_content_disposition(filename)},
    )


@router.get("/cases/{case_id}", response_model=TestcaseCase)
async def get_testcase_case(
    request: Request,
    project_id: str,
    case_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseCase:
    _bind_project_audit_scope(request, project_id)
    return await service.get_case(actor=actor, project_id=project_id, case_id=case_id)


@router.post("/cases", response_model=TestcaseCase)
async def create_testcase_case(
    request: Request,
    project_id: str,
    payload: CreateTestcaseCaseCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseCase:
    _bind_project_audit_scope(request, project_id)
    return await service.create_case(actor=actor, project_id=project_id, command=payload)


@router.patch("/cases/{case_id}", response_model=TestcaseCase)
async def update_testcase_case(
    request: Request,
    project_id: str,
    case_id: str,
    payload: UpdateTestcaseCaseCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseCase:
    _bind_project_audit_scope(request, project_id)
    return await service.update_case(
        actor=actor,
        project_id=project_id,
        case_id=case_id,
        command=payload,
    )


@router.delete("/cases/{case_id}", response_model=AckResponse)
async def delete_testcase_case(
    request: Request,
    project_id: str,
    case_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> AckResponse:
    _bind_project_audit_scope(request, project_id)
    await service.delete_case(actor=actor, project_id=project_id, case_id=case_id)
    return AckResponse()


@router.get("/batches/{batch_id}", response_model=TestcaseBatchDetail)
async def get_testcase_batch_detail(
    request: Request,
    project_id: str,
    batch_id: str,
    document_limit: int = Query(default=100, ge=1, le=500),
    document_offset: int = Query(default=0, ge=0),
    case_limit: int = Query(default=50, ge=1, le=500),
    case_offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: TestcaseService = Depends(get_testcase_service),
) -> TestcaseBatchDetail:
    _bind_project_audit_scope(request, project_id)
    return await service.get_batch_detail(
        actor=actor,
        project_id=project_id,
        batch_id=batch_id,
        query=GetTestcaseBatchDetailQuery(
            document_limit=document_limit,
            document_offset=document_offset,
            case_limit=case_limit,
            case_offset=case_offset,
        ),
    )
