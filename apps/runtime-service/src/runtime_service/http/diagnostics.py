"""Thread-bound diagnostics reader with a current platform ACL check."""

import asyncio
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header, HTTPException, Response

from runtime_service.auth.platform import authenticate, authorize_thread_targets
from runtime_service.observability.query import query_run_diagnostics

router = APIRouter(prefix="/internal/threads/{thread_id}/runs", tags=["diagnostics"])


@router.get("/{run_id}/execution-evidence")
async def execution_evidence_endpoint(
    thread_id: UUID,
    run_id: UUID,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    from runtime_service.observability.execution_evidence import read_execution

    facts = await authenticate(authorization)
    scope, principal = (
        facts.get("runtime_scope", {}),
        facts.get("runtime_principal", {}),
    )
    if (
        scope.get("operation") != "diagnostics-read"
        or scope.get("thread_id") != str(thread_id)
        or not scope.get("assistant_id")
        or scope.get("tenant_id") != principal.get("tenant_id")
        or scope.get("project_id") != principal.get("project_id")
    ):
        raise HTTPException(403, {"code": "diagnostics_scope_denied"})
    await authorize_thread_targets(facts, [str(thread_id)], action="read")
    try:
        result = await asyncio.to_thread(
            read_execution,
            principal["tenant_id"],
            principal["project_id"],
            str(thread_id),
            str(run_id),
        )
    except (psycopg.Error, KeyError):
        raise HTTPException(503, {"code": "execution_evidence_unavailable"}) from None
    if not result or result["graph_id"] != scope["assistant_id"]:
        raise HTTPException(404, {"code": "execution_evidence_missing"})
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{run_id}/diagnostics")
async def run_diagnostics_endpoint(
    thread_id: UUID,
    run_id: UUID,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    facts = await authenticate(authorization)
    scope = facts.get("runtime_scope", {})
    principal = facts.get("runtime_principal", {})
    if (
        scope.get("operation") != "diagnostics-read"
        or scope.get("thread_id") != str(thread_id)
        or not scope.get("assistant_id")
        or scope.get("tenant_id") != principal.get("tenant_id")
        or scope.get("project_id") != principal.get("project_id")
    ):
        raise HTTPException(403, {"code": "diagnostics_scope_denied"})
    await authorize_thread_targets(facts, [str(thread_id)], action="read")
    response.headers["Cache-Control"] = "no-store"
    return await query_run_diagnostics(
        tenant_id=principal["tenant_id"],
        project_id=principal["project_id"],
        graph_id=scope["assistant_id"],
        thread_id=str(thread_id),
        run_id=str(run_id),
    )
