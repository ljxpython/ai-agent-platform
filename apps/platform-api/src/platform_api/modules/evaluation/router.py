import hmac
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import (
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.evaluation import service
from platform_api.modules.evaluation.contracts import (
    AuthorizationBatchBody,
    ExportBody,
    FeedbackBody,
    InspectionExportBody,
    ProjectionBody,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    _require_project_id,
    get_runtime_gateway_service,
)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


def enabled(request: Request):
    if not request.app.state.settings.evaluation_feedback_enabled:
        raise ServiceUnavailableError(
            code="evaluation_disabled", message="评测反馈尚未启用。"
        )


@router.get("/capabilities")
def capabilities(request: Request, actor: ActorContext = Depends(get_actor_context)):
    settings = request.app.state.settings
    project_id = request.headers.get("x-project-id")
    assistant_model = None
    if (
        getattr(settings, "evaluation_workbench_enabled", False)
        and project_id == settings.evaluation_project_id
        and actor.project_role_set(project_id)
    ):
        from platform_api.core.db import session_scope
        from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
            RuntimeCatalogModelRecord,
        )

        try:
            with session_scope(request.app.state.db_session_factory) as session:
                model = session.get(
                    RuntimeCatalogModelRecord,
                    UUID(settings.evaluation_assistant_model_route),
                )
                assistant_model = model.display_name if model else "尚未配置"
        except ValueError:
            assistant_model = "尚未配置"
    return {
        "feedback": settings.evaluation_feedback_enabled,
        "workbench": bool(
            getattr(settings, "evaluation_workbench_enabled", False)
            and project_id == settings.evaluation_project_id
            and actor.project_role_set(project_id)
        ),
        "assistant_model": assistant_model,
        "synthetic_export": bool(
            settings.evaluation_feedback_enabled
            and settings.evaluation_synthetic_export_enabled
            and project_id == settings.evaluation_project_id
            and service.thread_access.is_manager(actor, project_id)
        ),
        "production_export": False,
        "quality_inspection": bool(
            settings.evaluation_feedback_enabled
            and settings.evaluation_inspection_enabled
            and project_id == settings.evaluation_project_id
            and service.thread_access.is_manager(actor, project_id)
        ),
        "inspection_policy": {
            "judge_route": settings.evaluation_inspection_judge_route,
            "budget_policy_version": settings.evaluation_inspection_budget_version,
        }
        if settings.evaluation_inspection_enabled
        else None,
    }


@router.get(
    "/threads/{thread_id}/messages/{message_id}/feedback",
    dependencies=[Depends(enabled)],
)
def feedback(
    request: Request,
    thread_id: UUID,
    message_id: str,
    actor: ActorContext = Depends(get_actor_context),
):
    return service.read_feedback(
        request.app.state.db_session_factory,
        actor,
        (_require_project_id(request), str(thread_id), message_id),
    )


@router.post(
    "/threads/{thread_id}/messages/{message_id}/feedback",
    dependencies=[Depends(enabled)],
)
async def save_feedback(
    request: Request,
    thread_id: UUID,
    message_id: str,
    body: FeedbackBody,
    actor: ActorContext = Depends(get_actor_context),
    gateway=Depends(get_runtime_gateway_service),
):
    project_id = _require_project_id(request)
    scope = (project_id, str(thread_id), message_id)
    current = await run_in_threadpool(
        service.read_feedback, request.app.state.db_session_factory, actor, scope
    )
    if current["revision"]:
        # The immutable source event already proves message membership, including after compaction.
        return await run_in_threadpool(
            service.save_feedback,
            request.app.state.db_session_factory,
            actor,
            scope,
            body,
            run_ids=current["run_ids"],
        )
    state = await gateway.get_thread_state(
        actor=actor, project_id=project_id, thread_id=str(thread_id), params=None
    )
    message = next(
        (
            m
            for m in state.get("values", {}).get("messages", [])
            if m.get("id") == message_id
            and m.get("type", m.get("role")) in {"ai", "assistant"}
        ),
        None,
    )
    if not message or len(message_id) > 256:
        raise NotFoundError(
            code="evaluation_message_missing", message="当前会话中未找到该助手消息。"
        )
    run_id = (message.get("response_metadata") or {}).get("runtime_run_id")
    if run_id:
        await gateway.get_thread_run(
            actor=actor, project_id=project_id, thread_id=str(thread_id), run_id=run_id
        )
    return await run_in_threadpool(
        service.save_feedback,
        request.app.state.db_session_factory,
        actor,
        (project_id, str(thread_id), message_id),
        body,
        run_ids=[run_id] if run_id else [],
    )


