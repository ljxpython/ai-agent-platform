import hmac
from uuid import UUID

from fastapi import APIRouter, Depends, Request

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
    ProjectionBody,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    _require_project_id,
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
    available = bool(
        getattr(settings, "evaluation_workbench_enabled", False)
        and project_id == settings.evaluation_project_id
        and actor.project_role_set(project_id)
    )
    return {
        "workbench": available,
        "authoring_url": (
            getattr(settings, "evaluation_web_url", "").rstrip("/")
            if available
            else None
        ),
    }


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
