"""Budget control plane, signed boundaries and durable delivery contracts."""

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import httpx
import pytest
from evaluation_fixtures import setup  # noqa: F401
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from platform_api.core.context.models import (
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)
from platform_api.core.errors import (
    PlatformApiError,
    ServiceUnavailableError,
)
from platform_api.core.errors.handlers import register_exception_handlers
from platform_api.entrypoints.http.dependencies import get_platform_request_context
from platform_api.entrypoints.http.middleware.request_context import (
    register_request_context_middleware,
)
from platform_api.main import create_app  # noqa: F401
from platform_api.modules.notifications.models import (
    NotificationChannelRecord,
    NotificationRecord,
)
from platform_api.modules.projects.models import (
    ProjectMemberRecord,
    ProjectRecord,
    TenantRecord,
)
from platform_api.modules.runtime_policies.application import (
    budget_notifications as notices,
)
from platform_api.modules.runtime_policies.application.budget_transport import encode
from platform_api.modules.runtime_policies.application.budgets import BudgetService
from platform_api.modules.runtime_policies.domain.budgets import BudgetInput, period
from platform_api.modules.runtime_policies.infra.sqlalchemy.budgets import (
    BudgetDeliveryRecord,
    BudgetTenantRecord,
)
from platform_api.modules.runtime_policies.presentation.budgets import (
    get_service,
    router,
)

SECRET = "budget-test-secret-at-least-32-bytes"


def body(project=None, **values):
    return {
        "scope": "PROJECT" if project else "GLOBAL",
        "project_id": project,
        "budget_amount": "1.000000000000",
        "duration": {"unit": "DAYS", "value": 1},
        "budget_unit": "USD",
        "action": "ALERT",
        **values,
    }


def response(snapshot, **kwargs):
    now = datetime.now(UTC)
    return {
        "tenant_id": snapshot["tenant_id"],
        "revision": snapshot["revision"],
        "version": 1,
        "capabilities": {"gateway_budget": True, "usage": True},
        "states": [
            {
                "policy_id": p["id"],
                "definition_version": p["definition_version"],
                "window_start": period(p["duration"]["unit"], now)[0].isoformat(),
                "window_end": period(p["duration"]["unit"], now)[1].isoformat(),
                "accounting_status": "complete",
                "known_spend": "0.000000000000",
                "current_spend": "0.000000000000",
                "is_exceeded": False,
                "as_of": now.isoformat(),
            }
            for p in snapshot["policies"]
            if not p.get("deleted_at")
            and (
                kwargs.get("project_id") is None
                or p.get("project_id") in (None, kwargs["project_id"])
            )
        ],
    }


@pytest.fixture
def env(setup, monkeypatch):  # noqa: F811
    factory, actor, scope = setup
    project = scope[0]
    with factory() as session:
        tenant = session.get(
            TenantRecord, session.get(ProjectRecord, UUID(project)).tenant_id
        ).slug
    context = PlatformRequestContext(
        RequestContext("budget-request", "trace", "GET", "/api/policies/budgets", 0),
        TenantContext(tenant),
        ProjectContext(project),
        actor,
    )
    service = BudgetService(
        factory,
        SimpleNamespace(
            runtime_delegation_secret=SECRET,
            langgraph_upstream_url="http://runtime.test",
        ),
    )
    monkeypatch.setattr(service, "runtime", response)
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    register_request_context_middleware(app)
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_platform_request_context] = lambda: context
    with TestClient(app) as client:
        yield SimpleNamespace(
            factory=factory,
            context=context,
            project=project,
            service=service,
            client=client,
        )


def test_crud_versions_and_definition(env):
    r = env.client.post("/api/policies/budgets", json=body(env.project))
    assert r.status_code == 201, r.text
    p = r.json()["policy"]
    assert r.json()["sync_status"] == "applied"
    path = "/api/policies/budgets/" + p["id"]
    for changes, version, definition in [
        ({"budget_amount": "2", "action": "REJECT"}, 2, 1),
        ({"duration": {"unit": "MONTHS", "value": 1}}, 3, 2),
    ]:
        value = env.client.put(path, json=body(env.project, **changes)).json()["policy"]
        assert (value["version"], value["definition_version"]) == (version, definition)
    items = env.client.get(
        "/api/policies/budgets", params={"project_id": env.project}
    ).json()["items"]
    assert len(items) == 1 and items[0]["current_spend"] == "0.000000000000"
    assert env.client.delete(path).json()["policy"]["deleted_at"]
    assert (
        env.client.get(
            "/api/policies/budgets", params={"project_id": env.project}
        ).json()["items"]
        == []
    )
    assert env.client.delete(path).status_code == 404
    assert env.service.snapshot(env.context.tenant.tenant_id)["revision"] == 4


