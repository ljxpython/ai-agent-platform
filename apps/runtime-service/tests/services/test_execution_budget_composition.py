from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares import (
    ExecutionBudgetMiddleware,
    LoopDetectionMiddleware,
    TimeoutWrapupMiddleware,
)


@pytest.mark.parametrize("service", ["dearflow", "showcase"])
def test_deep_agent_primary_and_children_explicitly_compose_budget(
    monkeypatch, tmp_path, service
):
    if service == "dearflow":
        from services.dearflow_agent.test_agent import config

        from runtime_service.services.dearflow_agent import agent
    else:
        from services.showcase_demo.test_agent import config

        from runtime_service.services.demo.showcase_demo import agent
    monkeypatch.setenv("RUNTIME_BACKEND", "local")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setenv("AGENT_WRAPUP_AFTER_SECONDS", "600")
    monkeypatch.setenv("AGENT_LOOP_DETECTION_ENABLED", "1")
    monkeypatch.setattr(
        agent,
        "build_model",
        lambda *args, **kwargs: BindableFakeMessagesChatModel(
            responses=[AIMessage(content="done")]
        ),
    )
    captured = {}
    real = agent.create_deep_agent

    def capture(**kwargs):
        captured.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(agent, "create_deep_agent", capture)
    graph = asyncio.run(agent.get_agent(config()))
    assert graph is not None
    primary = captured["middleware"]
    budget = next(
        item for item in primary if isinstance(item, ExecutionBudgetMiddleware)
    )
    assert budget.scope == "primary" and budget.exit_behavior == "error"
    assert any(isinstance(item, TimeoutWrapupMiddleware) for item in primary)
    detector = next(
        item for item in primary if isinstance(item, LoopDetectionMiddleware)
    )
    assert detector.scope == "primary" and detector.observed_tools <= {
        "ls",
        "read_file",
        "glob",
        "grep",
    }
    assert primary.index(detector) > primary.index(budget)
    for child in captured["subagents"]:
        child_budget = next(
            item
            for item in child["middleware"]
            if isinstance(item, ExecutionBudgetMiddleware)
        )
        assert (
            child_budget.scope == "subagent" and child_budget.exit_behavior == "error"
        )
        assert not any(
            isinstance(item, TimeoutWrapupMiddleware) for item in child["middleware"]
        )
        assert (
            next(
                item
                for item in child["middleware"]
                if isinstance(item, LoopDetectionMiddleware)
            ).scope
            == "subagent"
        )
    assert "runtime_budget_latches" not in graph.get_input_jsonschema()["properties"]
    assert "runtime_loop_state" not in graph.get_input_jsonschema()["properties"]


def test_workflow_inner_primary_notifications_reach_root_stream():
    from runtime_service.services.demo.workflow_demo import agent

    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_reference",
                        "args": {"topic": "budget"},
                        "id": "loop-1",
                    }
                ],
            )
        ]
    )

    async def run():
        graph = await agent.get_agent({"configurable": {"_runtime_model": model}})
        events = [
            event
            async for event in graph.astream(
                {"messages": [("user", "loop")]},
                {
                    "recursion_limit": 150,
                    "configurable": {"thread_id": "workflow-budget"},
                    "metadata": {"run_id": "run-workflow"},
                },
                stream_mode=["custom", "values"],
                subgraphs=True,
            )
        ]
        notices = [
            (namespace, value)
            for namespace, channel, value in events
            if channel == "custom" and value.get("type") == "runtime_budget_notice"
        ]
        assert [value["code"] for _, value in notices] == [
            "model_call_limit_approaching",
            "model_call_limit_reached",
        ]
        assert all(
            namespace == () and value["scope"] == "primary"
            for namespace, value in notices
        )
        assert all(value["run_id"] == "run-workflow" for _, value in notices)
        last = [
            value
            for namespace, channel, value in events
            if namespace == () and channel == "values"
        ][-1]
        assert (
            last["messages"][-1].additional_kwargs["runtime_budget_notice"]["code"]
            == "model_call_limit_reached"
        )

    asyncio.run(run())


@pytest.mark.parametrize("one_finishes", [False, True])
def test_parallel_subgraphs_have_distinct_notices_and_parent_finishes(one_finishes):
    from deepagents import create_deep_agent
    from langchain_core.outputs import ChatGeneration, ChatResult
    from middlewares.test_execution_budget import echo, loop_model

    class ChildModel(BindableFakeMessagesChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            if one_finishes and any(
                message.type == "human" and "second" in str(message.content)
                for message in messages
            ):
                return ChatResult(
                    generations=[
                        ChatGeneration(message=AIMessage(content="child completed"))
                    ]
                )
            return super()._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )

    child = create_deep_agent(
        model=ChildModel(responses=loop_model().responses),
        tools=[echo],
        middleware=[
            ExecutionBudgetMiddleware(
                run_limit=2, scope="subagent", exit_behavior="end"
            )
        ],
    )
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {
                            "description": "first",
                            "subagent_type": "budget-child",
                        },
                        "id": "child-1",
                    },
                    {
                        "name": "task",
                        "args": {
                            "description": "second",
                            "subagent_type": "budget-child",
                        },
                        "id": "child-2",
                    },
                ],
            ),
            AIMessage(content="parent finished"),
        ]
    )
    parent = create_deep_agent(
        model=model,
        subagents=[
            {
                "name": "budget-child",
                "description": "A bounded test task",
                "runnable": child,
            }
        ],
        middleware=[ExecutionBudgetMiddleware(run_limit=5, warning_calls=0)],
        checkpointer=InMemorySaver(),
    )

    async def run():
        events = [
            event
            async for event in parent.astream(
                {"messages": [("user", "two tasks")]},
                {
                    "recursion_limit": 100,
                    "configurable": {"thread_id": "parallel-budget"},
                    "metadata": {"run_id": "run-parallel"},
                },
                stream_mode=["custom", "values"],
                subgraphs=True,
            )
        ]
        notices = [
            (ns, data)
            for ns, mode, data in events
            if mode == "custom" and data.get("type") == "runtime_budget_notice"
        ]
        reached = [
            (ns, data)
            for ns, data in notices
            if data["code"] == "model_call_limit_reached"
        ]
        assert len(reached) == (1 if one_finishes else 2)
        assert len({data["notice_id"] for _, data in notices}) == len(notices)
        assert len({ns for ns, _ in notices}) == 2
        assert all(data["scope"] == "subagent" for _, data in reached)
        root_values = [
            data for ns, mode, data in events if ns == () and mode == "values"
        ][-1]
        assert root_values["messages"][-1].content == "parent finished"

    asyncio.run(run())
