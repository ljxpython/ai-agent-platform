# pyright: reportMissingImports=false, reportFunctionMemberAccess=false
from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import ToolMessage
from langchain_core.language_models.chat_models import BaseChatModel

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from graph_src_v2.services.usecase_workflow_agent import tools as workflow_tools  # noqa: E402
from graph_src_v2.tests import services_usecase_workflow as local_repl  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # noqa: E402


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
        "run_usecase_generation_subagent",
        "run_usecase_review_subagent",
        "run_usecase_persist_subagent",
        "record_requirement_analysis",
        "record_generated_usecases",
        "record_usecase_review",
    ]


def test_subagent_tools_hide_runtime_from_schema() -> None:
    requirement_tool = workflow_tools.build_requirement_analysis_subagent_tool(object())
    generation_tool = workflow_tools.build_usecase_generation_subagent_tool(object())
    review_tool = workflow_tools.build_usecase_review_subagent_tool(object())
    persist_plan_tool = workflow_tools.build_usecase_persist_subagent_tool(object())
    record_analysis_tool = workflow_tools.record_requirement_analysis
    record_generation_tool = workflow_tools.record_generated_usecases
    record_review_tool = workflow_tools.record_usecase_review

    assert set(requirement_tool.args.keys()) == set()
    assert set(generation_tool.args.keys()) == set()
    assert set(review_tool.args.keys()) == set()
    assert set(persist_plan_tool.args.keys()) == set()
    assert set(record_analysis_tool.args.keys()) == set()
    assert set(record_generation_tool.args.keys()) == set()
    assert set(record_review_tool.args.keys()) == set()


def test_subagent_tools_require_non_empty_context() -> None:
    requirement_tool = workflow_tools.build_requirement_analysis_subagent_tool(object())
    generation_tool = workflow_tools.build_usecase_generation_subagent_tool(object())
    review_tool = workflow_tools.build_usecase_review_subagent_tool(object())
    persist_plan_tool = workflow_tools.build_usecase_persist_subagent_tool(object())

    class DummyRuntime:
        def __init__(self) -> None:
            self.state: dict[str, Any] = {}

    with pytest.raises(ValueError, match="requirement_context is required"):
        requirement_tool.func(runtime=DummyRuntime())

    with pytest.raises(ValueError, match="generation_context is required"):
        generation_tool.func(runtime=DummyRuntime())

    with pytest.raises(ValueError, match="review_context is required"):
        review_tool.func(runtime=DummyRuntime())

    with pytest.raises(ValueError, match="persist_context is required"):
        persist_plan_tool.func(runtime=DummyRuntime())


def test_subagent_tools_can_derive_context_from_runtime_state(monkeypatch: Any) -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    HumanMessage(content="请分析这个需求文档并提炼核心功能点"),
                    ToolMessage(
                        content=json.dumps({"summary": "需求文档摘要", "requirements": ["登录"]}),
                        tool_call_id="tc_analysis",
                        name="run_requirement_analysis_subagent",
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "summary": "候选用例已完成评审",
                                "persistable": True,
                                "next_action": "await_user_confirmation",
                                "payload": {
                                    "project_id": "project-1",
                                    "candidate_usecases": {"usecases": [{"title": "登录成功"}]},
                                    "review_report": {"summary": "ready", "deficiencies": [], "strengths": [], "revision_suggestions": []},
                                },
                            }
                        ),
                        tool_call_id="tc_review",
                        name="record_usecase_review",
                    ),
                ],
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
        workflow_tools, "_build_usecase_generation_subagent", lambda model: DummySubagent()
    )
    monkeypatch.setattr(
        workflow_tools, "_build_usecase_review_subagent", lambda model: DummySubagent()
    )
    monkeypatch.setattr(
        workflow_tools,
        "_build_usecase_persist_subagent",
        lambda model, persist_tool: DummySubagent(),
    )

    requirement_tool = workflow_tools.build_requirement_analysis_subagent_tool(object())
    generation_tool = workflow_tools.build_usecase_generation_subagent_tool(object())
    review_tool = workflow_tools.build_usecase_review_subagent_tool(object())
    persist_plan_tool = workflow_tools.build_usecase_persist_subagent_tool(object())

    assert getattr(requirement_tool, "func")(runtime=DummyRuntime()) == "structured output"
    assert getattr(generation_tool, "func")(runtime=DummyRuntime()) == "structured output"
    assert getattr(review_tool, "func")(runtime=DummyRuntime()) == "structured output"
    assert getattr(persist_plan_tool, "func")(runtime=DummyRuntime()) == "structured output"