@pytest.mark.parametrize(
    "changes",
    [
        {"budget_amount": 0.1},
        {"budget_amount": "0"},
        {"budget_amount": "-1"},
        {"budget_amount": "NaN"},
        {"budget_amount": "1.0000000000001"},
        {"budget_amount": "10000000000000000"},
        {"duration": {"unit": "HOURS", "value": 1}},
        {"duration": {"unit": "DAYS", "value": 2}},
        {"duration": {"unit": "DAYS", "value": True}},
        {"duration": {"unit": "DAYS", "value": 1.0}},
        {"budget_unit": "CNY"},
        {"scope": "GLOBAL"},
        {"project_id": None},
        {"tenant_id": "forged"},
    ],
)
def test_invalid_input(env, changes):
    r = env.client.post("/api/policies/budgets", json=body(env.project, **changes))
    assert r.status_code == 422, r.text
    assert "error" in r.json()


def test_live_permissions_tenant_and_financial_visibility(env):
    assert env.client.post("/api/policies/budgets", json=body()).status_code == 403
    assert env.client.get("/api/policies/budgets").status_code == 403
    with env.factory.begin() as session:
        tenant = TenantRecord(slug="other-budget-tenant", name="Other")
        session.add(tenant)
        session.flush()
        project = ProjectRecord(tenant_id=tenant.id, name="Other")
        session.add(project)
        session.flush()
        other = str(project.id)
        session.add(
            ProjectMemberRecord(
                project_id=project.id,
                user_id=UUID(env.context.actor.user_id),
                role="project_admin",
            )
        )
    assert env.client.post("/api/policies/budgets", json=body(other)).status_code == 404
    env.service.save(env.context, BudgetInput.model_validate(body(env.project)))
    with env.factory.begin() as session:
        member = session.scalar(
            select(ProjectMemberRecord).where(
                ProjectMemberRecord.project_id == UUID(env.project)
            )
        )
        member.role = "executor"
    assert (
        env.client.get(
            "/api/policies/budgets", params={"project_id": env.project}
        ).status_code
        == 403
    )
    assert (
        env.client.post("/api/policies/budgets", json=body(env.project)).status_code
        == 403
    )


def test_reject_refuses_incompatible_runtime_and_sync_recovers(env, monkeypatch):
    def fail(*args, **kwargs):
        raise ServiceUnavailableError(
            code="BUDGET_ACCOUNTING_UNAVAILABLE", message="unavailable"
        )

    monkeypatch.setattr(env.service, "runtime", fail)
    assert (
        env.client.post(
            "/api/policies/budgets", json=body(env.project, action="REJECT")
        ).status_code
        == 503
    )
    assert env.service.snapshot(env.context.tenant.tenant_id)["revision"] == 0
    saved = env.client.post("/api/policies/budgets", json=body(env.project)).json()
    assert saved["sync_status"] == "pending"
    state = env.client.get(
        "/api/policies/budgets", params={"project_id": env.project}
    ).json()["items"][0]
    assert (
        state["accounting_status"] == "reconciling"
        and state["is_exceeded"] is None
        and state["current_spend"] is None
    )
    monkeypatch.setattr(env.service, "runtime", response)
    assert env.service.sync(env.context.tenant.tenant_id)
    with env.factory() as session:
        state = session.get(BudgetTenantRecord, env.context.tenant.tenant_id)
        assert state.revision == state.synced_revision == 1


