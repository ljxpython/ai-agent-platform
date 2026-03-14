from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from graph_src_v2.services.usecase_workflow_agent import tools as workflow_tools  # noqa: E402
from langchain_core.messages import HumanMessage  # noqa: E402


def _assert_snapshot_envelope(data: dict[str, Any]) -> None:
    assert data["workflow_type"] == "usecase_generation"
    assert isinstance(data["stage"], str) and data["stage"]
    assert isinstance(data["summary"], str) and data["summary"]
    assert isinstance(data["persistable"], bool)
    assert isinstance(data["next_action"], str) and data["next_action"]
    assert isinstance(data["payload"], dict)


def test_build_usecase_workflow_service_config_reads_private_flags() -> None:
    config = {
        "configurable": {
            "usecase_workflow_type": "custom_usecase_generation",
            "interaction_data_service_url": "http://localhost:8090",
            "interaction_data_service_timeout_seconds": "15",
        }
    }
    service_config = workflow_tools.build_usecase_workflow_service_config(config)
    assert service_config.workflow_type == "custom_usecase_generation"
    assert service_config.interaction_data_service_url == "http://localhost:8090"
    assert service_config.interaction_data_service_timeout_seconds == 15


def test_build_usecase_workflow_tools_exports_expected_names() -> None:
    tools = workflow_tools.build_usecase_workflow_tools(model=object())
    names = [getattr(tool, "name", "") for tool in tools]
    assert names == [
        "run_requirement_analysis_subagent",
        "run_usecase_review_subagent",
        "create_usecase_workflow",
        "record_requirement_analysis",
        "record_usecase_review",
        "persist_approved_usecases",
    ]


def test_subagent_tools_require_non_empty_context() -> None:
    requirement_tool = workflow_tools.build_requirement_analysis_subagent_tool(object())
    review_tool = workflow_tools.build_usecase_review_subagent_tool(object())

    class DummyRuntime:
        def __init__(self) -> None:
            self.state: dict[str, Any] = {}

    with pytest.raises(ValueError, match="requirement_context is required"):
        requirement_tool.func(runtime=DummyRuntime(), requirement_context="")

    with pytest.raises(ValueError, match="review_context is required"):
        review_tool.func(runtime=DummyRuntime(), review_context="")


def test_subagent_tools_can_derive_context_from_runtime_state(monkeypatch: Any) -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [HumanMessage(content="请分析这个需求文档并提炼核心功能点")],
                "multimodal_summary": "检测到以下多模态附件：PDF 已解析：需求文档摘要。",
            }

    class DummySubagent:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            messages = payload["messages"]
            assert "需求文档摘要" in messages[0].content
            return {"messages": [HumanMessage(content="structured output")]}

    monkeypatch.setattr(
        workflow_tools, "_build_requirement_analysis_subagent", lambda model: DummySubagent()
    )
    monkeypatch.setattr(
        workflow_tools, "_build_usecase_review_subagent", lambda model: DummySubagent()
    )

    requirement_tool = workflow_tools.build_requirement_analysis_subagent_tool(object())
    review_tool = workflow_tools.build_usecase_review_subagent_tool(object())

    assert requirement_tool.func(runtime=DummyRuntime()) == "structured output"
    assert review_tool.func(runtime=DummyRuntime()) == "structured output"


def test_create_usecase_workflow_returns_initialized_snapshot() -> None:
    payload = workflow_tools.create_usecase_workflow.invoke(
        {
            "project_id": "project-1",
            "title": "Login usecase workflow",
            "summary": "Generate login-related use cases",
        }
    )
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "workflow_initialized"
    assert data["payload"]["delivery_status"] == "not_configured"
    assert data["payload"]["project_id"] == "project-1"


def test_create_usecase_workflow_without_required_fields_returns_snapshot_instead_of_error() -> None:
    payload = workflow_tools.create_usecase_workflow.invoke({})
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["payload"]["delivery_status"] == "missing_required_fields"
    assert data["payload"]["missing_fields"] == ["project_id", "title"]


def test_record_usecase_review_reports_persistable_state() -> None:
    payload = workflow_tools.record_usecase_review.invoke(
        {
            "candidate_usecases_json": json.dumps({"usecases": [{"title": "login"}]}),
            "review_report_json": json.dumps({"deficiencies": []}),
        }
    )
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "reviewed_candidate_usecases"
    assert data["persistable"] is True
    assert data["next_action"] == "await_user_confirmation"
    assert data["payload"]["candidate_usecase_count"] == 1
    assert data["payload"]["deficiency_count"] == 0