def test_requirement_subagent_tool_retries_retryable_provider_error(
    monkeypatch: Any,
) -> None:
    attempts = {"count": 0}

    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [HumanMessage(content="请分析这个需求文档")],
                "multimodal_summary": "需求文档摘要",
            }

    class FlakySubagent:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            del payload
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise TypeError("Received response with null value for 'choices'.")
            return {"messages": [AIMessage(content="structured output")]}

    monkeypatch.setattr(
        workflow_tools,
        "_build_requirement_analysis_subagent",
        lambda model: FlakySubagent(),
    )

    requirement_tool = workflow_tools.build_requirement_analysis_subagent_tool(object())

    assert getattr(requirement_tool, "func")(runtime=DummyRuntime()) == "structured output"
    assert attempts["count"] == 2


def test_persist_plan_tool_falls_back_when_provider_response_is_malformed(
    monkeypatch: Any,
) -> None:
    class FailingSubagent:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            del payload
            raise TypeError("Received response with null value for 'choices'.")

    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "payload": {
                                    "workflow_id": "workflow-review",
                                    "project_id": "project-1",
                                    "candidate_usecases": {
                                        "usecases": [{"title": "login success"}]
                                    },
                                    "review_report": {
                                        "summary": "ready for persistence"
                                    },
                                },
                            }
                        ),
                        tool_call_id="tc_review_snapshot",
                        name="record_usecase_review",
                    ),
                    HumanMessage(content="I explicitly confirm persistence."),
                ]
            }

    monkeypatch.setattr(
        workflow_tools,
        "_build_usecase_persist_subagent",
        lambda model, persist_tool: FailingSubagent(),
    )
    persist_plan_tool = workflow_tools.build_usecase_persist_subagent_tool(object())

    result = getattr(persist_plan_tool, "func")(runtime=DummyRuntime())
    payload = json.loads(result)

    assert payload["summary"] == "Prepared fallback persistence plan from the latest reviewed use cases."
    assert payload["project_id"] == "project-1"
    assert payload["final_usecases"][0]["title"] == "login success"


def test_record_usecase_review_reports_persistable_state() -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "workflow_id": "workflow-1",
                "latest_snapshot": {"payload": {"project_id": "project-1"}},
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "generated_candidate_usecases",
                                "summary": "Generated candidate use cases",
                                "persistable": False,
                                "next_action": "run_usecase_review_subagent",
                                "payload": {
                                    "project_id": "project-1",
                                    "candidate_usecase_count": 1,
                                    "candidate_usecases": {"usecases": [{"title": "login"}]},
                                },
                            }
                        ),
                        tool_call_id="tc_generation_snapshot",
                        name="record_generated_usecases",
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Looks good",
                                "candidate_usecases": [{"title": "login"}],
                                "deficiencies": [],
                                "strengths": [],
                                "revision_suggestions": [],
                            }
                        ),
                        tool_call_id="tc_1",
                        name="run_usecase_review_subagent",
                    )
                ],
            }

    payload = getattr(workflow_tools.record_usecase_review, "func")(runtime=DummyRuntime())
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "reviewed_candidate_usecases"
    assert data["next_action"] == "await_user_confirmation"


def test_record_usecase_review_waits_for_user_revision_when_deficiencies_exist() -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "workflow_id": "workflow-1",
                "latest_snapshot": {"payload": {"project_id": "project-1"}},
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "generated_candidate_usecases",
                                "summary": "Generated candidate use cases",
                                "persistable": False,
                                "next_action": "run_usecase_review_subagent",
                                "payload": {
                                    "project_id": "project-1",
                                    "candidate_usecase_count": 1,
                                    "candidate_usecases": {"usecases": [{"title": "login"}]},
                                },
                            }
                        ),
                        tool_call_id="tc_generation_snapshot",
                        name="record_generated_usecases",
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Still missing edge cases",
                                "candidate_usecases": [{"title": "login"}],
                                "deficiencies": ["missing edge case"],
                                "strengths": ["clear happy path"],
                                "revision_suggestions": ["add boundary and exception flows"],
                            }
                        ),
                        tool_call_id="tc_review_with_gap",
                        name="run_usecase_review_subagent",
                    ),
                ],
            }

    payload = getattr(workflow_tools.record_usecase_review, "func")(runtime=DummyRuntime())
    data = json.loads(payload)

    assert data["stage"] == "reviewed_candidate_usecases"
    assert data["persistable"] is False
    assert data["next_action"] == "await_user_revision"


