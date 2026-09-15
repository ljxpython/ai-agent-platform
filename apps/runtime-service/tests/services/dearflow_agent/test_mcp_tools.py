import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from runtime_service.runtime import RuntimePrincipal, RuntimeResolutionError
from runtime_service.runtime.resource_bindings import thread_resource_metadata
from runtime_service.services.dearflow_agent.tools.mcp import load_mcp_tools


def test_real_mcp_binding_permissions_disconnect_and_close(monkeypatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(.1)
        else:
            pytest.fail("MCP test server did not start")
        monkeypatch.setenv("RUNTIME_MCP_CONNECTIONS_JSON", json.dumps({"test": {
            "transport": "streamable_http", "url": f"http://127.0.0.1:{port}/mcp",
            "allowed_tools": ["mcp_echo", "mcp_write"], "timeout": 2}}))
        principal = RuntimePrincipal("user", "tenant", "project", "developer", ("runtime.tool.read",))
        cfg = {"configurable": {"thread_id": "thread"}, "metadata": {
            "__graphharbor_thread_metadata": thread_resource_metadata(kind="mcp", provider="mcp_http", resource_id="test", principal=principal, thread_id="thread")}}
        async def run():
            assert await load_mcp_tools({}, principal, [], []) == []
            tools = await load_mcp_tools(cfg, principal, ["mcp_echo"], [])
            assert "verified" in str(await tools[0].ainvoke({"text": "verified"}))
            with pytest.raises(RuntimeResolutionError):
                await load_mcp_tools(cfg, principal, ["mcp_echo"], ["mcp_echo"])
            with pytest.raises(RuntimeResolutionError):
                await load_mcp_tools(cfg, principal, ["mcp_write"], [])
            with pytest.raises(RuntimeResolutionError):
                await load_mcp_tools({**cfg, "configurable": {"thread_id": "other"}}, principal, ["mcp_echo"], [])
            process.terminate()
            process.wait(timeout=10)
            with pytest.raises((ExceptionGroup, httpx.HTTPError, ConnectionError)):
                await tools[0].ainvoke({"text": "disconnected"})
        asyncio.run(run())
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    server = FastMCP("dear-p2-read", host="127.0.0.1", port=int(sys.argv[1]))
    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def mcp_echo(text: str) -> str:
        return text
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False))
    def mcp_write() -> str:
        return "must not execute"
    server.run(transport="streamable-http")