@router.post("/exports", dependencies=[Depends(enabled)])
def export(
    request: Request, body: ExportBody, actor: ActorContext = Depends(get_actor_context)
):
    if not request.app.state.settings.evaluation_synthetic_export_enabled:
        raise ServiceUnavailableError(
            code="evaluation_export_disabled", message="评测回流尚未启用。"
        )
    project_id = _require_project_id(request)
    if project_id != request.app.state.settings.evaluation_project_id:
        raise ForbiddenError(
            code="evaluation_project_denied", message="当前项目未获准回流评测。"
        )
    return service.create_export(
        request.app.state.db_session_factory, actor, project_id, body
    )


def source_access(request: Request):
    settings = request.app.state.settings
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not settings.evaluation_source_token or not hmac.compare_digest(
        token, settings.evaluation_source_token
    ):
        raise ForbiddenError(
            code="evaluation_source_denied", message="源数据接收方未授权。"
        )
    if not (
        settings.evaluation_synthetic_export_enabled
        or settings.evaluation_inspection_enabled
        or getattr(settings, "evaluation_workbench_enabled", False)
    ):
        raise ServiceUnavailableError(
            code="evaluation_source_paused", message="评测服务已暂停；现有授权未撤销。"
        )


@router.get("/internal/export", dependencies=[Depends(source_access)])
def source_package(request: Request, export_id: UUID):
    settings = request.app.state.settings
    package = service.authorized_package(
        request.app.state.db_session_factory, settings.evaluation_project_id, export_id
    )
    check_purpose(settings, package)
    return package


def check_purpose(settings, package):
    if package.get("source_kind") == "work_item":
        if not getattr(settings, "evaluation_workbench_enabled", False):
            raise ServiceUnavailableError(
                code="evaluation_purpose_paused",
                message="评测助手已暂停；现有授权未撤销。",
            )
        if package.get("model_route") != settings.evaluation_assistant_model_route:
            raise ForbiddenError(
                code="evaluation_purpose_disabled", message="评测助手模型路由已变化。"
            )
        return
    inspection = package.get("purpose") == "quality_inspection"
    if not (
        settings.evaluation_inspection_enabled
        if inspection
        else settings.evaluation_synthetic_export_enabled
    ):
        # Pausing a feature must not be interpreted by retention workers as revocation.
        raise ServiceUnavailableError(
            code="evaluation_purpose_paused", message="该用途已暂停；现有授权未撤销。"
        )
    if inspection and (
        package["judge_route"] != settings.evaluation_inspection_judge_route
        or package["budget_policy_version"]
        != settings.evaluation_inspection_budget_version
    ):
        raise ForbiddenError(
            code="evaluation_purpose_disabled", message="该用途授权已关闭或变更。"
        )


@router.post("/inspection/exports", dependencies=[Depends(enabled)])
async def inspection_export(
    request: Request,
    body: InspectionExportBody,
    actor: ActorContext = Depends(get_actor_context),
    gateway=Depends(get_runtime_gateway_service),
):
    settings = request.app.state.settings
    project_id = _require_project_id(request)
    check_purpose(settings, body.model_dump())
    if project_id != settings.evaluation_project_id:
        raise ForbiddenError(
            code="inspection_project_denied", message="项目未获准巡检。"
        )
    run = await gateway.get_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=str(body.thread_id),
        run_id=str(body.run_id),
    )
    context = await run_in_threadpool(
        service.inspection_agent,
        request.app.state.db_session_factory,
        actor,
        project_id,
        str(body.thread_id),
        str(body.run_id),
        run,
    )
    if context["agent_id"] != str(body.agent_id):
        raise ForbiddenError(
            code="inspection_run_denied", message="巡检仅接受该Agent已完成的运行。"
        )
    return await run_in_threadpool(
        service.create_inspection_export,
        request.app.state.db_session_factory,
        actor,
        project_id,
        body,
    )