def test_record_usecase_review_accepts_fenced_json_payload() -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "latest_snapshot": {"payload": {"project_id": "project-1"}},
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "generated_candidate_usecases",
                                "summary": "Generated candidate use cases",
                                "persistable": False,
                                "next_action": "run_usecase_review_subagent",
                                "payload": {
                                    "project_id": "project-1",
                                    "candidate_usecases": {"usecases": [{"title": "login"}]},
                                },
                            }
                        ),
                        tool_call_id="tc_generation_snapshot",
                        name="record_generated_usecases",
                    ),
                    ToolMessage(
                        content=(
                            "```json\n"
                            "{\"summary\":\"Looks good\",\"candidate_usecases\":[{\"title\":\"login\"}],"
                            "\"deficiencies\":[],\"strengths\":[],\"revision_suggestions\":[]}\n"
                            "```"
                        ),
                        tool_call_id="tc_review_fenced",
                        name="run_usecase_review_subagent",
                    ),
                ],
            }

    payload = getattr(workflow_tools.record_usecase_review, "func")(runtime=DummyRuntime())
    data = json.loads(payload)

    assert data["stage"] == "reviewed_candidate_usecases"
    assert data["persistable"] is True


def test_record_requirement_analysis_accepts_embedded_json_payload() -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=(
                            "下面是需求分析结果：\n"
                            "{\"summary\":\"需求摘要\",\"requirements\":[\"登录\"],"
                            "\"business_rules\":[],\"preconditions\":[],\"edge_cases\":[],"
                            "\"exception_scenarios\":[],\"open_questions\":[]}\n"
                            "请继续。"
                        ),
                        tool_call_id="tc_analysis_embedded",
                        name="run_requirement_analysis_subagent",
                    )
                ],
            }

    payload = getattr(workflow_tools.record_requirement_analysis, "func")(runtime=DummyRuntime())
    data = json.loads(payload)

    assert data["stage"] == "requirement_analysis"
    assert data["payload"]["analysis"]["requirements"] == ["登录"]
    assert data["persistable"] is False
    assert data["next_action"] == "run_usecase_generation_subagent"
    assert data["payload"]["requirement_count"] == 1


def test_record_requirement_analysis_returns_workflow_snapshot() -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Extracted core flows",
                                "project_id": "project-1",
                                "requirements": ["login", "logout"],
                            }
                        ),
                        tool_call_id="tc_1",
                        name="run_requirement_analysis_subagent",
                    )
                ]
            }

    payload = getattr(workflow_tools.record_requirement_analysis, "func")(runtime=DummyRuntime())
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "requirement_analysis"
    assert data["persistable"] is False
    assert data["payload"]["requirement_count"] == 2


def test_record_generated_usecases_returns_workflow_snapshot() -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Generated candidate use cases",
                                "project_id": "project-1",
                                "usecases": [
                                    {
                                        "title": "login success",
                                        "preconditions": ["user exists"],
                                        "steps": ["open login page", "submit credentials"],
                                        "expected_results": ["login succeeds"],
                                        "coverage_points": ["happy path"],
                                    }
                                ],
                            }
                        ),
                        tool_call_id="tc_1",
                        name="run_usecase_generation_subagent",
                    )
                ]
            }

    payload = getattr(workflow_tools.record_generated_usecases, "func")(runtime=DummyRuntime())
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "generated_candidate_usecases"
    assert data["persistable"] is False
    assert data["next_action"] == "run_usecase_review_subagent"
    assert data["payload"]["candidate_usecase_count"] == 1


def test_persist_approved_usecases_returns_persisted_snapshot(monkeypatch: Any) -> None:
    monkeypatch.delenv("INTERACTION_DATA_SERVICE_URL", raising=False)
    monkeypatch.delenv("INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("INTERACTION_DATA_SERVICE_TOKEN", raising=False)

    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "summary": "Reviewed candidate use cases are ready for persistence.",
                                "persistable": True,
                                "next_action": "await_user_confirmation",
                                "payload": {
                                    "project_id": "project-1",
                                    "candidate_usecases": {"usecases": [{"title": "login success"}]},
                                    "revised_usecases": None,
                                }
                            }
                        ),
                        tool_call_id="tc_1",
                        name="record_usecase_review",
                    )
                ]
            }

    payload = workflow_tools._persist_approved_usecases_from_state(
        DummyRuntime().state,
        approval_note="approved by reviewer",
    )
    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "persisted"
    assert data["persistable"] is True
    assert data["payload"]["final_usecase_count"] == 1
    assert data["payload"]["persistence_result"]["delivery_status"] == "not_configured"


