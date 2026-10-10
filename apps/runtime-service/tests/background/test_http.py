"""Exact task delegations and strict HTTP inputs."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from runtime_service.http import background_tasks as http

THREAD, TASK = str(uuid4()), str(uuid4())


@pytest.mark.parametrize("cursor", ["not_base64", "e30", "WzFd", "WyJ4IiwieSJd"])
def test_invalid_cursor_is_bounded_and_safe(cursor):
    with pytest.raises(HTTPException) as denied:
        http.cursor_value(cursor)
    assert denied.value.status_code == 422


def test_public_inputs_and_no_store(monkeypatch):
    app = FastAPI()
    app.include_router(http.router)
    operations = []

    async def authorize(token, thread, operation):
        operations.append(operation)
        return {"runtime_scope": {"thread_id": str(thread)}}

    async def storage(fn, *args):
        return {"task_id": TASK, "thread_id": THREAD}

    monkeypatch.setattr(http, "authorize", authorize)
    monkeypatch.setattr(http, "storage", storage)
    monkeypatch.setattr(http, "actions", lambda facts: ["read", "logs"])
    monkeypatch.setattr(
        http,
        "list_view",
        lambda scope, result, limit, actions: {"items": [], "thread_id": THREAD},
    )
    monkeypatch.setattr(http, "task_view", lambda row, *args: row)
    monkeypatch.setattr(
        http,
        "output_view",
        lambda row, text: {
            "text": "plain <script>",
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            path = f"/internal/threads/{THREAD}/background-tasks"
            for suffix in ("", f"/{TASK}", f"/{TASK}/output"):
                response = await client.get(path + suffix)
                assert (
                    response.status_code == 200
                    and response.headers["cache-control"] == "no-store"
                )
            response = await client.post(
                path + f"/{TASK}/cancel", json={}, headers={"Idempotency-Key": "same"}
            )
            assert (
                response.status_code == 202
                and response.headers["cache-control"] == "no-store"
            )
            for suffix in (
                "?limit=0",
                "?limit=101",
                "?limit=1&limit=2",
                "?scope=other",
                f"/{TASK}?container=other",
            ):
                assert (await client.get(path + suffix)).status_code == 422
            for body in ({"container_id": "other"}, {"command": "printf done"}):
                assert (
                    await client.post(
                        path + f"/{TASK}/cancel",
                        json=body,
                        headers={"Idempotency-Key": "same"},
                    )
                ).status_code == 422
            assert (
                await client.post(path + f"/{TASK}/cancel", json={})
            ).status_code == 422

    asyncio.run(check())
    assert operations[:4] == [
        "background-task-read",
        "background-task-read",
        "background-task-log-read",
        "background-task-cancel",
    ]


def test_wrong_operation_denied_before_storage(monkeypatch):
    from unittest.mock import AsyncMock

    authenticate = AsyncMock(
        return_value={
            "runtime_scope": {"thread_id": THREAD, "operation": "background-task-read"}
        }
    )
    monkeypatch.setattr(http, "authenticate", authenticate)
    with pytest.raises(HTTPException) as denied:
        asyncio.run(http.authorize("token", THREAD, "background-task-log-read"))
    assert denied.value.status_code == 403
