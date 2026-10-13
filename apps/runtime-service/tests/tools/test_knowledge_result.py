import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from deepagents.backends import FilesystemBackend
from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from mcp.types import CallToolResult, TextContent

from runtime_service.middlewares.filesystem import ResultFilesystemMiddleware
from runtime_service.runtime import RuntimePrincipal, RuntimeResolutionError
from runtime_service.runtime.capabilities import graph_tools
from runtime_service.runtime.mcp_config import configured_mcp_names
from runtime_service.runtime.resource_bindings import thread_resource_metadata
from runtime_service.tools import mcp
from runtime_service.tools.knowledge import (
    KNOWLEDGE_TOOL,
    knowledge_result_interceptor,
    project_knowledge_result,
)


def payload(count=1):
    return {
        "status": "ok",
        "sources": [
            {
                "source_id": f"call-{i}",
                "document_id": "kd_" + "1" * 32,
                "chunk_id": f"chunk-{i}",
                "title": f"[{i}] 文档.md",
                "kind": "knowledge",
                "preview": "中文" * 1000,
                "truncated": False,
                "raw_data": "SECRET",
                "source_uri": "/PRIVATE/file",
            }
            for i in range(count)
        ],
        "raw_data": "SECRET",
    }


def result(data, **kwargs):
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(data, ensure_ascii=False))],
        structuredContent=data,
        **kwargs,
    )


def test_safe_projection_is_bounded_and_drops_metadata():
    projected = project_knowledge_result(result(payload(9), _meta={"secret": "SECRET"}))
    assert not projected.isError
    assert len(projected.structuredContent["sources"]) == 8
    assert len(projected.content[0].text.encode()) <= 12 * 1024
    assert "SECRET" not in projected.model_dump_json()
    assert "PRIVATE" not in projected.model_dump_json()
    assert all(
        s["truncated"] and len(s["preview"]) <= 800
        for s in projected.structuredContent["sources"]
    )
    assert json.loads(projected.content[0].text) == projected.structuredContent


def test_errors_invalid_contract_and_empty_are_distinct():
    assert not project_knowledge_result(
        result({"status": "no_hit", "sources": []})
    ).isError
    for response in (
        result(payload(), isError=True),
        result({"status": "ok", "sources": []}),
        result({"status": "no_hit", "sources": [{}]}),
        CallToolResult(content=[TextContent(type="text", text="/PRIVATE SECRET")]),
    ):
        projected = project_knowledge_result(response)
        assert projected.isError
        assert "SECRET" not in projected.model_dump_json()
        assert "no_hit" not in projected.model_dump_json()


def test_interceptor_preserves_cancellation():
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            knowledge_result_interceptor(
                MCPToolCallRequest(
                    name=KNOWLEDGE_TOOL, args={"query": "test"}, server_name="bound"
                ),
                AsyncMock(side_effect=asyncio.CancelledError),
            )
        )


@pytest.mark.parametrize("limit", [1, 100, 800, 4000])
def test_f04_small_budget_preserves_json_and_same_source_snapshot(tmp_path, limit):
    projected = project_knowledge_result(result(payload(8)))
    original = ToolMessage(
        content=projected.content[0].text,
        name=KNOWLEDGE_TOOL,
        tool_call_id="knowledge-budget",
        artifact={"structured_content": projected.structuredContent},
    )
    middleware = ResultFilesystemMiddleware(
        backend=FilesystemBackend(root_dir=tmp_path),
        tool_token_limit_before_evict=limit,
    )

    async def run():
        processed, archived = await middleware._aprocess_large_message(
            original, middleware.backend
        )
        assert not archived
        body = json.loads(processed.content)
        assert "SECRET" not in processed.model_dump_json()
        assert original.artifact["structured_content"] == projected.structuredContent
        if limit == 1:
            assert processed.status == "error" and processed.artifact is None
        else:
            assert len(processed.content) <= 4 * limit
            assert body == processed.artifact["structured_content"]
            assert body["status"] == "ok" and body["sources"]

    asyncio.run(run())


def test_same_name_across_scopes_and_scope_denial_before_discovery(monkeypatch):
    connections = {
        n: {
            "scope": {"tenant_id": "t", "project_id": n},
            "allowed_tools": [KNOWLEDGE_TOOL],
            "transport": "streamable_http",
            "url": "http://unused",
        }
        for n in ("a", "b")
    }
    monkeypatch.setenv("RUNTIME_MCP_CONNECTIONS_JSON", json.dumps(connections))
    assert configured_mcp_names() == (KNOWLEDGE_TOOL,)
    for graph in ("dearflow_agent", "showcase_demo"):
        assert KNOWLEDGE_TOOL in graph_tools(graph)
    for graph in ("reference_agent", "workflow_demo"):
        assert KNOWLEDGE_TOOL not in graph_tools(graph)
    principal = RuntimePrincipal("u", "t", "a", "developer", ("runtime.tool.read",))
    config = {
        "configurable": {"thread_id": "thread"},
        "metadata": {
            "__graphharbor_thread_metadata": thread_resource_metadata(
                kind="mcp",
                provider="mcp_http",
                resource_id="b",
                principal=principal,
                thread_id="thread",
            )
        },
    }
    client = AsyncMock()
    monkeypatch.setattr(mcp, "MultiServerMCPClient", client)
    with pytest.raises(RuntimeResolutionError):
        asyncio.run(mcp.load_mcp_tools(config, principal, (KNOWLEDGE_TOOL,), ()))
    client.assert_not_called()
    connections["a"]["allowed_tools"].append(KNOWLEDGE_TOOL)
    monkeypatch.setenv("RUNTIME_MCP_CONNECTIONS_JSON", json.dumps(connections))
    with pytest.raises(ValueError):
        configured_mcp_names()