def test_persist_approved_usecases_with_revision_feedback_returns_review_snapshot(
    monkeypatch: Any,
) -> None:
    def fail_post(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("edit feedback must not trigger persistence")

    monkeypatch.setattr(workflow_tools.requests, "post", fail_post)

    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "summary": "Reviewed candidate use cases are ready for persistence.",
                                "persistable": True,
                                "next_action": "await_user_confirmation",
                                "payload": {
                                    "workflow_id": "workflow-1",
                                    "project_id": "project-1",
                                    "deficiency_count": 0,
                                    "candidate_usecases": {"usecases": [{"title": "login success"}]},
                                    "review_report": {
                                        "summary": "Looks good",
                                        "deficiencies": [],
                                        "strengths": ["clear happy path"],
                                        "revision_suggestions": [],
                                    },
                                    "revised_usecases": None,
                                }
                            }
                        ),
                        tool_call_id="tc_1",
                        name="record_usecase_review",
                    )
                ]
            }

    payload = workflow_tools._persist_approved_usecases_from_state(
        DummyRuntime().state,
        revision_feedback="Please split admin and member scenarios before saving.",
    )

    data = json.loads(payload)
    _assert_snapshot_envelope(data)
    assert data["stage"] == "reviewed_candidate_usecases"
    assert data["persistable"] is False
    assert data["next_action"] == "revise_and_review_again"
    assert data["payload"]["human_revision_feedback"] == (
        "Please split admin and member scenarios before saving."
    )


def test_persist_approved_usecases_prefers_latest_persist_plan(monkeypatch: Any) -> None:
    monkeypatch.delenv("INTERACTION_DATA_SERVICE_URL", raising=False)
    monkeypatch.delenv("INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("INTERACTION_DATA_SERVICE_TOKEN", raising=False)

    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "summary": "Reviewed candidate use cases are ready for persistence.",
                                "persistable": True,
                                "next_action": "await_user_confirmation",
                                "payload": {
                                    "workflow_id": "workflow-review",
                                    "project_id": "project-1",
                                    "candidate_usecases": {
                                        "usecases": [{"title": "review draft"}]
                                    },
                                    "revised_usecases": None,
                                }
                            }
                        ),
                        tool_call_id="tc_review",
                        name="record_usecase_review",
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Prepared final persist plan",
                                "workflow_id": "workflow-plan",
                                "project_id": "project-2",
                                "approval_note": "plan-approved",
                                "document_persistence_requested": False,
                                "final_usecases": [
                                    {"title": "persist plan use case", "description": "from plan"}
                                ],
                            }
                        ),
                        tool_call_id="tc_persist_plan",
                        name="run_usecase_persist_subagent",
                    ),
                ]
            }

    payload = workflow_tools._persist_approved_usecases_from_state(
        DummyRuntime().state,
        approval_note="ignored-when-plan-exists",
    )
    data = json.loads(payload)
    assert data["payload"]["approval_note"] == "plan-approved"
    assert data["payload"]["persist_plan"]["workflow_id"] == "workflow-plan"
    assert data["payload"]["persist_plan"]["project_id"] == "project-2"
    assert data["payload"]["final_usecases"]["usecases"][0]["title"] == "persist plan use case"
    assert data["payload"]["persistence_result"]["document_delivery_status"] == "skipped_by_plan"


def test_review_tool_context_includes_human_revision_feedback(monkeypatch: Any) -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    HumanMessage(content="Please revise the draft before persisting it."),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "generated_candidate_usecases",
                                "summary": "Generated candidate use cases",
                                "persistable": False,
                                "next_action": "run_usecase_review_subagent",
                                "payload": {
                                    "project_id": "project-1",
                                    "candidate_usecase_count": 1,
                                    "candidate_usecases": {"usecases": [{"title": "login"}]},
                                },
                            }
                        ),
                        tool_call_id="tc_generation_snapshot",
                        name="record_generated_usecases",
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Looks good",
                                "candidate_usecases": [{"title": "login"}],
                                "deficiencies": [],
                                "strengths": [],
                                "revision_suggestions": [],
                            }
                        ),
                        tool_call_id="tc_review_subagent",
                        name="run_usecase_review_subagent",
                    ),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "summary": "Human reviewer requested revisions before persistence.",
                                "persistable": False,
                                "next_action": "revise_and_review_again",
                                "payload": {
                                    "project_id": "project-1",
                                    "candidate_usecase_count": 1,
                                    "deficiency_count": 1,
                                    "candidate_usecases": {"usecases": [{"title": "login"}]},
                                    "review_report": {
                                        "summary": "Looks good",
                                        "deficiencies": [],
                                        "strengths": [],
                                        "revision_suggestions": [],
                                    },
                                    "human_revision_feedback": "Add separate admin and member flows.",
                                },
                            }
                        ),
                        tool_call_id="tc_edit_feedback",
                        name="run_usecase_persist_subagent",
                    ),
                ]
            }

    class DummySubagent:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            prompt = payload["messages"][0].content
            assert "[HUMAN_REVISION_FEEDBACK]" in prompt
            assert "Add separate admin and member flows." in prompt
            assert "[LATEST_GENERATED_CANDIDATE_USECASES]" in prompt
            assert "[LATEST_RECORDED_CANDIDATE_USECASES]" in prompt
            return {"messages": [HumanMessage(content="review output")]} 

    monkeypatch.setattr(
        workflow_tools, "_build_usecase_review_subagent", lambda model: DummySubagent()
    )

    review_tool = workflow_tools.build_usecase_review_subagent_tool(object())

    assert getattr(review_tool, "func")(runtime=DummyRuntime()) == "review output"


