import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ServiceUnavailableError,
)
from platform_api.modules.evaluation import targets


@pytest.fixture
def target(monkeypatch):
    project, agent, model = (str(uuid4()) for _ in range(3))
    spec = targets.TargetRequest(agent_id=agent, model_id=model)
    item = {
        "id": agent,
        "project_id": project,
        "graph_id": "dearflow_agent",
        "context": {},
        "status": "active",
    }
    monkeypatch.setattr(
        targets,
        "configured_target",
        lambda *args: (deepcopy(item), {"model": model, "graph": "dearflow_agent"}),
    )
    runtime = {
        "schema": "evaluation-runtime/v1",
        "available": True,
        "manifest": {"package_sha256": "r"},
        "tools": [],
    }
    gateway = NS(
        evaluation_capabilities=AsyncMock(return_value=runtime),
        create_thread_run=AsyncMock(return_value={"run_id": str(uuid4())}),
    )
    value = asyncio.run(targets.snapshot(gateway, None, project, spec))
    return gateway, project, spec, deepcopy(value)


def test_snapshot_is_deterministic_and_rejects_configuration_drift(target):
    gateway, project, spec, value = target
    assert asyncio.run(targets.snapshot(gateway, None, project, spec)) == value
    asyncio.run(targets.validate_target(gateway, None, project, value))
    gateway.evaluation_capabilities.return_value["manifest"]["package_sha256"] = "new"
    with pytest.raises(ConflictError, match="评测目标已变化"):
        asyncio.run(targets.validate_target(gateway, None, project, value))


def test_missing_runtime_contract_and_tampered_snapshot_fail_closed(target):
    gateway, project, spec, value = target
    value["context"]["max_tokens"] = 1
    with pytest.raises(BadRequestError, match="快照无效"):
        asyncio.run(targets.validate_target(gateway, None, project, value))
    gateway.evaluation_capabilities.return_value = {}
    with pytest.raises(ServiceUnavailableError, match="契约"):
        asyncio.run(targets.snapshot(gateway, None, project, spec))


def test_bound_run_keeps_identity_and_idempotency(target):
    gateway, project, _, value = target
    body = targets.EvaluationRun(
        target=value,
        run={
            "assistant_id": "dearflow_agent",
            "context": value["context"],
            "metadata": {"evaluation_attempt_id": "attempt"},
        },
    )
    asyncio.run(targets.create_run(gateway, None, project, "thread", body, "key"))
    call = gateway.create_thread_run.call_args.kwargs
    assert call["idempotency_key"] == "key"
    assert call["evaluation_target"] == value
    assert "evaluation_target" not in call["payload"]["metadata"]
    gateway.create_thread_run.reset_mock()
    body.run["assistant_id"] = "another"
    with pytest.raises(BadRequestError):
        asyncio.run(targets.create_run(gateway, None, project, "thread", body, "key"))
    gateway.create_thread_run.assert_not_called()


def test_configured_target_checks_execute_permission_before_reading_other_services():
    from platform_api.core.errors import ForbiddenError

    gateway = NS(
        _authorize=Mock(side_effect=ForbiddenError(code="denied", message="denied"))
    )
    spec = targets.TargetRequest(agent_id=uuid4(), model_id=uuid4())
    with pytest.raises(ForbiddenError):
        targets.configured_target(gateway, None, "other-project", spec)


def test_configured_target_uses_effective_policy_without_admin_listing(monkeypatch):
    project, agent, model, user = (str(uuid4()) for _ in range(4))
    item = Mock(project_id=project, graph_id="dearflow_agent", status="active")
    item.model_dump.return_value = {"id": agent}
    monkeypatch.setattr(
        targets,
        "AssistantsService",
        Mock(return_value=Mock(get_assistant=Mock(return_value=item))),
    )
    policy = Mock()
    policy.list_model_policies.return_value.items = [
        Mock(model_id=model, policy=NS(is_enabled=True))
    ]
    policy.list_graph_policies.return_value.items = [
        Mock(graph_id="dearflow_agent", policy=NS(is_enabled=True))
    ]
    policy.resolve_tool_overrides.return_value = {"tool_overrides": {"execute": False}}
    monkeypatch.setattr(
        targets, "RuntimePolicyOverlayService", Mock(return_value=policy)
    )
    factory = MagicMock()
    factory.return_value.__enter__.return_value.get.return_value = NS(
        enabled=True, updated_at="revision"
    )
    gateway = Mock(_require_session_factory=Mock(return_value=factory))
    _, resources = targets.configured_target(
        gateway,
        NS(user_id=user),
        project,
        targets.TargetRequest(agent_id=agent, model_id=model),
    )
    assert resources["tool_policy"] == {"tool_overrides": {"execute": False}}
    policy.resolve_tool_overrides.assert_called_once_with(
        project_id=project, user_id=user, graph_id="dearflow_agent"
    )
    policy.list_tool_restrictions.assert_not_called()


def test_bound_run_rejects_parameter_overrides_and_missing_idempotency(target):
    gateway, project, _, value = target
    body = targets.EvaluationRun(
        target=value,
        run={
            "assistant_id": "dearflow_agent",
            "context": {**value["context"], "system_prompt": "override"},
        },
    )
    with pytest.raises(BadRequestError, match="运行参数"):
        asyncio.run(targets.create_run(gateway, None, project, "thread", body, "key"))
    with pytest.raises(BadRequestError, match="幂等"):
        asyncio.run(targets.create_run(gateway, None, project, "thread", body, None))
    gateway.create_thread_run.assert_not_called()


def test_resume_preserves_original_gateway_configuration(target):
    gateway, project, _, value = target
    run = {
        "assistant_id": "dearflow_agent",
        "command": {"resume": {"interrupt": "approved"}},
    }
    body = targets.EvaluationRun(target=value, run=run)
    asyncio.run(targets.create_run(gateway, None, project, "thread", body, "key"))
    assert gateway.create_thread_run.call_args.kwargs["payload"] == run
