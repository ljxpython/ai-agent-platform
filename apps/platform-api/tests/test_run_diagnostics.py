from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from platform_api.core.context.models import ActorContext
from platform_api.core.db import (
    build_engine,
    build_session_factory,
    create_core_tables,
    session_scope,
)
from platform_api.core.errors import (
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    register_exception_handlers,
)
from platform_api.modules.iam.domain import ProjectRole
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.application.diagnostics import (
    RuntimeDiagnostics,
)
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    _redact_runtime_private_fields,
    _redact_sse_frame,
    get_actor_context,
    get_runtime_gateway_service,
    router,
)

THREAD, RUN = str(uuid4()), str(uuid4())
CANARY = "raw-provider-secret-canary"


def summary():
    return {
        "version": 1,
        "availability": "disabled",
        "unavailable_reason": "not_configured",
        "correlation": {
            "execution_request_id": "execution-request",
            "platform_trace_id": "execution-trace",
        },
        "trace": None,
        "graph_executions": [],
        "model_errors": [],
        "startup": None,
        "truncated": False,
    }


def test_service_run_authorization_and_safe_projection():
    upstream = SimpleNamespace(
        get_thread_run=AsyncMock(
            return_value={"thread_id": THREAD, "run_id": RUN, "status": "success"}
        ),
        get_run_diagnostics=AsyncMock(
            return_value={**summary(), "message": CANARY, "body": CANARY}
        ),
    )
    service = RuntimeGatewayService(session_factory=None, upstream=upstream)
    service._load_thread = AsyncMock(
        return_value={"thread_id": THREAD, "metadata": {"graph_id": "reference_agent"}}
    )
    service._thread_upstream = AsyncMock(return_value=upstream)
    kwargs = {
        "actor": ActorContext(user_id="owner"),
        "project_id": "project",
        "thread_id": THREAD,
        "run_id": RUN,
        "request_id": "query-request",
    }
    result = asyncio.run(service.get_thread_run_diagnostics(**kwargs))
    assert (
        result["request_id"] == "query-request"
        and result["correlation"]["execution_request_id"] == "execution-request"
    )
    assert result["run_status"] == "success" and CANARY not in json.dumps(result)
    assert service._thread_upstream.await_args.kwargs["operation"] == "diagnostics-read"
    upstream.get_run_diagnostics.reset_mock()
    for failure in (NotFoundError(), ForbiddenError()):
        upstream.get_thread_run.side_effect = failure
        with pytest.raises(type(failure)):
            asyncio.run(service.get_thread_run_diagnostics(**kwargs))
        upstream.get_run_diagnostics.assert_not_awaited()
    upstream.get_thread_run.side_effect = None
    upstream.get_thread_run.return_value = {
        "thread_id": str(uuid4()),
        "run_id": RUN,
        "status": "error",
    }
    with pytest.raises(NotFoundError):
        asyncio.run(service.get_thread_run_diagnostics(**kwargs))
    upstream.get_run_diagnostics.assert_not_awaited()
    upstream.get_thread_run.return_value = {
        "thread_id": THREAD,
        "run_id": RUN,
        "status": "error",
    }
    upstream.get_run_diagnostics.return_value = {**summary(), "version": 99}
    with pytest.raises(PlatformApiError) as invalid:
        asyncio.run(service.get_thread_run_diagnostics(**kwargs))
    assert invalid.value.status_code == 502


