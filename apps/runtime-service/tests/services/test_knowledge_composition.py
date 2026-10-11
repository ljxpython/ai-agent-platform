import asyncio
import json
from importlib import import_module
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from services.dearflow_agent.test_agent import call, config
from support import BindableFakeMessagesChatModel

from runtime_service.runtime import (
    RuntimePrincipal,
    RuntimeResolutionError,
    runtime_context_hash,
)
from runtime_service.runtime.resource_bindings import thread_resource_metadata
from runtime_service.tools import mcp
from runtime_service.tools.knowledge import KNOWLEDGE_TOOL


@pytest.mark.parametrize(
    "graph_id,module",
    [
        ("dearflow_agent", "runtime_service.services.dearflow_agent.agent"),
        ("showcase_demo", "runtime_service.services.demo.showcase_demo.agent"),
    ],
)
@pytest.mark.parametrize(
    "mode", ["enabled", "unbound", "deny", "plan", "offload", "schema"]
)
def test_two_composition_roots_keep_knowledge_at_authorized_root(
    monkeypatch, tmp_path, graph_id, module, mode
):
    root = import_module(module)
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dear"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_EXECUTION_MODE", "local")
    monkeypatch.setenv("AGENT_CONTEXT_MANAGEMENT_ENABLED", "1")
    monkeypatch.setenv(
        "RUNTIME_MCP_CONNECTIONS_JSON",
        json.dumps(
            {
                "knowledge": {
                    "scope": {"tenant_id": "tenant", "project_id": "project"},
                    "transport": "streamable_http",
                    "url": "http://unused",
                    "allowed_tools": [KNOWLEDGE_TOOL],
                }
            }
        ),
    )
    calls = []

    @tool(KNOWLEDGE_TOOL, response_format="content_and_artifact")
    async def query(query: str) -> tuple:
        """Fixture read-only project knowledge query."""
        calls.append(query)
        return '{"status":"no_hit","sources":[]}', {
            "structured_content": {"status": "no_hit", "sources": []}
        }

    query.metadata = {"readOnlyHint": True}
    client = AsyncMock()
    client.get_tools.return_value = [query]
    # MultiServerMCPClient is a synchronous constructor.
    monkeypatch.setattr(mcp, "MultiServerMCPClient", lambda *a, **kw: client)
    captured = []
    compile_agent = root.create_deep_agent

    def capture(**kwargs):
        captured.append(kwargs)
        return compile_agent(**kwargs)

    monkeypatch.setattr(root, "create_deep_agent", capture)
    model = BindableFakeMessagesChatModel(
        profile={"max_input_tokens": 128000, "max_output_tokens": 16384},
        responses=[
            call(KNOWLEDGE_TOOL, {"query": "facts"}),
            AIMessage(content="done"),
        ]
        if mode in {"enabled", "unbound", "deny", "plan"}
        else [AIMessage(content="done")],
    )
    monkeypatch.setattr(root, "build_model", lambda *a, **kw: model)
    cfg = config()
    cfg["configurable"].update(graph_id=graph_id, assistant_id=graph_id)
    user = cfg["configurable"]["langgraph_auth_user"]
    user["runtime_scope"]["assistant_id"] = graph_id
    principal = RuntimePrincipal("dear-test", "tenant", "project", "developer", ())
    if mode != "unbound":
        cfg["metadata"]["__graphharbor_thread_metadata"] = thread_resource_metadata(
            kind="mcp",
            provider="mcp_http",
            resource_id="knowledge",
            principal=principal,
            thread_id="dear-thread",
        )
    if mode == "deny":
        user["runtime_policy"]["tool_overrides"] = {KNOWLEDGE_TOOL: False}
    if mode in ("plan", "offload"):
        cfg["context"] = (
            {"plan_mode": True, "plan_execution_id": "knowledge-plan"}
            if mode == "plan"
            else {"offload_conversation": True}
        )
        user["runtime_context_hash"] = runtime_context_hash(cfg["context"])
    if mode == "schema":
        cfg = {"configurable": {"graph_id": graph_id, "assistant_id": graph_id}}

    async def run():
        graph = await root.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        names = {t.name for t in captured[-1]["tools"]}
        assert (KNOWLEDGE_TOOL in names) == (mode == "enabled")
        for child in captured[-1]["subagents"]:
            assert KNOWLEDGE_TOOL not in {
                getattr(t, "name", t) for t in child.get("tools", [])
            }
        if mode in {"enabled", "unbound", "deny", "plan"}:
            if mode == "enabled":
                result = await graph.ainvoke(
                    {"messages": [("user", "facts")]},
                    cfg,
                    context=cfg.get("context", {}),
                )
                assert any(
                    getattr(m, "name", None) == KNOWLEDGE_TOOL
                    for m in result["messages"]
                )
                assert calls == ["facts"]
                client.get_tools.assert_awaited_once()
            else:
                expected = (
                    "runtime.plan.tool_denied"
                    if mode == "plan"
                    else "runtime.tool.not_allowed"
                )
                with pytest.raises(RuntimeResolutionError, match=expected):
                    await graph.ainvoke(
                        {"messages": [("user", "facts")]},
                        cfg,
                        context=cfg.get("context", {}),
                    )
                assert calls == []
                client.get_tools.assert_not_awaited()
        else:
            client.get_tools.assert_not_awaited()

    asyncio.run(run())
