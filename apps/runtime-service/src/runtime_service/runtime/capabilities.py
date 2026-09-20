"""Side-effect-free declarations for deployed graphs, never user grants."""
import json
from importlib.resources import files
from runtime_service.services.dearflow_agent.capabilities import (
    DEAR_TOOLS, WORK_TOOLS, configured_mcp_names, graph_capabilities as graph_capabilities,
)

REFERENCE_TOOLS = ("read_reference",)
SHOWCASE_TOOLS = (
    *WORK_TOOLS, "task", "write_todos", "fetch_documentation", "present_artifacts",
    "generate_image", "edit_image", "analyze_image", "parse_document",
    *(item["name"] for item in json.loads(files("runtime_service.tools").joinpath("chart-schemas.json").read_text())
      if item["name"] != "generate_spreadsheet"),
)


def graph_tools(graph_id: str) -> tuple[str, ...]:
    return {
        "reference_agent": REFERENCE_TOOLS,
        "workflow_demo": REFERENCE_TOOLS,
        "showcase_demo": SHOWCASE_TOOLS,
        "dearflow_agent": (*DEAR_TOOLS, *configured_mcp_names()),
    }[graph_id]


def tool_catalog() -> dict:
    tools: dict[str, dict] = {}
    for graph in ("reference_agent", "workflow_demo", "showcase_demo", "dearflow_agent"):
        for name in graph_tools(graph):
            item = tools.setdefault(name, {"tool_key": name, "name": name, "source": "runtime",
                                           "description": name, "graph_ids": []})
            item["graph_ids"].append(graph)
    return {"tools": [tools[name] for name in sorted(tools)]}
