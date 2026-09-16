"""P3: deterministic models through the real Deep Agents graph and callbacks."""
import asyncio

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel

from runtime_service.runtime import runtime_context_hash
from runtime_service.services.dearflow_agent import agent
from runtime_service.services.dearflow_agent.tools import search
from .test_agent import config


@pytest.mark.parametrize("cancel", [False, True])
def test_parallel_children_are_isolated_and_follow_parent_cancel(monkeypatch, tmp_path, cancel):
    async def run():
        entered = set()
        cancelled = set()
        ready = asyncio.Event()
        release = asyncio.Event()
        inputs = {}
        callbacks = {}

        class Recorder(BaseCallbackHandler):
            def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
                callbacks[str(run_id)] = (str(parent_run_id), kwargs.get("metadata", {}))

        class Model(BindableFakeMessagesChatModel):
            async def _agenerate(self, messages, **kwargs):
                human = next(m.content for m in messages if isinstance(m, HumanMessage))
                if human == "parent-private-input":
                    result = AIMessage(content="done") if any(isinstance(m, ToolMessage) for m in messages) else AIMessage(
                        content="", tool_calls=[{"name": "task", "args": {"description": name,
                        "subagent_type": "general-purpose"}, "id": "dispatch-" + name, "type": "tool_call"}
                        for name in ("alpha", "beta")])
                else:
                    inputs[human] = [m.content for m in messages]
                    entered.add(human)
                    if len(entered) == 2:
                        ready.set()
                    try:
                        await release.wait()
                    except asyncio.CancelledError:
                        cancelled.add(human)
                        raise
                    result = AIMessage(content="result-" + human,
                                       usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}) if any(
                                           isinstance(m, ToolMessage) for m in messages) else AIMessage(
                                               content="", tool_calls=[{"name": "search_web", "args": {"query": human},
                                               "id": "same-inner-call", "type": "tool_call"}])
                return ChatResult(generations=[ChatGeneration(message=result)])

        monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
        monkeypatch.setenv("TAVILY_API_KEY", "synthetic")
        async def provider(operation, payload):
            return {"results": [{"url": "https://example.com/" + payload["query"], "content": payload["query"]}]}
        monkeypatch.setattr(search, "tavily", provider)
        monkeypatch.setattr(agent, "build_model", lambda *a, **kw: Model(responses=[]))
        cfg = config()
        cfg["context"] = {"execution_mode": "ultra"}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = runtime_context_hash(cfg["context"])
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        events = []

        async def consume():
            async for part in graph.astream({"messages": [("user", "parent-private-input")]},
                    {**cfg, "callbacks": [Recorder()]}, context=cfg["context"], subgraphs=True, stream_mode="updates"):
                events.append(part)

        execution = asyncio.create_task(consume())
        await asyncio.wait_for(ready.wait(), 30)
        assert entered == {"alpha", "beta"}
        assert all("parent-private-input" not in str(messages) for messages in inputs.values())
        if cancel:
            execution.cancel()
            with pytest.raises(asyncio.CancelledError):
                await execution
            assert cancelled == {"alpha", "beta"}
            state = await graph.aget_state(cfg)
            assert not any(isinstance(m, ToolMessage) and m.tool_call_id.startswith("dispatch-")
                           for m in state.values["messages"])
        else:
            release.set()
            await asyncio.wait_for(execution, 30)
            state = await graph.aget_state(cfg)
            returned = {m.tool_call_id: m.content for m in state.values["messages"] if isinstance(m, ToolMessage)}
            assert returned == {"dispatch-alpha": "result-alpha", "dispatch-beta": "result-beta"}
            scoped = {}
            evidence = []
            for namespace, update in events:
                for value in update.values():
                    if not namespace or not isinstance(value, dict):
                        continue
                    for message in value.get("messages", []):
                        if isinstance(message, ToolMessage) and message.artifact:
                            source = message.artifact["sources"][0]
                            assert source["tool_call_id"] == "same-inner-call"
                            assert source["thread_id"] == "dear-thread"
                            assert source["namespace"]
                            evidence.append(source)
                        if isinstance(message, AIMessage) and message.content in {"result-alpha", "result-beta"}:
                            scoped[message.content] = namespace
                            assert message.usage_metadata["total_tokens"] == 5
            assert len(scoped) == 2 and len(set(scoped.values())) == 2
            assert len(evidence) == 2 and len({source["namespace"] for source in evidence}) == 2
            assert {source["source_url"] for source in evidence} == {"https://example.com/alpha", "https://example.com/beta"}
            assert all("result-" not in m.content for m in state.values["messages"] if isinstance(m, AIMessage))
            # Native v3 carries the dispatch link in the lifecycle payload.
            # GraphHarbor currently retains this link in debug task input instead.
            graph.checkpointer = InMemorySaver()
            native = await graph.astream_events({"messages": [("user", "parent-private-input")]},
                                               cfg, context=cfg["context"], version="v3")
            associations = {}
            async with native:
                async for event in native:
                    if event["method"] != "lifecycle":
                        continue
                    data = event["params"]["data"]
                    cause = data.get("cause", {})
                    if cause.get("type") == "toolCall":
                        associations[cause["tool_call_id"]] = tuple(data["namespace"])
            assert set(associations) == {"dispatch-alpha", "dispatch-beta"}
            assert len(set(associations.values())) == 2
            from langgraph_runtime_pg.graph_executor import invoke_graph
            transported = []
            async def receive(event):
                transported.append(event)
            graph.checkpointer = InMemorySaver()
            await invoke_graph(graph, {"messages": [("user", "parent-private-input")]},
                               config=cfg, on_event=receive)
            lifecycle_links = {
                event["data"]["cause"]["tool_call_id"]: tuple(event["data"]["namespace"])
                for event in transported
                if event["event"] == "lifecycle" and event["data"].get("cause", {}).get("type") == "toolCall"
            }
            assert set(lifecycle_links) == {"dispatch-alpha", "dispatch-beta"}
            assert len(set(lifecycle_links.values())) == 2
            dispatch = {}
            child_namespaces = set()
            for event in transported:
                if event["namespace"]:
                    child_namespaces.add(tuple(event["namespace"]))
                if event["event"] == "debug" and event["data"].get("type") == "task":
                    data = event["data"]["payload"]
                    if data.get("name") == "tools" and isinstance(data.get("input"), list):
                        for call in data["input"]:
                            if call.get("id") in {"dispatch-alpha", "dispatch-beta"}:
                                dispatch[call["id"]] = "tools:" + data["id"]
            assert set(dispatch) == {"dispatch-alpha", "dispatch-beta"}
            assert all(any(segment in namespace for namespace in child_namespaces) for segment in dispatch.values())
        assert callbacks and all(parent != "None" for parent, _ in callbacks.values())

    asyncio.run(run())


