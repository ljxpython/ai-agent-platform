"""Optional MCP tools from a server-owned, scoped resource binding."""

import asyncio
import logging

from langchain_core.tools import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient

from runtime_service.runtime import RuntimeResolutionError, resolve_resource_binding
from runtime_service.runtime.mcp_config import (
    KNOWLEDGE_JOB_TOOL,
    KNOWLEDGE_SUBMIT_TOOL,
    knowledge_sources_version,
    knowledge_upload_enabled,
    mcp_connections,
)
from runtime_service.tools.errors import is_transport_error, tool_error_content
from runtime_service.tools.knowledge import KNOWLEDGE_TOOL, knowledge_result_interceptor
from runtime_service.tools.knowledge_upload import knowledge_upload_interceptor
from runtime_service.workspace.file_refs import MIME_EXT

logger = logging.getLogger(__name__)
_DISCOVERY_TIMEOUT_SECONDS = 10

FILE_REF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "path", "file_name", "mime_type", "size_bytes", "sha256"],
    "properties": {
        "version": {"type": "integer", "const": 1},
        "path": {
            "type": "string",
            "pattern": r"^/workspace/uploads/[a-f0-9]{64}\.[a-z]+$",
        },
        "file_name": {"type": "string", "minLength": 1, "maxLength": 200},
        "mime_type": {"type": "string", "enum": sorted(MIME_EXT)},
        "size_bytes": {"type": "integer", "minimum": 1, "maximum": 20 * 1024 * 1024},
        "sha256": {"type": "string", "pattern": r"^[a-f0-9]{64}$"},
    },
}

IMAGE_REF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "path", "mime_type", "size_bytes", "sha256"],
    "properties": {
        k: v for k, v in FILE_REF_SCHEMA["properties"].items() if k != "file_name"
    },
}
IMAGE_REF_SCHEMA["properties"]["path"] = {
    "type": "string",
    "pattern": r"^/workspace/uploads/[a-f0-9]{64}\.(png|jpg|jpeg)$",
}
IMAGE_REF_SCHEMA["properties"]["mime_type"] = {
    "type": "string",
    "enum": ["image/png", "image/jpeg"],
}
IMAGE_REF_SCHEMA["properties"]["size_bytes"] = {
    "type": "integer",
    "minimum": 1,
    "maximum": 5 * 1024 * 1024,
}


def _knowledge_schema(tool):
    if tool.name == KNOWLEDGE_TOOL:
        schema = tool.args_schema
        if not isinstance(schema, dict) or not isinstance(
            schema.get("properties"), dict
        ):
            raise RuntimeResolutionError("runtime.mcp.invalid_knowledge_schema")
        if (
            knowledge_sources_version() == 2
            and "sources_version" not in schema["properties"]
        ):
            raise RuntimeResolutionError("runtime.mcp.invalid_knowledge_schema")
        tool.args_schema = {
            **schema,
            "properties": {
                k: v for k, v in schema["properties"].items() if k != "sources_version"
            },
            "required": [
                k for k in schema.get("required", []) if k != "sources_version"
            ],
            "additionalProperties": False,
        }
        return
    if tool.name not in {KNOWLEDGE_JOB_TOOL, KNOWLEDGE_SUBMIT_TOOL}:
        return
    schema = tool.args_schema
    key = "file_ref" if tool.name == KNOWLEDGE_SUBMIT_TOOL else "job_id"
    expected_type = "object" if key == "file_ref" else "string"
    if (
        not isinstance(schema, dict)
        or schema.get("type") != "object"
        or schema.get("required") != [key]
        or set(schema.get("properties", {})) != {key}
        or not isinstance(schema["properties"][key], dict)
        or schema["properties"][key].get("type") != expected_type
    ):
        raise RuntimeResolutionError("runtime.mcp.invalid_knowledge_schema")
    tool.args_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [key],
        "properties": {
            key: {"anyOf": [FILE_REF_SCHEMA, IMAGE_REF_SCHEMA]}
            if key == "file_ref"
            else {"type": "string", "pattern": r"^kj_[a-f0-9]{32}$"},
        },
    }


async def _read_only_transport(request, handler):
    try:
        return await handler(request)
    except Exception as exc:
        if not is_transport_error(exc):
            raise
        raise ToolException("mcp_transport_unavailable") from exc


