"""Root-agent queue injection with cumulative checkpoint receipts."""

from __future__ import annotations

import asyncio
import os
from typing import Annotated, Any, NotRequired

import httpx
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr
from langchain_core.messages import HumanMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime

from runtime_service.messaging import MessageInbox
from runtime_service.messaging.reconcile import reconcile_run


class MessageQueueState(AgentState):
    runtime_message_claim: NotRequired[Annotated[dict[str, Any], PrivateStateAttr]]


class MessageQueueMiddleware(AgentMiddleware):
    state_schema = MessageQueueState

    async def abefore_model(
        self, state: MessageQueueState, runtime: Runtime
    ) -> dict[str, Any] | None:
        config = get_config()
        configurable = config.get("configurable", {})
        info = runtime.execution_info
        if info and "|" in info.checkpoint_ns:
            return None
        thread_id = info.thread_id if info else configurable.get("thread_id")
        run_id = (info.run_id if info else None) or config.get("metadata", {}).get(
            "run_id"
        )
        dsn = os.getenv("DATABASE_URI")
        if not thread_id or not run_id or not dsn:
            return None
        from langgraph_runtime_pg.checkpoint import get_checkpointer

        inbox = MessageInbox(dsn)
        await reconcile_run(
            inbox, get_checkpointer(), thread_id=str(thread_id), run_id=str(run_id)
        )
        token, rows = await asyncio.to_thread(
            inbox.claim,
            thread_id=str(thread_id),
            target_run_id=str(run_id),
            owner=str(os.getpid()),
            limit=20,
        )
        if not rows:
            return None
        endpoint = os.getenv("PLATFORM_RUNTIME_MESSAGE_AUTH_URL", "")
        if not endpoint:
            raise RuntimeError("Message authorization callback is not configured")
        authorized = []
        async with httpx.AsyncClient(timeout=10) as client:
            for row in rows:
                response = await client.get(
                    endpoint,
                    params={"thread_id": str(thread_id), "run_id": str(run_id)},
                    headers={"x-runtime-message-ref": row["authorization_ref"] or ""},
                )
                if response.status_code in {401, 403}:
                    await asyncio.to_thread(
                        inbox.reject,
                        token=token,
                        message_id=row["message_id"],
                        reason="permission_revoked",
                    )
                    continue
                response.raise_for_status()
                if response.json().get("allowed") is not True:
                    raise RuntimeError(
                        "Message authorization returned an invalid response"
                    )
                authorized.append(row)
        rows = authorized
        previous = state.get("runtime_message_claim", {})
        delivered = (
            set(previous.get("message_ids", []))
            if previous.get("run_id") == str(run_id)
            else set()
        )
        messages = [
            HumanMessage(id=row["message_id"], content=row["payload"])
            for row in rows
            if row["message_id"] not in delivered
        ]
        delivered.update(row["message_id"] for row in rows)
        return {
            "messages": messages,
            "runtime_message_claim": {
                "token": token,
                "run_id": str(run_id),
                "message_ids": sorted(delivered),
            },
        }


__all__ = ["MessageQueueMiddleware"]
