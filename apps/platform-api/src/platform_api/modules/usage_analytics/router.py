import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from platform_api.adapters.langgraph.runtime_gateway_upstream import (
    LangGraphRuntimeGatewayUpstream,
)
from platform_api.core.errors import BadRequestError
from platform_api.modules.usage_analytics.contracts import (
    UsageDashboardV1,
    UsageRunPageV1,
    parse_query,
)
from platform_api.modules.usage_analytics.service import UsageAnalyticsService

router = APIRouter(prefix="/api", tags=["usage"])


async def get_usage_service(request: Request):
    settings = request.app.state.settings
    slots = getattr(request.app.state, "usage_query_slots", None)
    if slots is None:
        slots = request.app.state.usage_query_slots = asyncio.Semaphore(2)
    return UsageAnalyticsService(
        session_factory=getattr(request.app.state, "db_session_factory", None),
        upstream=LangGraphRuntimeGatewayUpstream(
            base_url=settings.langgraph_upstream_url, timeout_seconds=5
        ),
        secret=settings.runtime_delegation_secret,
        query_slots=slots,
    )


def _query(request, response, *, project_id=None, runs=False):
    response.headers["Cache-Control"] = "no-store"
    if any(key.startswith("x-usage-query-") for key in request.headers):
        raise BadRequestError(
            code="invalid_usage_analytics_query",
            message="Internal usage headers are not public parameters",
        )
    if project_id is not None:
        try:
            project_id = str(UUID(project_id))
        except ValueError as exc:
            raise BadRequestError(
                code="invalid_usage_analytics_query",
                message="Invalid project identifier",
            ) from exc
    query, requested = parse_query(
        request.query_params, runs=runs, platform=project_id is None
    )
    request.state.audit_metadata = {
        "usage_from": query.start.isoformat(),
        "usage_to": query.end.isoformat(),
        "usage_group_by": getattr(query, "group_by", None),
        "usage_project_count": 1 if project_id else len(requested) if requested else 0,
    }
    return project_id, query, requested


@router.get("/usage/dashboard", response_model=UsageDashboardV1)
async def platform_dashboard(
    request: Request, response: Response, service=Depends(get_usage_service)
):
    _, query, requested = _query(request, response)
    result = await service.dashboard(
        context=request.state.platform_context,
        project_id=None,
        requested=requested,
        query=query,
    )
    request.state.audit_metadata["usage_project_count"] = (
        result.scope.covered_project_count
    )
    return result


@router.get("/projects/{project_id}/usage/dashboard", response_model=UsageDashboardV1)
async def project_dashboard(
    project_id: str,
    request: Request,
    response: Response,
    service=Depends(get_usage_service),
):
    project_id, query, _ = _query(request, response, project_id=project_id)
    return await service.dashboard(
        context=request.state.platform_context,
        project_id=project_id,
        requested=None,
        query=query,
    )


@router.get("/projects/{project_id}/usage/runs", response_model=UsageRunPageV1)
async def project_runs(
    project_id: str,
    request: Request,
    response: Response,
    service=Depends(get_usage_service),
):
    project_id, query, _ = _query(request, response, project_id=project_id, runs=True)
    return await service.runs(
        context=request.state.platform_context, project_id=project_id, query=query
    )
