import asyncio
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import ToolException, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from support import BindableFakeMessagesChatModel

from runtime_service.runtime.capabilities import graph_capabilities, graph_tools
from runtime_service.services.platform_assistant.agent import get_agent
from runtime_service.services.platform_assistant.approval import create_platform_agent
from runtime_service.services.platform_assistant.tools import (
    PlatformSQLDatabase,
    make_tools,
    validate_public_query,
)


def test_probe_has_real_tools_without_database_or_model_network(monkeypatch):
    monkeypatch.delenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", raising=False)
    agent = asyncio.run(get_agent({"configurable": {"graph_id": "platform_assistant"}}))
    assert agent.name == "platform_assistant"
    from langgraph.channels import DeltaChannel

    assert isinstance(agent.channels["messages"], DeltaChannel)
    assert agent.channels["messages"].snapshot_frequency == 50
    assert set(graph_tools("platform_assistant")) == {t.name for t in make_tools(None)}
    caps = graph_capabilities("platform_assistant")
    assert not any(
        caps[key] for key in ("workspace", "files", "terminal", "memory", "plan_mode")
    )


def test_sql_toolkit_adapter_keeps_execution_at_platform():
    calls = []

    def read(operation, **kwargs):
        calls.append((operation, kwargs))
        return {"evidence_id": "e1", "data": {"tables": ["runs"]}}

    db = PlatformSQLDatabase(read, "business")
    assert db.get_usable_table_names() == ["runs"]
    assert "e1" in db.run_no_throw("select count(*) from runs")
    assert calls[-1] == (
        "sql_query",
        {"database_id": "business", "query": "select count(*) from runs"},
    )
    db.get_table_info_no_throw(["runs"])
    assert calls[-1] == (
        "sql_schema",
        {"database_id": "business", "table_names": ["runs"], "table_offset": 0},
    )


@pytest.mark.parametrize(
    "decision,executions", [("approve", 1), ("reject", 0), ("edit", 0)]
)
def test_native_write_approval_waits_and_resumes_original_action(decision, executions):
    written = []

    @tool
    def test_write(value: str) -> str:
        """Test-only business mutation, never registered in production."""
        written.append(value)
        return "saved"

    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "test_write",
                        "args": {"value": "approved-value"},
                        "id": "write-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="完成"),
        ]
    )
    # Unit tests use memory only; deployed graph delegates persistence to GraphHarbor.
    agent = create_platform_agent(
        model,
        tools=[],
        business_write_tools=[test_write],
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": str(uuid4())}}
    result = agent.invoke(
        {"messages": [HumanMessage(content="执行测试")]},
        config,
        context={"access_policy": "full_access"},
    )
    assert not written
    interrupt = result["__interrupt__"][0]
    assert interrupt.value["review_configs"][0]["allowed_decisions"] == [
        "approve",
        "reject",
    ]
    assert interrupt.value["action_requests"][0]["args"] == {"value": "approved-value"}
    response = {
        "type": decision,
        **({"message": "用户选择不执行"} if decision == "reject" else {}),
    }
    if decision == "edit":
        response["edited_action"] = {
            "name": "test_write",
            "args": {"value": "tampered"},
        }
        with pytest.raises(ValueError):
            agent.invoke(
                Command(resume={interrupt.id: {"decisions": [response]}}), config
            )
        assert not written
        return
    if decision == "approve":
        response["args"] = {"value": "tampered"}
    agent.invoke(Command(resume={interrupt.id: {"decisions": [response]}}), config)
    assert len(written) == executions
    if written:
        assert written == ["approved-value"]
    assert not agent.get_state(config).interrupts


def test_public_search_cannot_invent_keywords_from_private_tool_results():
    validate_public_query("Python 文档", [HumanMessage(content="搜索 Python 文档")])
    for query in (
        "private-data",
        "api_key=secret",
        "123456789",
        "https://internal.example",
    ):
        with pytest.raises(ToolException):
            validate_public_query(
                query,
                [HumanMessage(content="搜索 Python 文档"), AIMessage(content=query)],
            )


@pytest.mark.parametrize("asynchronous", [False, True])
def test_authorization_refreshes_catalog_without_mutating_request(
    monkeypatch, asynchronous
):
    from langchain.agents.middleware import ModelRequest
    from langchain_core.messages import SystemMessage

    from runtime_service.services.platform_assistant import agent as module

    versions = iter(["旧目录", "新目录"])
    statuses = iter(["not_checked", "denied"])
    calls = []

    def read(*args, **kwargs):
        calls.append(args[1])
        return {
            "data": {
                "authorized": True,
                "document_status": "available",
                "document_catalog": [{"document_id": "chat", "title": next(versions)}],
                "capabilities": {
                    "logs": {"availability": next(statuses)},
                    "shell": False,
                },
            }
        }

    monkeypatch.setattr(module, "platform_read", read)
    middleware = module.CurrentAuthorization(None)
    request = ModelRequest(
        model=BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")]),
        messages=[],
        system_message=SystemMessage(content="原规则"),
    )
    seen = []

    def handler(req):
        seen.append(req.system_message.text)
        return "ok"

    async def ahandler(req):
        return handler(req)

    for _ in range(2):
        if asynchronous:
            assert asyncio.run(middleware.awrap_model_call(request, ahandler)) == "ok"
        else:
            assert middleware.wrap_model_call(request, handler) == "ok"
    assert "旧目录" in seen[0] and "新目录" in seen[1] and "旧目录" not in seen[1]
    assert "not_checked" in seen[0] and "denied" in seen[1]
    assert '"availability": "not_checked"' not in seen[1]
    assert request.system_message.text == "原规则"
    assert calls == ["authorize", "authorize"]

    def denied(*args, **kwargs):
        raise ToolException("assistant_project_denied")

    monkeypatch.setattr(module, "platform_read", denied)
    with pytest.raises(ToolException):
        if asynchronous:
            asyncio.run(middleware.awrap_model_call(request, ahandler))
        else:
            middleware.wrap_model_call(request, handler)
    assert len(seen) == 2


def test_document_and_run_log_tools_forward_selected_ids_and_window(monkeypatch):
    import json
    from types import SimpleNamespace

    from runtime_service.services.platform_assistant import tools as module

    calls = []

    def read(facts, operation, **kwargs):
        calls.append((operation, kwargs))
        return {"data": {"ok": True}}

    monkeypatch.setattr(module, "platform_read", read)
    tools = {t.name: t for t in module.make_tools(None)}
    runtime = SimpleNamespace(tool_call_id="test")
    assert json.loads(tools["search_documents"].func(runtime, document_id="chat"))[
        "data"
    ]["ok"]
    assert calls[-1][1]["document_id"] == "chat"
    tools["read_run_logs"].func(
        str(uuid4()),
        str(uuid4()),
        runtime,
        start="2026-01-01T00:00:00Z",
        end="2026-01-01T01:00:00Z",
    )
    assert calls[-1][1]["log_start"] == "2026-01-01T00:00:00Z"


@pytest.mark.parametrize("tool_name", ["read_run_diagnostics", "read_run_logs"])
def test_run_tools_reject_invalid_uuid_with_tool_exception_and_no_crash(
    monkeypatch, tool_name
):
    from types import SimpleNamespace

    from runtime_service.services.platform_assistant import tools as module

    monkeypatch.setattr(module, "platform_read", lambda *a, **k: {"data": {}})
    tools = {t.name: t for t in module.make_tools(None)}
    runtime = SimpleNamespace(tool_call_id="test-invalid-uuid")
    with pytest.raises(ToolException, match="assistant_invalid_"):
        tools[tool_name].func("70f0ab34", str(uuid4()), runtime)
    with pytest.raises(ToolException, match="assistant_invalid_run_id"):
        tools[tool_name].func(str(uuid4()), "bad-run-id", runtime)


def test_agent_graph_handles_invalid_uuid_tool_call_without_crashing():
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_run_diagnostics",
                        "args": {"thread_id": "70f0ab34", "run_id": "70f0ab34"},
                        "id": "diag-invalid-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="需要完整的 36 位 UUID。"),
        ]
    )
    agent = create_platform_agent(
        model,
        tools=make_tools(None),
        checkpointer=InMemorySaver(),
    )
    result = agent.invoke(
        {"messages": [HumanMessage(content="帮我查下 70f0ab34")]},
        {"configurable": {"thread_id": str(uuid4())}},
    )
    tool_msgs = [m for m in result["messages"] if m.type == "tool"]
    assert len(tool_msgs) == 1
    assert "assistant_invalid_thread_id" in tool_msgs[0].content
    assert result["messages"][-1].content == "需要完整的 36 位 UUID。"


