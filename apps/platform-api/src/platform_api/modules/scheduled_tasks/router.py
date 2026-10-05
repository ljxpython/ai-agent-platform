from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from platform_api.core.context.models import ActorContext
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    _require_project_id,
    get_runtime_gateway_service,
)
from platform_api.modules.scheduled_tasks.schemas import (
    Schedule,
    TaskCreate,
    TaskUpdate,
)
from platform_api.modules.scheduled_tasks.service import (
    ScheduledTasksService,
    preview,
    task_item,
)

router = APIRouter(prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])


def get_service(
    request: Request,
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return ScheduledTasksService(
        gateway,
        tenant_id=request.state.platform_context.tenant.tenant_id or "__default",
        secret=request.app.state.settings.runtime_delegation_secret,
    )


@router.post("/preview")
async def preview_schedule(
    request: Request,
    payload: Schedule,
    count: int = Query(5, ge=1, le=20),
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    upstream = await service._upstream(
        actor=actor, project_id=_require_project_id(request), write=False
    )
    return await preview(upstream, payload, count=count)


@router.get("")
async def list_tasks(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    enabled: bool | None = None,
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    return await service.list(
        actor=actor,
        project_id=_require_project_id(request),
        limit=limit,
        offset=offset,
        enabled=enabled,
    )


@router.post("", status_code=201)
async def create_task(
    request: Request,
    payload: TaskCreate,
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    return await service.create(
        actor=actor, project_id=_require_project_id(request), spec=payload
    )


@router.get("/{task_id}")
async def get_task(
    request: Request,
    task_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    return task_item(
        await service.get_native(
            actor=actor, project_id=_require_project_id(request), task_id=str(task_id)
        )
    )


@router.patch("/{task_id}")
async def update_task(
    request: Request,
    task_id: UUID,
    payload: TaskUpdate,
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    return await service.update(
        actor=actor,
        project_id=_require_project_id(request),
        task_id=str(task_id),
        changes=payload.model_dump(mode="json", exclude_unset=True),
    )


@router.post("/{task_id}/pause")
async def pause_task(
    request: Request,
    task_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    return await service.set_enabled(
        actor=actor,
        project_id=_require_project_id(request),
        task_id=str(task_id),
        enabled=False,
    )


@router.post("/{task_id}/resume")
async def resume_task(
    request: Request,
    task_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    return await service.set_enabled(
        actor=actor,
        project_id=_require_project_id(request),
        task_id=str(task_id),
        enabled=True,
    )


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    request: Request,
    task_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    await service.delete(
        actor=actor, project_id=_require_project_id(request), task_id=str(task_id)
    )
    return Response(status_code=204)


@router.post("/{task_id}/trigger", status_code=202)
async def trigger_task(
    request: Request,
    task_id: UUID,
    idempotency_key: str = Header(min_length=1, max_length=128),
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    return await service.trigger(
        actor=actor,
        project_id=_require_project_id(request),
        task_id=str(task_id),
        idempotency_key=idempotency_key,
    )


@router.get("/{task_id}/runs")
async def task_history(
    request: Request,
    task_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: ScheduledTasksService = Depends(get_service),
):
    return await service.history(
        actor=actor,
        project_id=_require_project_id(request),
        task_id=str(task_id),
        limit=limit,
        offset=offset,
    )