def test_record_requirement_analysis_is_in_memory_only(
    monkeypatch: Any,
) -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Extracted core flows",
                                "project_id": "project-1",
                                "requirements": ["login"],
                            }
                        ),
                        tool_call_id="tc_1",
                        name="run_requirement_analysis_subagent",
                    )
                ]
            }

    payload = getattr(workflow_tools.record_requirement_analysis, "func")(runtime=DummyRuntime())
    data = json.loads(payload)
    assert data["stage"] == "requirement_analysis"


def test_workflow_tool_selection_infers_generation_stage_from_tool_message() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["analysis"]
                + workflow_graph.STAGE_ALLOWED_TOOLS["generation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state={
            "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "requirement_analysis",
                                "persistable": False,
                        }
                    ),
                    tool_call_id="tc_1",
                )
            ]
        },
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_usecase_generation_subagent"]
        assert "Current workflow stage: generation." in updated_request.system_message.content
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].tool_calls[0]["name"] == "run_usecase_generation_subagent"


def test_workflow_tool_selection_moves_from_generation_snapshot_to_review() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["generation"]
                + workflow_graph.STAGE_ALLOWED_TOOLS["review"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state={
            "messages": [
                ToolMessage(
                    content=json.dumps(
                        {
                            "stage": "generated_candidate_usecases",
                            "persistable": False,
                        }
                    ),
                    tool_call_id="tc_generation",
                    name="record_generated_usecases",
                )
            ]
        },
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_usecase_review_subagent"]
        assert "Current workflow stage: review." in updated_request.system_message.content
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].tool_calls[0]["name"] == "run_usecase_review_subagent"


def test_workflow_tool_selection_uses_latest_review_message_to_reenter_generation() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["generation"]
                + workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "current_stage": "awaiting_user_confirmation",
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "persistable": False,
                                "next_action": "revise_and_review_again",
                            }
                        ),
                        tool_call_id="tc_edit",
                        name="run_usecase_persist_subagent",
                    )
                ],
            },
        ),
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_usecase_generation_subagent"]
        assert "Current workflow stage: generation." in updated_request.system_message.content
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls[0]["name"] == "run_usecase_generation_subagent"


def test_workflow_tool_selection_injects_generation_progress_text() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="请继续生成候选用例")],
        tools=cast(
            Any,
            [DummyTool(name) for name in workflow_graph.STAGE_ALLOWED_TOOLS["generation"]],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {"current_stage": "generation"}),
    )

    def handler(updated_request: Any) -> ModelResponse:
        del updated_request
        return ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "run_usecase_generation_subagent",
                            "args": {},
                            "id": "call_generation",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        )

    response = middleware.wrap_model_call(request, handler)

    assert "正在根据需求分析生成候选用例" in response.result[0].content


def test_workflow_tool_selection_hides_tools_for_greeting_only_first_turn() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="你好")],
        tools=cast(
            Any,
            [DummyTool(name) for name in workflow_graph.STAGE_ALLOWED_TOOLS["analysis"]],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {}),
    )

    def handler(updated_request: Any) -> ModelResponse:
        assert updated_request.tools == []
        assert (
            "Greeting-only check-in detected with no active workflow context."
            in updated_request.system_message.content
        )
        assert "current_stage" not in updated_request.state
        return ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "run_requirement_analysis_subagent",
                            "args": {},
                            "id": "call_analysis_from_greeting",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        )

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls == []


def test_workflow_tool_selection_allows_explicit_workflow_request_after_greeting() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="你好，帮我分析这个需求")],
        tools=cast(
            Any,
            [DummyTool(name) for name in workflow_graph.STAGE_ALLOWED_TOOLS["analysis"]],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {}),
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_requirement_analysis_subagent"]
        assert "Current workflow stage: analysis." in updated_request.system_message.content
        assert updated_request.state["current_stage"] == "analysis"
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls[0]["name"] == "run_requirement_analysis_subagent"


def test_workflow_tool_selection_allows_greeting_turn_when_attachment_context_exists() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="你好")],
        tools=cast(
            Any,
            [DummyTool(name) for name in workflow_graph.STAGE_ALLOWED_TOOLS["analysis"]],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "multimodal_summary": "检测到以下多模态附件：PDF 已解析。",
                "multimodal_attachments": [{"attachment_id": "att_1", "kind": "pdf"}],
            },
        ),
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_requirement_analysis_subagent"]
        assert "Current workflow stage: analysis." in updated_request.system_message.content
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls[0]["name"] == "run_requirement_analysis_subagent"