def test_thread_lookup_tools_accept_uuid_and_prefix_and_reject_invalid(monkeypatch):
    import json
    from types import SimpleNamespace

    from runtime_service.services.platform_assistant import tools as module

    calls = []

    def read(facts, operation, **kwargs):
        calls.append((operation, kwargs))
        return {"data": {"match_status": "matched", "runs": []}}

    monkeypatch.setattr(module, "platform_read", read)
    tools = {t.name: t for t in module.make_tools(None)}
    runtime = SimpleNamespace(tool_call_id="test-lookup")

    full_tid = str(uuid4())
    for tool_name, expected_op in (
        ("list_thread_runs", "thread_runs"),
        ("read_thread_activity", "thread_activity"),
    ):
        res_full = json.loads(tools[tool_name].func(full_tid, runtime))
        assert res_full["data"]["match_status"] == "matched"
        assert calls[-1] == (
            expected_op,
            {"tool_call_id": "test-lookup", "target_thread_id": full_tid},
        )

        tools[tool_name].func(" 70F0AB34 ", runtime)
        assert calls[-1] == (
            expected_op,
            {"tool_call_id": "test-lookup", "query": "70f0ab34"},
        )

        for bad in ("abc", "70f0ab34;drop", ""):
            with pytest.raises(ToolException, match="assistant_invalid_thread_id"):
                tools[tool_name].func(bad, runtime)


def test_agent_graph_handles_thread_lookup_tool_calls(monkeypatch):
    from runtime_service.services.platform_assistant import tools as module

    monkeypatch.setattr(
        module,
        "platform_read",
        lambda *a, **k: {
            "evidence_id": str(uuid4()),
            "data": {
                "match_status": "matched",
                "thread_id": "70f0ab34-bd4e-439b-b8ce-20a3957557f9",
                "runs": [],
            },
        },
    )
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "list_thread_runs",
                        "args": {"thread_id": "70f0ab34"},
                        "id": "lookup-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_thread_activity",
                        "args": {"thread_id": "bad"},
                        "id": "lookup-2",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="已完成查询。"),
        ]
    )
    agent = create_platform_agent(
        model,
        tools=make_tools(None),
        checkpointer=InMemorySaver(),
    )
    result = agent.invoke(
        {"messages": [HumanMessage(content="帮我查下 70f0ab34")]},
        {"configurable": {"thread_id": str(uuid4())}},
    )
    tool_msgs = [m for m in result["messages"] if m.type == "tool"]
    assert len(tool_msgs) == 2
    assert "70f0ab34-bd4e-439b-b8ce-20a3957557f9" in tool_msgs[0].content
    assert "assistant_invalid_thread_id" in tool_msgs[1].content
    assert result["messages"][-1].content == "已完成查询。"
