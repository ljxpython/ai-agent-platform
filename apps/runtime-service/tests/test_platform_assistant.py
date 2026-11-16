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
