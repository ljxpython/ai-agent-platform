"""Pinned AntV MCP tools, lazy sessions and thread-owned image artifacts."""

import asyncio
import json
from importlib.resources import files

from langchain_mcp_adapters.tools import convert_mcp_tool_to_langchain_tool
from mcp.types import CallToolResult, TextContent, Tool

from runtime_service.tools.images import ImageWorkspace, download_image

CHART_PACKAGE = "@antv/mcp-server-chart@0.9.10"


def build_chart_tools(workspace: ImageWorkspace):
    # Snapshot keeps introspection/offline construction free of npm/network IO.
    schemas = json.loads(files(__package__).joinpath("chart-schemas.json").read_text())

    async def persist_image(request, handler):
        try:
            async with asyncio.timeout(120):
                result = await handler(request)
                if result.isError:
                    return result
                content = []
                refs = []
                for block in result.content:
                    if isinstance(block, TextContent) and block.text.startswith(
                        "https://"
                    ):
                        data = await download_image(
                            block.text.strip(), allowed_hosts={"mdn.alipayobjects.com"}
                        )
                        ref = await asyncio.to_thread(workspace.save_asset, data, "charts")
                        content.append(TextContent(type="text", text=ref["path"]))
                        refs.append(ref)
                    else:
                        content.append(block)
                update_dict: dict[str, object] = {"content": content}
                if refs:
                    structured = dict(result.structuredContent or {})
                    structured["runtime_images"] = refs
                    update_dict["structuredContent"] = structured
                return result.model_copy(update=update_dict)
        except Exception:  # noqa: BLE001 - MCP/transport errors must not expose host details
            return CallToolResult(
                isError=True,
                content=[
                    TextContent(
                        type="text",
                        text="Chart MCP failed or its image could not be saved. Retry later.",
                    )
                ],
            )

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
        if item["name"] != "generate_spreadsheet"
    ]
