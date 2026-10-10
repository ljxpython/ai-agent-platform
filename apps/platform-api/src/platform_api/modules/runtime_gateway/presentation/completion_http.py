"""Completion endpoints retain the existing session and runtime gateway boundaries."""

import hashlib
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import (
    BadRequestError,
    PlatformApiError,
    ServiceUnavailableError,
)
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.runtime_gateway.application import completion
from platform_api.modules.runtime_gateway.domain.completion import (
    CompletionAck,
    ReadBody,
    ReadCompletion,
    RunCompletion,
    RunNotifications,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    _require_project_id,
    get_runtime_gateway_service,
)


class PrivateCompletionRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                response = await original(request)
            except (PlatformApiError, RequestValidationError) as exc:
                error_handler = request.app.exception_handlers.get(
                    type(exc)
                ) or request.app.exception_handlers.get(PlatformApiError)
                if error_handler is None:
                    raise
                response = await error_handler(request, exc)
            response.headers["Cache-Control"] = "private, no-store"
            return response

        return handler


router = APIRouter(tags=["runtime-completion"], route_class=PrivateCompletionRoute)


def _factory(request):
    factory = getattr(request.app.state, "db_session_factory", None)
    if factory is None:
        raise ServiceUnavailableError(
            code="completion_storage_unavailable",
            message="Completion storage unavailable",
        )
    return factory


def _query(request, allowed):
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise BadRequestError(
            code="invalid_completion_query", message="Invalid completion query"
        )


async def _body(request):
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
        raise PlatformApiError(
            code="completion_content_type_invalid",
            status_code=415,
            message="JSON content type required",
        )
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > 65536:
            raise PlatformApiError(
                code="completion_body_too_large",
                status_code=413,
                message="Completion body too large",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/api/runtime/internal/run-completion", response_model=CompletionAck)
async def receive_run_completion(request: Request):
    settings = request.app.state.settings
    if not settings.runtime_completion_enabled:
        raise ServiceUnavailableError(
            code="runtime_completion_disabled", message="Runtime completion disabled"
        )
    _query(request, set())
    raw = await _body(request)
    terminal, runtime_id = completion.parse_callback(
        settings, raw, request.headers, method=request.method, path=request.url.path
    )
    return await run_in_threadpool(
        completion.accept_completion,
        _factory(request),
        terminal,
        digest=hashlib.sha256(raw).hexdigest(),
        runtime_id=runtime_id,
    )


@router.get(
    "/api/langgraph/threads/{thread_id}/runs/{run_id}/completion",
    response_model=RunCompletion,
)
async def get_run_completion(
    request: Request,
    response: Response,
    thread_id: UUID,
    run_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    service=Depends(get_runtime_gateway_service),
):
    _query(request, set())
    response.headers["Cache-Control"] = "private, no-store"
    project_id = _require_project_id(request)
    snapshot = await service.get_thread_run(
        actor=actor, project_id=project_id, thread_id=str(thread_id), run_id=str(run_id)
    )
    if snapshot.get("run_id") != str(run_id) or snapshot.get("thread_id") != str(
        thread_id
    ):
        raise BadRequestError(
            code="completion_target_mismatch", message="Completion target mismatch"
        )
    availability, summary = await run_in_threadpool(
        completion.get_completion,
        _factory(request),
        actor=actor,
        project_id=project_id,
        thread_id=str(thread_id),
        run_id=str(run_id),
    )
    return {
        "version": 1,
        "thread_id": thread_id,
        "run_id": run_id,
        "availability": availability,
        "completion": summary,
        "request_id": request.state.platform_context.request.request_id,
    }


@router.get("/api/runtime/run-notifications", response_model=RunNotifications)
def get_run_notifications(
    request: Request,
    response: Response,
    actor: ActorContext = Depends(get_actor_context),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=1024),
    unread_only: bool = True,
):
    _query(request, {"limit", "cursor", "unread_only"})
    response.headers["Cache-Control"] = "private, no-store"
    project_id = _require_project_id(request)
    enabled = request.app.state.settings.runtime_completion_enabled
    result = (
        completion.list_notifications(
            _factory(request),
            request.app.state.settings,
            actor=actor,
            project_id=project_id,
            limit=limit,
            cursor=cursor,
            unread_only=unread_only,
        )
        if enabled
        else {"items": [], "next_cursor": None, "scan_limit_reached": False}
    )
    return {
        "version": 1,
        "availability": "available" if enabled else "disabled",
        **result,
        "request_id": request.state.platform_context.request.request_id,
    }


@router.post(
    "/api/runtime/run-notifications/{event_id}/read", response_model=ReadCompletion
)
def read_run_notification(
    request: Request,
    response: Response,
    event_id: UUID,
    payload: ReadBody = Body(),
    actor: ActorContext = Depends(get_actor_context),
):
    _query(request, set())
    response.headers["Cache-Control"] = "private, no-store"
    if not request.app.state.settings.runtime_completion_enabled:
        raise ServiceUnavailableError(
            code="runtime_completion_disabled", message="Runtime completion disabled"
        )
    read_at = completion.mark_read(
        _factory(request),
        actor=actor,
        project_id=_require_project_id(request),
        event_id=event_id,
    )
    return {
        "version": 1,
        "event_id": event_id,
        "read_at": read_at,
        "request_id": request.state.platform_context.request.request_id,
    }