def test_record_requirement_analysis_returns_workflow_snapshot() -> None:
    payload = workflow_tools.record_requirement_analysis.invoke(
        {
            "summary": "Extracted core flows",
            "analysis_json": json.dumps(
                {
                    "project_id": "project-1",
                    "workflow_id": "workflow-1",
                    "requirements": ["login", "logout"],
                }
            ),
        }
    )
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "requirement_analysis"
    assert data["persistable"] is False
    assert data["payload"]["requirement_count"] == 2
    assert data["payload"]["persistence_result"]["delivery_status"] == "not_configured"


def test_persist_approved_usecases_returns_persisted_snapshot() -> None:
    payload = workflow_tools.persist_approved_usecases.invoke(
        {
            "final_usecases_json": json.dumps(
                {"workflow_id": "workflow-1", "usecases": [{"title": "login success"}]}
            ),
            "approval_note": "approved by reviewer",
        }
    )
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "persisted"
    assert data["persistable"] is True
    assert data["payload"]["final_usecase_count"] == 1
    assert data["payload"]["persistence_result"]["delivery_status"] == "not_configured"


def test_record_requirement_analysis_posts_snapshot_when_configured(
    monkeypatch: Any,
) -> None:
    calls: list[dict[str, Any]] = []

    class DummyResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: int) -> DummyResponse:
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return DummyResponse({"id": "snap_1", "status": json["status"]})

    monkeypatch.setenv("INTERACTION_DATA_SERVICE_URL", "http://localhost:8090")
    monkeypatch.setattr(workflow_tools.requests, "post", fake_post)

    payload = workflow_tools.record_requirement_analysis.invoke(
        {
            "summary": "Extracted core flows",
            "analysis_json": json.dumps(
                {
                    "project_id": "project-1",
                    "workflow_id": "workflow-1",
                    "requirements": ["login"],
                }
            ),
        }
    )
    data = json.loads(payload)
    assert len(calls) == 1
    assert calls[0]["url"] == "http://localhost:8090/api/workflows/workflow-1/snapshots"
    assert calls[0]["json"]["status"] == "requirement_analysis"
    assert calls[0]["json"]["persistable"] is False
    assert data["payload"]["persistence_result"]["delivery_status"] == "persisted"


def test_persist_approved_usecases_posts_to_interaction_data_service(
    monkeypatch: Any,
) -> None:
    calls: list[dict[str, Any]] = []

    class DummyResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: int) -> DummyResponse:
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        if url.endswith("/approve"):
            return DummyResponse({"id": "workflow-1", "status": "approved_for_persistence"})
        if url.endswith("/persist"):
            return DummyResponse(
                {
                    "workflow": {"id": "workflow-1", "status": "persisted"},
                    "use_case": {"id": "uc_1", "status": "active"},
                }
            )
        return DummyResponse({"ok": True})

    monkeypatch.setenv("INTERACTION_DATA_SERVICE_URL", "http://localhost:8090")
    monkeypatch.setenv("INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS", "12")
    monkeypatch.setattr(workflow_tools.requests, "post", fake_post)

    payload = workflow_tools.persist_approved_usecases.invoke(
        {
            "final_usecases_json": json.dumps(
                {
                    "workflow_id": "workflow-1",
                    "usecases": [{"title": "login success", "description": "user logs in"}],
                }
            ),
            "approval_note": "approved",
        }
    )

    data = json.loads(payload)
    assert len(calls) == 2
    assert calls[0]["url"] == "http://localhost:8090/api/workflows/workflow-1/approve"
    assert calls[1]["url"] == "http://localhost:8090/api/workflows/workflow-1/persist"
    assert calls[1]["timeout"] == 12
    assert data["payload"]["persistence_result"]["delivery_status"] == "persisted"
    assert data["payload"]["persistence_result"]["persist_result"]["use_case"]["id"] == "uc_1"


