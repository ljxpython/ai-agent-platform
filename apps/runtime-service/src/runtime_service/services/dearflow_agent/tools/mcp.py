"""Optional MCP tools from a server-owned, scoped resource binding."""
import json
import os

from langchain_mcp_adapters.client import MultiServerMCPClient
from runtime_service.runtime import resolve_resource_binding, RuntimeResolutionError


async def load_mcp_tools(config, principal, requested, reserved):
    names = {name for name in requested if name.startswith("mcp_")}
    if not names:
        return []
    binding = resolve_resource_binding(config, principal, "mcp")
    try:
        connections = json.loads(os.environ.get("RUNTIME_MCP_CONNECTIONS_JSON", "{}"))
        connection = dict(connections[binding.resource_id])
        allowed = connection.pop("allowed_tools", [])
        if names - set(allowed):
            raise ValueError()
        if binding.provider != "mcp_http" or connection.get("transport") != "streamable_http":
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeResolutionError("runtime.mcp.recovery_failed") from exc
    # Connections/headers are server configuration, never Context or tool arguments.
    client = MultiServerMCPClient({"bound": connection}, tool_name_prefix=False)
    tools = await client.get_tools()
    actual = [tool.name for tool in tools]
    if len(set(actual)) != len(actual) or set(actual) & set(reserved):
        raise RuntimeResolutionError("runtime.tool.name_conflict")
    if names - set(actual):
        raise RuntimeResolutionError("runtime.mcp.required_unavailable")
    # P2 only accepts explicitly read-only bound tools. Mutations need their own HITL policy.
    if any((tool.metadata or {}).get("readOnlyHint") is not True for tool in tools if tool.name in names):
        raise RuntimeResolutionError("runtime.mcp.read_only_required")
    return [tool for tool in tools if tool.name in names]
