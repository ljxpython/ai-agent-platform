"""Owner-scoped Dear memory management without a thread dependency."""
import os

import psycopg

from fastapi import APIRouter, Header, HTTPException

from runtime_service.auth.platform import authenticate
from runtime_service.http.dear_governance import call
from runtime_service.runtime.tool_access import require_tool_access
from runtime_service.services.dearflow_agent.memory import MemoryCommand, MemoryStorage

router = APIRouter(prefix="/internal/dear/memory", tags=["dear-memory"])
LIMITS = {"fact_text_chars": 1000, "facts": 100, "candidates": 100,
          "restore_items": 100, "request_bytes": 1500000}


async def storage_call(function, *args, **kwargs):
    try:
        return await call(function, *args, **kwargs)
    except psycopg.Error as exc:
        raise HTTPException(503, {"code": "memory_storage_unavailable"}) from exc


async def authorize(authorization, *, write=False):
    facts = await authenticate(authorization)
    scope, principal = facts.get("runtime_scope", {}), facts.get("runtime_principal", {})
    if (scope.get("operation") != ("dear-memory-write" if write else "dear-memory-read")
            or scope.get("assistant_id") != "dearflow_agent" or scope.get("thread_id") is not None
            or not all(principal.get(k) for k in ("tenant_id", "project_id", "user_id"))
            or any(scope.get(k) != principal.get(k) for k in ("tenant_id", "project_id"))):
        raise HTTPException(403, {"code": "dear_memory_scope_denied"})
    require_tool_access(facts, "manage_memory" if write else "search_memory")
    return tuple(principal[k] for k in ("tenant_id", "project_id", "user_id"))


def envelope(scope, document=None, extraction=None, mutation=None):
    enabled = os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") == "1"
    if not enabled:
        document = extraction = mutation = None
    if document is not None:
        def fact_view(fact):
            return {"id": fact["id"], "text": fact["text"], "category": fact["category"],
                    "expires_at": fact.get("expires_at"), "origin": fact["origin"],
                    "revision": fact["revision"], "created_at": fact["created_at"],
                    "updated_at": fact["updated_at"], "source_kind": fact.get("source_kind") or (
                        "management" if fact.get("source_message_id") == "explicit-management" else "legacy"),
                    "source_thread_id": fact.get("source_thread_id"),
                    "source_message_id": None if fact.get("source_message_id") == "explicit-management"
                                         else fact.get("source_message_id"),
                    "source_call_id": fact.get("source_call_id"), "quote": fact.get("quote")}
        document = {**document, "facts": [fact_view(f) for f in document["facts"]],
                    "candidates": [fact_view(f) for f in document["candidates"]]}
    return {"status": "ready" if enabled else "disabled",
            "scope": {"kind": "project_user", "project_id": scope[1], "user_id": scope[2]},
            "capabilities": {"memory_enabled": enabled, "can_read": enabled, "can_write": enabled},
            "limits": LIMITS, "document": document,
            "counts": {"facts": len(document["facts"]), "candidates": len(document["candidates"])} if document else None,
            "extraction": extraction, "mutation": mutation}


@router.get("")
async def read_memory(authorization: str | None = Header(default=None)):
    scope = await authorize(authorization)
    if os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") != "1":
        return envelope(scope)
    document, extraction = await storage_call(MemoryStorage().view, scope)
    return envelope(scope, document, extraction)


@router.post("")
async def change_memory(command: MemoryCommand, authorization: str | None = Header(default=None)):
    scope = await authorize(authorization, write=True)
    if os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") != "1":
        raise HTTPException(409, {"code": "dear_governance_disabled"})
    document = await storage_call(MemoryStorage().change, scope, command,
                          thread_id="", source_id="explicit-management")
    mutation = document.pop("mutation")
    extraction = document.pop("extraction")
    return envelope(scope, document, extraction, mutation)
