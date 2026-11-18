import hashlib
import hmac
import json
import time
from dataclasses import replace

from fastapi import APIRouter, Depends, Request, Response
from starlette.concurrency import run_in_threadpool

from platform_api.core.context.models import ProjectContext, TenantContext
from platform_api.core.errors import ForbiddenError, ServiceUnavailableError
from platform_api.entrypoints.http.dependencies.context import get_actor_context
from platform_api.modules.identity.actors import load_user_actor
from platform_api.modules.platform_assistant.contracts import (
    InternalReadRequest,
    ReadRequest,
)
from platform_api.modules.platform_assistant.service import (
    read,
    require_scope,
    sources,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_runtime_gateway_service,
)

router = APIRouter(prefix="/api/platform-assistant", tags=["platform-assistant"])


def _target_gateway(request, target_actor, target_project):
    factory = request.app.state.db_session_factory
    context = request.state.platform_context
    tenant_id = require_scope(factory, target_actor, target_project)
    # Runtime's delegation must match the target, while evidence stays in the assistant scope.
    target_request = Request(
        {
            **request.scope,
            "state": {
                **request.scope.get("state", {}),
                "platform_context": replace(
                    context,
                    actor=target_actor,
                    project=ProjectContext(project_id=target_project),
                    tenant=TenantContext(tenant_id=tenant_id),
                ),
            },
        }
    )
    return get_runtime_gateway_service(target_request, target_actor)


@router.post("/bootstrap")
async def setup_assistant(
    request: Request, response: Response, actor=Depends(get_actor_context)
):
    from platform_api.modules.platform_assistant.bootstrap import bootstrap

    if not request.app.state.settings.platform_assistant_enabled:
        raise ServiceUnavailableError(
            code="assistant_disabled", message="平台助手已关闭。"
        )
    response.headers["Cache-Control"] = "private, no-store"
    return await run_in_threadpool(
        bootstrap,
        request.app.state.db_session_factory,
        actor,
        request.state.platform_context.project.project_id,
    )


@router.get("/capabilities")
async def capabilities(
    request: Request, response: Response, actor=Depends(get_actor_context)
):
    project_id = request.state.platform_context.project.project_id
    await run_in_threadpool(
        require_scope, request.app.state.db_session_factory, actor, project_id
    )
    settings = request.app.state.settings
    response.headers["Cache-Control"] = "private, no-store"
    return {
        "enabled": settings.platform_assistant_enabled,
        "graph_id": "platform_assistant",
        "history": True,
        "long_term_memory": False,
        "sandbox": False,
        "write_tools": [],
        "source": actor.user_id in settings.assistant_source_users,
        "databases": list(sources(settings, actor, project_id)),
    }


@router.post("/read")
async def public_read(
    request: Request,
    response: Response,
    body: ReadRequest,
    actor=Depends(get_actor_context),
):
    response.headers["Cache-Control"] = "private, no-store"
    project_id = request.state.platform_context.project.project_id
    gateway = get_runtime_gateway_service(request, actor)
    return await read(
        request,
        actor,
        project_id,
        body,
        gateway,
        correlation={"request_id": request.state.platform_context.request.request_id},
        target_gateway_factory=lambda a, p: _target_gateway(request, a, p),
    )


@router.post("/internal/read")
async def internal_read(
    request: Request, response: Response, body: InternalReadRequest
):
    settings = request.app.state.settings
    timestamp = request.headers.get("x-assistant-time", "")
    encoded = json.dumps(
        body.model_dump(mode="json"), sort_keys=True, ensure_ascii=False
    )
    expected = hmac.new(
        settings.runtime_delegation_secret.encode(),
        ("platform-assistant\n" + timestamp + "\n" + encoded).encode(),
        hashlib.sha256,
    ).hexdigest()
    try:
        valid = (
            bool(settings.runtime_delegation_secret)
            and abs(time.time() - int(timestamp)) <= 30
            and hmac.compare_digest(
                expected, request.headers.get("x-assistant-signature", "")
            )
        )
    except ValueError:
        valid = False
    if not valid:
        raise ForbiddenError(
            code="assistant_origin_denied", message="助手来源无法确认。"
        )
    project_id = str(body.project_id)
    actor = await run_in_threadpool(
        load_user_actor,
        session_factory=request.app.state.db_session_factory,
        user_id=str(body.actor_id),
        project_id=project_id,
    )
    tenant_id = await run_in_threadpool(
        require_scope, request.app.state.db_session_factory, actor, project_id
    )
    request.state.platform_context = replace(
        request.state.platform_context,
        actor=actor,
        project=ProjectContext(project_id=project_id),
        tenant=TenantContext(tenant_id=tenant_id),
    )
    gateway = get_runtime_gateway_service(request, actor)
    thread = await gateway.get_thread(
        actor=actor, project_id=project_id, thread_id=str(body.thread_id)
    )
    await run_in_threadpool(
        gateway._assert_runtime_target_allowed,
        project_id=project_id,
        assistant_id="platform_assistant",
        thread=thread,
    )
    if (
        thread.get("graph_id") or thread.get("metadata", {}).get("graph_id")
    ) != "platform_assistant":
        raise ForbiddenError(
            code="assistant_thread_denied", message="此会话不是平台助手会话。"
        )
    run = await gateway.get_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=str(body.thread_id),
        run_id=str(body.run_id),
    )
    if (
        run.get("run_id") != str(body.run_id)
        or run.get("thread_id") != str(body.thread_id)
        or run.get("status")
        not in {
            "pending",
            "running",
            "interrupted",
        }
    ):
        raise ForbiddenError(
            code="assistant_run_denied", message="助手运行已结束或关联不符。"
        )
    response.headers["Cache-Control"] = "private, no-store"
    return await read(
        request,
        actor,
        project_id,
        body,
        gateway,
        correlation={
            "assistant_thread_id": str(body.thread_id),
            "assistant_run_id": str(body.run_id),
            "tool_call_id": body.tool_call_id,
            "request_id": request.state.platform_context.request.request_id,
        },
        target_gateway_factory=lambda a, p: _target_gateway(request, a, p),
    )
