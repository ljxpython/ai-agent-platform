from __future__ import annotations

import asyncio
import hashlib
import hmac

import httpx
import pytest
from langchain.agents import create_agent as real_create_agent
from langchain_core.messages import AIMessage
from langgraph.pregel import Pregel
from langgraph.types import Command
from support import (
    BindableFakeChatModel,
    BindableFakeMessagesChatModel,
    with_run_budget,
)

from runtime_service.graphs.workflow_demo import get_agent
from runtime_service.middlewares.timeout_wrapup import TIMEOUT_WRAPUP_INSTRUCTION
from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.services.demo.workflow_demo import agent


def _graph(*responses: str) -> Pregel:
    return asyncio.run(
        get_agent(
            {
                "configurable": {
                    "_runtime_model": BindableFakeChatModel(
                        responses=list(responses or ("model response",))
                    )
                }
            }
        )
    )


def _config(thread_id: str) -> dict[str, object]:
    return {"configurable": {"thread_id": thread_id}}


def test_internal_model_rebuild_keeps_outer_budget_and_actual_prompt(monkeypatch):
    budgets, prompts = [], []

    class Model(BindableFakeMessagesChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            prompts.append(messages[0].text)
            return super()._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )

    def capture(**kwargs):
        budgets.append(
            next(
                item.budget
                for item in kwargs["middleware"]
                if type(item).__name__ == "TimeoutWrapupMiddleware"
            )
        )
        return real_create_agent(**kwargs)

    monkeypatch.setattr(agent, "create_agent", capture)

    async def run():
        cfg = with_run_budget(
            {
                "configurable": {
                    "thread_id": "workflow-budget",
                    "_runtime_model": Model(responses=[AIMessage(content="report")]),
                }
            },
            remaining=30,
        )
        graph = await get_agent(cfg)
        await graph.ainvoke({"message": "first"}, _config("workflow-budget"))
        await graph.ainvoke({"message": "second"}, _config("workflow-budget"))
        assert len(budgets) == 2 and budgets[0] is budgets[1]
        assert all(TIMEOUT_WRAPUP_INSTRUCTION in prompt for prompt in prompts)

    asyncio.run(run())


@pytest.mark.parametrize("resume_reference", [None, "renewed-reference"])
def test_model_connection_is_signed_and_fetched_only_when_responding(
    monkeypatch, resume_reference
):
    monkeypatch.setenv(
        "PLATFORM_RUNTIME_MODEL_CONFIG_URL", "https://platform.invalid/model"
    )
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "test-secret")
    requests = []
    connection = {
        "model_id": agent._DEFAULTS.model_id,
        "provider": "deepseek",
        "base_url": "https://model.invalid",
        "protocol": "deepseek",
        "model": "test-model",
        "api_key": "test-key",
    }

    def respond(request):
        requests.append(request)
        reference = resume_reference or "original-reference"
        assert request.headers["x-runtime-model-ref"] == reference
        assert request.headers["x-project-id"] == "workflow-project"
        timestamp = request.headers["x-runtime-model-time"]
        expected = hmac.new(
            b"test-secret",
            f"{timestamp}\nworkflow-project\n{reference}".encode(),
            hashlib.sha256,
        ).hexdigest()
        assert request.headers["x-runtime-model-signature"] == expected
        return httpx.Response(200, json=connection)

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )

    def build_model(resolved, *, connection):
        assert connection["api_key"] == "test-key"
        return BindableFakeChatModel(responses=["model response"])

    monkeypatch.setattr(agent, "build_model", build_model)

    async def run():
        graph = await get_agent(
            {
                "configurable": {
                    "_runtime_test_local_auth": True,
                    "runtime_model_ref": "original-reference",
                }
            }
        )
        assert not requests
        config = _config("workflow-catalog-resume")
        paused = await graph.ainvoke(
            {"message": "hello", "requires_confirmation": True}, config
        )
        assert paused["__interrupt__"]
        assert not requests
        decision = {"decisions": [{"type": "approve"}]}
        if resume_reference:
            decision["_runtime_model_ref"] = resume_reference
        completed = await graph.ainvoke(Command(resume=decision), config)
        assert completed["response"] == "model response"
        assert len(requests) == 1

    asyncio.run(run())


