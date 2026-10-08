"""Public stop boundary and projection contract."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import PlatformApiError, register_exception_handlers
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_actor_context,
    get_runtime_gateway_service,
    router,
)

THREAD, STOP = str(uuid4()), str(uuid4())


def receipt():
    return {
        "version": 1,
        "stop_id": STOP,
        "thread_id": THREAD,
        "phase": "accepted",
        "requested_at": datetime.now(UTC).isoformat(),
        "accepted_at": None,
        "confirmed_at": None,
        "target_count": None,
        "execution_stopped": None,
        "resource_cleanup": "pending",
        "has_pending_interrupts": None,
        "queue": {
            "pending_cancelled_count": None,
            "inbox_consumed_count": None,
            "inbox_not_consumed_count": None,
        },
        "report": None,
        "reason_code": None,
    }


def test_service_ownership_and_private_projection():
    upstream = SimpleNamespace(
        stop_thread=AsyncMock(
            return_value={**receipt(), "auth_facts": {"token": "PRIVATE"}}
        )
    )
    service = RuntimeGatewayService(session_factory=None, upstream=upstream)
    service._load_thread = AsyncMock(return_value={"thread_id": THREAD})
    service._thread_upstream = AsyncMock(return_value=upstream)
    kwargs = {
        "actor": ActorContext(user_id="owner"),
        "project_id": "project",
        "thread_id": THREAD,
        "key": "same",
        "request_id": "trusted-request",
    }
    result = asyncio.run(service.thread_stop_action(**kwargs))
    assert result["request_id"] == "trusted-request" and "PRIVATE" not in json.dumps(
        result
    )
    assert service._load_thread.await_args.kwargs["write"] is True
    assert service._thread_upstream.await_args.kwargs["operation"] == "thread-stop"
    upstream.stop_thread.return_value = {**receipt(), "thread_id": str(uuid4())}
    with pytest.raises(PlatformApiError) as failed:
        asyncio.run(service.thread_stop_action(**kwargs))
    assert failed.value.status_code == 502


def test_http_input_contract_request_id_and_no_store():
    service = SimpleNamespace(
        thread_stop_action=AsyncMock(
            return_value={**receipt(), "request_id": "trusted"}
        )
    )
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    app.dependency_overrides[get_actor_context] = lambda: ActorContext(user_id="owner")
    app.dependency_overrides[get_runtime_gateway_service] = lambda: service

    @app.middleware("http")
    async def context(request, call_next):
        request.state.platform_context = SimpleNamespace(
            project=SimpleNamespace(project_id=request.headers.get("x-project-id")),
            request=SimpleNamespace(request_id="trusted"),
        )
        return await call_next(request)

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            path = f"/api/langgraph/threads/{THREAD}/cancel"
            headers = {
                "x-project-id": "project",
                "Idempotency-Key": "same",
                "x-request-id": "untrusted",
            }
            response = await client.post(path, json={}, headers=headers)
            assert (
                response.status_code == 202
                and response.headers["cache-control"] == "no-store"
            )
            assert (
                service.thread_stop_action.await_args.kwargs["request_id"] == "trusted"
            )
            for body in (
                {"run_ids": [str(uuid4())]},
                {"context": {}},
                {"action": "rollback"},
            ):
                assert (
                    await client.post(path, json=body, headers=headers)
                ).status_code == 422
            assert (
                await client.post(path, json={}, headers={"x-project-id": "project"})
            ).status_code == 422
            assert (
                await client.post(path + "?run_id=malicious", json={}, headers=headers)
            ).status_code == 422
            assert (
                await client.post(
                    path.replace(THREAD, "invalid"), json={}, headers=headers
                )
            ).status_code == 422
            assert (
                await client.get(
                    f"/api/langgraph/threads/{THREAD}/stop-requests/{STOP}?limit=1",
                    headers=headers,
                )
            ).status_code == 422

    asyncio.run(check())


@pytest.mark.parametrize(
    "status,code",
    [
        (403, "stop_scope_denied"),
        (404, "stop_request_not_found"),
        (409, "thread_stopping"),
        (422, "invalid_stop_cursor"),
        (503, "stop_storage_unavailable"),
    ],
)
def test_stop_errors_keep_safe_codes(status, code):
    from platform_api.adapters.langgraph.sdk_client import create_runtime_upstream_error

    error = create_runtime_upstream_error(
        status_code=status,
        detail={"detail": {"code": code, "message": "PRIVATE Bearer credential"}},
        fallback_code="upstream_failed",
    )
    assert (
        error.status_code == (502 if status >= 500 else status) and error.code == code
    )
    assert "PRIVATE" not in error.message and "Bearer" not in error.message


def test_stop_callback_signature_window_and_body_binding(monkeypatch):
    from platform_api.modules.runtime_catalog.presentation import http
    from platform_api.modules.runtime_gateway.application.run_control import (
        StopAuditBody,
    )

    secret = "synthetic-stop-callback-secret-at-least-32-bytes"
    data = StopAuditBody(
        stop_id=STOP,
        tenant_id="tenant",
        project_id=uuid4(),
        thread_id=THREAD,
        owner_id="service-account:" + str(uuid4()),
        credential_id=uuid4(),
        authorize=True,
        phase="accepted",
        request_id="probe",
        platform_trace_id=None,
        target_count=None,
    ).model_dump(mode="json")
    app = FastAPI()
    app.include_router(http.router)
    app.state.settings = SimpleNamespace(runtime_delegation_secret=secret)
    app.state.db_session_factory = object()
    register_exception_handlers(app)
    callback = Mock(return_value={"allowed": True})
    monkeypatch.setattr(http, "authorize_and_audit_stop", callback)

    def headers(stamp):
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            secret.encode(),
            f"{stamp}\nstop-authorization\n{canonical}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return {
            "x-runtime-acl-timestamp": str(stamp),
            "x-runtime-acl-signature": signature,
        }

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            path = "/api/runtime/internal/stop-authorization"
            valid = headers(int(time.time()))
            assert (
                await client.post(path, json=data, headers=valid)
            ).status_code == 200
            for body, signed in (
                (data, {}),
                (data, headers(int(time.time()) - 60)),
                (data, headers(int(time.time()) + 60)),
                ({**data, "thread_id": str(uuid4())}, valid),
                ({**data, "credential_id": str(uuid4())}, valid),
                (data, {**valid, "x-runtime-acl-signature": "0" * 64}),
            ):
                response = await client.post(path, json=body, headers=signed)
                assert response.status_code == 403, response.text
                assert (
                    response.json()["error"]["code"] == "runtime_acl_signature_invalid"
                )
        assert callback.call_count == 1
        assert str(callback.call_args.args[1].credential_id) == data["credential_id"]

    asyncio.run(check())
