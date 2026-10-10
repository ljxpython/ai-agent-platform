"""F07 HTTP/Worker verification using the existing isolated native-service harness."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from dotenv import dotenv_values
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from tests.integration import test_model_resilience_worker as harness

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_THREAD_TITLE_FLOW") != "1",
        reason="isolated title HTTP/Worker opt-in",
    ),
]


@pytest.mark.parametrize("provider", ["fixture", "real"])
def test_isolated_thread_title_http_worker_and_real_model(
    monkeypatch, tmp_path, provider
):
    if provider == "real" and os.getenv("TITLE_REAL_MODEL") != "1":
        pytest.skip("real managed-model opt-in")
    from platform_api import config
    from platform_api.core.security import empty_runtime_context_hash
    from platform_api.modules.runtime_catalog.infra.sqlalchemy.repository import (
        SqlAlchemyRuntimeCatalogRepository,
    )

    original_settings = config.Settings
    active_settings = {}
    platform_state = {}
    monkeypatch.setenv("MODEL_RESILIENCE_WORKER_SCENARIOS", "title-only")
    title_started, release_title = asyncio.Event(), asyncio.Event()
    behavior = {"title": "ok"}

    def install_provider(app, calls):
        @app.post("/fixture/v1/chat/completions")
        async def complete(request: Request):
            body = await request.json()
            is_title = not body.get("stream")
            kind = "title" if is_title else "agent"
            calls[kind] = calls.get(kind, 0) + 1
            if is_title:
                assert "tools" not in body and body.get("stream") is not True
                if behavior["title"] == "wait":
                    title_started.set()
                    await asyncio.wait_for(release_title.wait(), 10)
                if behavior["title"] == "failure":
                    return JSONResponse(
                        status_code=503,
                        content={
                            "error": {
                                "message": "private-provider-error",
                                "type": "server_error",
                            }
                        },
                    )
                return JSONResponse(
                    {
                        "id": "title-fixture",
                        "object": "chat.completion",
                        "model": "fixture",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "原子更新设计",
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 40,
                            "completion_tokens": 6,
                            "total_tokens": 46,
                        },
                    }
                )

            async def stream():
                for delta, finish in (
                    (
                        {"role": "assistant", "content": "使用数据库原子条件更新。"},
                        None,
                    ),
                    ({}, "stop"),
                ):
                    chunk = {
                        "id": "agent-fixture",
                        "object": "chat.completion.chunk",
                        "model": "fixture",
                        "choices": [
                            {"index": 0, "delta": delta, "finish_reason": finish}
                        ],
                    }
                    yield "data: " + json.dumps(chunk) + "\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(stream(), media_type="text/event-stream")

    async def create_agent(app, client, project, provider_url):
        platform_state["session_factory"] = app.state.db_session_factory
        (await client.post("/api/runtime/graphs/refresh")).raise_for_status()
        if provider == "real":
            secrets = dotenv_values(
                os.getenv(
                    "TITLE_MODEL_ENV_FILE", str(Path.home() / ".my_best" / ".env")
                )
            )
            if os.getenv("TITLE_REAL_PROVIDER") == "bailian":
                connection = {
                    "base_url": secrets.get("BAILIAN_URL"),
                    "api_key": secrets.get("BAILIAN_KEY"),
                    "model": "qwen-plus",
                }
            else:
                connection = {
                    "base_url": secrets.get("MIAOMIAOAI_PROXY_URL"),
                    "api_key": secrets.get("MIAOMIAOAI_PROXY_API_KEY"),
                    "model": secrets.get("MIAOMIAOAI_PROXY_DEFAULT_MODEL"),
                }
            assert all(connection.values()), "real model configuration is required"
        else:
            connection = {
                "base_url": "https://provider.invalid/v1",
                "api_key": "synthetic-key",
                "model": "fixture",
            }
        response = await client.post(
            "/api/runtime/models",
            json={
                "provider": "openai",
                "display_name": "Title fixture",
                "protocol": "openai",
                "scope_type": "project",
                "project_id": project,
                **connection,
            },
        )
        response.raise_for_status()
        model_id = response.json()["id"]
        if provider == "fixture":
            with app.state.db_session_factory.begin() as session:
                SqlAlchemyRuntimeCatalogRepository(session).update_configured_model(
                    UUID(model_id), values={"base_url": provider_url + "/fixture/v1"}
                )
        response = await client.post(
            f"/api/projects/{project}/agents",
            json={
                "name": "Title fixture",
                "graph_id": "reference_agent",
                "context": {"model_id": model_id},
            },
        )
        response.raise_for_status()
        return response.json(), [model_id]

    async def verify(client, dsn, calls, ids, agent, directory):
        evidence = {"provider": provider, "scenarios": []}

        async def wait_for_title(request):
            waiting = asyncio.create_task(title_started.wait())
            try:
                done, _ = await asyncio.wait(
                    {waiting, request}, timeout=35, return_when=asyncio.FIRST_COMPLETED
                )
                if waiting not in done:
                    response = request.result() if request.done() else None
                    reason = (
                        response.json().get("reason")
                        if response is not None
                        else "pending"
                    )
                    raise AssertionError(f"title did not reach provider: {reason}")
            finally:
                waiting.cancel()
                await asyncio.gather(waiting, return_exceptions=True)

        async def new_round():
            response = await client.post(
                "/api/langgraph/threads",
                json={
                    "auto_title": True,
                    "metadata": {"graph_id": "reference_agent", "title": "规则标题"},
                },
            )
            response.raise_for_status()
            thread = response.json()
            assert (
                thread["metadata"]["auto_title_pending"] is True
                and "_runtime_title_seed" not in thread["metadata"]
            )
            path = "/api/langgraph/threads/" + thread["thread_id"]
            response = await client.post(
                path + "/runs",
                json={
                    "assistant_id": "reference_agent",
                    "context": {"model_id": ids[0]},
                    "input": {
                        "messages": [
                            {
                                "role": "user",
                                "content": "只用一句中文解释数据库的原子更新，不调用工具。",
                            }
                        ]
                    },
                },
                headers={"Idempotency-Key": str(uuid4())},
            )
            response.raise_for_status()
            run_id = response.json()["run_id"]
            try:
                async with asyncio.timeout(180 if provider == "real" else 60):
                    while True:
                        run = await client.get(path + "/runs/" + run_id)
                        run.raise_for_status()
                        if run.json()["status"] not in {"pending", "running"}:
                            break
                        await asyncio.sleep(0.1)
            except TimeoutError:
                status = run.json().get("status")
                raise AssertionError(f"main model Run wait expired: {status}") from None
            assert run.json()["status"] == "success", (
                "main model Run failed: " + run.json()["status"]
            )
            stream = await client.get(
                path + "/runs/" + run_id + "/stream",
                params={"cancel_on_disconnect": "false"},
            )
            stream.raise_for_status()
            state = (await client.get(path + "/state")).json()
            assert state["values"]["messages"][-1]["content"]
            return path, run_id, state, stream.text

        path, run_id, before, main_stream = await new_round()
        started = time.monotonic()
        body = {"mode": "auto", "run_id": run_id}
        response = await client.post(path + "/title/summarize", json=body)
        response.raise_for_status()
        result = response.json()
        diagnostic = {
            "provider": provider,
            "real_provider": os.getenv("TITLE_REAL_PROVIDER", "miaomiao")
            if provider == "real"
            else None,
            "outcome": result["outcome"],
            "reason": result["reason"],
            "duration_seconds": round(time.monotonic() - started, 3),
            "run_status": "success",
        }
        (directory / "title-diagnostic.json").write_text(
            json.dumps(diagnostic, indent=2)
        )
        print(json.dumps(diagnostic))
        assert result["outcome"] == "applied", diagnostic
        assert (
            len(result["title"]) <= 10
            and result["metadata"]["auto_title_pending"] is False
        )
        assert (await client.get(path)).json()["metadata"]["title"] == result["title"]
        assert (await client.get(path + "/state")).json() == before
        assert (
            await client.get(
                path + "/runs/" + run_id + "/stream",
                params={"cancel_on_disconnect": "false"},
            )
        ).text == main_stream
        assert (await client.post(path + "/title/summarize", json=body)).json()[
            "reason"
        ] == "not_pending"
        assert (
            "_runtime_title_seed" not in response.text
            and "private-provider" not in response.text
        )
        evidence["scenarios"].append(
            {
                "name": "success-refresh-main-stream-isolation",
                "duration_seconds": round(time.monotonic() - started, 3),
                "title_chars": len(result["title"]),
                "run_status": "success",
            }
        )
        if provider == "real":
            (directory / "title-evidence.json").write_text(
                json.dumps(evidence, indent=2)
            )
            print(json.dumps(evidence))
            return
        assert calls["agent"] == 1 and calls["title"] == 1
        project = client.headers["x-project-id"]
        claims = {
            "type": "runtime_delegation",
            "delegation_version": 2,
            "sub": "user",
            "tenant_id": "tenant",
            "project_id": project,
            "role": "project_member",
            "permissions": [],
            "policy_version": "v1",
            "allowed_model_ids": ids,
            "tool_overrides": {},
            "tool_policy_version": "v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
            "iss": "platform-api",
            "aud": "runtime-service",
            "scope": {
                "tenant_id": "tenant",
                "project_id": project,
                "thread_id": path.rsplit("/", 1)[-1],
                "assistant_id": "reference_agent",
                "operation": "title-generate",
            },
            "context_hash": empty_runtime_context_hash(),
        }
        import jwt

        runtime_url = os.environ["TITLE_TEST_RUNTIME_URL"]
        async with httpx.AsyncClient(
            base_url=runtime_url, trust_env=False, timeout=5
        ) as raw:
            internal = (
                f"/internal/threads/{claims['scope']['thread_id']}/title/summarize"
            )
            assert (
                await raw.post(internal, json={"assistant_id": "reference_agent"})
            ).status_code == 401
            auth = {
                "Authorization": "Bearer "
                + jwt.encode(claims, harness.SECRET, algorithm="HS256")
            }
            for uri in (
                path.replace("/api/langgraph", ""),
                path.replace("/api/langgraph", "") + "/runs",
                "/mcp",
            ):
                assert (await raw.get(uri, headers=auth)).status_code in {403, 404}
            assert (
                await raw.post(internal, json={"assistant_id": "other"}, headers=auth)
            ).status_code == 403
        behavior["title"] = "wait"
        title_started.clear()
        release_title.clear()
        path, run_id, _, _ = await new_round()
        request = asyncio.create_task(
            client.post(
                path + "/title/summarize", json={"mode": "auto", "run_id": run_id}
            )
        )
        await wait_for_title(request)
        renamed = await client.patch(path, json={"title": "规则标题"})
        renamed.raise_for_status()
        release_title.set()
        result = await request
        result.raise_for_status()
        assert (
            result.json()["reason"] == "not_pending"
            and result.json()["title"] == "规则标题"
        )
        behavior["title"] = "failure"
        path, run_id, _, _ = await new_round()
        result = await client.post(
            path + "/title/summarize", json={"mode": "auto", "run_id": run_id}
        )
        result.raise_for_status()
        assert (
            result.json()["outcome"] == "degraded"
            and result.json()["title"] == "规则标题"
        )
        assert result.json()["metadata"]["auto_title_pending"] is False
        assert calls["title"] == 3
        behavior["title"] = "ok"
        path, run_id, _, _ = await new_round()
        results = await asyncio.gather(
            *(
                client.post(
                    path + "/title/summarize", json={"mode": "auto", "run_id": run_id}
                )
                for _ in range(2)
            )
        )
        for response in results:
            response.raise_for_status()
        assert sum(response.json()["outcome"] == "applied" for response in results) == 1
        assert (await client.get(path)).json()["metadata"][
            "auto_title_pending"
        ] is False
        evidence["scenarios"] += [
            {"name": "native-title-token-denied"},
            {"name": "same-name-manual-wins"},
            {"name": "provider-failure-keeps-rule-no-retry"},
            {"name": "two-requests-one-cas-winner"},
        ]
        evidence["calls"] = calls
        for mutation in ("gate", "model", "acl"):
            behavior["title"] = "wait"
            title_started.clear()
            release_title.clear()
            path, run_id, _, _ = await new_round()
            request = asyncio.create_task(
                client.post(
                    path + "/title/summarize", json={"mode": "auto", "run_id": run_id}
                )
            )
            await wait_for_title(request)
            if mutation == "gate":
                active_settings["settings"].title_auto_enabled = False
            elif mutation == "model":
                (
                    await client.patch(
                        "/api/runtime/models/" + ids[0], json={"enabled": False}
                    )
                ).raise_for_status()
            else:
                from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
                    ThreadAccessRecord,
                )

                thread_id = path.rsplit("/", 1)[-1]
                with platform_state["session_factory"].begin() as session:
                    access = session.get(ThreadAccessRecord, thread_id)
                    owner = access.owner_user_id
                    access.owner_user_id = None
            release_title.set()
            result = await request
            if mutation == "gate":
                result.raise_for_status()
                assert result.json()["reason"] == "disabled"
                active_settings["settings"].title_auto_enabled = True
            elif mutation == "model":
                assert result.status_code == 403
                (
                    await client.patch(
                        "/api/runtime/models/" + ids[0], json={"enabled": True}
                    )
                ).raise_for_status()
            else:
                assert result.status_code == 403
                with platform_state["session_factory"].begin() as session:
                    session.get(ThreadAccessRecord, thread_id).owner_user_id = owner
            persisted = (await client.get(path)).json()["metadata"]
            assert (
                persisted["title"] == "规则标题"
                and persisted["auto_title_pending"] is True
            )
            evidence["scenarios"].append(
                {"name": mutation + "-revoked-during-model-no-write"}
            )
        behavior["title"] = "ok"
        path, run_id, _, _ = await new_round()
        from platform_api.adapters.langgraph.runtime_client import (
            LangGraphRuntimeClient,
        )
        from platform_api.core.errors import UpstreamServiceError

        original_json = LangGraphRuntimeClient.require_json

        async def lose_cas_response(self, method, uri, **kwargs):
            stored = await original_json(self, method, uri, **kwargs)
            if uri.endswith("/metadata/cas"):
                raise UpstreamServiceError(
                    upstream="langgraph",
                    status_code=504,
                    code="langgraph_upstream_timeout",
                    message="fixture response lost",
                )
            return stored

        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(
                LangGraphRuntimeClient, "require_json", lose_cas_response
            )
            result = await client.post(
                path + "/title/summarize", json={"mode": "auto", "run_id": run_id}
            )
        assert (
            result.status_code == 503
            and result.json()["error"]["code"] == "title_write_unconfirmed"
        )
        persisted = (await client.get(path)).json()["metadata"]
        assert (
            persisted["title"] == "原子更新设计"
            and persisted["auto_title_pending"] is False
        )
        before_calls = calls["title"]
        assert (
            await client.post(
                path + "/title/summarize", json={"mode": "auto", "run_id": run_id}
            )
        ).json()["reason"] == "not_pending"
        assert calls["title"] == before_calls
        evidence["scenarios"].append(
            {"name": "committed-cas-response-lost-get-reconciles"}
        )
        (directory / "title-evidence.json").write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence))

    original_factory = original_settings

    def configured_settings(**kwargs):
        result = original_factory(**kwargs, title_auto_enabled=True)
        active_settings["settings"] = result
        monkeypatch.setenv("TITLE_TEST_RUNTIME_URL", result.langgraph_upstream_url)
        return result

    monkeypatch.setattr(config, "Settings", configured_settings)
    monkeypatch.setattr(harness, "install_provider", install_provider)
    monkeypatch.setattr(harness, "create_managed_agent", create_agent)
    monkeypatch.setattr(harness, "verify_scenarios", verify)
    harness.test_isolated_platform_worker_preserves_attempt_budget_and_error_stream(
        monkeypatch, tmp_path
    )
