from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import deepagents.graph as deep_graph
import deepagents.middleware.subagents as subagent_graph
import httpx
import openai
import pytest
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import tool
from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import Field
from services.dearflow_agent.test_agent import config as dear_config
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.model_resilience import (
    ModelResilienceMiddleware,
    ModelResilienceSummarizationMiddleware,
)
from runtime_service.runtime import (
    ModelConnectionBundle,
    ModelResiliencePolicy,
    modeling,
)
from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.services.dearflow_agent import agent as dearflow
from runtime_service.services.demo.showcase_demo import agent as showcase
from runtime_service.services.demo.workflow_demo import agent as workflow
from runtime_service.services.reference_agent import agent as reference

A = "00000000-0000-0000-0000-000000000001"
B = "00000000-0000-0000-0000-000000000002"


def outage():
    return openai.APIStatusError(
        "private provider body",
        response=httpx.Response(
            503, request=httpx.Request("POST", "https://secret.invalid")
        ),
        body={},
    )


class ScriptedModel(BindableFakeMessagesChatModel):
    script: list = Field(default_factory=list, exclude=True)
    seen: list = Field(default_factory=list, exclude=True)
    max_retries: int = 2

    def _generate(self, messages, **kwargs):
        self.seen.append(messages)
        result = self.script.pop(0)
        if isinstance(result, Exception):
            raise result
        return ChatResult(generations=[ChatGeneration(message=result)])

    async def _agenerate(self, messages, **kwargs):
        return self._generate(messages, **kwargs)


@tool
def synthetic_chart() -> str:
    """Return a chart without external services."""
    return "chart"


def managed_config(graph_id):
    cfg = dear_config()
    context = {"model_id": A, "temperature": 0.4, "execution_mode": "ultra"}
    cfg["context"] = context
    cfg["configurable"].update(assistant_id=graph_id, graph_id=graph_id)
    user = cfg["configurable"]["langgraph_auth_user"]
    user["runtime_scope"]["assistant_id"] = graph_id
    user["runtime_policy"]["allowed_model_ids"] = [A, B]
    user["runtime_context_hash"] = runtime_context_hash(context)
    return cfg


def install_models(monkeypatch, module, tmp_path, primary_script, backup_script):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dear"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setattr(showcase, "build_chart_tools", lambda *args: [synthetic_chart])
    models = {
        A: ScriptedModel(responses=[], script=primary_script),
        B: ScriptedModel(responses=[], script=backup_script),
    }
    construction = []

    def build(resolved, **kwargs):
        construction.append((resolved.model_id, kwargs.get("max_retries")))
        if "max_retries" not in kwargs or kwargs["max_retries"] is None:
            return ScriptedModel(responses=[], script=[AIMessage("summary")])
        return models[resolved.model_id]

    monkeypatch.setattr(module, "build_model", build)
    monkeypatch.setattr(modeling, "build_model", build)
    bundle = ModelConnectionBundle(
        primary={"model_id": A},
        fallback={"model_id": B},
        policy=ModelResiliencePolicy(enabled=True, fallback_model_id=B),
    )
    monkeypatch.setattr(module, "fetch_model_bundle", AsyncMock(return_value=bundle))
    return models, construction


@pytest.mark.parametrize(
    "module,graph_id",
    [
        (reference, "reference_agent"),
        (dearflow, "dearflow_agent"),
        (showcase, "showcase_demo"),
        (workflow, "workflow_demo"),
    ],
)
def test_managed_policy_runs_through_all_real_composition_roots(
    monkeypatch, tmp_path, module, graph_id
):
    models, construction = install_models(
        monkeypatch, module, tmp_path, [outage()], [AIMessage("backup result")]
    )
    compiled = {}

    def capture(*args, **kwargs):
        compiled[kwargs["name"]] = kwargs["middleware"]
        return create_agent(*args, **kwargs)

    monkeypatch.setattr(deep_graph, "create_agent", capture)
    monkeypatch.setattr(subagent_graph, "create_agent", capture)
    if module in (reference, workflow):
        monkeypatch.setattr(module, "create_agent", capture)

    async def run():
        cfg = managed_config(graph_id)
        graph = await module.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        return await graph.ainvoke(
            {"messages": [HumanMessage("hello")]}, cfg, context=cfg["context"]
        )

    result = asyncio.run(run())
    summary = result["messages"][-1].response_metadata["platform_model_resilience"]
    assert result["messages"][-1].content == "backup result"
    assert summary == {
        "version": 1,
        "requested_model_id": A,
        "effective_model_id": B,
        "attempts": 2,
        "fallback_used": True,
    }
    assert len(models[A].seen) == len(models[B].seen) == 1
    assert (A, 0) in construction and (B, 0) in construction
    if module in (dearflow, showcase):
        assert (A, None) in construction
        expected = (
            {graph_id, "general-purpose"}
            if module is dearflow
            else {graph_id, "research", "general-purpose", "chart-agent"}
        )
        assert set(compiled) == expected
    for middleware in compiled.values():
        names = [item.name for item in middleware]
        resilience = names.index("ModelResilienceMiddleware")
        assert names.index("ModelCallTimeoutMiddleware") > resilience
        if "RuntimeConfigMiddleware" in names:
            assert names.index("RuntimeConfigMiddleware") < resilience
        if module in (dearflow, showcase):
            assert names.count("SummarizationMiddleware") == 1
            assert names.index("SummarizationMiddleware") < resilience
            summary_middleware = next(
                item for item in middleware if item.name == "SummarizationMiddleware"
            )
            assert isinstance(
                summary_middleware, ModelResilienceSummarizationMiddleware
            )