def test_model_reference_without_endpoint_does_not_fall_back(monkeypatch):
    monkeypatch.delenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail(
            "invalid model reference must not fall back to environment credentials"
        )

    monkeypatch.setattr(agent, "build_model", forbidden)

    async def run():
        graph = await get_agent(
            {
                "configurable": {
                    "_runtime_test_local_auth": True,
                    "runtime_model_ref": "original-reference",
                }
            }
        )
        with pytest.raises(
            RuntimeResolutionError, match="runtime.model.initialization_failed"
        ):
            await graph.ainvoke(
                {"message": "hello"}, _config("workflow-missing-endpoint")
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    ("route", "expected"),
    [("approve", "model response"), ("reject", "model response")],
)
def test_workflow_demo_routes_to_one_conditional_branch(
    route: str, expected: str
) -> None:
    result = asyncio.run(
        _graph().ainvoke(
            {"message": "hello", "route": route},
            _config(f"workflow-branch-{route}"),
        )
    )

    assert result["response"] == expected


def test_workflow_demo_accepts_standard_chat_messages() -> None:
    result = asyncio.run(
        _graph().ainvoke(
            {"messages": [{"role": "user", "content": "hello from chat"}]},
            _config("workflow-chat-input"),
        )
    )

    assert result["response"] == "model response"
    assert result["messages"][-1].content == "model response"


def test_workflow_demo_uses_latest_user_message_in_same_thread() -> None:
    graph = _graph("first model response", "second model response")
    config = _config("workflow-multi-turn-test")

    first = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "你好"}]},
            config,
        )
    )
    second = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "你好啊，你是谁呀？"}]},
            config,
        )
    )

    assert first["response"] == "first model response"
    assert second["message"] == "你好啊，你是谁呀？"
    assert second["response"] == "second model response"


def test_workflow_demo_static_topology_is_stable() -> None:
    first = _graph()
    second = _graph()
    first_graph = first.get_graph()
    second_graph = second.get_graph()

    assert first is not second
    assert set(first_graph.nodes) == set(second_graph.nodes)
    assert {(edge.source, edge.target) for edge in first_graph.edges} == {
        (edge.source, edge.target) for edge in second_graph.edges
    }
    assert first.input_schema == second.input_schema
    assert first.output_schema == second.output_schema


def test_workflow_demo_interrupt_resume_does_not_repeat_completed_step() -> None:
    graph = _graph()
    config = {"configurable": {"thread_id": "workflow-resume-test"}}

    paused = asyncio.run(
        graph.ainvoke(
            {
                "message": "hello",
                "route": "reject",
                "requires_confirmation": True,
            },
            config,
        )
    )

    assert paused["__interrupt__"][0].value["kind"] == "workflow_confirmation"
    assert paused["__interrupt__"][0].value["action_requests"][0]["name"] == (
        "workflow_confirmation"
    )
    assert paused["prepared_count"] == 1

    interrupt_id = paused["__interrupt__"][0].id
    completed = asyncio.run(
        graph.ainvoke(Command(resume={interrupt_id: "approve"}), config)
    )

    assert completed["response"] == "model response"
    assert completed["prepared_count"] == 1
    assert completed["confirmation"] == "approve"


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_workflow_demo_accepts_web_hitl_decision_envelope(decision: str) -> None:
    graph = _graph()
    config = _config(f"workflow-web-resume-{decision}")

    paused = asyncio.run(
        graph.ainvoke(
            {"message": "需要人工确认后再继续", "requires_confirmation": True},
            config,
        )
    )
    interrupt_id = paused["__interrupt__"][0].id
    completed = asyncio.run(
        graph.ainvoke(
            Command(
                resume={
                    interrupt_id: {
                        "decisions": [{"type": decision}],
                        "_runtime_model_ref": "opaque-reference",
                    }
                }
            ),
            config,
        )
    )

    assert completed["confirmation"] == decision
    assert completed["response"] == "model response"
    assert completed["_runtime_model_ref"] == "opaque-reference"


def test_workflow_demo_chat_phrase_enters_hitl() -> None:
    graph = _graph()
    config = {"configurable": {"thread_id": "browser-hitl"}}

    paused = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "需要人工确认后再继续"}]},
            config,
        )
    )

    assert paused["__interrupt__"][0].value["kind"] == "workflow_confirmation"


def test_workflow_demo_rejects_invalid_resume_without_completing_run() -> None:
    graph = _graph()
    config = {"configurable": {"thread_id": "workflow-invalid-resume-test"}}
    asyncio.run(
        graph.ainvoke(
            {"message": "hello", "requires_confirmation": True},
            config,
        )
    )

    invalid = asyncio.run(
        graph.ainvoke(Command(resume={"missing-interrupt-id": "approve"}), config)
    )
    assert invalid["__interrupt__"][0].value["error"] == "workflow.invalid_resume"

    interrupt_id = invalid["__interrupt__"][0].id
    completed = asyncio.run(
        graph.ainvoke(Command(resume={interrupt_id: "reject"}), config)
    )
    assert completed["response"] == "model response"