@pytest.mark.parametrize(
    "corruption",
    [
        "tenant",
        "float",
        "unknown",
        "missing",
        "duplicate",
        "nondict",
        "capability",
        "version",
    ],
)
def test_runtime_response_boundary(env, monkeypatch, corruption):
    env.service.save(env.context, BudgetInput.model_validate(body(env.project)))
    snapshot = env.service.snapshot(env.context.tenant.tenant_id)
    value = response(snapshot)
    if corruption == "tenant":
        value["tenant_id"] = "other"
    if corruption == "float":
        value["states"][0]["current_spend"] = 0.0
    if corruption == "unknown":
        value["states"][0]["accounting_status"] = "unverifiable"
    if corruption == "missing":
        value["states"] = []
    if corruption == "duplicate":
        value["states"] *= 2
    if corruption == "nondict":
        value = []
    if corruption == "capability":
        value["capabilities"]["gateway_budget"] = "true"
    if corruption == "version":
        value["version"] = True
    client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=value))
        ),
    )
    with pytest.raises(ServiceUnavailableError):
        BudgetService.runtime(env.service, snapshot)


def test_preflight_codes_retry_after_and_unknown(env, monkeypatch):
    env.service.save(
        env.context, BudgetInput.model_validate(body(env.project, action="REJECT"))
    )

    def full(snapshot, **kwargs):
        result = response(snapshot, **kwargs)
        result["states"][0].update(
            known_spend="1.000000000000",
            current_spend="1.000000000000",
            is_exceeded=True,
        )
        return result

    monkeypatch.setattr(env.service, "runtime", full)
    with pytest.raises(PlatformApiError) as exc:
        env.service.preflight(env.context.tenant.tenant_id, env.project)
    assert exc.value.status_code == 429 and int(exc.value.headers["Retry-After"]) > 0

    def unknown(snapshot, **kwargs):
        result = response(snapshot, **kwargs)
        result["states"][0].update(
            accounting_status="unverifiable", current_spend=None, is_exceeded=None
        )
        return result

    monkeypatch.setattr(env.service, "runtime", unknown)
    with pytest.raises(ServiceUnavailableError):
        env.service.preflight(env.context.tenant.tenant_id, env.project)


def test_preflight_http_envelope_and_earliest_known_reset(env, monkeypatch):
    for unit in ("MONTHS", "WEEKS", "DAYS"):
        env.service.save(
            env.context,
            BudgetInput.model_validate(
                body(env.project, action="REJECT", duration={"unit": unit, "value": 1})
            ),
        )

    def full(snapshot, **kwargs):
        result = response(snapshot, **kwargs)
        for state in result["states"]:
            state.update(
                known_spend="1.000000000000",
                current_spend="1.000000000000",
                is_exceeded=True,
            )
        # An unverifiable rule must not hide a known exhausted rule.
        result["states"][0].update(
            accounting_status="unverifiable", current_spend=None, is_exceeded=None
        )
        return result

    monkeypatch.setattr(env.service, "runtime", full)
    app = FastAPI()
    register_exception_handlers(app)
    register_request_context_middleware(app)

    @app.post("/preflight")
    def preflight():
        env.service.preflight(env.context.tenant.tenant_id, env.project)

    with TestClient(app) as client:
        result = client.post("/preflight")
    assert result.status_code == 429
    value = result.json()
    assert value["request_id"] and value["error"]["code"] == "BUDGET_LIMIT_EXCEEDED"
    assert isinstance(value["error"]["details"], list)
    states = full(env.service.snapshot(env.context.tenant.tenant_id))["states"]
    expected = min(
        datetime.fromisoformat(s["window_end"]) for s in states if s["is_exceeded"]
    )
    assert datetime.fromisoformat(value["error"]["extra"]["resets_at"]) == expected
    assert int(result.headers["retry-after"]) > 0
    assert "known_spend" not in value["error"]["extra"]


def signed(env, path, payload, **kwargs):
    raw, headers = encode(SECRET, path, payload)
    return env.client.post(path, content=raw, headers=headers, **kwargs)


def test_internal_auth_path_body_replay_and_tenant(env):
    path = "/api/runtime/internal/budgets/resolve"
    payload = {"tenant_id": env.context.tenant.tenant_id, "project_id": env.project}
    raw, headers = encode(SECRET, path, payload)
    assert env.client.post(path, content=raw, headers=headers).status_code == 200
    assert env.client.post(path, content=raw, headers=headers).status_code == 403
    raw, headers = encode(SECRET, path, payload)
    assert env.client.post(path, content=raw + b" ", headers=headers).status_code == 403
    assert (
        env.client.post(path + "?skip=true", content=raw, headers=headers).status_code
        == 403
    )
    assert (
        env.client.post(
            "/api/runtime/internal/budgets/events", content=raw, headers=headers
        ).status_code
        == 403
    )
    assert signed(env, path, {**payload, "tenant_id": "other"}).status_code == 403
    assert env.client.post(path, json=payload).status_code == 403


