# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import asyncio
import importlib
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from graph_src_v2.services.usecase_workflow_agent import tools as workflow_tools  # noqa: E402
from graph_src_v2.tests.test_usecase_workflow_langgraph_api_smoke import (  # noqa: E402
    _build_review_snapshot,
)


class ToolReadyFakeChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> Any:
        del tools, tool_choice, kwargs
        return self


def _seed_review_state(project_id: str, user_text: str) -> dict[str, Any]:
    snapshot = _build_review_snapshot(project_id)
    return {
        "current_stage": "awaiting_user_confirmation",
        "latest_snapshot": snapshot,
        "ready_for_persist": True,
        "messages": [
            ToolMessage(
                name="record_usecase_review",
                tool_call_id="seed_review_snapshot",
                content=json.dumps(snapshot, ensure_ascii=False),
            ),
            HumanMessage(content=user_text),
        ],
    }


def _thread_config() -> dict[str, Any]:
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


def _build_local_agent(responses: list[AIMessage], monkeypatch: Any) -> Any:
    local_repl = importlib.import_module("graph_src_v2.tests.services_usecase_workflow")
    fake_model = ToolReadyFakeChatModel(responses=cast(Any, responses))

    monkeypatch.setattr(local_repl, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(
        local_repl,
        "build_runtime_config",
        lambda config, ctx: SimpleNamespace(model_spec="fake-model", system_prompt=""),
    )
    monkeypatch.setattr(local_repl, "resolve_model", lambda spec: fake_model)
    monkeypatch.setattr(local_repl, "apply_model_runtime_params", lambda model, options: model)

    return asyncio.run(local_repl._build_local_agent({"configurable": {}}))


def _build_resume_agent(
    *, responses: list[AIMessage], expected_feedback: str, monkeypatch: Any
) -> tuple[Any, list[str], str]:
    observed_feedback: list[str] = []

    class DummyGenerationSubagent:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            prompt = payload["messages"][0].content
            marker = "[HUMAN_REVISION_FEEDBACK]\n"
            latest_feedback = ""
            if marker in prompt:
                latest_feedback = prompt.split(marker, 1)[1].split("\n\n", 1)[0].strip()
            observed_feedback.append(latest_feedback)
            return {
                "messages": [
                    AIMessage(
                        content=json.dumps(
                            {
                                "summary": "Regenerated candidate use cases with the requested revisions.",
                                "usecases": [
                                    {"title": "admin login separated from member login"}
                                ],
                            }
                        )
                    )
                ]
            }

    class DummyReviewSubagent:
        def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
            del payload
            return {
                "messages": [
                    AIMessage(
                        content=json.dumps(
                            {
                                "summary": "Updated use cases address the requested revisions.",
                                "candidate_usecases": [
                                    {"title": "admin login separated from member login"}
                                ],
                                "deficiencies": [],
                                "strengths": ["revisions incorporated"],
                                "revision_suggestions": [],
                            }
                        )
                    )
                ]
            }

    monkeypatch.setattr(
        workflow_tools,
        "_build_usecase_generation_subagent",
        lambda model: DummyGenerationSubagent(),
    )
    monkeypatch.setattr(
        workflow_tools,
        "_build_usecase_review_subagent",
        lambda model: DummyReviewSubagent(),
    )
    monkeypatch.setattr(
        workflow_tools.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("edit resume must not persist")
        ),
    )

    agent = _build_local_agent(responses=responses, monkeypatch=monkeypatch)
    return agent, observed_feedback, expected_feedback


def test_local_invoke_without_confirmation_asks_for_confirmation(monkeypatch: Any) -> None:
    agent = _build_local_agent(
        responses=[
            AIMessage(
                content="I have the reviewed use cases ready, but I need your explicit confirmation before persisting them."
            )
        ],
        monkeypatch=monkeypatch,
    )
    project_id = str(uuid.uuid4())

    result = asyncio.run(
        agent.ainvoke(
            _seed_review_state(
                project_id,
                "The review looks good. What happens if I have not explicitly confirmed persistence yet?",
            ),
            config=_thread_config(),
        )
    )

    assert "__interrupt__" not in result
    assert result["messages"][-1].type == "ai"
    assert not result["messages"][-1].tool_calls
    assert "confirm" in result["messages"][-1].content.lower()


