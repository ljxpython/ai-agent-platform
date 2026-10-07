"""Optional MCP tools from a server-owned, scoped resource binding."""

import json
import os

from langchain_core.tools import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient

from runtime_service.runtime import RuntimeResolutionError, resolve_resource_binding
from runtime_service.tools.errors import is_transport_error, tool_error_content


async def _read_only_transport(request, handler):
    try:
        return await handler(request)
    except Exception as exc:
        if not is_transport_error(exc):
            raise
        raise ToolException("mcp_transport_unavailable") from exc


async def load_mcp_tools(config, principal, requested, reserved):
    names = {name for name in requested if name.startswith("mcp_")}
    if not names:
        return []
    metadata = config.get("metadata") or {}
    thread_metadata = metadata.get("__graphharbor_thread_metadata") or {}
    bindings = thread_metadata.get("runtime_resource_bindings") or {}
    if "mcp" not in bindings:
        return []
    binding = resolve_resource_binding(config, principal, "mcp")
    try:
        connections = json.loads(os.environ.get("RUNTIME_MCP_CONNECTIONS_JSON", "{}"))
        connection = dict(connections[binding.resource_id])
        allowed = connection.pop("allowed_tools", [])
        names.intersection_update(allowed)
        if (
            binding.provider != "mcp_http"
            or connection.get("transport") != "streamable_http"
        ):
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeResolutionError("runtime.mcp.recovery_failed") from exc
    if not names:
        return []
    # Connections/headers are server configuration, never Context or tool arguments.
    client = MultiServerMCPClient(
        {"bound": connection},
        tool_name_prefix=False,
        tool_interceptors=[_read_only_transport],
    )
    tools = await client.get_tools()
    actual = [tool.name for tool in tools]
    if len(set(actual)) != len(actual) or set(actual) & set(reserved):
        raise RuntimeResolutionError("runtime.tool.name_conflict")
    if names - set(actual):
        raise RuntimeResolutionError("runtime.mcp.required_unavailable")
    # P2 only accepts explicitly read-only bound tools. Mutations need their own HITL policy.
    if any(
        (tool.metadata or {}).get("readOnlyHint") is not True
        for tool in tools
        if tool.name in names
    ):
        raise RuntimeResolutionError("runtime.mcp.read_only_required")
    selected = [tool for tool in tools if tool.name in names]
    for item in selected:
        native_handler = item.handle_tool_error

        def handle_error(exc, *, name=item.name, native=native_handler):
            content = tool_error_content(exc, name)
            if content is not None:
                return content
            if callable(native):
                return native(exc)
            raise exc

        item.handle_tool_error = handle_error
    return selected