def test_workflow_tool_selection_keeps_active_stage_during_greeting_turn() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="你好")],
        tools=cast(
            Any,
            [DummyTool(name) for name in workflow_graph.STAGE_ALLOWED_TOOLS["review"]],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {"current_stage": "review"}),
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_usecase_review_subagent"]
        assert "Current workflow stage: review." in updated_request.system_message.content
        assert updated_request.state["current_stage"] == "review"
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls[0]["name"] == "run_usecase_review_subagent"


def test_local_repl_builds_structured_edit_resume_payload() -> None:
    payload = local_repl._build_interrupt_resume_payload(
        "edit", "Please split admin and member scenarios before saving."
    )

    assert payload == {
        "decisions": [
            {
                "type": "edit",
                "edited_action": {
                    "name": "persist_approved_usecases",
                    "args": {
                        "revision_feedback": "Please split admin and member scenarios before saving."
                    },
                },
            }
        ]
    }


def test_workflow_tool_selection_drops_blank_tool_name_from_model_response() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="Please keep analyzing the requirements.")],
        tools=cast(
            Any,
            [DummyTool(name) for name in workflow_graph.STAGE_ALLOWED_TOOLS["analysis"]],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {"current_stage": "analysis"}),
    )

    def handler(updated_request: Any) -> ModelResponse:
        del updated_request
        return ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "",
                            "args": {},
                            "id": "call_blank_tool_name",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        )

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls[0]["name"] == "run_requirement_analysis_subagent"


def test_workflow_tool_selection_keeps_valid_confirmation_persist_plan_tool_call() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="I explicitly confirm persistence.")],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {"current_stage": "awaiting_user_confirmation"}),
    )

    valid_tool_call = {
        "name": "run_usecase_persist_subagent",
        "args": {},
        "id": "call_run_usecase_persist_subagent",
        "type": "tool_call",
    }

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_usecase_persist_subagent"]
        return ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "",
                            "args": {},
                            "id": "call_blank_tool_name",
                            "type": "tool_call",
                        },
                        valid_tool_call,
                    ],
                )
            ]
        )

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls == [valid_tool_call]


def test_workflow_tool_selection_keeps_persist_plan_only_after_plan_exists() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "current_stage": "awaiting_user_confirmation",
                "messages": [
                    HumanMessage(content="I explicitly confirm persistence."),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Prepared final persist plan",
                                "workflow_id": "workflow-1",
                                "project_id": "project-1",
                                "approval_note": "confirmed",
                                "document_persistence_requested": False,
                                "final_usecases": [{"title": "login success"}],
                            }
                        ),
                        tool_call_id="tc_persist_plan",
                        name="run_usecase_persist_subagent",
                    ),
                ],
            },
        ),
    )

    valid_tool_call = {
        "name": "run_usecase_persist_subagent",
        "args": {},
        "id": "call_run_usecase_persist_subagent",
        "type": "tool_call",
    }

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_usecase_persist_subagent"]
        return ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "persist_approved_usecases",
                            "args": {"approval_note": "confirmed"},
                            "id": "call_invalid_root_persist",
                            "type": "tool_call",
                        },
                        valid_tool_call,
                    ],
                )
            ]
        )

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls == [valid_tool_call]


def test_workflow_tool_selection_infers_awaiting_confirmation_stage_from_review_snapshot() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="The review looks good. What should I do next?")],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "persistable": True,
                            }
                        ),
                        tool_call_id="tc_reviewed_ready",
                        name="record_usecase_review",
                    )
                ]
            },
        ),
    )

    def handler(updated_request: Any) -> ModelResponse:
        assert updated_request.tools == []
        assert (
            "Current workflow stage: awaiting_user_confirmation."
            in updated_request.system_message.content
        )
        assert "waiting for an explicit user decision" in updated_request.system_message.content
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_workflow_tool_selection_infers_awaiting_revision_stage_from_review_snapshot() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="这轮评审结果具体是什么意思？")],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_revision"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "persistable": False,
                                "next_action": "await_user_revision",
                            }
                        ),
                        tool_call_id="tc_reviewed_needs_revision",
                        name="record_usecase_review",
                    )
                ]
            },
        ),
    )

    def handler(updated_request: Any) -> ModelResponse:
        assert updated_request.tools == []
        assert (
            "Current workflow stage: awaiting_user_revision."
            in updated_request.system_message.content
        )
        assert "requires revisions before persistence is possible" in updated_request.system_message.content
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "ok"


def test_workflow_tool_selection_routes_revision_request_to_generation_during_confirmation() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="请先修改这一版，并把管理员和成员场景拆开。")],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {"current_stage": "awaiting_user_confirmation"}),
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_usecase_generation_subagent"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls[0]["name"] == "run_usecase_generation_subagent"