def event(env):
    policy = env.service.save(
        env.context, BudgetInput.model_validate(body(env.project))
    )["policy"]
    start, end = period("DAYS", datetime.now(UTC))
    identity = (env.context.tenant.tenant_id, policy["id"], 1, start)
    return {
        "event_id": str(
            uuid5(NAMESPACE_URL, "gateway-budget:" + ":".join(map(str, identity)))
        ),
        "tenant_id": identity[0],
        "policy": policy,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "known_spend": "1.100000000000",
    }


def test_event_persistent_dedup_validation_and_channel_retry(env, monkeypatch):
    with env.factory.begin() as session:
        channel = NotificationChannelRecord(
            name="Synthetic",
            endpoint_url="https://notice.invalid",
            channel_type="feishu",
        )
        session.add(channel)
        session.flush()
        channel_id = str(channel.id)
    payload = event(env)
    path = "/api/runtime/internal/budgets/events"
    assert signed(env, path, payload).status_code == 200
    assert signed(env, path, payload).status_code == 200
    with env.factory() as session:
        notifications = session.scalars(select(NotificationRecord)).all()
        assert len(notifications) == 1 and notifications[0].recipient_user_id == UUID(
            env.context.actor.user_id
        )
    for invalid in (
        {"event_id": str(uuid4())},
        {"known_spend": 1.1},
        {"window_end": "2026-11-18T13:00:00Z"},
    ):
        assert signed(env, path, {**payload, **invalid}).status_code == 400
    attempts = []

    async def send(*args, **kwargs):
        attempts.append(args)
        return len(attempts) > 1, None

    monkeypatch.setattr(notices.FeishuBotClient, "send_card", send)
    asyncio.run(notices.deliver(env.factory))
    with env.factory.begin() as session:
        delivery = session.get(BudgetDeliveryRecord, (payload["event_id"], channel_id))
        assert (
            delivery.attempts == 1
            and delivery.delivered_at is None
            and delivery.last_error
        )
        delivery.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    asyncio.run(notices.deliver(env.factory))
    asyncio.run(notices.deliver(env.factory))
    with env.factory() as session:
        delivery = session.get(BudgetDeliveryRecord, (payload["event_id"], channel_id))
        assert (
            delivery.attempts == 2 and delivery.delivered_at and not delivery.last_error
        )
    assert len(attempts) == 2


def test_external_success_before_ack_commit_can_replay(env, monkeypatch):
    with env.factory.begin() as session:
        channel = NotificationChannelRecord(
            name="Synthetic ACK loss",
            endpoint_url="https://notice.invalid",
            channel_type="feishu",
        )
        session.add(channel)
    payload = event(env)
    assert (
        signed(env, "/api/runtime/internal/budgets/events", payload).status_code == 200
    )
    sends = []

    async def send(*args, **kwargs):
        sends.append(args)
        return True, None

    class InterruptedFactory:
        crash = True

        def __call__(self):
            return env.factory()

        @contextmanager
        def begin(self):
            with env.factory.begin() as session:
                yield session
                if self.crash and any(
                    isinstance(row, BudgetDeliveryRecord) and row.delivered_at
                    for row in session.dirty
                ):
                    self.crash = False
                    raise RuntimeError(
                        "synthetic exit after external success before ACK commit"
                    )

    monkeypatch.setattr(notices.FeishuBotClient, "send_card", send)
    factory = InterruptedFactory()
    asyncio.run(notices.deliver(factory))
    with env.factory.begin() as session:
        delivery = session.scalar(select(BudgetDeliveryRecord))
        assert delivery.delivered_at is None and delivery.last_error
        delivery.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    asyncio.run(notices.deliver(factory))
    with env.factory() as session:
        delivery = session.scalar(select(BudgetDeliveryRecord))
        assert delivery.delivered_at and delivery.attempts == 2
        assert len(session.scalars(select(NotificationRecord)).all()) == 1
    assert len(sends) == 2
