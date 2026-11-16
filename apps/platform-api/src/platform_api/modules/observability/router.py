from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from platform_api.entrypoints.http.dependencies.context import get_actor_context
from platform_api.modules.observability.models import TraceLogsResponse
from platform_api.modules.platform_assistant.logs import authorized_logs

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


@router.get("/traces/{trace_id}/logs", response_model=TraceLogsResponse)
async def get_trace_logs(
    trace_id: str,
    request: Request,
    response: Response,
    actor=Depends(get_actor_context),
) -> TraceLogsResponse:
    response.headers["Cache-Control"] = "private, no-store"
    return await authorized_logs(
        request, actor, request.state.platform_context.project.project_id, trace_id
    )
