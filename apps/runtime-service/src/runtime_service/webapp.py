"""Agent Server application lifespan owned by Runtime Service."""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from runtime_service.auth.platform import authenticate
from runtime_service.messaging import MessageInbox
from runtime_service.messaging.reconcile import reconcile_run
from runtime_service.observability import close_langfuse, initialize_langfuse


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_langfuse()
    try:
        yield
    finally:
        close_langfuse(timeout_seconds=5.0)


app = FastAPI(lifespan=lifespan)
logger = logging.getLogger(__name__)


class EnqueueMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_run_id: UUID
    client_message_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=128)
    content: str | list[dict]
    authorization_ref: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, content: str | list[dict]) -> str | list[dict]:
        if not content or isinstance(content, str) and not content.strip():
            raise ValueError("empty_message")
        if isinstance(content, str):
            return content
        for block in content:
            if block.get("type") == "text":
                if set(block) <= {"type", "text"} and isinstance(
                    block.get("text"), str
                ):
                    continue
            elif block.get("type") in {"image", "file"}:
                allowed = (
                    {"image/jpeg", "image/png", "image/gif", "image/webp"}
                    if block["type"] == "image"
                    else {"application/pdf"}
                )
                if (
                    set(block) <= {"type", "mimeType", "data", "metadata"}
                    and block.get("mimeType") in allowed
                    and isinstance(block.get("data"), str)
                ):
                    try:
                        if base64.b64decode(block["data"], validate=True):
                            continue
                    except (ValueError, binascii.Error):
                        pass
            raise ValueError("unsupported_message_block")
        return content


@app.post("/internal/threads/{thread_id}/messages", status_code=202)
async def enqueue_message(
    thread_id: str,
    payload: EnqueueMessage,
    authorization: str | None = Header(default=None),
) -> dict:
    facts = await authenticate(authorization)
    scope = facts.get("runtime_scope", {})
    if (
        scope.get("operation") != "message-enqueue"
        or scope.get("thread_id") != thread_id
        or scope.get("project_id") is None
        or scope.get("assistant_id") not in {"reference_agent", "showcase_demo"}
    ):
        raise HTTPException(403, "thread scope denied")
    dsn = os.getenv("DATABASE_URI")
    if not dsn:
        raise HTTPException(503, "message inbox unavailable")
    if os.getenv("RUNTIME_MESSAGE_QUEUE_ENABLED", "true").lower() not in {"true", "1"}:
        existing = await asyncio.to_thread(
            MessageInbox(dsn).has_message,
            thread_id=thread_id,
            sender_id=str(facts["identity"]),
            message_id=str(payload.client_message_id),
        )
        if not existing:
            raise HTTPException(409, "queue_disabled")
    async with httpx.AsyncClient(
        base_url=os.getenv("RUNTIME_SELF_URL", "http://127.0.0.1:8123"),
        headers={"authorization": authorization},
        timeout=10,
    ) as client:
        response = await client.get(
            f"/threads/{thread_id}/runs/{payload.target_run_id}"
        )
        response.raise_for_status()
        if response.json().get("status") != "running":
            # Resolve an earlier accepted request even after its Run ended.
            existing = await asyncio.to_thread(
                MessageInbox(dsn).has_message,
                thread_id=thread_id,
                sender_id=str(facts["identity"]),
                message_id=str(payload.client_message_id),
            )
            if not existing:
                raise HTTPException(409, "run_changed")
    try:
        receipt = await asyncio.to_thread(
            MessageInbox(dsn).enqueue,
            thread_id=thread_id,
            target_run_id=str(payload.target_run_id),
            sender_id=str(facts.get("identity", "")),
            client_message_id=str(payload.client_message_id),
            idempotency_key=payload.idempotency_key,
            content=payload.content,
            authorization_ref=payload.authorization_ref,
        )
    except ValueError as exc:
        status = {"payload_too_large": 413, "queue_full": 429}.get(str(exc), 409)
        logger.info(
            "runtime_message_intake_rejected reason=%s status=%s", str(exc), status
        )
        raise HTTPException(status, str(exc)) from exc
    return receipt.__dict__


@app.get("/internal/threads/{thread_id}/messages")
async def list_messages(
    thread_id: str, authorization: str | None = Header(default=None)
) -> dict:
    facts = await authenticate(authorization)
    scope = facts.get("runtime_scope", {})
    if (
        scope.get("operation") not in {"message-read", "message-enqueue"}
        or scope.get("thread_id") != thread_id
    ):
        raise HTTPException(403, "thread scope denied")
    dsn = os.getenv("DATABASE_URI")
    if not dsn:
        raise HTTPException(503, "message inbox unavailable")
    from langgraph_runtime_pg.checkpoint import get_checkpointer

    inbox = MessageInbox(dsn)
    pending_runs = await asyncio.to_thread(
        inbox.pending_runs, thread_id=thread_id, sender_id=str(facts["identity"])
    )
    async with httpx.AsyncClient(
        base_url=os.getenv("RUNTIME_SELF_URL", "http://127.0.0.1:8123"),
        headers={"authorization": authorization},
        timeout=10,
    ) as client:
        for run_id in pending_runs:
            response = await client.get(f"/threads/{thread_id}/runs/{run_id}")
            response.raise_for_status()
            status = response.json()["status"]
            reason = (
                ("run_cancelled" if status == "cancelled" else "run_ended")
                if status in {"success", "error", "timeout", "cancelled", "interrupted"}
                else None
            )
            await reconcile_run(
                inbox,
                get_checkpointer(),
                thread_id=thread_id,
                run_id=run_id,
                terminal_reason=reason,
            )
    rows = await asyncio.to_thread(
        inbox.list, thread_id=thread_id, sender_id=str(facts["identity"])
    )
    return {"messages": [item.__dict__ for item in rows]}


@app.get("/internal/capabilities/tools")
async def tool_catalog(authorization: str | None = Header(default=None)) -> dict:
    """Runtime owns tool capabilities; the platform owns project grants."""
    await authenticate(authorization)
    from runtime_service.services.demo.showcase_demo.agent import _TOOL_PERMISSIONS

    permissions = {"read_reference": "runtime.tool.read", **_TOOL_PERMISSIONS}
    return {
        "tools": [
            {
                "tool_key": name,
                "name": name,
                "source": "runtime",
                "permissions": [permission],
            }
            for name, permission in sorted(permissions.items())
        ]
    }


__all__ = ["app", "lifespan"]
