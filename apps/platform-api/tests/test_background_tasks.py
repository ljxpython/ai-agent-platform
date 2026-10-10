"""Public background DTOs, precise delegation and completion trust boundaries."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from platform_api.adapters.langgraph.sdk_client import redact_runtime_private_fields
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import (
    ForbiddenError,
    PlatformApiError,
    register_exception_handlers,
)
from platform_api.core.runtime_contract import reject_private_runtime_state
from platform_api.modules.runtime_gateway.application import (
    background_completion as completion,
)
from platform_api.modules.runtime_gateway.application.background_tasks import (
    background_task_action,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_actor_context,
    get_runtime_gateway_service,
    router,
)

THREAD, TASK, RUN, EVENT = (str(uuid4()) for _ in range(4))


def task():
    now = datetime.now(UTC).isoformat()
    return {
        "version": 1,
        "task_id": TASK,
        "thread_id": THREAD,
        "graph_id": "showcase_demo",
        "origin_run_id": RUN,
        "status": "running",
        "reason_code": None,
        "exit_code": None,
        "created_at": now,
        "started_at": now,
        "finished_at": None,
        "deadline_at": now,
        "updated_at": now,
        "cleanup_state": "pending",
        "output": {
            "available": False,
            "retained_bytes": 0,
            "omitted_bytes": 0,
            "truncated": False,
            "updated_at": None,
        },
        "delivery": {
            "state": "not_ready",
            "event_id": None,
            "run_id": None,
            "reason_code": None,
        },
        "allowed_actions": ["read", "logs", "cancel"],
        "container_id": "PRIVATE",
        "command": "PRIVATE",
    }


def page():
    return {
        "version": 1,
        "thread_id": THREAD,
        "items": [task()],
        "next_cursor": None,
        "has_unresolved": True,
        "latest_delivery_run_id": None,
    }


@pytest.mark.parametrize(
    "action,operation",
    [
        ("list", "background-task-read"),
        ("detail", "background-task-read"),
        ("output", "background-task-log-read"),
        ("cancel", "background-task-cancel"),
    ],
)
def test_scope_private_projection_and_exact_operations(action, operation, monkeypatch):
    output = {
        "version": 1,
        "thread_id": THREAD,
        "task_id": TASK,
        "text": "<script>plain text</script>",
        **task()["output"],
    }
    output["available"] = True
    upstream = SimpleNamespace(
        list_background_tasks=AsyncMock(return_value=page()),
        get_background_task=AsyncMock(return_value=task()),
        get_background_output=AsyncMock(return_value=output),
        cancel_background_task=AsyncMock(return_value=task()),
    )
    gateway = SimpleNamespace(
        _load_thread=AsyncMock(
            return_value={"metadata": {"graph_id": "showcase_demo"}}
        ),
        _thread_upstream=AsyncMock(return_value=upstream),
    )
    monkeypatch.setattr(
        "platform_api.modules.runtime_gateway.application.background_tasks.thread_access.allowed",
        lambda *args: False,
    )
    result = asyncio.run(
        background_task_action(
            gateway,
            actor=ActorContext(user_id="owner"),
            project_id="project",
            thread_id=THREAD,
            task_id=None if action == "list" else TASK,
            action=action,
            key="same",
        )
    )
    assert "PRIVATE" not in json.dumps(result)
    assert gateway._thread_upstream.await_args.kwargs["operation"] == operation
    assert gateway._load_thread.await_args.kwargs["write"] is (action == "cancel")
    if action != "output":
        item = result["items"][0] if action == "list" else result
        assert item["allowed_actions"] == ["read", "logs"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("origin_run_id", "None"),
        ("thread_id", str(uuid4())),
        ("graph_id", "other"),
        ("output", {"available": False}),
        (
            "delivery",
            {
                "state": "accepted",
                "run_id": None,
                "event_id": EVENT,
                "reason_code": None,
            },
        ),
    ],
)
def test_invalid_upstream_facts_become_safe_502(field, value):
    payload = task()
    payload[field] = value
    upstream = SimpleNamespace(get_background_task=AsyncMock(return_value=payload))
    gateway = SimpleNamespace(
        _load_thread=AsyncMock(
            return_value={"metadata": {"graph_id": "showcase_demo"}}
        ),
        _thread_upstream=AsyncMock(return_value=upstream),
    )
    with pytest.raises(PlatformApiError) as failed:
        asyncio.run(
            background_task_action(
                gateway,
                actor=ActorContext(user_id="owner"),
                project_id="project",
                thread_id=THREAD,
                task_id=TASK,
                action="detail",
            )
        )
    assert (
        failed.value.status_code == 502
        and failed.value.code == "langgraph_upstream_invalid_response"
    )
    assert "PRIVATE" not in failed.value.message


def test_http_input_and_no_store():
    service = SimpleNamespace(background_task_action=AsyncMock(return_value=task()))
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    app.dependency_overrides[get_actor_context] = lambda: ActorContext(user_id="owner")
    app.dependency_overrides[get_runtime_gateway_service] = lambda: service

    @app.middleware("http")
    async def context(request, call_next):
        request.state.platform_context = SimpleNamespace(
            project=SimpleNamespace(project_id="project")
        )
        return await call_next(request)

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            path = f"/api/langgraph/threads/{THREAD}/background-tasks/{TASK}"
            for method, suffix in (("GET", ""), ("POST", "/cancel")):
                kwargs = (
                    {"json": {}, "headers": {"Idempotency-Key": "same"}}
                    if method == "POST"
                    else {}
                )
                response = await client.request(method, path + suffix, **kwargs)
                assert response.status_code == (202 if method == "POST" else 200)
                assert response.headers["cache-control"] == "no-store"
            for body in ({"command": "PRIVATE"}, {"container_id": "PRIVATE"}):
                assert (
                    await client.post(
                        path + "/cancel", json=body, headers={"Idempotency-Key": "same"}
                    )
                ).status_code == 422
            assert (await client.post(path + "/cancel", json={})).status_code == 422
            assert (await client.get(path + "?scope=other")).status_code == 422
            assert (
                await client.get(path.rsplit("/", 1)[0] + "?limit=1&limit=2")
            ).status_code == 422

    asyncio.run(check())


def test_hmac_operation_window_body_and_unicode_signature():
    from platform_api.modules.runtime_catalog.presentation.http import (
        _verify_background_signature,
    )

    secret = "synthetic-background-verification-secret"
    body = {"task_id": TASK}
    stamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(),
        f"{stamp}\nbackground-task-delivery\n{completion.canonical(body)}".encode(),
        hashlib.sha256,
    ).hexdigest()
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(runtime_delegation_secret=secret)
            )
        ),
        headers={
            "x-runtime-acl-timestamp": stamp,
            "x-runtime-acl-signature": signature,
        },
    )
    _verify_background_signature(request, body, "background-task-delivery")
    for payload, operation, changed_stamp, changed_signature in (
        ({"task_id": str(uuid4())}, "background-task-delivery", stamp, signature),
        (body, "background-task-authorization", stamp, signature),
        (body, "background-task-delivery", "0", signature),
        (body, "background-task-delivery", stamp, "非ASCII"),
    ):
        request.headers.update(
            {
                "x-runtime-acl-timestamp": changed_stamp,
                "x-runtime-acl-signature": changed_signature,
            }
        )
        with pytest.raises(PlatformApiError):
            _verify_background_signature(request, payload, operation)


@pytest.mark.parametrize("operation", ["delivery", "authorization"])
def test_completion_audit_names_check_and_only_retains_safe_identity(operation):
    from platform_api.modules.audit.http_resolution import (
        AuditHttpRequest,
        resolve_http_audit,
    )
    from platform_api.modules.audit.schemas import AuditPlane, AuditResult

    audit = resolve_http_audit(
        request=AuditHttpRequest(
            method="POST",
            path="/api/runtime/internal/background-task-" + operation,
            query_params={},
            query_string=None,
            state_project_id="project",
            client_ip=None,
            user_agent=None,
            response_content_length=None,
            metadata={
                "task_id": TASK,
                "event_id": EVENT,
                "origin_run_id": RUN,
                "command": "PRIVATE",
                "marker": "PRIVATE",
            },
        ),
        response_payload={"state": "unknown"},
        actor_user_id="owner",
        status_code=200,
        result=AuditResult.SUCCESS,
    )
    assert audit.plane == AuditPlane.RUNTIME_GATEWAY and audit.target_id == TASK
    assert audit.action == f"runtime.background_task.{operation}.checked"
    assert audit.metadata["event_id"] == EVENT and "PRIVATE" not in json.dumps(
        audit.metadata
    )


def test_private_completion_injection_is_rejected_and_read_is_stripped():
    for payload in (
        {"config": {"configurable": {"platform_background_completion": {}}}},
        {"messages": [{"metadata": {"platform_background_completion": {}}}]},
    ):
        with pytest.raises(ValueError):
            reject_private_runtime_state(payload)
    assert "platform_background_completion" not in json.dumps(
        redact_runtime_private_fields(
            {
                "config": {
                    "configurable": {
                        "platform_background_completion": {"signature": "PRIVATE"}
                    }
                }
            }
        )
    )


def test_reconcile_only_with_lost_ack_never_creates_new_run(monkeypatch):
    values = {
        "version": 1,
        "tenant_id": "tenant",
        "project_id": str(uuid4()),
        "owner_id": "owner",
        "credential_id": None,
        "graph_id": "showcase_demo",
        "thread_id": THREAD,
        "origin_run_id": RUN,
        "task_id": TASK,
        "event_id": EVENT,
        "status": "succeeded",
        "exit_code": 0,
        "reconcile_only": True,
    }
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(db_session_factory=object()))
    )
    monkeypatch.setattr(
        completion,
        "records",
        Mock(
            return_value=(
                SimpleNamespace(context_snapshot={}),
                SimpleNamespace(run_id=None),
            )
        ),
    )
    actor = Mock()
    monkeypatch.setattr(completion, "current_actor", actor)
    result = asyncio.run(
        completion.deliver(request, completion.CompletionEvent.model_validate(values))
    )
    assert result["state"] == "unknown" and result["run_id"] is None
    actor.assert_not_called()


def test_accepted_receipt_remains_queryable_without_new_authorization(monkeypatch):
    values = {
        "version": 1,
        "tenant_id": "tenant",
        "project_id": str(uuid4()),
        "owner_id": "owner",
        "credential_id": None,
        "graph_id": "showcase_demo",
        "thread_id": THREAD,
        "origin_run_id": RUN,
        "task_id": TASK,
        "event_id": EVENT,
        "status": "succeeded",
        "exit_code": 0,
        "reconcile_only": True,
    }
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(db_session_factory=object()))
    )
    monkeypatch.setattr(
        completion, "records", Mock(return_value=(None, SimpleNamespace(run_id=RUN)))
    )
    result = asyncio.run(
        completion.deliver(request, completion.CompletionEvent.model_validate(values))
    )
    assert result == {"state": "accepted", "run_id": RUN, "reason_code": None}


@pytest.mark.parametrize(
    "kind",
    [
        "user-disabled",
        "user-deleted",
        "user-credential",
        "account-disabled",
        "account-deleted",
        "credential-revoked",
        "credential-expired",
        "credential-revoked-at",
        "credential-swapped",
    ],
)
def test_completion_identity_rechecks_persisted_revocation_and_credentials(
    tmp_path, kind
):
    from platform_api.modules.identity.models import UserRecord
    from platform_api.modules.service_accounts.models import (
        ServiceAccountRecord,
        ServiceAccountTokenRecord,
    )

    engine = build_engine(f"sqlite:///{tmp_path / 'completion-identity.db'}")
    factory = build_session_factory(engine)
    create_core_tables(engine)
    project = str(uuid4())
    try:
        with factory.begin() as session:
            user = UserRecord(username="owner", external_subject="owner")
            account = ServiceAccountRecord(name="background-owner")
            other = ServiceAccountRecord(name="other-owner")
            session.add_all([user, account, other])
            session.flush()
            token = ServiceAccountTokenRecord(
                service_account_id=account.id,
                name="background",
                token_prefix="synthetic",
                token_secret_hash="synthetic",
            )
            session.add(token)
            session.flush()
            user_id, account_id, token_id = user.id, account.id, token.id
            data = {
                "project_id": project,
                "owner_id": str(user_id)
                if kind.startswith("user-")
                else "service-account:" + str(account_id),
                "credential_id": None if kind.startswith("user-") else str(token_id),
            }
            other_id = other.id
        assert completion.current_actor(factory, data) is not None
        with factory.begin() as session:
            if kind == "user-disabled":
                session.get(UserRecord, user_id).status = "disabled"
            elif kind == "user-deleted":
                session.delete(session.get(UserRecord, user_id))
            elif kind == "user-credential":
                data["credential_id"] = str(token_id)
            elif kind == "account-disabled":
                session.get(ServiceAccountRecord, account_id).status = "disabled"
            elif kind == "account-deleted":
                session.delete(session.get(ServiceAccountRecord, account_id))
            elif kind == "credential-revoked":
                session.get(ServiceAccountTokenRecord, token_id).status = "revoked"
            elif kind == "credential-expired":
                session.get(ServiceAccountTokenRecord, token_id).expires_at = (
                    datetime.now(UTC) - timedelta(seconds=1)
                )
            elif kind == "credential-revoked-at":
                session.get(
                    ServiceAccountTokenRecord, token_id
                ).revoked_at = datetime.now(UTC)
            else:
                data["owner_id"] = "service-account:" + str(other_id)
        with pytest.raises(ForbiddenError, match="Background task identity denied"):
            completion.current_actor(factory, data)
    finally:
        engine.dispose()
