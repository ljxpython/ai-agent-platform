"""Platform identity and authorization bridge to EvalFlow's evaluation business records."""

from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    ServiceUnavailableError,
)
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.evaluation import service
from platform_api.modules.evaluation.delegation import (
    issue_command,
    require_action,
    verify_command,
)
from platform_api.modules.evaluation.privacy import require_safe_material
from platform_api.modules.evaluation.router import source_access
from platform_api.modules.evaluation.workbench_grants import (
    GrantBody,
    create_grant,
    revoke_grant,
)
from platform_api.modules.identity.actors import load_user_actor
from platform_api.modules.runtime_gateway.presentation.http import (
    _require_project_id,
)


class CommandBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    data: dict = Field(default_factory=dict)


class IntrospectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(max_length=8192)
    body: dict


class ReviewerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    project_id: UUID


class MemberBody(ReviewerBody):
    operation: str = "generate"


class SourceBody(ReviewerBody):
    thread_id: UUID
    message_id: str = Field(min_length=1, max_length=256)


class AuthoringCommand(CommandBody):
    operation: str
    item_id: UUID | None = None


def enabled(request: Request):
    if not request.app.state.settings.evaluation_workbench_enabled:
        raise ServiceUnavailableError(
            code="evaluation_workbench_disabled", message="评测与改进尚未启用。"
        )
    selected = request.headers.get("x-evalflow-connection")
    if (
        selected is not None
        and selected != request.app.state.settings.evaluation_connection_id
    ):
        raise ForbiddenError(
            code="evaluation_connection_denied", message="评测连接不属于当前Agent平台。"
        )


router = APIRouter(
    prefix="/api/evaluation",
    tags=["evaluation-workbench"],
    dependencies=[Depends(enabled)],
)


@router.get("/internal/connection", dependencies=[Depends(source_access)])
def connection_descriptor(request: Request):
    settings = request.app.state.settings
    return {
        "connection_id": settings.evaluation_connection_id,
        "project_id": settings.evaluation_project_id,
    }


def reject_client_source_snapshots(data):
    if data.get("source_materials") or data.get("material_submission"):
        raise BadRequestError(
            code="evaluation_source_server_owned",
            message="原始Session资料只能通过会话资料交付接口取得，不能由客户端填写。",
        )


@router.post("/authoring/token")
def authoring_token(
    request: Request,
    body: AuthoringCommand,
    actor: ActorContext = Depends(get_actor_context),
):
    """Identity service only: EvalFlow owns and applies the evaluation command."""
    import json

    project_id = _require_project_id(request)
    if project_id != request.app.state.settings.evaluation_project_id:
        raise ForbiddenError(code="evaluation_project_denied", message="项目未获准。")
    if body.operation not in {
        "list",
        "read",
        "create",
        "edit",
        "generate",
        "revise",
        "approve",
        "run",
        "cancel",
        "explain",
        "compare",
        "dispute",
        "tool_decision",
        "defer",
        "regression",
    }:
        raise ForbiddenError(
            code="evaluation_command_denied", message="不允许此评测操作。"
        )
    require_action(actor, project_id, body.operation)
    if body.operation in {"create", "edit", "generate", "revise", "dispute"}:
        require_safe_material(json.dumps(body.data, ensure_ascii=False))
    if body.operation == "create":
        reject_client_source_snapshots(body.data)
        from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord

        with session_scope(request.app.state.db_session_factory) as session:
            try:
                agent_id = UUID(body.data.get("agent_id", ""))
            except (ValueError, TypeError):
                raise BadRequestError(
                    code="evaluation_agent_required", message="请选择要验证的Agent。"
                ) from None
            agent = session.get(AgentRecord, agent_id)
            if (
                not agent
                or str(agent.project_id) != project_id
                or agent.status != "active"
            ):
                raise ForbiddenError(
                    code="evaluation_agent_denied", message="当前Agent不可用。"
                )
    return {
        "token": issue_command(
            request.app.state.settings.evaluation_source_token,
            actor,
            project_id,
            body.operation,
            str(body.item_id) if body.item_id else None,
            str(body.request_id),
            body.data,
            connection_id=request.app.state.settings.evaluation_connection_id,
        )
    }


@router.post("/internal/workbench/source", dependencies=[Depends(source_access)])
def source_feedback_state(request: Request, body: SourceBody):
    project_id = str(body.project_id)
    if project_id != request.app.state.settings.evaluation_project_id:
        raise ForbiddenError(code="evaluation_project_denied", message="项目未获准。")
    factory = request.app.state.db_session_factory
    actor = load_user_actor(
        session_factory=factory, user_id=str(body.user_id), project_id=project_id
    )
    require_action(actor, project_id, "read")
    with session_scope(factory) as session:
        service.authorize(session, actor, project_id, str(body.thread_id), "read")
        event = service.latest(
            session, actor.user_id, str(body.thread_id), body.message_id
        )
        return {
            "revision": event.revision if event else 0,
            "withdrawn": bool(event and event.payload.get("rating") == "withdrawn"),
        }