def test_workflow_tool_selection_routes_revision_request_to_generation_during_revision_wait() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="请补充异常流程，并拆分管理员与普通用户场景。")],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_revision"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {"current_stage": "awaiting_user_revision"}),
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["run_usecase_generation_subagent"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls[0]["name"] == "run_usecase_generation_subagent"


def test_workflow_tool_selection_uses_record_tool_after_generation_result() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        tools=cast(
            Any,
            [DummyTool(name) for name in workflow_graph.STAGE_ALLOWED_TOOLS["generation"]],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "current_stage": "generation",
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Generated draft use cases",
                                "usecases": [{"title": "login success"}],
                            }
                        ),
                        tool_call_id="tc_generation_result",
                        name="run_usecase_generation_subagent",
                    )
                ],
            },
        ),
    )

    def handler(updated_request: Any) -> ModelResponse:
        names = [tool.name for tool in updated_request.tools]
        assert names == ["record_generated_usecases"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls[0]["name"] == "record_generated_usecases"


def test_workflow_tool_selection_requires_fresh_confirmation_after_re_review() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "current_stage": "awaiting_user_confirmation",
                "messages": [
                    HumanMessage(content="I explicitly confirm persistence."),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "persistable": True,
                            }
                        ),
                        tool_call_id="tc_review_after_edit",
                        name="record_usecase_review",
                    ),
                ],
            },
        ),
    )

    def handler(updated_request: Any) -> ModelResponse:
        assert updated_request.tools == []
        return ModelResponse(result=[AIMessage(content="Please confirm this new version again.")])

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].text == "Please confirm this new version again."


def test_workflow_tool_selection_strips_persist_tool_without_explicit_confirmation() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="The review looks good. What should I do next?")],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {"current_stage": "awaiting_user_confirmation"}),
    )

    def handler(updated_request: Any) -> ModelResponse:
        assert updated_request.tools == []
        return ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "persist_approved_usecases",
                            "args": {"approval_note": "confirmed"},
                            "id": "call_persist_without_confirmation",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        )

    response = middleware.wrap_model_call(request, handler)

    assert response.result[0].tool_calls == []


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
        if url.endswith("/api/usecase-generation/use-cases"):
            return DummyResponse({"id": "uc_1", "status": "active"})
        return DummyResponse({"ok": True})

    monkeypatch.setenv("INTERACTION_DATA_SERVICE_URL", "http://localhost:8090")
    monkeypatch.setenv("INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS", "12")
    monkeypatch.setattr(workflow_tools.requests, "post", fake_post)

    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "stage": "reviewed_candidate_usecases",
                                "summary": "Reviewed candidate use cases are ready for persistence.",
                                "persistable": True,
                                "next_action": "await_user_confirmation",
                                "payload": {
                                    "project_id": "project-1",
                                    "candidate_usecases": {
                                        "usecases": [{"title": "login success", "description": "user logs in"}]
                                    },
                                    "revised_usecases": None,
                                }
                            }
                        ),
                        tool_call_id="tc_1",
                        name="record_usecase_review",
                    )
                ]
            }

    payload = workflow_tools._persist_approved_usecases_from_state(
        DummyRuntime().state,
        approval_note="approved",
    )

    data = json.loads(payload)
    assert len(calls) == 1
    assert calls[0]["url"] == "http://localhost:8090/api/usecase-generation/use-cases"
    assert calls[0]["timeout"] == 12
    assert data["payload"]["persistence_result"]["delivery_status"] == "persisted"
    assert data["payload"]["persistence_result"]["persisted_items"][0]["id"] == "uc_1"


def test_record_usecase_review_is_in_memory_only(
    monkeypatch: Any,
) -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "latest_snapshot": {"payload": {"project_id": "project-1"}},
                "messages": [
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Looks good",
                                "candidate_usecases": [{"title": "login"}],
                                "deficiencies": [],
                                "strengths": [],
                                "revision_suggestions": [],
                            }
                        ),
                        tool_call_id="tc_1",
                        name="run_usecase_review_subagent",
                    )
                ]
            }

    payload = getattr(workflow_tools.record_usecase_review, "func")(runtime=DummyRuntime())
    data = json.loads(payload)
    assert data["stage"] == "reviewed_candidate_usecases"


def test_make_graph_preserves_production_streaming_with_pdf_middleware_and_hitl(
    monkeypatch: Any,
) -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    captured: dict[str, Any] = {}

    class DummyModel:
        disable_streaming = False

    class DummyOptions:
        model_spec = DummyModel()
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
    assert captured["model"].disable_streaming is False
    assert any(getattr(tool, "name", "") == "run_requirement_analysis_subagent" for tool in captured["tools"])
    assert any(getattr(tool, "name", "") == "run_usecase_generation_subagent" for tool in captured["tools"])
    assert any(getattr(tool, "name", "") == "run_usecase_review_subagent" for tool in captured["tools"])
    assert any(getattr(tool, "name", "") == "run_usecase_persist_subagent" for tool in captured["tools"])
    middleware_names = [type(item).__name__ for item in captured["middleware"]]
    assert "MultimodalMiddleware" in middleware_names
    assert captured["system_prompt"]


