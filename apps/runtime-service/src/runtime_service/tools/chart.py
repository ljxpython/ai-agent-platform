"""Pinned AntV MCP tools, lazy sessions and thread-owned image artifacts."""

import asyncio
import json
from importlib.resources import files

from jsonschema import ValidationError, validate
from langchain_core.tools import ToolException
from langchain_mcp_adapters.tools import convert_mcp_tool_to_langchain_tool
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, TextContent, Tool

from runtime_service.tools.errors import is_transport_error, tool_error_content
from runtime_service.tools.images import ImageWorkspace, download_image

CHART_PACKAGE = "@antv/mcp-server-chart@0.9.10"


def normalize_chart_args(tool_name: str, raw_args: dict | None) -> dict:
    """Normalize and repair common model argument anomalies before validation."""
    if not isinstance(raw_args, dict):
        return {}
    args = dict(raw_args)

    if tool_name in ("generate_flow_diagram", "generate_network_graph"):
        if "data" not in args or not isinstance(args["data"], dict):
            args["data"] = {
                "edges": args.pop("edges", []),
                "nodes": args.pop("nodes", []),
            }
        data = args["data"]
        raw_edges = data.get("edges", [])
        raw_nodes = data.get("nodes", [])

        merged_edges: dict[tuple[str, str], dict[str, str]] = {}
        all_node_names: set[str] = set()

        if isinstance(raw_edges, list):
            for edge in raw_edges:
                if not isinstance(edge, dict):
                    continue
                source = str(edge.get("source") or "").strip()
                target = str(edge.get("target") or "").strip()
                if not source or not target:
                    continue
                all_node_names.add(source)
                all_node_names.add(target)
                key = (source, target)
                name = str(edge.get("name") or "").strip()
                if key not in merged_edges:
                    merged_edges[key] = {
                        "source": source,
                        "target": target,
                        "name": name,
                    }
                else:
                    existing_name = merged_edges[key].get("name", "")
                    if name:
                        if existing_name and name not in existing_name:
                            merged_edges[key]["name"] = f"{existing_name} / {name}"
                        elif not existing_name:
                            merged_edges[key]["name"] = name

        data["edges"] = list(merged_edges.values())

        existing_node_names: set[str] = set()
        cleaned_nodes: list[dict[str, str]] = []

        if isinstance(raw_nodes, list):
            for node in raw_nodes:
                if isinstance(node, dict) and node.get("name"):
                    n_name = str(node["name"]).strip()
                    if n_name and n_name not in existing_node_names:
                        existing_node_names.add(n_name)
                        cleaned_nodes.append({"name": n_name})
                elif isinstance(node, str) and node.strip():
                    n_name = node.strip()
                    if n_name not in existing_node_names:
                        existing_node_names.add(n_name)
                        cleaned_nodes.append({"name": n_name})

        for node_name in sorted(all_node_names - existing_node_names):
            cleaned_nodes.append({"name": node_name})

        if not cleaned_nodes and not data["edges"]:
            cleaned_nodes = [{"name": "Start"}]

        data["nodes"] = cleaned_nodes

    elif tool_name in (
        "generate_fishbone_diagram",
        "generate_mind_map",
        "generate_organization_chart",
    ):
        if "data" not in args or not isinstance(args["data"], dict):
            if "name" in args:
                tree_data = {"name": args.pop("name")}
                if "children" in args:
                    tree_data["children"] = args.pop("children")
                if "description" in args:
                    tree_data["description"] = args.pop("description")
                args["data"] = tree_data

    elif "data" not in args:
        if "items" in args and isinstance(args["items"], list):
            args["data"] = args.pop("items")

    return args


def build_chart_tools(workspace: ImageWorkspace, *, include_spreadsheet=False):
    # Snapshot keeps introspection/offline construction free of npm/network IO.
    schemas = json.loads(files(__package__).joinpath("chart-schemas.json").read_text())
    by_name = {item["name"]: item["schema"] for item in schemas}

    def failure(name, code):
        return CallToolResult(
            isError=True,
            content=[
                TextContent(
                    type="text",
                    text=tool_error_content(ToolException(code), name),
                )
            ],
        )

    async def persist_image(request, handler):
        try:
            request.args = normalize_chart_args(request.name, request.args)
            try:
                payload = json.dumps(request.args, allow_nan=False)
            except ValueError as exc:
                raise ValueError("chart_invalid_input") from exc
            if len(payload.encode()) > 128 * 1024:
                raise ValueError("chart_data_limit")
            validate(request.args, by_name[request.name])
            for dimension in ("width", "height"):
                if not 1 <= request.args.get(dimension, 600) <= 4096:
                    raise ValueError("chart_dimension_limit")
            async with asyncio.timeout(120):
                try:
                    result = await handler(request)
                except FileNotFoundError:
                    return failure(request.name, "chart_provider_failed")
                if result.isError:
                    return failure(request.name, "chart_provider_failed")
                content = []
                refs = []
                # Maps return imageUrl in structuredContent, ordinary charts use a text URL.
                map_url = (result.structuredContent or {}).get("imageUrl")
                blocks = (
                    [TextContent(type="text", text=map_url)]
                    if isinstance(map_url, str)
                    else result.content
                )
                for block in blocks:
                    if isinstance(block, TextContent) and block.text.startswith(
                        "https://"
                    ):
                        data = await download_image(
                            block.text.strip(), allowed_hosts={"mdn.alipayobjects.com"}
                        )
                        ref = await asyncio.to_thread(
                            workspace.save_asset, data, "charts"
                        )
                        content.append(TextContent(type="text", text=ref["path"]))
                        refs.append(ref)
                    else:
                        content.append(block)
                update_dict: dict[str, object] = {"content": content}
                if refs:
                    structured = dict(result.structuredContent or {})
                    structured["runtime_images"] = refs
                    update_dict["structuredContent"] = structured
                else:
                    raise ValueError("chart_image_missing")
                return result.model_copy(update=update_dict)
        except ValidationError:
            return failure(request.name, "chart_invalid_input")
        except McpError:
            return failure(request.name, "chart_provider_failed")
        except ValueError as err:
            if (
                type(err) is not ValueError
                or len(err.args) != 1
                or err.args[0]
                not in {
                    "chart_invalid_input",
                    "chart_dimension_limit",
                    "chart_data_limit",
                    "chart_image_missing",
                }
            ):
                raise
            return failure(request.name, err.args[0])
        except Exception as exc:
            if not is_transport_error(exc):
                raise
            return failure(request.name, "chart_provider_failed")

    return [
        convert_mcp_tool_to_langchain_tool(
            None,
            Tool(
                name=item["name"],
                description=item["name"].replace("_", " "),
                inputSchema=item["schema"],
            ),
            connection={
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", CHART_PACKAGE],
            },
            server_name="chart",
            tool_interceptors=[persist_image],
        )
        for item in schemas
        if include_spreadsheet or item["name"] != "generate_spreadsheet"
    ]
