"""Dear Agent capability declarations."""
import json
import os
import re
from importlib.resources import files

from runtime_service.workspace.artifact_refs import ARTIFACT_MIMES

CHART_NAMES = tuple(sorted(p.stem for p in files("runtime_service.services.dearflow_agent").joinpath("skills/chart-visualization/references").iterdir() if p.name.endswith(".md")))

WORK_TOOLS = ("ls", "read_file", "glob", "grep", "write_file", "edit_file", "execute")
MEMORY_READ_TOOLS = ("search_memory",)
MEMORY_WRITE_TOOLS = ("manage_memory",)
SKILL_READ_TOOLS = ("list_skills", "review_skill_package", "find_skills")
SKILL_WRITE_TOOLS = ("upload_skill", "update_skill", "set_skill_enabled", "delete_skill", "import_skill")
MEDIA_TOOLS = ("generate_image", "edit_image", "get_media_task")
DEAR_TOOLS = (*WORK_TOOLS, *CHART_NAMES, *MEDIA_TOOLS, *MEMORY_READ_TOOLS,
              *MEMORY_WRITE_TOOLS, *SKILL_READ_TOOLS, *SKILL_WRITE_TOOLS,
              "deploy_preview", "fetch_web_guidelines", "request_information",
              "present_artifacts", "parse_document", "search_web", "fetch_page",
              "github_query", "arxiv_search", "write_todos", "task")


def configured_mcp_names() -> tuple[str, ...]:
    configured = json.loads(os.environ.get("RUNTIME_MCP_CONNECTIONS_JSON", "{}"))
    if not isinstance(configured, dict) or any(
        not isinstance(connection, dict) or not isinstance(connection.get("allowed_tools", []), list)
        for connection in configured.values()
    ):
        raise ValueError("invalid_mcp_tool_declarations")
    names = [name for connection in configured.values() for name in connection.get("allowed_tools", [])]
    if any(not isinstance(n, str) or len(n) > 128 or not re.fullmatch(r"mcp_[A-Za-z0-9_.:-]+", n) for n in names) or len(names) != len(set(names)):
        raise ValueError("invalid_or_duplicate_mcp_tool_name")
    return tuple(sorted(names))


def graph_capabilities(graph_id: str) -> dict:
    """Return a fresh transport value; capabilities never grant permissions."""
    return {
        "schema_version": 1,
        "graph_id": graph_id,
        "files": graph_id in {"showcase_demo", "dearflow_agent"},
        "workspace": graph_id in {"showcase_demo", "dearflow_agent"},
        "terminal": graph_id in {"showcase_demo", "dearflow_agent"} and os.name == "posix" and os.getenv("RUNTIME_TERMINAL_ENABLED", "0") == "1",
        "images": graph_id in {"showcase_demo", "dearflow_agent"},
        "message_queue": graph_id in {"reference_agent", "showcase_demo", "dearflow_agent"},
        "execution_modes": ["flash", "standard", "pro", "ultra"] if graph_id == "dearflow_agent" else [],
        "clarification_field_types": ["text", "textarea", "number", "select", "multi_select", "checkbox", "date"] if graph_id == "dearflow_agent" else [],
        "research": bool(os.environ.get("TAVILY_API_KEY")) if graph_id == "dearflow_agent" else False,
        "artifacts": sorted(set(ARTIFACT_MIMES.values())) if graph_id in {"dearflow_agent", "showcase_demo"} else [],
        "independent_subagent_cancel": False,
        "memory": graph_id == "dearflow_agent" and os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") == "1",
        "skill_management": graph_id == "dearflow_agent" and os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") == "1",
    }
