"""Real signed Delegation and title route boundaries; no model/provider calls."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import jwt
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langgraph_sdk import Auth

from runtime_service.auth import platform
from runtime_service.http import title_summary as titles
from runtime_service.runtime.resolver import runtime_context_hash

SECRET = "title-test-secret-at-least-32-bytes"


def token(operation="title-generate", **updates):
    claims = {
        "type": "runtime_delegation",
        "delegation_version": 2,
        "sub": "user",
        "tenant_id": "tenant",
        "project_id": "project",
        "role": "project_member",
        "permissions": [],
        "policy_version": "v1",
        "allowed_model_ids": ["model"],
        "tool_overrides": {},
        "tool_policy_version": "v1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        "iss": "platform-api",
        "aud": "runtime-service",
        "scope": {
            "tenant_id": "tenant",
            "project_id": "project",
            "thread_id": "thread",
            "assistant_id": "reference_agent",
            "operation": operation,
        },
        "context_hash": runtime_context_hash(None),
        **updates,
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_signed_title_http_scope_schema_acl_and_native_denial(monkeypatch):
    for key, value in {
        "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
        "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
        "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
    }.items():
        monkeypatch.setenv(key, value)
    generate = AsyncMock(
        return_value={"title": "用户注册方案", "outcome": "applied", "reason": None}
    )
    acl = AsyncMock()
    monkeypatch.setattr(titles, "generate_thread_title", generate)
    monkeypatch.setattr(titles, "authorize_thread_targets", acl)
    app = FastAPI()
    app.include_router(titles.router)

    @app.exception_handler(Auth.exceptions.HTTPException)
    async def handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    async def run():
        body = {
            "assistant_id": "reference_agent",
            "messages": [{"role": "user", "content": "注册接口"}],
        }
        path = "/internal/threads/thread/title/summarize"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.post(path, json=body)).status_code == 401
            for operation in (
                "read",
                "suggestions-generate",
                "usage-read",
                "thread-edit",
            ):
                assert (
                    await client.post(
                        path,
                        json=body,
                        headers={"authorization": f"Bearer {token(operation)}"},
                    )
                ).status_code == 403
            for changes in ({"exp": int(time.time()) - 1}, {"project_id": "other"}):
                assert (
                    await client.post(
                        path,
                        json=body,
                        headers={"authorization": f"Bearer {token(**changes)}"},
                    )
                ).status_code == 401
            headers = {"authorization": f"Bearer {token()}"}
            assert (
                await client.post(
                    path.replace("thread/title", "other/title"),
                    json=body,
                    headers=headers,
                )
            ).status_code == 403
            assert (
                await client.post(
                    path, json={**body, "assistant_id": "other"}, headers=headers
                )
            ).status_code == 403
            for changes in (
                {"seed": "inject"},
                {"messages": [{"role": "system", "content": "bad"}]},
                {"messages": [{"role": "user", "content": "x" * 4001}]},
                {"messages": body["messages"] * 9},
            ):
                assert (
                    await client.post(path, json={**body, **changes}, headers=headers)
                ).status_code == 422
            generate.assert_not_awaited()
            response = await client.post(path, json=body, headers=headers)
            assert (
                response.status_code == 200
                and response.json()["title"] == "用户注册方案"
            )
            assert [call.kwargs["action"] for call in acl.await_args_list] == [
                "comment",
                "edit",
            ]
            user = await platform.authenticate(headers["authorization"])
            for resource in ("threads", "assistants", "store"):
                try:
                    await platform.deny_image_scope_on_server_resources(
                        SimpleNamespace(user=user, resource=resource, action="read"),
                        {"thread_id": "thread"},
                    )
                except Auth.exceptions.HTTPException as exc:
                    assert exc.status_code == 403
                else:
                    raise AssertionError("title token accessed native resources")
            acl.side_effect = Auth.exceptions.HTTPException(403, "revoked")
            generate.reset_mock()
            assert (
                await client.post(path, json=body, headers=headers)
            ).status_code == 403
            generate.assert_not_awaited()

    asyncio.run(run())
