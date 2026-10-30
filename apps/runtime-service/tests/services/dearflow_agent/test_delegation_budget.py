"""Real child graphs share admission reservations and the native Run ledger."""

import asyncio
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel

from runtime_service.db.repositories import usage as repository
from runtime_service.observability import usage
from runtime_service.runtime import runtime_context_hash
from runtime_service.services.dearflow_agent import agent

from .test_agent import config


def test_parent_and_three_children_share_inflight_token_budget(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", "100")
    writes = []
    for name in ("begin_collection", "upsert_call", "finish_collection"):
        monkeypatch.setattr(repository, name, lambda *args: writes.append(args))
    monkeypatch.setattr(
        repository,
        "read_budget",
        lambda identity: {
            "policy": {"version": 1, "max_tokens": 100, "warn_at_tokens": 80},
            "used_tokens": 0,
            "unverifiable": False,
            "stop_code": None,
            "calls": [],
        },
    )
    # Fixed tokenizer and provider usage make the race deterministic.
    monkeypatch.setattr(
        usage,
        "_estimate_input_tokens",
        lambda messages, tools, response_format=None: 29,
    )

    async def run():
        started = []
        collectors = []
        barrier = asyncio.Event()

        class Model(BindableFakeMessagesChatModel):
            def _get_invocation_params(self, stop=None, **kwargs):
                return {
                    **super()._get_invocation_params(stop=stop, **kwargs),
                    "max_tokens": 1,
                }

            async def _agenerate(self, messages, **kwargs):
                name = next(m.content for m in messages if isinstance(m, HumanMessage))
                collector = usage.current_runtime_usage_callback()
                assert collector is not None
                collectors.append(collector)
                started.append(name)
                if name == "parent":
                    result = AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "task",
                                "args": {
                                    "description": child,
                                    "subagent_type": "general-purpose",
                                },
                                "id": "dispatch-" + child,
                            }
                            for child in ("alpha", "beta", "gamma")
                        ],
                    )
                    total = 10
                else:
                    if len(started) == 4:
                        barrier.set()
                    await asyncio.wait_for(barrier.wait(), 30)
                    assert (
                        collector.token_budget.used_tokens
                        + collector.token_budget.reserved_tokens
                        <= 100
                    )
                    result = AIMessage(content="Source unavailable")
                    total = 30
                result.usage_metadata = {
                    "input_tokens": total - 1,
                    "output_tokens": 1,
                    "total_tokens": total,
                }
                return ChatResult(generations=[ChatGeneration(message=result)])

        monkeypatch.setattr(agent, "build_model", lambda *a, **kw: Model(responses=[]))
        cfg = config()
        thread = str(uuid4())
        cfg["configurable"]["thread_id"] = thread
        cfg["configurable"]["__graphharbor_run_budget"]["thread_id"] = thread
        cfg["configurable"]["langgraph_auth_user"]["runtime_scope"]["thread_id"] = (
            thread
        )
        cfg["context"] = {"execution_mode": "ultra"}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        result = await graph.ainvoke(
            {"messages": [("user", "parent")]}, cfg, context=cfg["context"]
        )
        assert "Token" in result["messages"][-1].content
        assert started[0] == "parent" and set(started[1:]) == {"alpha", "beta", "gamma"}
        assert len(started) == 4 and len({id(c) for c in collectors}) == 1
        collector = collectors[0]
        assert collector.token_budget.used_tokens == 100
        assert collector.token_budget.reserved_tokens == 0
        assert collector.token_budget.stop_code == "token_budget_exhausted"
        calls = list(collector._calls.values())
        assert len(calls) == 4
        assert sum(c["tokens"]["total_tokens"] for c in calls) == 100
        assert sum(c["scope"] == "primary" for c in calls) == 1
        children = [c for c in calls if c["scope"] == "subagent"]
        assert len(children) == 3
        assert len({tuple(c["namespace"]) for c in children}) == 3
        assert writes

    asyncio.run(run())
