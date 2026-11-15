from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from pydantic import ValidationError
from test_evaluation_feedback import setup as _feedback_setup

from platform_api.core.db import session_scope
from platform_api.core.errors import BadRequestError, ConflictError, ForbiddenError
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.evaluation.contracts import InspectionExportBody
from platform_api.modules.evaluation.models import EvaluationExport
from platform_api.modules.evaluation.service import (
    authorized_package,
    create_inspection_export,
    revoke_export,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)

setup = _feedback_setup


@pytest.fixture
def inspection(setup):
    factory, actor, scope = setup
    agent_id = uuid4()
    with session_scope(factory) as session:
        session.add(
            AgentRecord(
                id=agent_id,
                project_id=UUID(scope[0]),
                name="Inspection fixture",
                graph_id="dearflow_agent",
                created_by=UUID(actor.user_id),
                updated_by=UUID(actor.user_id),
            )
        )
    return InspectionExportBody(
        export_id=uuid4(),
        thread_id=scope[1],
        run_id=uuid4(),
        agent_id=agent_id,
        purpose="quality_inspection",
        data_class="synthetic",
        synthetic_attestation=True,
        input="Return test@example.invalid",
        output="test@example.invalid",
        judge_route="synthetic-judge",
        budget_policy_version="inspection-test-v1",
    )


def test_independent_consent_minimization_idempotency_and_revocation(setup, inspection):
    factory, actor, scope = setup
    saved = create_inspection_export(factory, actor, scope[0], inspection)
    assert create_inspection_export(factory, actor, scope[0], inspection) == saved
    package = authorized_package(factory, scope[0], inspection.export_id)
    assert package["purpose"] == "quality_inspection"
    assert package["input"] == "Return [REDACTED_1]"
    assert package["output"] == "[REDACTED_1]"
    assert (
        not {"feedback", "scenario", "expected", "tools", "retrieval"} & package.keys()
    )
    with pytest.raises(ConflictError):
        create_inspection_export(
            factory,
            actor,
            scope[0],
            inspection.model_copy(update={"output": "changed"}),
        )
    revoke_export(factory, actor, scope[0], inspection.export_id)
    revoke_export(factory, actor, scope[0], inspection.export_id)
    with pytest.raises(ForbiddenError):
        authorized_package(factory, scope[0], inspection.export_id)


@pytest.mark.parametrize(
    "field,value",
    [
        ("data_class", "production"),
        ("purpose", "regression"),
        ("allowed_fields", ["input", "tools"]),
        ("judge_route", "https://attacker.invalid"),
        ("synthetic_attestation", False),
        ("tool_results", "secret"),
    ],
)
def test_inspection_contract_rejects_scope_expansion(inspection, field, value):
    with pytest.raises(ValidationError):
        InspectionExportBody.model_validate({**inspection.model_dump(), field: value})


def test_inspection_revalidates_agent_and_expiry(setup, inspection):
    factory, actor, scope = setup
    create_inspection_export(factory, actor, scope[0], inspection)
    with session_scope(factory) as session:
        session.get(AgentRecord, inspection.agent_id).status = "disabled"
    with pytest.raises(ForbiddenError):
        authorized_package(factory, scope[0], inspection.export_id)
    with session_scope(factory) as session:
        session.get(AgentRecord, inspection.agent_id).status = "active"
        session.get(EvaluationExport, str(inspection.export_id)).expires_at = (
            datetime.now(UTC) - timedelta(seconds=1)
        )
    with pytest.raises(ForbiddenError):
        authorized_package(factory, scope[0], inspection.export_id)


def test_inspection_refuses_secrets_and_cross_agent(setup, inspection):
    factory, actor, scope = setup
    with pytest.raises(BadRequestError):
        create_inspection_export(
            factory,
            actor,
            scope[0],
            inspection.model_copy(update={"input": "api_key=synthetic-secret"}),
        )
    with pytest.raises(ForbiddenError):
        create_inspection_export(
            factory,
            actor,
            scope[0],
            inspection.model_copy(update={"agent_id": uuid4()}),
        )