def test_local_invoke_with_confirmation_exposes_persist_interrupt(monkeypatch: Any) -> None:
    agent = _build_local_agent(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "run_usecase_persist_subagent",
                        "args": {},
                        "id": "call_run_usecase_persist_subagent",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "persist_approved_usecases",
                        "args": {"approval_note": "Explicitly confirmed by the reviewer."},
                        "id": "call_persist_approved_usecases",
                        "type": "tool_call",
                    }
                ],
            ),
        ],
        monkeypatch=monkeypatch,
    )
    project_id = str(uuid.uuid4())

    result = asyncio.run(
        agent.ainvoke(
            _seed_review_state(
                project_id,
                "I explicitly confirm persistence. Please save the approved use cases now.",
            ),
            config=_thread_config(),
        )
    )

    assert "__interrupt__" in result
    assert any(
        action_request["name"] == "persist_approved_usecases"
        for interrupt in result["__interrupt__"]
        for action_request in getattr(interrupt, "value", {}).get("action_requests", [])
    )
    assert any(
        tool_call["name"] == "run_usecase_persist_subagent"
        for message in result["messages"]
        if getattr(message, "type", None) == "ai"
        for tool_call in getattr(message, "tool_calls", [])
    )


def test_local_resume_with_edit_feedback_returns_to_review_loop(monkeypatch: Any) -> None:
    feedback = "Please split admin and member scenarios before saving."
    agent, observed_feedback, expected_feedback = _build_resume_agent(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "run_usecase_persist_subagent",
                        "args": {},
                        "id": "call_run_usecase_persist_subagent",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "persist_approved_usecases",
                        "args": {"approval_note": "Explicitly confirmed by the reviewer."},
                        "id": "call_persist_approved_usecases",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content=""),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "run_usecase_generation_subagent",
                        "args": {},
                        "id": "call_run_usecase_generation_subagent",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "record_generated_usecases",
                        "args": {},
                        "id": "call_record_generated_usecases",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "run_usecase_review_subagent",
                        "args": {},
                        "id": "call_run_usecase_review_subagent",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "record_usecase_review",
                        "args": {},
                        "id": "call_record_usecase_review",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="Updated review completed. Please confirm again before persistence."
            ),
        ],
        expected_feedback=feedback,
        monkeypatch=monkeypatch,
    )
    project_id = str(uuid.uuid4())
    config = _thread_config()

    initial_result = asyncio.run(
        agent.ainvoke(
            _seed_review_state(
                project_id,
                "I explicitly confirm persistence. Please save the approved use cases now.",
            ),
            config=config,
        )
    )

    assert "__interrupt__" in initial_result

    resume_result = asyncio.run(
        agent.ainvoke(
            Command(
                resume={
                    "decisions": [
                        {
                            "type": "edit",
                            "edited_action": {
                                "name": "persist_approved_usecases",
                                "args": {"revision_feedback": feedback},
                            },
                        }
                    ]
                }
            ),
            config=config,
        )
    )

    assert "__interrupt__" not in resume_result
    assert observed_feedback == [expected_feedback]
    assert resume_result["messages"][-1].type == "ai"
    assert "confirm again" in resume_result["messages"][-1].content.lower()
    generated_messages = [
        message
        for message in resume_result["messages"]
        if getattr(message, "type", None) == "tool"
        and getattr(message, "name", None) == "record_generated_usecases"
    ]
    assert generated_messages
    persist_messages = [
        message
        for message in resume_result["messages"]
        if getattr(message, "type", None) == "tool"
        and getattr(message, "name", None) == "run_usecase_persist_subagent"
    ]
    assert persist_messages
    persist_payload = json.loads(persist_messages[-1].content)
    assert persist_payload["stage"] == "reviewed_candidate_usecases"
    assert persist_payload["payload"]["human_revision_feedback"] == feedback