def test_reliability_optional_dto_safety_and_private_marker_boundary():
    from platform_api.core.runtime_contract import reject_private_runtime_state

    preparation = {
        "observation_id": "prep",
        "scope": "primary",
        "namespace": [],
        "component": "workspace",
        "outcome": "reused",
        "duration_ms": 0,
        "fingerprint": CANARY,
    }
    retry = {
        "observation_id": "retry",
        "scope": "primary",
        "namespace": [],
        "unit": "model",
        "role": None,
        "attempts": 2,
        "outcome": "success",
        "code": "provider_rate_limited",
        "body": CANARY,
    }
    old = RuntimeDiagnostics.model_validate(summary()).model_dump()
    assert old["preparations"] == old["retries"] == []
    new = RuntimeDiagnostics.model_validate(
        {**summary(), "preparations": [preparation], "retries": [retry]}
    ).model_dump()
    assert CANARY not in json.dumps(new) and new["retries"][0]["attempts"] == 2
    for attempts in (0, 3, True, 1.5):
        with pytest.raises(ValidationError):
            RuntimeDiagnostics.model_validate(
                {**summary(), "retries": [{**retry, "attempts": attempts}]}
            )
    for duration in (-1, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            RuntimeDiagnostics.model_validate(
                {
                    **summary(),
                    "preparations": [{**preparation, "duration_ms": duration}],
                }
            )
    with pytest.raises(ValidationError):
        RuntimeDiagnostics.model_validate({**summary(), "retries": [retry] * 21})
    with pytest.raises(ValueError, match="private state"):
        reject_private_runtime_state({"runtime_prepare": {"workspace": "a" * 64}})
    values = {
        "runtime_prepare": {"workspace": CANARY},
        "messages": [{"content": "ordinary"}],
    }
    assert _redact_runtime_private_fields({"values": values}) == {
        "values": {"messages": [{"content": "ordinary"}]}
    }


def test_real_acl_owner_shared_peer_and_cross_project():
    with tempfile.TemporaryDirectory() as directory:
        engine = build_engine(f"sqlite:///{Path(directory) / 'acl.db'}")
        factory = build_session_factory(engine)
        create_core_tables(engine)
        with session_scope(factory) as session:
            repo = SqlAlchemyProjectsRepository(session)
            tenant = repo.get_or_create_default_tenant()
            project = str(
                repo.create_project(
                    tenant_id=tenant.id, name="Diagnostics", description=""
                ).id
            )
            other = str(
                repo.create_project(
                    tenant_id=tenant.id, name="Other", description=""
                ).id
            )
            identities = SqlAlchemyIdentityRepository(session)
            users = [
                identities.create_user(
                    username=name,
                    password_hash="unused",
                    external_subject=name,
                    email=None,
                    platform_roles=(),
                    is_super_admin=False,
                ).id
                for name in ("owner", "peer")
            ]
            from uuid import UUID

            for user in users:
                repo.upsert_project_member(
                    project_id=UUID(project), user_id=user, role=ProjectRole.EXECUTOR
                )
        owner = ActorContext(
            user_id=str(users[0]),
            project_roles={
                project: ("project_executor",),
                other: ("project_executor",),
            },
        )
        peer = ActorContext(
            user_id=str(users[1]), project_roles={project: ("project_executor",)}
        )
        thread_access.register(
            factory, thread_id=THREAD, project_id=project, actor=owner
        )
        upstream = SimpleNamespace(
            get_thread=AsyncMock(
                return_value={
                    "thread_id": THREAD,
                    "metadata": {"project_id": project, "graph_id": "reference_agent"},
                }
            ),
            get_thread_run=AsyncMock(
                return_value={"thread_id": THREAD, "run_id": RUN, "status": "error"}
            ),
            get_run_diagnostics=AsyncMock(return_value=summary()),
        )
        service = RuntimeGatewayService(session_factory=factory, upstream=upstream)
        kwargs = {
            "project_id": project,
            "thread_id": THREAD,
            "run_id": RUN,
            "request_id": "query",
        }
        assert (
            asyncio.run(service.get_thread_run_diagnostics(actor=owner, **kwargs))[
                "run_status"
            ]
            == "error"
        )
        upstream.get_run_diagnostics.reset_mock()
        for actor, scope in ((peer, project), (owner, other)):
            with pytest.raises(ForbiddenError):
                asyncio.run(
                    service.get_thread_run_diagnostics(
                        actor=actor, **{**kwargs, "project_id": scope}
                    )
                )
            upstream.get_run_diagnostics.assert_not_awaited()
        asyncio.run(
            service.share_thread(
                actor=owner,
                project_id=project,
                thread_id=THREAD,
                user_id=peer.user_id,
                actions=["read"],
            )
        )
        assert (
            asyncio.run(service.get_thread_run_diagnostics(actor=peer, **kwargs))[
                "availability"
            ]
            == "disabled"
        )
        engine.dispose()


@pytest.mark.parametrize(
    "bad",
    [
        {"version": 2},
        {"truncated": "yes"},
        {"trace": {"provider": "langfuse", "trace_id": "id", "url": "https://secret"}},
        {
            "graph_executions": [
                {
                    "observation_id": "id",
                    "outcome": "failed",
                    "duration_ms": float("inf"),
                }
            ]
        },
    ],
)
def test_dto_rejects_invalid_or_sensitive_shapes(bad):
    with pytest.raises(ValidationError):
        RuntimeDiagnostics.model_validate({**summary(), **bad})


def test_error_slots_and_normal_tool_content():
    original = {
        "error": "normal tool error",
        "message": CANARY,
        "thread_id": "tool-payload",
    }
    payload = {
        "thread_id": THREAD,
        "error": {"type": "RateLimitError", "message": CANARY, "stack": CANARY},
        "values": {"messages": [original]},
        "tasks": [{"id": "task", "error": CANARY}],
        "checkpoint": {"id": "checkpoint"},
    }
    safe = _redact_runtime_private_fields(payload)
    assert safe["values"]["messages"] == [original]
    assert safe["error"]["type"] == "RateLimitError" and CANARY not in json.dumps(
        safe["error"]
    )
    assert CANARY not in json.dumps(safe["tasks"])
    frame = (
        b"id: cursor-1\nevent: messages\ndata: "
        + json.dumps(
            {
                "method": "lifecycle",
                "seq": 8,
                "event_id": "event-8",
                "params": {
                    "run_id": RUN,
                    "namespace": [],
                    "data": {
                        "event": "error",
                        "status": "error",
                        "error": {
                            "type": "RateLimitError",
                            "message": CANARY,
                            "stack": CANARY,
                        },
                    },
                },
            }
        ).encode()
    )
    cleaned = _redact_sse_frame(frame)
    assert (
        CANARY.encode() not in cleaned
        and b"id: cursor-1" in cleaned
        and b'"seq":8' in cleaned
    )
    decoded = json.loads(cleaned.decode().split("data: ")[1])
    assert decoded["params"]["data"]["event"] == "failed"
    for event in ("error", "lifecycle"):
        data = (
            {"error": "RateLimitError", "message": CANARY}
            if event == "error"
            else {"status": "error", "error": CANARY}
        )
        safe_frame = _redact_sse_frame(
            f"event: {event}\nid: 1\ndata: {json.dumps(data)}".encode(), protocol=False
        )
        assert CANARY.encode() not in safe_frame
    normal = _redact_sse_frame(
        b"event: messages\ndata: " + json.dumps(original).encode(), protocol=False
    )
    assert CANARY.encode() in normal


@pytest.mark.parametrize(
    ("protocol", "typed"), [(True, True), (False, True), (False, False)]
)
def test_debug_task_result_error_and_checkpoint_slots(protocol, typed):
    original = {"error": "normal tool error", "message": CANARY}
    for method, data in (
        (
            "debug",
            {
                "type": "task_result",
                "payload": {"error": CANARY, "result": original, "interrupts": []},
            },
        ),
        (
            "checkpoints",
            {"tasks": [{"error": CANARY}], "values": {"messages": [original]}},
        ),
    ):
        payload = (
            {"method": method, "params": {"namespace": [], "data": data}, "seq": 9}
            if typed
            else data
        )
        event = "event" if protocol else f"{method}|researcher"
        cleaned = _redact_sse_frame(
            f"id: 9\nevent: {event}\ndata: {json.dumps(payload)}".encode(),
            protocol=protocol,
        )
        assert f"event: {event}".encode() in cleaned and b"id: 9" in cleaned
        safe = json.loads(cleaned.decode().split("data: ")[1])
        safe_data = safe["params"]["data"] if typed else safe
        if method == "debug":
            assert CANARY not in json.dumps(safe_data["payload"]["error"])
            assert safe_data["payload"]["result"] == original
        else:
            assert CANARY not in json.dumps(safe_data["tasks"])
            assert safe_data["values"]["messages"] == [original]


def test_http_no_store_and_errors():
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    service = SimpleNamespace(
        get_thread_run_diagnostics=AsyncMock(
            return_value={
                **summary(),
                "thread_id": THREAD,
                "run_id": RUN,
                "run_status": "error",
                "request_id": "query",
            }
        )
    )
    app.dependency_overrides[get_actor_context] = lambda: ActorContext(user_id="owner")
    app.dependency_overrides[get_runtime_gateway_service] = lambda: service

    @app.middleware("http")
    async def scope(request, call_next):
        request.state.platform_context = SimpleNamespace(
            project=SimpleNamespace(project_id=request.headers.get("x-project-id")),
            request=SimpleNamespace(request_id="query"),
        )
        return await call_next(request)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            url = f"/api/langgraph/threads/{THREAD}/runs/{RUN}/diagnostics"
            response = await client.get(url, headers={"x-project-id": "project"})
            assert (
                response.status_code == 200
                and response.headers["cache-control"] == "no-store"
            )
            assert response.json()["request_id"] == "query"
            service.get_thread_run_diagnostics.reset_mock()
            assert (await client.get(url)).status_code == 400
            service.get_thread_run_diagnostics.assert_not_awaited()
            service.get_thread_run_diagnostics.side_effect = ForbiddenError()
            assert (
                await client.get(url, headers={"x-project-id": "project"})
            ).status_code == 403
            assert (
                await client.get(
                    url.replace(RUN, "invalid"), headers={"x-project-id": "project"}
                )
            ).status_code == 422

    asyncio.run(run())