@router.get("/inspection/context", dependencies=[Depends(enabled)])
async def inspection_context(
    request: Request,
    thread_id: UUID,
    run_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    gateway=Depends(get_runtime_gateway_service),
):
    project_id = _require_project_id(request)
    run = await gateway.get_thread_run(
        actor=actor, project_id=project_id, thread_id=str(thread_id), run_id=str(run_id)
    )
    return await run_in_threadpool(
        service.inspection_agent,
        request.app.state.db_session_factory,
        actor,
        project_id,
        str(thread_id),
        str(run_id),
        run,
    )


@router.get("/inspection/exports", dependencies=[Depends(enabled)])
def inspection_exports(
    request: Request,
    thread_id: UUID,
    run_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
):
    return service.read_inspection_exports(
        request.app.state.db_session_factory,
        actor,
        _require_project_id(request),
        str(thread_id),
        str(run_id),
    )


@router.post(
    "/internal/authorizations", dependencies=[Depends(enabled), Depends(source_access)]
)
def source_authorizations(request: Request, body: AuthorizationBatchBody):
    result = {}
    for export_id in body.export_ids:
        try:
            package = service.authorized_package(
                request.app.state.db_session_factory,
                request.app.state.settings.evaluation_project_id,
                export_id,
            )
            check_purpose(request.app.state.settings, package)
            result[str(export_id)] = True
        except (ForbiddenError, NotFoundError):
            result[str(export_id)] = False
    return {"authorizations": result}


@router.post(
    "/internal/projection", dependencies=[Depends(enabled), Depends(source_access)]
)
def projection(request: Request, body: ProjectionBody):
    return service.save_projection(
        request.app.state.db_session_factory,
        request.app.state.settings.evaluation_project_id,
        body,
    )


@router.post("/exports/{export_id}/deliver", dependencies=[Depends(enabled)])
async def deliver(
    request: Request, export_id: UUID, actor: ActorContext = Depends(get_actor_context)
):
    settings = request.app.state.settings
    project_id = _require_project_id(request)
    if (
        project_id != settings.evaluation_project_id
        or not settings.evaluation_receiver_username
        or not settings.evaluation_receiver_password
    ):
        raise ForbiddenError(
            code="evaluation_receiver_unconfigured", message="未配置获准接收方。"
        )
    package = await run_in_threadpool(
        service.authorized_package,
        request.app.state.db_session_factory,
        project_id,
        export_id,
    )
    check_purpose(settings, package)
    if package["authorized_by"] != actor.user_id:
        raise ForbiddenError(
            code="evaluation_export_denied", message="只能投递自己的导出包。"
        )
    url = urlsplit(settings.evaluation_receiver_url)
    if (
        url.scheme != "http"
        or url.hostname not in {"127.0.0.1", "localhost"}
        or url.username
        or url.query
        or url.fragment
    ):
        raise ForbiddenError(
            code="evaluation_receiver_invalid",
            message="接收方必须为已配置的本地隔离服务。",
        )
    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=False,
            trust_env=False,
            auth=(
                settings.evaluation_receiver_username,
                settings.evaluation_receiver_password,
            ),
        ) as client:
            response = await client.post(
                settings.evaluation_receiver_url.rstrip("/")
                + (
                    "/ajax-api/evalflow/inspection/exports"
                    if package.get("purpose") == "quality_inspection"
                    else "/ajax-api/evalflow/curation/exports"
                ),
                json={"export_id": str(export_id)},
                headers={"x-evalflow-request": "1"},
            )
        response.raise_for_status()
    except httpx.HTTPError:
        raise ServiceUnavailableError(
            code="evaluation_delivery_pending",
            message="接收结果待确认，可重试同一导出编号；不会创建新候选。",
        ) from None
    return await run_in_threadpool(
        service.save_receipt,
        request.app.state.db_session_factory,
        export_id,
        response.json(),
    )


@router.post("/exports/{export_id}/revoke", dependencies=[Depends(enabled)])
def revoke(
    request: Request, export_id: UUID, actor: ActorContext = Depends(get_actor_context)
):
    return service.revoke_export(
        request.app.state.db_session_factory,
        actor,
        _require_project_id(request),
        export_id,
    )