def v2_payload(count=1, **locator):
    data = payload(count)
    data["sources_version"] = 2
    for source in data["sources"]:
        source["locator"] = {
            "unit": "page",
            "start": 3,
            "end": 5,
            "block_type": "table",
            **locator,
        }
    return data


@pytest.mark.parametrize(
    "locator",
    [
        {},
        {"unit": "slide", "start": 2, "end": 2, "block_type": "image"},
        {"unit": "unknown", "start": None, "end": None, "block_type": None},
    ],
)
def test_v2_locator_survives_projection_and_budget(locator):
    from runtime_service.tools.knowledge import fit_knowledge_message

    response = project_knowledge_result(result(v2_payload(8, **locator)))
    assert not response.isError and response.structuredContent["sources_version"] == 2
    message = ToolMessage(
        content=response.content[0].text,
        tool_call_id="v2",
        artifact={"structured_content": response.structuredContent},
    )
    fitted = fit_knowledge_message(message, 1600)
    assert fitted.status != "error"
    assert len(fitted.content) <= 1600
    assert json.loads(fitted.content) == fitted.artifact["structured_content"]
    assert all(
        s["locator"] == v2_payload(**locator)["sources"][0]["locator"]
        for s in fitted.artifact["structured_content"]["sources"]
    )
    assert (
        "PRIVATE" not in fitted.model_dump_json()
        and "SECRET" not in fitted.model_dump_json()
    )
    assert response.structuredContent["sources_version"] == 2


@pytest.mark.parametrize(
    "locator",
    [
        {"unit": "url"},
        {"start": True},
        {"start": 0},
        {"start": "3"},
        {"start": 6, "end": 5},
        {"end": None},
        {"block_type": "html"},
        {"unit": "unknown"},
        {"path": "/PRIVATE"},
        {"url": "https://evil.invalid"},
    ],
)
def test_invalid_v2_locator_fails_closed(locator):
    safe = project_knowledge_result(result(v2_payload(**locator)))
    assert safe.isError
    assert safe.content[0].text == '{"code":"knowledge_retrieval_failed"}'


@pytest.mark.parametrize("version", [True, 2.0, "2", 3, None])
def test_unknown_sources_version_is_not_silently_downgraded(version):
    assert project_knowledge_result(
        result({**v2_payload(), "sources_version": version})
    ).isError


@pytest.mark.parametrize("version", ["1", "2"])
def test_request_version_is_server_owned_and_hidden_from_model(monkeypatch, version):
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_SOURCES_VERSION", version)
    schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
            "sources_version": {"enum": [1, 2]},
        },
    }
    tool = SimpleNamespace(name=KNOWLEDGE_TOOL, args_schema=schema)
    mcp._knowledge_schema(tool)
    assert "sources_version" not in tool.args_schema["properties"]
    request = MCPToolCallRequest(
        name=KNOWLEDGE_TOOL,
        args={"query": "test", "sources_version": 99},
        server_name="bound",
    )
    handler = AsyncMock(
        return_value=result(v2_payload() if version == "2" else payload())
    )
    safe = asyncio.run(knowledge_result_interceptor(request, handler))
    assert not safe.isError
    sent = handler.call_args.args[0].args
    assert sent == (
        {"query": "test", "sources_version": 2} if version == "2" else {"query": "test"}
    )
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_SOURCES_VERSION", "invalid")
    with pytest.raises(ValueError):
        asyncio.run(knowledge_result_interceptor(request, handler))


def test_provider_cannot_silently_change_selected_version(monkeypatch):
    monkeypatch.setenv("RUNTIME_KNOWLEDGE_SOURCES_VERSION", "2")
    request = MCPToolCallRequest(
        name=KNOWLEDGE_TOOL, args={"query": "test"}, server_name="bound"
    )
    handler = AsyncMock(return_value=result(payload()))
    assert asyncio.run(knowledge_result_interceptor(request, handler)).isError


def test_v2_requires_locator_and_preserves_empty_no_hit():
    data = v2_payload()
    del data["sources"][0]["locator"]
    assert project_knowledge_result(result(data)).isError
    safe = project_knowledge_result(
        result({"status": "no_hit", "sources": [], "sources_version": 2})
    )
    assert not safe.isError and safe.structuredContent["sources_version"] == 2