def test_inspection_rechecks_thread_ownership_after_consent(setup, inspection):
    factory, actor, scope = setup
    create_inspection_export(factory, actor, scope[0], inspection)
    with session_scope(factory) as session:
        session.get(ThreadAccessRecord, scope[1]).owner_user_id = str(uuid4())
    with pytest.raises(ForbiddenError):
        authorized_package(factory, scope[0], inspection.export_id)


@pytest.fixture
def inspection_http(setup, inspection):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from platform_api.core.errors import register_exception_handlers
    from platform_api.entrypoints.http.dependencies import get_actor_context
    from platform_api.modules.evaluation.router import (
        get_runtime_gateway_service,
        router,
    )

    factory, actor, scope = setup
    run = {
        "thread_id": scope[1],
        "run_id": str(inspection.run_id),
        "status": "success",
        "assistant_id": str(uuid5(NAMESPACE_URL, "dearflow_agent")),
    }
    gateway = SimpleNamespace(get_thread_run=AsyncMock(return_value=run))
    app = FastAPI()

    @app.middleware("http")
    async def project_context(request, call_next):
        request.state.platform_context = SimpleNamespace(
            project=SimpleNamespace(project_id=scope[0])
        )
        return await call_next(request)

    app.state.db_session_factory = factory
    app.state.settings = SimpleNamespace(
        evaluation_feedback_enabled=True,
        evaluation_inspection_enabled=True,
        evaluation_inspection_judge_route=inspection.judge_route,
        evaluation_inspection_budget_version=inspection.budget_policy_version,
        evaluation_project_id=scope[0],
    )
    app.dependency_overrides[get_actor_context] = lambda: actor
    app.dependency_overrides[get_runtime_gateway_service] = lambda: gateway
    register_exception_handlers(app)
    app.include_router(router)
    with TestClient(app, headers={"x-project-id": scope[0]}) as client:
        yield client, run


@pytest.mark.parametrize(
    "assistant", ["dearflow_agent", str(uuid5(NAMESPACE_URL, "dearflow_agent"))]
)
def test_http_resolves_runtime_assistant_to_platform_agent(
    inspection_http, inspection, assistant
):
    client, run = inspection_http
    run["assistant_id"] = assistant
    response = client.get(
        "/api/evaluation/inspection/context",
        params={
            "thread_id": str(inspection.thread_id),
            "run_id": str(inspection.run_id),
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "agent_id": str(inspection.agent_id),
        "graph_id": "dearflow_agent",
    }
    assert (
        client.post(
            "/api/evaluation/inspection/exports",
            json=inspection.model_dump(mode="json"),
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "running"),
        ("thread_id", str(uuid4())),
        ("run_id", str(uuid4())),
        ("assistant_id", str(uuid4())),
    ],
)
def test_http_rejects_unbound_or_unfinished_run(
    inspection_http, inspection, field, value
):
    client, run = inspection_http
    run[field] = value
    assert (
        client.post(
            "/api/evaluation/inspection/exports",
            json=inspection.model_dump(mode="json"),
        ).status_code
        == 403
    )


def test_http_rejects_client_agent_substitution(inspection_http, inspection, setup):
    client, _ = inspection_http
    factory, actor, scope = setup
    other = uuid4()
    with session_scope(factory) as session:
        session.add(
            AgentRecord(
                id=other,
                project_id=UUID(scope[0]),
                name="Other",
                graph_id="other",
                created_by=UUID(actor.user_id),
                updated_by=UUID(actor.user_id),
            )
        )
    body = inspection.model_dump(mode="json")
    body["agent_id"] = str(other)
    assert (
        client.post("/api/evaluation/inspection/exports", json=body).status_code == 403
    )