async def load_mcp_tools(config, principal, requested, reserved, target_servers=None):
    names = {name for name in requested if name.startswith("mcp_")}
    if not names:
        return []
    if not knowledge_upload_enabled():
        names.discard(KNOWLEDGE_SUBMIT_TOOL)
    if not names:
        return []
    metadata = config.get("metadata") or {}
    thread_metadata = metadata.get("__graphharbor_thread_metadata") or {}
    bindings = thread_metadata.get("runtime_resource_bindings") or {}
    if "mcp" not in bindings:
        return []
    binding = resolve_resource_binding(config, principal, "mcp")
    try:
        connections = mcp_connections()
        if binding.resource_id in connections:
            connection = dict(connections[binding.resource_id])
            scope = connection.pop("scope")
            if scope != {
                "tenant_id": binding.tenant_id,
                "project_id": binding.project_id,
            }:
                raise ValueError()
            allowed = connection.pop("allowed_tools", [])
            names.intersection_update(allowed)
            if (
                binding.provider != "mcp_http"
                or connection.get("transport") != "streamable_http"
            ):
                raise ValueError()
            server_key = binding.resource_id
        elif binding.auth_token:
            import os

            from runtime_service.tools.knowledge import KNOWLEDGE_MCP_TOOLS

            gateway_url = binding.gateway_url or os.getenv(
                "RUNTIME_KNOWLEDGE_MCP_GATEWAY_URL",
                "http://152.136.27.196:8000/mcp",
            )
            if not gateway_url.endswith("/mcp"):
                gateway_url = gateway_url.rstrip("/") + "/mcp"
            connection = {
                "url": gateway_url,
                "transport": "streamable_http",
                "headers": {"Authorization": f"Bearer {binding.auth_token}"},
            }
            allowed = list(KNOWLEDGE_MCP_TOOLS)
            names.intersection_update(allowed)
            if binding.provider != "mcp_http":
                raise ValueError()
            server_key = "knowledge"
        else:
            raise KeyError(binding.resource_id)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeResolutionError("runtime.mcp.recovery_failed") from exc
    if not names:
        return []
    if target_servers is not None:
        target_set = set(target_servers)
        if server_key not in target_set and not (
            server_key.startswith("knowledge") and "knowledge" in target_set
        ):
            return []
    # Connections/headers are server configuration, never Context or tool arguments.
    client = MultiServerMCPClient(
        {server_key: connection},
        tool_name_prefix=False,
        tool_interceptors=[
            _read_only_transport,
            knowledge_result_interceptor,
            knowledge_upload_interceptor(binding, connection),
        ],
    )
    try:
        tools = await asyncio.wait_for(
            client.get_tools(server_name=server_key),
            timeout=_DISCOVERY_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning(
            "Failed to load MCP tools from server %s: %s",
            server_key,
            exc,
            exc_info=True,
        )
        return []

    actual = [tool.name for tool in tools]
    if len(set(actual)) != len(actual) or set(actual) & set(reserved):
        raise RuntimeResolutionError("runtime.tool.name_conflict")
    missing = names - set(actual)
    if missing:
        logger.warning(
            "Requested MCP tools missing from %s: %s",
            server_key,
            sorted(missing),
        )
    selected = [tool for tool in tools if tool.name in names]
    if not selected:
        return []

    # Only the exact project upload is a mutation; its root HITL and fresh grant remain mandatory.
    if any(
        (tool.metadata or {}).get("readOnlyHint") is not True
        for tool in selected
        if tool.name != KNOWLEDGE_SUBMIT_TOOL
    ):
        raise RuntimeResolutionError("runtime.mcp.read_only_required")
    for item in selected:
        if item.name == KNOWLEDGE_SUBMIT_TOOL and any(
            (item.metadata or {}).get(k) is not v
            for k, v in {
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }.items()
        ):
            raise RuntimeResolutionError("runtime.mcp.invalid_knowledge_annotations")
        _knowledge_schema(item)
        native_handler = item.handle_tool_error

        def handle_error(exc, *, name=item.name, native=native_handler):
            content = tool_error_content(exc, name)
            if content is not None:
                return content
            if callable(native):
                try:
                    return native(exc)
                except Exception:
                    pass
            if is_transport_error(exc):
                return tool_error_content(
                    ToolException("mcp_transport_unavailable"), name
                )
            logger.warning(
                "Unhandled MCP tool execution error on %s: %s",
                name,
                exc,
                exc_info=True,
            )
            return tool_error_content(ToolException("mcp_transport_unavailable"), name)

        item.handle_tool_error = handle_error
    return selected
