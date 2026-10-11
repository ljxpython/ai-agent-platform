"""Verify the official HTTP Adapter and F04 against controlled provider responses."""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from runtime_service.middlewares.filesystem import ResultFilesystemMiddleware
from runtime_service.runtime import RuntimePrincipal
from runtime_service.runtime.resource_bindings import thread_resource_metadata
from runtime_service.tools.knowledge import KNOWLEDGE_TOOL
from runtime_service.tools.mcp import load_mcp_tools


def test_http_contract_errors_projection_and_frontend_fixtures(monkeypatch, tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail("controlled knowledge provider exited")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("controlled knowledge provider startup timeout")
        monkeypatch.setenv(
            "RUNTIME_MCP_CONNECTIONS_JSON",
            json.dumps(
                {
                    "fixture": {
                        "scope": {"tenant_id": "tenant", "project_id": "project"},
                        "transport": "streamable_http",
                        "url": f"http://127.0.0.1:{port}/mcp",
                        "allowed_tools": [KNOWLEDGE_TOOL],
                        "timeout": 2,
                    }
                }
            ),
        )
        principal = RuntimePrincipal("u", "tenant", "project", "developer", ())
        config = {
            "configurable": {"thread_id": "fixture-thread"},
            "metadata": {
                "__graphharbor_thread_metadata": thread_resource_metadata(
                    kind="mcp",
                    provider="mcp_http",
                    resource_id="fixture",
                    principal=principal,
                    thread_id="fixture-thread",
                )
            },
        }

        async def run():
            from deepagents.backends import FilesystemBackend

            tool = (await load_mcp_tools(config, principal, [KNOWLEDGE_TOOL], []))[0]
            messages = {}
            for scenario in ("ok", "no_hit", "error", "malformed", "oversized"):
                message = await tool.ainvoke(
                    {
                        "type": "tool_call",
                        "name": KNOWLEDGE_TOOL,
                        "id": "fixture-" + scenario,
                        "args": {"query": scenario},
                    }
                )
                encoded = message.model_dump_json()
                assert "SECRET" not in encoded and "PRIVATE" not in encoded
                if scenario in {"error", "malformed"}:
                    assert message.status == "error" and message.artifact is None
                    assert json.loads(message.content[0]["text"]) == {
                        "code": "knowledge_retrieval_failed"
                    }
                else:
                    assert message.status == "success"
                    body = json.loads(message.content[0]["text"])
                    assert body == message.artifact["structured_content"]
                    assert body["status"] == (
                        "no_hit" if scenario == "no_hit" else "ok"
                    )
                    assert len(message.content[0]["text"].encode()) <= 12 * 1024
                if scenario == "oversized":
                    middleware = ResultFilesystemMiddleware(
                        backend=FilesystemBackend(root_dir=tmp_path),
                        tool_token_limit_before_evict=800,
                    )
                    message, archived = await middleware._aprocess_large_message(
                        message, middleware.backend
                    )
                    assert not archived
                    assert len(message.content) <= 3200
                    assert (
                        json.loads(message.content)
                        == message.artifact["structured_content"]
                    )
                    assert any(
                        s["truncated"]
                        for s in message.artifact["structured_content"]["sources"]
                    )
                messages[scenario] = message.model_dump(mode="json")
            process.terminate()
            process.wait(timeout=15)
            disconnected = await tool.ainvoke(
                {
                    "type": "tool_call",
                    "name": KNOWLEDGE_TOOL,
                    "id": "disconnected",
                    "args": {"query": "ok"},
                }
            )
            assert disconnected.status == "error"
            assert (
                json.loads(disconnected.content)["code"] == "tool.upstream_unavailable"
            )
            assert "127.0.0.1" not in disconnected.content
            messages["disconnected"] = disconnected.model_dump(mode="json")
            destination = os.environ.get("KNOWLEDGE_FRONTEND_FIXTURES")
            if destination:
                directory = Path(destination)
                directory.mkdir(parents=True, exist_ok=True)
                for scenario, message in messages.items():
                    (directory / (scenario + ".json")).write_text(
                        json.dumps(
                            {
                                "origin": "controlled-http-provider-through-official-adapter",
                                "scenario": scenario,
                                "tool_message": message,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )

        asyncio.run(run())
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP
    from mcp.types import CallToolResult, TextContent, ToolAnnotations

    server = FastMCP("controlled-knowledge", host="127.0.0.1", port=int(sys.argv[1]))

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def mcp_query_project_knowledge(query: str) -> CallToolResult:
        count = 8 if query == "oversized" else 2
        payload = {
            "status": "no_hit" if query == "no_hit" else "ok",
            "sources": []
            if query == "no_hit"
            else [
                {
                    "source_id": f"fixture:{i}",
                    "document_id": f"kd_{i:032x}",
                    "chunk_id": f"chunk-{i}",
                    "title": f"[{i}] 同名规范.md",
                    "kind": "knowledge",
                    "preview": "受控协议片段。" * (500 if query == "oversized" else 2),
                    "truncated": False,
                    "source_uri": "/PRIVATE",
                    "raw_data": "SECRET",
                }
                for i in range(1, count + 1)
            ],
            "raw_data": "SECRET",
        }
        if query == "malformed":
            payload["sources"] = [{"bad": "SECRET /PRIVATE"}]
        return CallToolResult(
            isError=query == "error",
            content=[
                TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))
            ],
            structuredContent=payload,
            _meta={"credential": "SECRET"},
        )

    server.run(transport="streamable-http")