async def forward(request, actor, project_id, operation, item_id, request_id, data):
    settings = request.app.state.settings
    if project_id != settings.evaluation_project_id:
        raise ForbiddenError(
            code="evaluation_project_denied", message="当前项目未启用评测工作台。"
        )
    token = issue_command(
        settings.evaluation_source_token,
        actor,
        project_id,
        operation,
        item_id,
        str(request_id),
        data,
        connection_id=settings.evaluation_connection_id,
    )
    try:
        url = urlsplit(settings.evaluation_receiver_url)
        _ = url.port
        trusted = (
            url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost"}
        ) or f"{url.scheme}://{url.netloc}" in getattr(
            settings, "evaluation_receiver_allowed_origins", ()
        )
    except ValueError:
        trusted = False
    if (
        not trusted
        or url.scheme not in {"http", "https"}
        or url.username
        or url.password
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
        or any(char.isspace() for char in settings.evaluation_receiver_url)
        or not settings.evaluation_receiver_username
        or not settings.evaluation_receiver_password
    ):
        raise ServiceUnavailableError(
            code="evaluation_receiver_invalid", message="尚未配置受信的评测服务地址。"
        )
    try:
        async with httpx.AsyncClient(
            timeout=30,
            trust_env=False,
            follow_redirects=False,
            auth=(
                settings.evaluation_receiver_username,
                settings.evaluation_receiver_password,
            ),
        ) as client:
            response = await client.post(
                settings.evaluation_receiver_url.rstrip("/")
                + "/ajax-api/evalflow/internal/workbench/command",
                json=data,
                headers={
                    "x-evaluation-command": token,
                    "x-evalflow-request": "1",
                    "x-evalflow-connection": settings.evaluation_connection_id,
                },
            )
        if response.status_code == 403:
            raise ForbiddenError(
                code="evaluation_workbench_denied",
                message="当前身份无权读取或操作此工作项。",
            )
        if response.status_code in {400, 404, 409, 422}:
            raise ConflictError(
                code="evaluation_workbench_conflict",
                message=response.json().get("detail", "当前操作无法完成。"),
            )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise ServiceUnavailableError(
            code="evaluation_receipt_pending",
            message="评测服务回执待确认。请保留当前请求重试，不会重复创建。",
        ) from None


def record_action(factory, actor, project_id, request_id, action):
    with session_scope(factory) as session:
        service.audit(
            session,
            actor,
            project_id,
            str(request_id),
            "evaluation.workbench." + action,
        )


@router.post("/internal/workbench/authorize", dependencies=[Depends(source_access)])
def authorize_command(request: Request, body: IntrospectionBody):
    settings = request.app.state.settings
    claims = verify_command(
        settings.evaluation_source_token,
        body.token,
        body.body,
        request.app.state.db_session_factory,
        connection_id=settings.evaluation_connection_id,
    )
    if claims["project_id"] != settings.evaluation_project_id:
        raise ForbiddenError(
            code="evaluation_project_denied", message="评测项目未获准。"
        )
    return claims


@router.post("/internal/workbench/reviewer", dependencies=[Depends(source_access)])
def reviewer_valid(request: Request, body: ReviewerBody):
    project_id = str(body.project_id)
    if project_id != request.app.state.settings.evaluation_project_id:
        raise ForbiddenError(code="evaluation_project_denied", message="项目未获准。")
    actor = load_user_actor(
        session_factory=request.app.state.db_session_factory,
        user_id=str(body.user_id),
        project_id=project_id,
    )
    require_action(actor, project_id, "approve")
    return {"authorized": True}


@router.post("/internal/workbench/member", dependencies=[Depends(source_access)])
def authoring_member(request: Request, body: MemberBody):
    project_id = str(body.project_id)
    if project_id != request.app.state.settings.evaluation_project_id:
        raise ForbiddenError(code="evaluation_project_denied", message="项目未获准。")
    actor = load_user_actor(
        session_factory=request.app.state.db_session_factory,
        user_id=str(body.user_id),
        project_id=project_id,
    )
    require_action(actor, project_id, body.operation)
    return {
        "sub": actor.user_id,
        "project_id": project_id,
        "roles": sorted(actor.project_role_set(project_id)),
    }


@router.post("/work-items/{item_id}/{action}")
async def item_action(
    request: Request,
    item_id: UUID,
    action: str,
    body: CommandBody,
    actor: ActorContext = Depends(get_actor_context),
):
    project_id = _require_project_id(request)
    if action not in {"grant", "revoke"}:
        raise BadRequestError(
            code="evaluation_action_invalid",
            message="此入口仅用于资料用途授权与撤销，请在EvalFlow操作评测。",
        )
    require_action(actor, project_id, action)
    data = body.data
    item = await forward(request, actor, project_id, "read", str(item_id), uuid4(), {})
    if action == "grant":
        try:
            grant = GrantBody.model_validate(data)
        except ValidationError:
            raise BadRequestError(
                code="evaluation_grant_invalid",
                message="请选择有效的资料用途和授权期限。",
            ) from None
        saved = await run_in_threadpool(
            create_grant,
            request.app.state.db_session_factory,
            actor,
            project_id,
            item,
            grant,
            request.app.state.settings.evaluation_assistant_model_route,
        )
        data = {"grant_id": saved["grant_id"]}
    else:
        try:
            grant_id = str(UUID(data["grant_id"]))
        except (KeyError, ValueError, TypeError):
            raise BadRequestError(
                code="evaluation_grant_invalid", message="请选择要撤销的资料用途。"
            ) from None
        if grant_id not in item["grants"].values():
            raise ForbiddenError(
                code="evaluation_grant_denied", message="授权不属于本工作项。"
            )
        return await run_in_threadpool(
            revoke_grant,
            request.app.state.db_session_factory,
            actor,
            project_id,
            grant_id,
        )
    result = await forward(
        request, actor, project_id, action, str(item_id), body.request_id, data
    )
    await run_in_threadpool(
        record_action,
        request.app.state.db_session_factory,
        actor,
        project_id,
        body.request_id,
        action,
    )
    return result
