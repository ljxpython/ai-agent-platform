"""Exactly two Thread-bound usage reads with current Platform ACL checks."""

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response

from runtime_service.auth.platform import authenticate, authorize_thread_targets
from runtime_service.observability.usage_query import (
    query_run_usage,
    query_thread_usage,
)

router = APIRouter(prefix="/internal/threads/{thread_id}", tags=["usage"])


async def _identity(thread_id, authorization):
    try:
        thread_id = str(UUID(thread_id))
    except ValueError as exc:
        raise HTTPException(400, {"code": "invalid_thread_id"}) from exc
    facts = await authenticate(authorization)
    scope, principal = (
        facts.get("runtime_scope", {}),
        facts.get("runtime_principal", {}),
    )
    if (
        scope.get("operation") != "usage-read"
        or scope.get("thread_id") != thread_id
        or not scope.get("assistant_id")
        or scope.get("tenant_id") != principal.get("tenant_id")
        or scope.get("project_id") != principal.get("project_id")
    ):
        raise HTTPException(403, {"code": "usage_scope_denied"})
    await authorize_thread_targets(facts, [thread_id], action="read")
    return {
        "tenant_id": principal["tenant_id"],
        "project_id": principal["project_id"],
        "graph_id": scope["assistant_id"],
        "thread_id": thread_id,
    }


@router.get("/runs/{run_id}/usage")
async def run_usage_endpoint(
    thread_id: str,
    run_id: str,
    response: Response,
    limit: str = "50",
    cursor: str | None = None,
    authorization: str | None = Header(default=None),
):
    identity = await _identity(thread_id, authorization)
    try:
        identity["run_id"] = str(UUID(run_id))
        result = await query_run_usage(identity, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(400, {"code": "invalid_usage_query"}) from exc
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/usage")
async def thread_usage_endpoint(
    thread_id: str,
    response: Response,
    created_from: str | None = None,
    created_to: str | None = None,
    authorization: str | None = Header(default=None),
):
    identity = await _identity(thread_id, authorization)
    try:
        result = await query_thread_usage(
            identity, created_from=created_from, created_to=created_to
        )
    except ValueError as exc:
        raise HTTPException(400, {"code": "invalid_usage_query"}) from exc
    response.headers["Cache-Control"] = "no-store"
    return result