def test_live_subagent_trace():
    """Read back actual exported child observations; never invent per-task costs."""
    import os

    import httpx
    from dotenv import dotenv_values

    thread_id = os.environ.get("DEAR_SUBAGENT_TRACE_THREAD")
    if not thread_id:
        pytest.skip("DEAR_SUBAGENT_TRACE_THREAD enables read-only Langfuse verification")
    settings = {**dotenv_values(".env"), **os.environ}
    with httpx.Client(base_url=settings["LANGFUSE_BASE_URL"].rstrip("/"),
                      auth=(settings["LANGFUSE_PUBLIC_KEY"], settings["LANGFUSE_SECRET_KEY"]),
                      timeout=30, trust_env=False) as client:
        response = client.get("/api/public/traces", params={"sessionId": thread_id, "limit": 20})
        response.raise_for_status()
        traces = response.json()["data"]
        assert traces, "No exported trace for this verified thread"
        detail = client.get("/api/public/traces/" + traces[0]["id"])
        detail.raise_for_status()
        trace = detail.json()
        assert trace["metadata"]["execution_mode"] == "ultra"
        assert all(trace["metadata"].get(key) for key in ("policy_hash", "skills_hash", "effective_reasoning"))
        observations = {item["id"]: item for item in trace["observations"]}
        children = {key for key, item in observations.items() if item.get("name") == "general-purpose"}
        assert len(children) == 2
        attributed = set()
        for item in observations.values():
            if item.get("type") != "GENERATION":
                continue
            parent = item.get("parentObservationId")
            visited = set()
            while parent in observations and parent not in visited:
                visited.add(parent)
                if parent in children:
                    assert item["usage"]["total"] > 0
                    attributed.add(parent)
                    break
                parent = observations[parent].get("parentObservationId")
        assert attributed == children
        print(f"Langfuse trace={trace['id']} children={len(children)} actual_usage_verified")
