from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from platform_api.core.errors import register_exception_handlers
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.evaluation import router, workbench


@pytest.fixture
def client(setup):
    factory, actor, scope = setup
    app = FastAPI()
    app.state.db_session_factory = factory
    app.state.settings = SimpleNamespace(
        evaluation_workbench_enabled=True,
        evaluation_project_id=scope[0],
        evaluation_source_token="test-only",
        evaluation_assistant_model_route="route",
        evaluation_web_url="https://evalflow.example",
    )

    @app.middleware("http")
    async def project_context(request, call_next):
        request.state.platform_context = SimpleNamespace(
            project=SimpleNamespace(project_id=scope[0])
        )
        return await call_next(request)

    app.dependency_overrides[get_actor_context] = lambda: actor
    register_exception_handlers(app)
    app.include_router(router.router)
    app.include_router(workbench.router)
    with TestClient(app, headers={"x-project-id": scope[0]}) as value:
        yield value


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/work-items"),
        ("POST", "/work-items"),
        ("GET", "/workbench-summary"),
        ("GET", f"/work-items/{uuid4()}"),
        ("GET", f"/threads/{uuid4()}/messages/message/feedback"),
        ("POST", f"/threads/{uuid4()}/messages/message/feedback"),
        ("POST", "/exports"),
        ("POST", f"/exports/{uuid4()}/deliver"),
        ("POST", "/inspection/exports"),
        ("GET", "/inspection/exports"),
        ("GET", "/inspection/context"),
    ],
)
def test_retired_public_routes_do_not_execute(client, method, path):
    response = client.request(method, "/api/evaluation" + path)
    assert response.status_code in {404, 405}
    assert "error" in response.json()


def test_main_router_does_not_register_retired_assistant_callbacks():
    from platform_api.entrypoints.http.router import api_router as main_router

    paths = {route.path for route in main_router.routes}
    assert "/api/evaluation/internal/assistant" not in paths
    assert "/api/evaluation/internal/workbench/advance" not in paths


@pytest.mark.parametrize(
    "action",
    [
        "generate",
        "revise",
        "edit",
        "approve",
        "run",
        "cancel",
        "compare",
        "explain",
        "assign",
        "dispute",
        "defer",
        "withdraw",
        "regression",
        "tool_decision",
    ],
)
def test_old_public_actions_rejected_before_forwarding(client, monkeypatch, action):
    async def forbidden(*args):
        pytest.fail("Retired public action must not forward or start an assistant")

    monkeypatch.setattr(workbench, "forward", forbidden)
    response = client.post(
        f"/api/evaluation/work-items/{uuid4()}/{action}",
        json={"request_id": str(uuid4()), "data": {}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "evaluation_action_invalid"


def test_capabilities_and_evalflow_command_signing_remain(client):
    assert client.get("/api/evaluation/capabilities").json() == {
        "workbench": True,
        "authoring_url": "https://evalflow.example",
    }
    response = client.post(
        "/api/evaluation/authoring/token",
        json={
            "operation": "generate",
            "item_id": str(uuid4()),
            "request_id": str(uuid4()),
            "data": {},
        },
    )
    assert response.status_code == 200 and response.json()["token"]


def test_grant_and_revoke_still_use_scoped_platform_authorization(client, monkeypatch):
    grant_id, item_id = str(uuid4()), str(uuid4())
    calls = []

    async def forward(request, actor, project, operation, item, request_id, data):
        calls.append((operation, data))
        return {"id": item_id, "grants": {"evaluation_assistance": grant_id}}

    monkeypatch.setattr(workbench, "forward", forward)
    monkeypatch.setattr(workbench, "create_grant", lambda *args: {"grant_id": grant_id})
    monkeypatch.setattr(workbench, "revoke_grant", lambda *args: {"status": "revoked"})
    response = client.post(
        f"/api/evaluation/work-items/{item_id}/grant",
        json={
            "request_id": str(uuid4()),
            "data": {
                "grant_id": grant_id,
                "purpose": "evaluation_assistance",
                "synthetic_attestation": True,
            },
        },
    )
    assert response.status_code == 200
    assert calls[-1] == ("grant", {"grant_id": grant_id})
    response = client.post(
        f"/api/evaluation/work-items/{item_id}/revoke",
        json={"request_id": str(uuid4()), "data": {"grant_id": str(uuid4())}},
    )
    assert response.status_code == 403
    response = client.post(
        f"/api/evaluation/work-items/{item_id}/revoke",
        json={"request_id": str(uuid4()), "data": {"grant_id": grant_id}},
    )
    assert response.status_code == 200 and response.json()["status"] == "revoked"
