import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from runtime_service.errors import RuntimeAuthError
from runtime_service.graphs.evaluation_assistant import get_agent
from runtime_service.runtime.capabilities import graph_tools, tool_catalog
from runtime_service.services.evaluation_assistant.tools import calculate, make_tools
from runtime_service.services.evaluation_assistant.workflow import build_graph


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("120+80+100-20-150", "130"),
        ("120+100-20-150", "50"),
        ("120+100-20", "200"),
        ("0.1+0.2", "0.3"),
        ("(31+24)/5", "11"),
    ],
)
def test_exact_business_calculation(expression, expected):
    assert calculate(expression) == expected


@pytest.mark.parametrize(
    "expression",
    ["__import__('os').system('ls')", "2**10000", "1/0", "[1]*10000", "1e99"],
)
def test_arithmetic_cannot_execute_or_allocate_unbounded(expression):
    with pytest.raises(ValueError):
        calculate(expression)


def test_probe_is_side_effect_free_and_not_executable():
    async def scenario():
        graph = await get_agent({"configurable": {"graph_id": "evaluation_assistant"}})
        assert set(graph.get_input_jsonschema()["properties"]) == {
            "work_item_id",
            "job_id",
        }
        assert graph.checkpointer is None
        with pytest.raises(RuntimeAuthError):
            await graph.ainvoke({"work_item_id": str(uuid4()), "job_id": str(uuid4())})

    asyncio.run(scenario())


def test_tools_recheck_access_and_do_not_expose_other_evidence():
    async def scenario():
        read = AsyncMock(return_value={"evidence": {"case:C01": {"result": "55"}}})
        tools = {t.name: t for t in make_tools(read)}
        assert set(tools) == set(graph_tools("evaluation_assistant"))
        assert "未找到" in await tools["read_evidence"].ainvoke(
            {"reference": "other-project/secret"}
        )
        read.side_effect = RuntimeAuthError("evaluation.material_unavailable")
        with pytest.raises(RuntimeAuthError):
            await tools["decimal_calculate"].ainvoke({"expression": "31+24"})
        registered = {
            t["name"]
            for t in tool_catalog()["tools"]
            if "evaluation_assistant" in t["graph_ids"]
        }
        assert registered == set(tools)

    asyncio.run(scenario())


def test_valid_proposal_finishes_run_and_saves_once():
    async def scenario():
        calls = []

        async def read(state, **kwargs):
            operation = kwargs.get("operation", "read")
            calls.append(operation)
            return (
                {"valid": True}
                if operation == "validate"
                else {"description": "合成算式31+24"}
            )

        model = AsyncMock(
            return_value=SimpleNamespace(
                ainvoke=AsyncMock(
                    return_value={"messages": [AIMessage(content='{"summary":"55"}')]}
                )
            )
        )
        graph = build_graph(model, read_current=read)
        result = await graph.ainvoke(
            {"work_item_id": str(uuid4()), "job_id": str(uuid4())}
        )
        assert result["proposal"] == {"summary": "55"}
        assert calls.count("complete") == 1
        assert model.await_count == 1

    asyncio.run(scenario())


def test_one_repair_only_and_revocation_discards_result():
    async def scenario():
        async def read(state, **kwargs):
            return (
                {"valid": False, "reason": "invalid"}
                if kwargs.get("operation") == "validate"
                else {}
            )

        model = AsyncMock(
            return_value=SimpleNamespace(
                ainvoke=AsyncMock(return_value={"messages": [AIMessage(content="{}")]})
            )
        )
        graph = build_graph(model, read_current=read)
        with pytest.raises(ValueError, match="一次修复"):
            await graph.ainvoke({"work_item_id": str(uuid4()), "job_id": str(uuid4())})
        assert model.await_count == 2
        attempts = 0

        async def revoked(state, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts > 2:
                raise RuntimeAuthError("evaluation.material_unavailable")
            return {}

        graph = build_graph(model, read_current=revoked)
        with pytest.raises(RuntimeAuthError):
            await graph.ainvoke({"work_item_id": str(uuid4()), "job_id": str(uuid4())})

    asyncio.run(scenario())