@pytest.mark.parametrize(
    "module,graph_id,role",
    [
        (dearflow, "dearflow_agent", "general-purpose"),
        (showcase, "showcase_demo", "research"),
        (showcase, "showcase_demo", "general-purpose"),
        (showcase, "showcase_demo", "chart-agent"),
    ],
)
def test_each_actual_child_uses_policy_and_keeps_namespace(
    monkeypatch, tmp_path, module, graph_id, role
):
    dispatch = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "task",
                "args": {"description": "research", "subagent_type": role},
                "id": "dispatch",
            }
        ],
    )
    models, _ = install_models(
        monkeypatch,
        module,
        tmp_path,
        [dispatch, outage(), AIMessage("parent done")],
        [AIMessage("child done")],
    )

    async def run():
        cfg = managed_config(graph_id)
        graph = await module.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        events = []
        async for event in graph.astream(
            {"messages": [HumanMessage("parent question")]},
            cfg,
            context=cfg["context"],
            stream_mode="updates",
            subgraphs=True,
        ):
            events.append(event)
        return events, (await graph.aget_state(cfg)).values

    events, state = asyncio.run(run())
    assert len(models[A].seen) == 3 and len(models[B].seen) == 1
    assert state["messages"][-1].content == "parent done"
    children = [
        message
        for namespace, update in events
        if namespace
        for value in update.values()
        if isinstance(value, dict)
        for message in value.get("messages", [])
        if isinstance(message, AIMessage) and message.content == "child done"
    ]
    assert len(children) == 1
    assert children[0].response_metadata["platform_model_resilience"]["attempts"] == 2
    assert "parent question" not in str(models[B].seen)