def test_local_repl_builds_non_streaming_agent_with_pdf_middleware(
    monkeypatch: Any,
) -> None:
    local_repl = importlib.import_module("graph_src_v2.tests.services_usecase_workflow")
    captured: dict[str, Any] = {}

    class DummyModel:
        disable_streaming = False

    class DummyOptions:
        model_spec = DummyModel()
        system_prompt = None

    def fake_create_agent(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured["args"] = args
        captured.update(kwargs)
        return {"name": kwargs.get("name"), "tools": kwargs.get("tools")}

    monkeypatch.setattr(local_repl, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(local_repl, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(local_repl, "resolve_model", lambda spec: spec)
    monkeypatch.setattr(local_repl, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(local_repl, "create_agent", fake_create_agent)

    result = asyncio.run(local_repl._build_local_agent({"configurable": {}}))

    assert result["name"] == "usecase_workflow_agent"
    assert captured["model"].disable_streaming is True
    middleware_names = [type(item).__name__ for item in captured["middleware"]]
    assert "MultimodalMiddleware" in middleware_names


def test_workflow_tool_selection_retries_retryable_model_error_once() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="hello")],
        tools=cast(Any, []),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {}),
    )
    attempts = {"count": 0}

    async def handler(updated_request: Any) -> ModelResponse:
        del updated_request
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TypeError("Received response with null value for 'choices'.")
        return ModelResponse(result=[AIMessage(content="ok")])

    response = asyncio.run(middleware.awrap_model_call(request, handler))

    assert attempts["count"] == 2
    assert response.result[0].text == "ok"


def test_workflow_tool_selection_returns_fallback_message_after_repeat_retryable_error() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="hello")],
        tools=cast(Any, []),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {}),
    )
    attempts = {"count": 0}

    async def handler(updated_request: Any) -> ModelResponse:
        del updated_request
        attempts["count"] += 1
        raise TypeError("Received response with null value for 'choices'.")

    response = asyncio.run(middleware.awrap_model_call(request, handler))

    assert attempts["count"] == 2
    assert "不兼容的响应格式" in response.result[0].text


def test_workflow_tool_selection_synthesizes_persist_plan_after_repeat_retryable_error() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "current_stage": "awaiting_user_confirmation",
                "messages": [HumanMessage(content="I explicitly confirm persistence.")],
            },
        ),
    )
    attempts = {"count": 0}

    async def handler(updated_request: Any) -> ModelResponse:
        del updated_request
        attempts["count"] += 1
        raise TypeError("Received response with null value for 'choices'.")

    response = asyncio.run(middleware.awrap_model_call(request, handler))

    assert attempts["count"] == 2
    assert response.result[0].tool_calls[0]["name"] == "run_usecase_persist_subagent"


def test_workflow_tool_selection_synthesizes_persist_plan_after_plan_exists_on_repeat_retryable_error() -> None:
    workflow_graph = importlib.import_module(
        "graph_src_v2.services.usecase_workflow_agent.graph"
    )
    middleware = workflow_graph.WorkflowToolSelectionMiddleware()

    class DummyTool:
        def __init__(self, name: str) -> None:
            self.name = name

    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[],
        tools=cast(
            Any,
            [
                DummyTool(name)
                for name in workflow_graph.STAGE_ALLOWED_TOOLS["awaiting_user_confirmation"]
            ],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(
            Any,
            {
                "current_stage": "awaiting_user_confirmation",
                "messages": [
                    HumanMessage(content="I explicitly confirm persistence."),
                    ToolMessage(
                        content=json.dumps(
                            {
                                "summary": "Prepared final persist plan",
                                "workflow_id": "workflow-1",
                                "project_id": "project-1",
                                "approval_note": "confirmed",
                                "document_persistence_requested": False,
                                "final_usecases": [{"title": "login success"}],
                            }
                        ),
                        tool_call_id="tc_persist_plan",
                        name="run_usecase_persist_subagent",
                    ),
                ],
            },
        ),
    )
    attempts = {"count": 0}

    async def handler(updated_request: Any) -> ModelResponse:
        del updated_request
        attempts["count"] += 1
        raise TypeError("Received response with null value for 'choices'.")

    response = asyncio.run(middleware.awrap_model_call(request, handler))

    assert attempts["count"] == 2
    assert response.result[0].tool_calls[0]["name"] == "run_usecase_persist_subagent"


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
