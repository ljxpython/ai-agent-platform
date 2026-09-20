"""Locked Platform signer -> Runtime authentication -> model/tool/HTTP contract."""
import asyncio
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from langchain.agents.middleware import ModelRequest, ToolCallRequest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from runtime_service.auth.platform import authenticate
from runtime_service.middlewares.runtime_config import RuntimeConfigMiddleware
from runtime_service.runtime import AgentDefaults, RuntimeContext, RuntimePolicy, RuntimePrincipal, RuntimeResolutionError, resolve_runtime_config
from runtime_service.runtime.capabilities import graph_tools, tool_catalog
from runtime_service.runtime.resolver import parse_tool_overrides
from runtime_service.runtime.tool_access import require_tool_access


@pytest.mark.parametrize("value", [None, [], True, {"read_reference": True}, {"read_reference": 0}, {"read_reference": None}, {"read_reference": "false"}])
def test_false_only_boundary(value):
    with pytest.raises(RuntimeResolutionError):
        parse_tool_overrides(value)


def test_effective_and_declaration_hashes_and_required_availability():
    args = dict(principal=RuntimePrincipal("u", "t", "p", "viewer", ()), context=RuntimeContext(),
                policy=RuntimePolicy("models", ("model",), (), "tools"),
                defaults=AgentDefaults("model", "prompt", "v1", optional_tool_names=("one", "two")))
    full = resolve_runtime_config(**args)
    limited = resolve_runtime_config(**args, available_tool_names=("one",))
    assert limited.optional_tool_names == ("one",)
    assert full.config_hash != limited.config_hash
    args["defaults"] = replace(args["defaults"], optional_tool_names=("one", "two", "three"))
    changed = resolve_runtime_config(**args, available_tool_names=("one",))
    assert changed.tool_declaration_version != limited.tool_declaration_version
    assert changed.config_hash != limited.config_hash
    args["defaults"] = replace(args["defaults"], required_tool_names=("required",))
    with pytest.raises(RuntimeResolutionError, match="required_tool.unavailable"):
        resolve_runtime_config(**args, available_tool_names=())


def test_deployed_registry_matches_display_declarations():
    registry = json.loads((Path(__file__).resolve().parents[2] / "langgraph.json").read_text())["graphs"]
    catalog = tool_catalog()["tools"]
    assert {g for item in catalog for g in item["graph_ids"]} == set(registry)
    for graph in registry:
        assert len(graph_tools(graph)) == len(set(graph_tools(graph)))


def test_mcp_declarations_reject_malformed_names_and_shapes(monkeypatch):
    from runtime_service.services.dearflow_agent.capabilities import configured_mcp_names
    for payload in ([], {"one": []}, {"one": {"allowed_tools": "mcp_one"}},
                    {"one": {"allowed_tools": [["mcp_one"]]}},
                    {"one": {"allowed_tools": ["mcp_bad name"]}},
                    {"one": {"allowed_tools": ["mcp_one", "mcp_one"]}}):
        monkeypatch.setenv("RUNTIME_MCP_CONNECTIONS_JSON", json.dumps(payload))
        with pytest.raises(ValueError):
            configured_mcp_names()
    monkeypatch.setenv("RUNTIME_MCP_CONNECTIONS_JSON", "{}")
    assert configured_mcp_names() == ()


def test_platform_signed_denial_reaches_every_execution_boundary(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "platform-api/src"))
    from platform_api.config import Settings
    from platform_api.core.security.tokens import create_runtime_delegation_token

    secret = "tool-contract-test-secret-at-least-32-bytes"
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", secret)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "platform-api")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    settings = Settings(runtime_delegation_secret=secret)
    defaults = AgentDefaults("model", "prompt", "v1", optional_tool_names=("read_reference",))
    model = FakeListChatModel(responses=["ok"])

    async def run():
        for denied in ({}, {"read_reference": False}):
            token = create_runtime_delegation_token(subject="u", tenant_id="t", project_id="p", role="viewer", permissions=[],
                policy_version="models", allowed_model_ids=["model"], tool_overrides=denied, tool_policy_version="revision",
                scope={"tenant_id": "t", "project_id": "p", "assistant_id": "reference_agent", "thread_id": "thread", "operation": "run-create"}, settings=settings)
            facts = await authenticate("Bearer " + token)
            runtime = Runtime(context=RuntimeContext(), server_info=SimpleNamespace(user=facts, graph_id="reference_agent", assistant_id="reference_agent"), execution_info=SimpleNamespace(thread_id="thread"))
            middleware = RuntimeConfigMiddleware(defaults=defaults, base_model=model)
            seen = []
            async def model_handler(request):
                seen.extend(request.tools)
                return AIMessage(content="ok")
            request = ModelRequest(model=model, messages=[], tools=[{"name": "read_reference"}], runtime=runtime)
            await middleware.awrap_model_call(request, model_handler)
            handler = AsyncMock(return_value="executed")
            call = ToolCallRequest(tool_call={"name": "read_reference", "args": {}, "id": "call", "type": "tool_call"}, tool=None, state={}, runtime=runtime)
            if denied:
                assert seen == []
                with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
                    await middleware.awrap_tool_call(call, handler)
                handler.assert_not_awaited()
                forged = AsyncMock(return_value=AIMessage(content="", tool_calls=[{"name": "read_reference", "args": {}, "id": "call"}]))
                with pytest.raises(RuntimeResolutionError):
                    await middleware.awrap_model_call(request, forged)
                with pytest.raises(HTTPException) as error:
                    require_tool_access(facts, "read_reference")
                assert error.value.status_code == 403
            else:
                assert seen == [{"name": "read_reference"}]
                assert await middleware.awrap_tool_call(call, handler) == "executed"
                require_tool_access(facts, "read_reference")
    asyncio.run(run())