@pytest.mark.skipif(
    os.getenv("RUN_MODEL_RESILIENCE_GRAPH_WORKER") != "1",
    reason="requires isolated GraphHarbor PostgreSQL/Redis",
)
@pytest.mark.parametrize("phase", ["provider", "backoff", "cooldown"])
@pytest.mark.parametrize(
    "module,graph_id,role",
    [
        (dearflow, "dearflow_agent", "general-purpose"),
        (showcase, "showcase_demo", "research"),
        (showcase, "showcase_demo", "general-purpose"),
    ],
)
def test_worker_cancel_stops_actual_child_and_candidate_waits(
    monkeypatch, tmp_path, phase, module, graph_id, role
):
    import langchain.agents.middleware.model_retry as retry_module
    from httpx import ASGITransport, AsyncClient
    from langgraph_runtime_pg.auth import sign_runtime_context
    from langgraph_runtime_pg.checkpoint import get_checkpointer, teardown_checkpointer
    from langgraph_runtime_pg.database import (
        connect,
        start_pool,
        stop_pool,
        truncate_all,
    )
    from langgraph_runtime_pg.models import RunRow
    from langgraph_runtime_pg.production_worker import ProductionWorker
    from langgraph_runtime_pg.run_store import stopped_event
    from langhost.server import create_app

    from runtime_service.middlewares import model_resilience

    assert "graphharbor_" in os.environ["DATABASE_URI"]
    assert os.environ["GRAPHHARBOR_REDIS_PREFIX"].startswith("graphharbor:cancel:")
    monkeypatch.delenv("LG_BG_JOB_HEARTBEAT", raising=False)
    monkeypatch.setenv("GRAPHHARBOR_ENV", "development")
    monkeypatch.setenv(
        "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET", "isolated-child-context-secret-32-bytes"
    )
    dispatch = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "task",
                "args": {"description": "research", "subagent_type": role},
                "id": "cancel-child",
            }
        ],
    )
    failure = outage()
    if phase == "cooldown":
        failure.response.headers["retry-after"] = "100"
    models, _ = install_models(
        monkeypatch, module, tmp_path, [dispatch, failure], [outage()]
    )

    async def run():
        await start_pool()
        from runtime_service.db import upgrade

        await asyncio.to_thread(upgrade, os.environ["POSTGRES_URI"])
        await truncate_all()
        entered, cleaning, release, exited = (asyncio.Event() for _ in range(4))

        async def block(*args):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
                exited.set()

        original_generate = ScriptedModel._agenerate

        async def generate(self, messages, **kwargs):
            # Middleware copies the model, keeping its script and call log shared.
            if (
                phase == "provider"
                and self.seen is models[A].seen
                and len(self.seen) == 1
            ):
                self.seen.append(messages)
                return await block()
            return await original_generate(self, messages, **kwargs)

        monkeypatch.setattr(ScriptedModel, "_agenerate", generate)
        if phase == "backoff":
            monkeypatch.setattr(retry_module, "asyncio", SimpleNamespace(sleep=block))
        if phase == "cooldown":
            monkeypatch.setattr(retry_module, "calculate_delay", lambda *a, **k: 0)
            monkeypatch.setattr(
                model_resilience,
                "asyncio",
                SimpleNamespace(sleep=block, timeout=asyncio.timeout),
            )

        @asynccontextmanager
        async def open_graph(_, cfg):
            managed = managed_config(graph_id)
            managed["configurable"]["langgraph_auth_user"]["runtime_scope"][
                "thread_id"
            ] = cfg["configurable"]["thread_id"]
            cfg["configurable"].update(
                {
                    key: value
                    for key, value in managed["configurable"].items()
                    if key != "thread_id"
                }
            )
            cfg["context"] = managed["context"]
            graph = await module.get_agent(cfg)
            graph.checkpointer = get_checkpointer()
            yield graph

        worker = ProductionWorker(
            SimpleNamespace(open=open_graph), owner="actual-child"
        )
        task = None
        try:
            async with AsyncClient(
                transport=ASGITransport(app=create_app({"graphs": {}})),
                base_url="http://test",
            ) as client:
                assistant = (
                    await client.post("/assistants", json={"graph_id": graph_id})
                ).json()
                thread_id = (await client.post("/threads", json={})).json()["thread_id"]
                root = f"/threads/{thread_id}/runs"
                response = await client.post(
                    root,
                    json={
                        "assistant_id": assistant["assistant_id"],
                        "input": {
                            "messages": [{"type": "human", "content": "research"}]
                        },
                        "context": managed_config(graph_id)["context"],
                    },
                )
                response.raise_for_status()
                run_id = response.json()["run_id"]
                user = dict(
                    managed_config(graph_id)["configurable"]["langgraph_auth_user"]
                )
                user.update(identity="dear-test", is_authenticated=True, permissions=[])
                user["runtime_scope"]["thread_id"] = thread_id
                async with connect() as conn:
                    row = await conn.session.get(RunRow, UUID(run_id))
                    row.kwargs = {
                        **row.kwargs,
                        "runtime_context_token": sign_runtime_context(
                            {"auth_user": user, "permissions": []},
                            run_id=run_id,
                            thread_id=thread_id,
                        ),
                    }
                task = asyncio.create_task(worker.run_once())
                ready = asyncio.create_task(entered.wait())
                done, _ = await asyncio.wait(
                    (ready, task), timeout=15, return_when=asyncio.FIRST_COMPLETED
                )
                if ready not in done:
                    ready.cancel()
                    await asyncio.gather(ready, return_exceptions=True)
                    async with connect() as conn:
                        row = await conn.session.get(RunRow, UUID(run_id))
                        raise AssertionError(
                            (
                                row.status,
                                row.reason,
                                len(models[A].seen),
                                len(models[B].seen),
                            )
                        )
                counts = (len(models[A].seen), len(models[B].seen))
                confirmation = asyncio.create_task(
                    client.post(root + f"/{run_id}/cancel?wait=true")
                )
                await asyncio.wait_for(cleaning.wait(), 5)
                assert not confirmation.done() and not exited.is_set()
                assert (len(models[A].seen), len(models[B].seen)) == counts
                release.set()
                response = await asyncio.wait_for(confirmation, 5)
                assert response.status_code == 200, response.text
                assert await asyncio.wait_for(task, 5)
                assert exited.is_set()
                assert (len(models[A].seen), len(models[B].seen)) == counts
                assert counts == ((2, 0) if phase == "provider" else (2, 1))
                async with connect() as conn:
                    row = await conn.session.get(RunRow, UUID(run_id))
                    assert row.status == "interrupted" and row.lease_owner is None
                    assert (await stopped_event(conn.session, row)).payload[
                        "execution_stopped"
                    ]
                (tmp_path / "child-cancel-evidence.json").write_text(
                    json.dumps(
                        {
                            "graph_id": graph_id,
                            "role": role,
                            "phase": phase,
                            "candidate_calls_before_cancel": counts,
                            "candidate_calls_after_confirmation": (
                                len(models[A].seen),
                                len(models[B].seen),
                            ),
                            "wait_blocked_before_child_cleanup": True,
                            "child_cleanup_completed": exited.is_set(),
                            "terminal_execution_stopped": True,
                            "worker_lease_released": True,
                        },
                        indent=2,
                    )
                    + "\n"
                )
        finally:
            release.set()
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await teardown_checkpointer()
            await stop_pool()

    asyncio.run(run())