def test_record_usecase_review_posts_snapshot_and_review_when_configured(
    monkeypatch: Any,
) -> None:
    calls: list[dict[str, Any]] = []

    class DummyResponse:
        def __init__(self, payload: dict[str, Any]) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return self._payload

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, Any], timeout: int) -> DummyResponse:
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if url.endswith("/snapshots"):
            return DummyResponse({"id": "snap_1", "status": json["status"]})
        return DummyResponse({"id": "rev_1", "status": "reviewed", "summary": json["summary"]})

    monkeypatch.setenv("INTERACTION_DATA_SERVICE_URL", "http://localhost:8090")
    monkeypatch.setattr(workflow_tools.requests, "post", fake_post)

    payload = workflow_tools.record_usecase_review.invoke(
        {
            "candidate_usecases_json": json.dumps(
                {
                    "project_id": "project-1",
                    "workflow_id": "workflow-1",
                    "usecases": [{"title": "login"}],
                }
            ),
            "review_report_json": json.dumps(
                {"summary": "Looks good", "deficiencies": [], "revision_suggestions": []}
            ),
        }
    )
    data = json.loads(payload)
    assert len(calls) == 2
    assert calls[0]["url"] == "http://localhost:8090/api/workflows/workflow-1/snapshots"
    assert calls[1]["url"] == "http://localhost:8090/api/workflows/workflow-1/review"
    assert data["payload"]["persistence_result"]["delivery_status"] == "persisted"
    assert data["payload"]["review_persistence_result"]["delivery_status"] == "persisted"


def test_make_graph_builds_business_agent_with_pdf_middleware_and_hitl(monkeypatch: Any) -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    captured: dict[str, Any] = {}

    class DummyOptions:
        model_spec = object()
        system_prompt = None

    def fake_create_agent(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured["args"] = args
        captured.update(kwargs)
        return {"name": kwargs.get("name"), "tools": kwargs.get("tools")}

    monkeypatch.setattr(workflow_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(workflow_graph, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(workflow_graph, "resolve_model", lambda spec: spec)
    monkeypatch.setattr(workflow_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(workflow_graph, "create_agent", fake_create_agent)

    result = asyncio.run(workflow_graph.make_graph({"configurable": {}}, object()))

    assert result["name"] == "usecase_workflow_agent"
    assert any(getattr(tool, "name", "") == "run_requirement_analysis_subagent" for tool in captured["tools"])
    assert any(getattr(tool, "name", "") == "run_usecase_review_subagent" for tool in captured["tools"])
    assert any(getattr(tool, "name", "") == "persist_approved_usecases" for tool in captured["tools"])
    middleware_names = [type(item).__name__ for item in captured["middleware"]]
    assert "HumanInTheLoopMiddleware" in middleware_names
    assert "MultimodalMiddleware" in middleware_names
    assert captured["system_prompt"]


def test_make_graph_uses_service_prompt_when_runtime_prompt_is_default(monkeypatch: Any) -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    captured: dict[str, Any] = {}

    class DummyOptions:
        model_spec = object()
        system_prompt = ""

    def fake_create_agent(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args
        captured.update(kwargs)
        return {"name": kwargs.get("name")}

    monkeypatch.setattr(workflow_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(workflow_graph, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(workflow_graph, "resolve_model", lambda spec: spec)
    monkeypatch.setattr(workflow_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(workflow_graph, "build_usecase_workflow_tools", lambda model: ["tool"])
    monkeypatch.setattr(workflow_graph, "create_agent", fake_create_agent)

    asyncio.run(workflow_graph.make_graph({"configurable": {}}, object()))

    assert captured["system_prompt"] == workflow_graph.SYSTEM_PROMPT


def test_make_graph_uses_custom_runtime_prompt_when_provided(monkeypatch: Any) -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    captured: dict[str, Any] = {}

    class DummyOptions:
        model_spec = object()
        system_prompt = "custom runtime prompt"

    def fake_create_agent(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args
        captured.update(kwargs)
        return {"name": kwargs.get("name")}

    monkeypatch.setattr(workflow_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(workflow_graph, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(workflow_graph, "resolve_model", lambda spec: spec)
    monkeypatch.setattr(workflow_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(workflow_graph, "build_usecase_workflow_tools", lambda model: ["tool"])
    monkeypatch.setattr(workflow_graph, "create_agent", fake_create_agent)

    asyncio.run(workflow_graph.make_graph({"configurable": {}}, object()))

    assert captured["system_prompt"] == "custom runtime prompt"


def test_langgraph_registers_usecase_workflow_agent() -> None:
    langgraph_file = _PROJECT_ROOT / "graph_src_v2" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "usecase_workflow_agent" in data["graphs"]
