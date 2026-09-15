"""Dear Agent capability declarations."""
import os
import json

_TOOL_PERMISSIONS = {
    **dict.fromkeys(("ls", "read_file", "glob", "grep", "parse_document", "fetch_documentation", "read_reference", "request_information", "search_web", "fetch_page"), "runtime.tool.read"),
    **dict.fromkeys(("write_file", "edit_file", "write_todos", "present_artifacts"), "runtime.tool.write"),
    "execute": "runtime.tool.execute",
    "task": "runtime.tool.delegate",
}


def tool_permissions() -> dict[str, str]:
    result = dict(_TOOL_PERMISSIONS)
    configured = json.loads(os.environ.get("RUNTIME_MCP_CONNECTIONS_JSON", "{}"))
    for connection in configured.values():
        for name in connection.get("allowed_tools", []):
            if not isinstance(name, str) or not name.startswith("mcp_") or name in result:
                raise ValueError("invalid_or_duplicate_mcp_tool_name")
            result[name] = "runtime.tool.read"
    return result


def graph_capabilities(graph_id: str) -> dict:
    """Return a fresh transport value; capabilities never grant permissions."""
    return {
        "schema_version": 1,
        "graph_id": graph_id,
        "files": graph_id in {"showcase_demo", "dearflow_agent"},
        "images": graph_id == "showcase_demo",
        "message_queue": graph_id in {"reference_agent", "showcase_demo", "dearflow_agent"},
        "execution_modes": ["flash", "standard", "pro", "ultra"] if graph_id == "dearflow_agent" else [],
        "clarification_field_types": ["text", "textarea", "number", "select", "multi_select", "checkbox", "date"] if graph_id == "dearflow_agent" else [],
        "research": bool(os.environ.get("TAVILY_API_KEY")) if graph_id == "dearflow_agent" else False,
        "artifacts": ["text/plain"] if graph_id == "dearflow_agent" else [],
        "independent_subagent_cancel": False,
    }