def test_mcp_disabled_or_unbound_never_connects_and_binding_limits_names(monkeypatch):
    from runtime_service.runtime.resource_bindings import thread_resource_metadata
    from runtime_service.services.dearflow_agent.tools import mcp
    principal = RuntimePrincipal("u", "t", "p", "viewer", ())
    client = SimpleNamespace(get_tools=AsyncMock(return_value=[SimpleNamespace(name="mcp_one", metadata={"readOnlyHint": True})]))
    constructed = []
    monkeypatch.setattr(mcp, "MultiServerMCPClient", lambda *args, **kwargs: constructed.append(args) or client)
    monkeypatch.setenv("RUNTIME_MCP_CONNECTIONS_JSON", json.dumps({
        "one": {"transport": "streamable_http", "url": "http://unused", "allowed_tools": ["mcp_one"]},
        "two": {"allowed_tools": ["mcp_two"]}}))
    config = {"configurable": {"thread_id": "thread"}, "metadata": {"__graphharbor_thread_metadata": thread_resource_metadata(kind="mcp", provider="mcp_http", resource_id="one", principal=principal, thread_id="thread")}}
    async def run():
        assert await mcp.load_mcp_tools(config, principal, (), ()) == []
        assert await mcp.load_mcp_tools({}, principal, ("mcp_one",), ()) == []
        assert constructed == []
        loaded = await mcp.load_mcp_tools(config, principal, ("mcp_one", "mcp_two"), ())
        assert [tool.name for tool in loaded] == ["mcp_one"]
        assert len(constructed) == 1
    asyncio.run(run())


def test_signed_denials_block_direct_http_before_side_effects(monkeypatch, tmp_path):
    import httpx
    import jwt
    import time
    from runtime_service.webapp import app
    from runtime_service.runtime.resolver import runtime_context_hash
    secret = "tool-http-test-secret-at-least-32-bytes"
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", secret)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_DEAR_GOVERNANCE_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "workspace"))
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for operation, tool, method, path in (
                ("image-upload", "write_file", "PUT", "/internal/threads/thread/images/uploads/" + "0" * 64),
                ("workspace-file-read", "read_file", "GET", "/internal/threads/thread/workspace/tree"),
                ("dear-skills-write", "delete_skill", "DELETE", "/internal/dear/skills/custom/test?expected_revision=revision"),
            ):
                claims = {"type": "runtime_delegation", "delegation_version": 2, "sub": "u", "tenant_id": "t", "project_id": "p", "role": "admin", "permissions": [],
                    "policy_version": "models", "allowed_model_ids": ["model"], "tool_overrides": {tool: False}, "tool_policy_version": "tools",
                    "scope": {"tenant_id": "t", "project_id": "p", "assistant_id": "dearflow_agent", "thread_id": None if operation == "dear-skills-write" else "thread", "operation": operation},
                    "context_hash": runtime_context_hash(None), "iss": "test", "aud": "runtime-service", "iat": int(time.time()), "exp": int(time.time()) + 60}
                token = jwt.encode(claims, secret, algorithm="HS256")
                response = await client.request(method, path, headers={"authorization": "Bearer " + token})
                assert response.status_code == 403, response.text
                assert response.json()["detail"]["code"] == "runtime.tool.not_allowed"
            assert not (tmp_path / "workspace").exists()
    asyncio.run(run())
