"""Pure server-owned MCP declarations shared by the two explicit consumers."""

import json
import os
import re


def mcp_connections() -> dict:
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


def configured_mcp_names() -> tuple[str, ...]:
    return tuple(
        sorted(
            {n for c in mcp_connections().values() for n in c.get("allowed_tools", [])}
        )
    )