def test_dearflow_child_cannot_gain_write_or_execute_tools(monkeypatch, tmp_path):
    dispatch = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "task",
                "args": {"description": "research", "subagent_type": "general-purpose"},
                "id": "dispatch",
            }
        ],
    )
    illegal = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "write_file",
                "args": {"file_path": "/workspace/work/illegal.txt", "content": "bad"},
                "id": "illegal",
            }
        ],
    )
    models, _ = install_models(
        monkeypatch, dearflow, tmp_path, [dispatch, outage()], [illegal]
    )

    async def run():
        cfg = managed_config("dearflow_agent")
        graph = await dearflow.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
            await graph.ainvoke(
                {"messages": [HumanMessage("research")]}, cfg, context=cfg["context"]
            )

    asyncio.run(run())
    assert not list(tmp_path.rglob("illegal.txt"))
    assert len(models[B].seen) == 1


@pytest.mark.parametrize("recovered", [True, False])
def test_native_context_overflow_recovers_before_final_normalization(recovered):
    primary = ScriptedModel(
        responses=[],
        script=[
            ContextOverflowError("private overflow"),
            AIMessage("recovered")
            if recovered
            else ContextOverflowError("private overflow"),
        ],
    )
    auxiliary = ScriptedModel(
        responses=[], script=[AIMessage("compressed conversation")]
    )
    backup = ScriptedModel(responses=[], script=[AIMessage("must not run")])
    backend = StateBackend()
    graph = create_deep_agent(
        model=primary,
        backend=backend,
        checkpointer=InMemorySaver(),
        middleware=[
            ModelResilienceSummarizationMiddleware(auxiliary, backend),
            ModelResilienceMiddleware(
                ModelResiliencePolicy(enabled=True, fallback_model_id=B),
                backup,
                primary_model_id=A,
                context_recovery=True,
            ),
        ],
    )
    history = [
        message
        for i in range(20)
        for message in (HumanMessage(f"question {i}"), AIMessage(f"answer {i}"))
    ]

    async def run():
        cfg = {"configurable": {"thread_id": "overflow"}}
        if recovered:
            result = await graph.ainvoke({"messages": history}, cfg)
            assert result["messages"][-1].content == "recovered"
            assert (
                result["messages"][-1].response_metadata["platform_model_resilience"][
                    "attempts"
                ]
                == 1
            )
            state = await graph.aget_state(cfg)
            assert (
                state.values["_summarization_event"]["file_path"]
                in state.values["files"]
            )
        else:
            with pytest.raises(RuntimeResolutionError) as error:
                await graph.ainvoke({"messages": history}, cfg)
            assert error.value.code == "runtime.model.provider_rejected"
            assert error.value.__context__ is None

    asyncio.run(run())
    assert len(primary.seen) == 2 and len(auxiliary.seen) == 1
    assert not backup.seen


def test_approved_tool_is_not_replayed_by_a_later_model_fallback():
    executions = []

    @tool
    def approved_action(value: str) -> str:
        """Record an explicitly approved fixture action."""
        executions.append(value)
        return value

    primary = ScriptedModel(
        responses=[],
        script=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "approved-once",
                        "name": "approved_action",
                        "args": {"value": "fixture"},
                    }
                ],
            ),
            outage(),
        ],
    )
    backup = ScriptedModel(responses=[], script=[AIMessage("done")])
    graph = create_agent(
        primary,
        tools=[approved_action],
        middleware=[
            HumanInTheLoopMiddleware(interrupt_on={"approved_action": True}),
            ModelResilienceMiddleware(
                ModelResiliencePolicy(enabled=True, fallback_model_id=B),
                backup,
                primary_model_id=A,
            ),
        ],
        checkpointer=InMemorySaver(),
    )

    async def run():
        cfg = {"configurable": {"thread_id": "approved-action"}}
        interrupted = await graph.ainvoke({"messages": [HumanMessage("act")]}, cfg)
        assert interrupted["__interrupt__"] and not executions
        result = await graph.ainvoke(
            Command(resume={"decisions": [{"type": "approve"}]}), cfg
        )
        assert result["messages"][-1].content == "done"
        assert (
            result["messages"][-1].response_metadata["platform_model_resilience"][
                "attempts"
            ]
            == 2
        )
        assert sum(message.type == "tool" for message in result["messages"]) == 1

    asyncio.run(run())
    assert executions == ["fixture"]
    assert len(primary.seen) == 2 and len(backup.seen) == 1
