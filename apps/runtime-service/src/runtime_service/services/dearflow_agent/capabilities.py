"""Dear Agent capability declarations."""
import os
import json
from importlib.resources import files

CHART_NAMES = tuple(sorted(p.stem for p in files("runtime_service.services.dearflow_agent").joinpath("skills/chart-visualization/references").iterdir() if p.name.endswith(".md")))

_TOOL_PERMISSIONS = {
    **dict.fromkeys(("ls", "read_file", "glob", "grep", "parse_document", "fetch_documentation", "read_reference", "request_information", "search_web", "fetch_page", "github_query", "arxiv_search", "fetch_web_guidelines"), "runtime.tool.read"),
    **dict.fromkeys(("write_file", "edit_file", "write_todos", "present_artifacts"), "runtime.tool.write"),
    **dict.fromkeys(CHART_NAMES, "runtime.tool.write"),
    "execute": "runtime.tool.execute",
    "task": "runtime.tool.delegate",
    "generate_image": "runtime.tool.write",
    "edit_image": "runtime.tool.write",
    "get_media_task": "runtime.tool.read",
    "deploy_preview": "runtime.tool.write",
    **dict.fromkeys(("search_memory", "list_skills", "review_skill_package", "find_skills"), "runtime.tool.read"),
    **dict.fromkeys(("manage_memory", "create_skill_candidate", "evaluate_skill_candidate", "publish_skill", "revoke_skill", "import_skill"), "runtime.tool.write"),
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
        "images": graph_id in {"showcase_demo", "dearflow_agent"},
        "message_queue": graph_id in {"reference_agent", "showcase_demo", "dearflow_agent"},
        "execution_modes": ["flash", "standard", "pro", "ultra"] if graph_id == "dearflow_agent" else [],
        "clarification_field_types": ["text", "textarea", "number", "select", "multi_select", "checkbox", "date"] if graph_id == "dearflow_agent" else [],
        "research": bool(os.environ.get("TAVILY_API_KEY")) if graph_id == "dearflow_agent" else False,
        "artifacts": ["text/plain", "text/markdown", "text/x-bibtex", "text/csv", "application/json", "text/html", "text/css", "text/javascript", "application/zip", "application/vnd.openxmlformats-officedocument.presentationml.presentation"] if graph_id == "dearflow_agent" else [],
        "independent_subagent_cancel": False,
        "memory": graph_id == "dearflow_agent" and os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") == "1",
        "skill_management": graph_id == "dearflow_agent" and os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") == "1",
    }
