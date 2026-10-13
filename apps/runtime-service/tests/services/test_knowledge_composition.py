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
from runtime_service.tools.knowledge_jobs import JOB_TOOL, SUBMIT_TOOL


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
@pytest.mark.parametrize("tool_name", [KNOWLEDGE_TOOL, SUBMIT_TOOL, JOB_TOOL])
def test_two_composition_roots_keep_knowledge_at_authorized_root(
    monkeypatch, tmp_path, graph_id, module, mode, tool_name
):
    root = import_module(module)
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dear"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_EXECUTION_MODE", "local")
    monkeypatch.setenv("AGENT_CONTEXT_MANAGEMENT_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "1")
    monkeypatch.setenv(
        "RUNTIME_MCP_CONNECTIONS_JSON",
        json.dumps(
            {
                "knowledge": {
                    "scope": {"tenant_id": "tenant", "project_id": "project"},
                    "transport": "streamable_http",
                    "url": "http://unused",
                    "allowed_tools": [tool_name],
                }
            }
        ),
    )
    calls = []

    @tool(tool_name, response_format="content_and_artifact")
    async def query(**args) -> tuple:
        """Fixture read-only project knowledge query."""
        calls.append(args)
        return '{"status":"no_hit","sources":[]}', {
            "structured_content": {"status": "no_hit", "sources": []}
        }

    key = (
        "query"
        if tool_name == KNOWLEDGE_TOOL
        else "file_ref"
        if tool_name == SUBMIT_TOOL
        else "job_id"
    )
    query.args_schema = {
        "type": "object",
        "required": [key],
        "properties": {key: {"type": "object" if key == "file_ref" else "string"}},
    }
    query.metadata = {
        "readOnlyHint": tool_name != SUBMIT_TOOL,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    args = {key: {} if key == "file_ref" else "facts"}
    if tool_name == SUBMIT_TOOL:
        # Composition-only: file bytes and authorization are tested through the real interceptor separately.
        args[key] = {
            "version": 1,
            "path": "/workspace/uploads/" + "a" * 64 + ".md",
            "file_name": "fixture.md",
            "mime_type": "text/markdown",
            "size_bytes": 3,
            "sha256": "a" * 64,
        }
    elif tool_name == JOB_TOOL:
        args[key] = "kj_" + "1" * 32
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
            call(tool_name, args),
            AIMessage(content="done"),
        ]
        if mode in {"enabled", "unbound", "deny", "plan"}
        else [AIMessage(content="done")],
    )
    monkeypatch.setattr(root, "build_model", lambda *a, **kw: model)
    cfg = config()
    cfg["context"] = {"access_policy": "full_access"}
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
        user["runtime_policy"]["tool_overrides"] = {tool_name: False}
    if mode in ("plan", "offload"):
        cfg["context"] = (
            {"plan_mode": True, "plan_execution_id": "knowledge-plan"}
            if mode == "plan"
            else {"offload_conversation": True}
        )
        user["runtime_context_hash"] = runtime_context_hash(cfg["context"])
    user["runtime_context_hash"] = runtime_context_hash(cfg["context"])
    if mode == "schema":
        cfg = {"configurable": {"graph_id": graph_id, "assistant_id": graph_id}}

    async def run():
        graph = await root.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        names = {t.name for t in captured[-1]["tools"]}
        assert (tool_name in names) == (mode == "enabled")
        for child in captured[-1]["subagents"]:
            assert tool_name not in {
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
                    getattr(m, "name", None) == tool_name for m in result["messages"]
                )
                assert calls == [args]
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


@pytest.mark.parametrize(
    "module",
    [
        "runtime_service.services.dearflow_agent.agent",
        "runtime_service.services.demo.showcase_demo.agent",
    ],
)
@pytest.mark.parametrize("policy", ["review", "workspace_write", "full_access"])
@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_knowledge_upload_uses_existing_root_hitl(
    monkeypatch, tmp_path, module, policy, decision
):
    from langgraph.types import Command

    from runtime_service.runtime.access_policy import interrupts_for_access_policy

    root = import_module(module)
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dear"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_EXECUTION_MODE", "local")
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "1")
    monkeypatch.setenv(
        "RUNTIME_MCP_CONNECTIONS_JSON",
        json.dumps(
            {
                "knowledge": {
                    "scope": {"tenant_id": "tenant", "project_id": "project"},
                    "transport": "streamable_http",
                    "url": "http://unused",
                    "allowed_tools": [SUBMIT_TOOL],
                }
            }
        ),
    )
    calls = []

    @tool(SUBMIT_TOOL)
    async def submit(file_ref: dict) -> str:
        """Controlled mutation after the root's existing approval."""
        calls.append(file_ref)
        return "queued"

    monkeypatch.setattr(root, "load_mcp_tools", AsyncMock(return_value=[submit]))
    model = BindableFakeMessagesChatModel(
        responses=[
            call(SUBMIT_TOOL, {"file_ref": {"fixture": True}}),
            AIMessage(content="done"),
        ]
    )
    monkeypatch.setattr(root, "build_model", lambda *a, **kw: model)
    cfg = config()
    graph_id = "dearflow_agent" if ".dearflow_agent." in module else "showcase_demo"
    cfg["configurable"].update(graph_id=graph_id, assistant_id=graph_id)
    cfg["context"] = {"access_policy": policy}
    user = cfg["configurable"]["langgraph_auth_user"]
    user["runtime_scope"]["assistant_id"] = graph_id
    user["runtime_context_hash"] = runtime_context_hash(cfg["context"])
    if policy == "full_access":
        cfg["metadata"]["__graphharbor_thread_metadata"] = {
            "project_id": "project",
            "access_version": 1,
            "owner_user_id": "dear-test",
            "visibility": "private",
            "shared_actions": {},
        }

    async def run():
        graph = await root.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        result = await graph.ainvoke(
            {"messages": [("user", "明确将附件加入项目知识库")]},
            cfg,
            context=cfg["context"],
        )
        if policy == "full_access":
            assert calls == [{"fixture": True}]
            assert not result.get("__interrupt__")
            return
        assert calls == []
        action = result["__interrupt__"][0].value["action_requests"][0]
        assert action["name"] == SUBMIT_TOOL
        await graph.ainvoke(
            Command(resume={"decisions": [{"type": decision}]}),
            cfg,
            context=cfg["context"],
        )
        assert bool(calls) == (decision == "approve")

    assert (
        SUBMIT_TOOL
        not in __import__(
            "runtime_service.runtime.access_policy", fromlist=["WORKSPACE_WRITE_TOOLS"]
        ).WORKSPACE_WRITE_TOOLS
    )
    assert SUBMIT_TOOL in interrupts_for_access_policy(
        "workspace_write", {SUBMIT_TOOL: True}
    )
    asyncio.run(run())
