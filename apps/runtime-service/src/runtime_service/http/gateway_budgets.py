"""Signed, purpose-bound control-plane budget queries; no end-user authority."""

import asyncio
import os
from datetime import UTC, datetime
from typing import Literal

import psycopg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, ValidationError

from runtime_service.db.repositories.usage import _connection
from runtime_service.gateway_budget import ledger
from runtime_service.gateway_budget.contracts import PolicySnapshot
from runtime_service.gateway_budget.service import enabled
from runtime_service.gateway_budget.transport import decode, verify

router = APIRouter(prefix="/internal/budgets", tags=["gateway-budgets"])


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot: PolicySnapshot
    mode: Literal["sync", "status", "check"]
    project_id: str | None = None


def execute(query, nonce):
    snapshot = query.snapshot.model_dump(mode="json")
    if query.mode in {"sync", "check"}:
        states = ledger.synchronize(snapshot, project_id=query.project_id, nonce=nonce)
    else:
        at = datetime.now(UTC)
        states = []
        with _connection() as conn:
            ledger.locked(conn, snapshot["tenant_id"])
            conn.execute(
                "INSERT INTO runtime_budget_nonces(nonce) VALUES(%s)", (nonce,)
            )
            current = conn.execute(
                "SELECT revision FROM runtime_budget_tenants WHERE tenant_id=%s",
                (snapshot["tenant_id"],),
            ).fetchone()
            for policy in snapshot["policies"]:
                if policy.get("deleted_at"):
                    continue
                start, _ = ledger.window(policy["duration"]["unit"], at)
                row = conn.execute(
                    "SELECT * FROM runtime_budget_windows WHERE "
                    "(tenant_id,policy_id,definition_version,window_start)=(%s,%s,%s,%s)",
                    (
                        snapshot["tenant_id"],
                        policy["id"],
                        policy["definition_version"],
                        start,
                    ),
                ).fetchone()
                if row and current and current["revision"] == snapshot["revision"]:
                    states.append(ledger.status(conn, row, at))
    return {
        "version": 1,
        "tenant_id": snapshot["tenant_id"],
        "revision": snapshot["revision"],
        "states": states,
        "capabilities": {"gateway_budget": enabled(), "usage": True},
    }


@router.post("/query")
async def query_endpoint(request: Request):
    if not enabled():
        raise HTTPException(503, {"code": "gateway_budget_not_enabled"})
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 262144:
            raise HTTPException(413, {"code": "budget_body_too_large"})
    try:
        if request.query_params:
            raise ValueError("unexpected_query")
        nonce = verify(
            os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", ""),
            request.url.path,
            request.headers,
            bytes(body),
        )
        query = Query.model_validate(decode(body))
    except (ValueError, ValidationError):
        raise HTTPException(403, {"code": "budget_request_denied"}) from None
    try:
        return await asyncio.to_thread(execute, query, nonce)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, {"code": "budget_replay_denied"}) from None
    except (psycopg.Error, ValueError):
        raise HTTPException(503, {"code": "budget_accounting_unavailable"}) from None
