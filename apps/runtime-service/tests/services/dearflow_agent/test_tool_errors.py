"""Real composition roots must distinguish recoverable errors from Run failures."""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import ToolException
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import Field
from support import BindableFakeMessagesChatModel

from runtime_service.runtime import (
    RuntimeAuthError,
    RuntimeResolutionError,
    runtime_context_hash,
)
from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.services.dearflow_agent import agent
from runtime_service.services.dearflow_agent.tools import search
from runtime_service.services.dearflow_agent.workspace.backend import (
    DearWorkspaceBackend,
)

from .test_agent import call, config


class RecordingModel(BindableFakeMessagesChatModel):
    seen: list = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture
def build(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")

    async def create(responses, cfg=None):
        cfg = cfg or config()
        model = RecordingModel(responses=responses)
        monkeypatch.setattr(agent, "build_model", lambda *a, **kw: model)
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        return graph, cfg, model

    return create


def error_messages(model):
    return [
        m
        for messages in model.seen
        for m in messages
        if isinstance(m, ToolMessage) and m.status == "error"
    ]


def test_main_model_consumes_safe_native_error(build):
    async def run():
        graph, cfg, model = await build(
            [
                call("search_web", {"query": ""}),
                AIMessage(content="alternative answer"),
            ]
        )
        result = await graph.ainvoke(
            {"messages": [("user", "research")]}, cfg, context={}
        )
        message = error_messages(model)[0]
        payload = json.loads(message.content)
        assert payload["code"] == "tool.invalid_input"
        assert payload["outcome"] == "not_started"
        assert message.name == payload["name"] == "search_web"
        assert message.tool_call_id == "tool-1"
        assert result["messages"][-1].content == "alternative answer"

    asyncio.run(run())


@pytest.mark.parametrize(
    "error",
    [
        ToolException("UNRECOGNIZED_CANARY"),
        RuntimeAuthError("runtime.auth.test_denied"),
        RuntimeError("PROGRAM_CANARY"),
    ],
)
def test_unclassified_or_security_error_stops_main_model(build, monkeypatch, error):
    async def provider(*args):
        raise error

    monkeypatch.setattr(search, "tavily", provider)

    async def run():
        graph, cfg, model = await build(
            [
                call("search_web", {"query": "valid"}),
                AIMessage(content="must not continue"),
            ]
        )
        with pytest.raises(type(error)):
            await graph.ainvoke({"messages": [("user", "research")]}, cfg, context={})
        assert len(model.seen) == 1

    asyncio.run(run())


@pytest.mark.parametrize("provider", [search.tavily, search.jina_extract])
@pytest.mark.parametrize(
    "error", [RuntimeAuthError("denied"), ValueError("unknown_defect")]
)
def test_provider_http_boundary_does_not_reclassify_security_or_defects(
    monkeypatch, provider, error
):
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")

    def fail(**kwargs):
        raise error

    monkeypatch.setattr(search.httpx, "AsyncClient", fail)
    args = (
        ("search", {"query": "valid"})
        if provider is search.tavily
        else ("https://example.com",)
    )
    with pytest.raises(type(error)) as caught:
        asyncio.run(provider(*args))
    assert caught.value is error


def test_researcher_consumes_its_own_error_then_returns_to_parent(build):
    async def run():
        cfg = config()
        cfg["context"] = {"execution_mode": "ultra"}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph, cfg, model = await build(
            [
                call(
                    "task",
                    {"subagent_type": "general-purpose", "description": "research"},
                ),
                call("search_web", {"query": ""}, "child-error"),
                AIMessage(content="child alternative"),
                AIMessage(content="parent answer"),
            ],
            cfg,
        )
        result = await graph.ainvoke(
            {"messages": [("user", "delegate")]}, cfg, context=cfg["context"]
        )
        message = error_messages(model)[0]
        assert json.loads(message.content)["code"] == "tool.invalid_input"
        assert message.tool_call_id == "child-error"
        parent_tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert [m.name for m in parent_tools] == ["task"]
        assert "child alternative" in parent_tools[0].content
        assert result["messages"][-1].content == "parent answer"

    asyncio.run(run())


@pytest.mark.parametrize("approval", [False, True])
def test_parallel_success_and_error_are_paired_and_consumed_once(
    build, monkeypatch, approval
):
    calls = []

    async def provider(*args):
        calls.append(args[1]["query"])
        return {"results": []}

    monkeypatch.setattr(search, "tavily", provider)

    async def run():
        response = call("search_web", {"query": ""}, "error")
        response.tool_calls += call(
            "search_web", {"query": "valid"}, "success"
        ).tool_calls
        if approval:
            response.tool_calls += call(
                "write_file",
                {"file_path": "/workspace/work/parallel.txt", "content": "once"},
                "approval",
            ).tool_calls
        graph, cfg, model = await build([response, AIMessage(content="continued")])
        result = await graph.ainvoke(
            {"messages": [("user", "parallel")]}, cfg, context={}
        )
        if approval:
            pending = result["__interrupt__"][0]
            assert pending.value["action_requests"][0]["name"] == "write_file"
            target = DearWorkspaceBackend("tenant", "project", "dear-thread").root
            assert calls == [] and not (target / "work/parallel.txt").exists()
            assert not error_messages(model)
            result = await graph.ainvoke(
                Command(resume={pending.id: {"decisions": [{"type": "approve"}]}}),
                cfg,
                context={},
            )
            assert (target / "work/parallel.txt").read_text() == "once"
        messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        expected = [
            ("error", "error"),
            ("success", "success"),
        ]
        if approval:
            expected.insert(0, ("approval", "success"))
        assert sorted((m.tool_call_id, m.status) for m in messages) == expected
        assert calls == ["valid"]
        assert len(error_messages(model)) == 1
        assert result["messages"][-1].content == "continued"

    asyncio.run(run())


@pytest.mark.parametrize(
    "error",
    [
        ToolException("unknown"),
        RuntimeAuthError("runtime.auth.denied"),
        RuntimeWorkspaceError("runtime.workspace.unavailable"),
    ],
)
def test_child_fatal_error_is_not_swallowed_by_parent_task(build, monkeypatch, error):
    async def provider(*args):
        raise error

    monkeypatch.setattr(search, "tavily", provider)

    async def run():
        cfg = config()
        cfg["context"] = {"execution_mode": "ultra"}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph, cfg, model = await build(
            [
                call(
                    "task",
                    {"subagent_type": "general-purpose", "description": "research"},
                ),
                call("search_web", {"query": "valid"}),
                AIMessage(content="must not continue"),
            ],
            cfg,
        )
        with pytest.raises(type(error)):
            await graph.ainvoke(
                {"messages": [("user", "delegate")]}, cfg, context=cfg["context"]
            )
        assert len(model.seen) == 2

    asyncio.run(run())


def test_tool_policy_rejects_before_any_provider_call(build, monkeypatch):
    calls = []

    async def provider(*args):
        calls.append(args)
        raise AssertionError("authorization must run first")

    monkeypatch.setattr(search, "tavily", provider)

    async def run():
        cfg = config()
        cfg["configurable"]["langgraph_auth_user"]["runtime_policy"][
            "tool_overrides"
        ] = {"search_web": False}
        graph, cfg, model = await build([call("search_web", {"query": "valid"})], cfg)
        with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
            await graph.ainvoke({"messages": [("user", "denied")]}, cfg, context={})
        assert calls == []
        assert len(model.seen) == 1

    asyncio.run(run())


def test_repeated_recoverable_errors_still_exhaust_existing_child_budget(
    build, monkeypatch
):
    from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError

    monkeypatch.setenv("AGENT_MODEL_CALL_LIMIT_PER_RUN", "2")

    async def run():
        cfg = config()
        cfg["context"] = {"execution_mode": "ultra"}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph, cfg, model = await build(
            [
                call(
                    "task",
                    {"subagent_type": "general-purpose", "description": "research"},
                ),
                call("search_web", {"query": ""}, "first"),
                call("search_web", {"query": ""}, "second"),
            ],
            cfg,
        )
        with pytest.raises(ModelCallLimitExceededError):
            await graph.ainvoke(
                {"messages": [("user", "delegate")]}, cfg, context=cfg["context"]
            )
        assert len(model.seen) == 3

    asyncio.run(run())
