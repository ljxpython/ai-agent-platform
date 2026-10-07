from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import jwt
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langgraph_sdk import Auth

from runtime_service.auth import platform
from runtime_service.http import diagnostics
from runtime_service.observability.query import empty_diagnostics
from runtime_service.runtime.resolver import runtime_context_hash

THREAD, RUN = str(uuid4()), str(uuid4())
SECRET = "diagnostics-test-secret-at-least-32-bytes"


def token(operation="diagnostics-read", **scope_overrides):
    claims = {
        "type": "runtime_delegation",
        "delegation_version": 2,
        "sub": "service-account:test",
        "credential_id": str(uuid4()),
        "tenant_id": "tenant",
        "project_id": "project",
        "role": "project_viewer",
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
            "assistant_id": "reference_agent",
            "thread_id": THREAD,
            "operation": operation,
            **scope_overrides,
        },
        "context_hash": runtime_context_hash(None),
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_real_delegation_acl_signature_and_operation_matrix(monkeypatch):
    for key, value in {
        "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
        "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
        "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
        "PLATFORM_THREAD_AUTHORIZATION_URL": "http://acl.test",
    }.items():
        monkeypatch.setenv(key, value)
    queried = AsyncMock(return_value=empty_diagnostics("not_configured"))
    monkeypatch.setattr(diagnostics, "query_run_diagnostics", queried)
    allowed = [THREAD]
    calls = []

    async def acl(endpoint, payload, headers):
        calls.append(payload)
        assert payload["action"] == "read" and payload["credential_id"]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(
            SECRET.encode(),
            f"{headers['x-runtime-acl-timestamp']}\nthread-authorization\n{canonical}".encode(),
            hashlib.sha256,
        ).hexdigest()
        assert headers["x-runtime-acl-signature"] == expected
        return httpx.Response(
            200,
            request=httpx.Request("POST", endpoint),
            json={"allowed_thread_ids": allowed},
        )

    monkeypatch.setattr(platform, "post_acl", acl)
    app = FastAPI()
    app.include_router(diagnostics.router)

    @app.exception_handler(Auth.exceptions.HTTPException)
    async def handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://runtime.test"
        ) as client:
            path = f"/internal/threads/{THREAD}/runs/{RUN}/diagnostics"
            for operation in (
                "read",
                "run-create",
                "suggestions-generate",
                "message-read",
            ):
                response = await client.get(
                    path, headers={"authorization": f"Bearer {token(operation)}"}
                )
                assert response.status_code == 403
            queried.assert_not_awaited()
            assert not calls
            response = await client.get(
                path, headers={"authorization": f"Bearer {token()}"}
            )
            assert (
                response.status_code == 200
                and response.headers["cache-control"] == "no-store"
            )
            assert queried.await_args.kwargs["run_id"] == RUN
            queried.reset_mock()
            allowed.clear()
            response = await client.get(
                path, headers={"authorization": f"Bearer {token()}"}
            )
            assert response.status_code == 403
            queried.assert_not_awaited()
            response = await client.get(
                path,
                headers={"authorization": f"Bearer {token(thread_id=str(uuid4()))}"},
            )
            assert response.status_code == 403
            response = await client.get(
                path, headers={"authorization": f"Bearer {token(tenant_id='wrong')}"}
            )
            assert response.status_code == 401
            response = await client.get(
                path, headers={"authorization": "Bearer forged"}
            )
            assert response.status_code == 401
            response = await client.get(
                path.replace(RUN, "invalid"),
                headers={"authorization": f"Bearer {token()}"},
            )
            assert response.status_code == 422

    asyncio.run(run())
