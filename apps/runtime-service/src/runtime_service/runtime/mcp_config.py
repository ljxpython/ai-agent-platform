"""Pure server-owned MCP declarations shared by the two explicit consumers."""

import json
import os
import re

KNOWLEDGE_SUBMIT_TOOL = "mcp_submit_project_knowledge_document"
KNOWLEDGE_JOB_TOOL = "mcp_get_project_knowledge_ingest_job"


def knowledge_sources_version() -> int:
    value = os.getenv("RUNTIME_KNOWLEDGE_SOURCES_VERSION", "1")
    if value not in {"1", "2"}:
        raise ValueError("invalid_knowledge_sources_version")
    return int(value)


def knowledge_upload_enabled() -> bool:
    value = os.getenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "0")
    if value not in {"0", "1"}:
        raise ValueError("invalid_knowledge_upload_flag")
    return value == "1"


def mcp_connections() -> dict:
    knowledge_sources_version()
    configured = json.loads(os.environ.get("RUNTIME_MCP_CONNECTIONS_JSON", "{}"))
    if not isinstance(configured, dict):
        raise ValueError("invalid_mcp_tool_declarations")
    for connection in configured.values():
        if not isinstance(connection, dict):
            raise ValueError("invalid_mcp_tool_declarations")
        scope = connection.get("scope")
        if (
            not isinstance(scope, dict)
            or set(scope) != {"tenant_id", "project_id"}
            or any(
                not isinstance(v, str) or not v or v != v.strip()
                for v in scope.values()
            )
        ):
            raise ValueError("invalid_mcp_scope")
        names = connection.get("allowed_tools", [])
        if (
            not isinstance(names, list)
            or any(
                not isinstance(n, str)
                or len(n) > 128
                or not re.fullmatch(r"mcp_[A-Za-z0-9_.:-]+", n)
                for n in names
            )
            or len(set(names)) != len(names)
        ):
            raise ValueError("invalid_or_duplicate_mcp_tool_name")
    return configured


def dynamic_knowledge_tools() -> tuple[str, ...]:
    gateway = os.getenv("RUNTIME_KNOWLEDGE_MCP_GATEWAY_URL")
    secret = os.getenv("RUNTIME_KNOWLEDGE_SECRET")
    if not gateway and not secret:
        return ()
    from runtime_service.tools.knowledge import KNOWLEDGE_MCP_TOOLS

    return tuple(
        n
        for n in KNOWLEDGE_MCP_TOOLS
        if n != KNOWLEDGE_SUBMIT_TOOL or knowledge_upload_enabled()
    )


def configured_mcp_names() -> tuple[str, ...]:
    dynamic = dynamic_knowledge_tools()
    static = {
        n
        for c in mcp_connections().values()
        for n in c.get("allowed_tools", [])
        if n != KNOWLEDGE_SUBMIT_TOOL or knowledge_upload_enabled()
    }
    return tuple(sorted(set(dynamic) | static))
