import asyncio
import hashlib
import hmac
import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import jwt
import pytest
from fastapi import FastAPI
from langgraph_runtime_pg.auth import PrincipalMiddleware
from langgraph_sdk import Auth

from runtime_service.auth.platform import (
    auth,
    authenticate_ingress,
    deny_image_scope_on_server_resources,
)
from runtime_service.http.usage_analytics import router
from runtime_service.runtime.resolver import runtime_context_hash

SECRET = "usage-test-secret-at-least-32-bytes"
PATH = "/internal/usage/aggregate"
BODY = {
    "version": 1,
    "actor_id": "actor",
    "tenant_id": "analytics-test",
    "project_ids": ["10000000-0000-0000-0000-000000000001"],
    "request_id": "request",
    "from": "2026-10-01T00:00:00Z",
    "to": "2026-10-02T00:00:00Z",
}


def signed(body, *, path=PATH, method="POST", stamp=None):
    stamp = str(int(time.time())) if stamp is None else str(stamp)
    signature = hmac.new(
        SECRET.encode(),
        f"usage-query/v1\n{stamp}\n{method}\n{path}\n".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    return {
        "x-usage-query-timestamp": stamp,
        "x-usage-query-signature": "sha256=" + signature,
    }


def test_signed_query_and_all_authentication_boundaries(monkeypatch):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    app = FastAPI()
    app.include_router(router)

    async def verify():
        body = json.dumps(BODY).encode()
        with patch(
            "runtime_service.http.usage_analytics.query_aggregate",
            AsyncMock(return_value={"safe": True}),
        ) as execute:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://runtime"
            ) as client:
                good = await client.post(PATH, content=body, headers=signed(body))
                assert (
                    good.status_code == 200
                    and good.headers["cache-control"] == "no-store"
                )
                bad_headers = [
                    {},
                    {"authorization": "Bearer OLD_USAGE_READ_JWT"},
                    signed(body, stamp=int(time.time()) - 31),
                    signed(body, method="GET"),
                    signed(body, path="/internal/usage/runs/query"),
                    {**signed(body), "x-usage-query-signature": "sha256=wrong"},
                    {**signed(body), "x-usage-query-signature": b"\xe9"},
                ]
                for headers in bad_headers:
                    assert (
                        await client.post(PATH, content=body, headers=headers)
                    ).status_code == 401
                changed = json.dumps({**BODY, "tenant_id": "other"}).encode()
                assert (
                    await client.post(PATH, content=changed, headers=signed(body))
                ).status_code == 401
                repeated = list(signed(body).items()) + [
                    ("x-usage-query-timestamp", str(int(time.time())))
                ]
                assert (
                    await client.post(PATH, content=body, headers=repeated)
                ).status_code == 401
                oversized = b"x" * 65537
                assert (
                    await client.post(
                        PATH, content=oversized, headers=signed(oversized)
                    )
                ).status_code == 413
                for invalid in (
                    json.dumps({**BODY, "unknown": "SECRET"}).encode(),
                    b'{"version":1,"version":1}',
                    b"broken",
                ):
                    assert (
                        await client.post(
                            PATH, content=invalid, headers=signed(invalid)
                        )
                    ).status_code == 400
                assert (await client.get(PATH, headers=signed(body))).status_code == 405
                assert (
                    await client.post(
                        "/internal/usage/runs/query", content=body, headers=signed(body)
                    )
                ).status_code == 401
                execute.assert_awaited_once()

    asyncio.run(verify())


def test_engine_principal_middleware_and_router_enforce_hmac(monkeypatch):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "usage-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    app = FastAPI()
    app.include_router(router)
    guarded = PrincipalMiddleware(app, auth_handler=auth, allow_anonymous=False)
    now = int(time.time())
    token = jwt.encode(
        {
            "type": "runtime_delegation",
            "sub": "actor",
            "tenant_id": "analytics-test",
            "project_id": BODY["project_ids"][0],
            "role": "admin",
            "permissions": ["project.runtime.read"],
            "policy_version": "1",
            "allowed_model_ids": ["model"],
            "delegation_version": 2,
            "tool_overrides": {},
            "tool_policy_version": "1",
            "iat": now,
            "exp": now + 60,
            "iss": "usage-test",
            "aud": "runtime-service",
            "scope": {
                "tenant_id": "analytics-test",
                "project_id": BODY["project_ids"][0],
                "assistant_id": "agent",
                "thread_id": "thread",
                "operation": "usage-read",
            },
            "context_hash": runtime_context_hash(None),
        },
        SECRET,
        algorithm="HS256",
    )

    async def verify():
        body = json.dumps(BODY).encode()
        with patch(
            "runtime_service.http.usage_analytics.query_aggregate",
            AsyncMock(return_value={"safe": True}),
        ) as execute:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=guarded), base_url="http://runtime"
            ) as client:
                assert (
                    await client.post(PATH, content=body, headers=signed(body))
                ).status_code == 200
                for headers in (
                    {},
                    {"authorization": "Bearer " + token},
                    {**signed(body), "x-usage-query-signature": "sha256=wrong"},
                    list(signed(body).items())
                    + [
                        (
                            "x-usage-query-signature",
                            signed(body)["x-usage-query-signature"],
                        )
                    ],
                ):
                    assert (
                        await client.post(PATH, content=body, headers=headers)
                    ).status_code == 401
                for path in (
                    "/assistants/search",
                    "/threads/thread/runs",
                    "/internal/models/resolve",
                    "/internal/threads/thread/workspace/files",
                    PATH + "/",
                ):
                    assert (
                        await client.post(
                            path, content=body, headers=signed(body, path=path)
                        )
                    ).status_code == 401
                assert (await client.get(PATH, headers=signed(body))).status_code == 401
                execute.assert_awaited_once()
        ingress = await authenticate_ingress(
            path=PATH,
            method="POST",
            headers={k.encode(): v.encode() for k, v in signed(body).items()},
        )
        assert ingress["permissions"] == [] and "runtime_scope" not in ingress
        with pytest.raises(Auth.exceptions.HTTPException) as denied:
            await deny_image_scope_on_server_resources(
                SimpleNamespace(user=ingress, resource="threads", action="read"), {}
            )
        assert denied.value.status_code == 403

    asyncio.run(verify())


def test_frozen_hmac_vector_matches_runtime_verifier(monkeypatch):
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[4]
            / "docs/projects/20261011-token-usage-dashboard/fixtures/hmac-vector.json"
        ).read_text()
    )
    monkeypatch.setenv(
        "PLATFORM_RUNTIME_DELEGATION_SECRET", fixture["secret_for_test_only"]
    )
    body = fixture["body_utf8"].encode()
    canonical = (
        f"usage-query/v1\n{fixture['timestamp']}\nPOST\n{fixture['path']}\n".encode()
        + body
    )
    assert hashlib.sha256(canonical).hexdigest() == fixture["canonical_sha256"]
    app = FastAPI()
    app.include_router(router)

    async def verify():
        with (
            patch(
                "runtime_service.http.usage_analytics.time.time",
                return_value=int(fixture["timestamp"]),
            ),
            patch(
                "runtime_service.http.usage_analytics.query_aggregate",
                AsyncMock(return_value={"safe": True}),
            ),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://runtime"
            ) as client:
                response = await client.post(
                    fixture["path"],
                    content=body,
                    headers={
                        "x-usage-query-timestamp": fixture["timestamp"],
                        "x-usage-query-signature": fixture["signature"],
                    },
                )
                assert response.status_code == 200

    asyncio.run(verify())
