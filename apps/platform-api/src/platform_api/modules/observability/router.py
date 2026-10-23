from __future__ import annotations

from fastapi import APIRouter, Request

from platform_api.modules.observability.models import TraceLogsResponse
from platform_api.modules.observability.service import ObservabilityService

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


@router.get("/traces/{trace_id}/logs", response_model=TraceLogsResponse)
async def get_trace_logs(
    trace_id: str,
    request: Request,
) -> TraceLogsResponse:
    settings = request.app.state.settings
    service = ObservabilityService(settings)
    return await service.get_trace_logs(trace_id)
