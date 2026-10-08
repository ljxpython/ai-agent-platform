import asyncio
from unittest.mock import AsyncMock

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langgraph_sdk import Auth

from runtime_service.auth import platform
from runtime_service.http import usage
from runtime_service.observability.usage_query import empty_summary
from tests.http.test_diagnostics import RUN, SECRET, THREAD, token


def test_usage_operation_acl_and_invalid_queries(monkeypatch):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "platform-api")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("PLATFORM_THREAD_AUTHORIZATION_URL", "http://acl.test")
    allowed = [THREAD]

    async def acl(endpoint, payload, headers):
        return httpx.Response(
            200,
            request=httpx.Request("POST", endpoint),
            json={"allowed_thread_ids": allowed},
        )

    monkeypatch.setattr(platform, "post_acl", acl)
    queried = AsyncMock(
        return_value={
            **empty_summary("not_recorded"),
            "thread_id": THREAD,
            "run_id": RUN,
        }
    )
    monkeypatch.setattr(usage, "query_run_usage", queried)
    app = FastAPI()
    app.include_router(usage.router)

    @app.exception_handler(Auth.exceptions.HTTPException)
    async def handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://runtime.test"
        ) as client:
            path = f"/internal/threads/{THREAD}/runs/{RUN}/usage"
            for operation in (
                "read",
                "diagnostics-read",
                "run-create",
                "message-read",
                "workspace-file-read",
                "cron-read",
                "suggestions-generate",
            ):
                assert (
                    await client.get(
                        path, headers={"authorization": "Bearer " + token(operation)}
                    )
                ).status_code == 403
            queried.assert_not_awaited()
            headers = {"authorization": "Bearer " + token("usage-read")}
            result = await client.get(path, headers=headers)
            assert (
                result.status_code == 200
                and result.headers["cache-control"] == "no-store"
            )
            assert queried.await_args.args[0]["run_id"] == RUN
            allowed.clear()
            queried.reset_mock()
            assert (await client.get(path, headers=headers)).status_code == 403
            queried.assert_not_awaited()
            assert (
                await client.get(path, headers={"authorization": "Bearer forged"})
            ).status_code == 401

    asyncio.run(run())
