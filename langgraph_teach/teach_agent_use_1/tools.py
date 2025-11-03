import asyncio
import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

# 全局输出目录（可通过 set_output_dir 修改）
OUTPUT_DIR = os.path.join(os.getcwd(), "artifacts", "ui-tests")


@tool
def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"{city}，今天是晴天，温度为 25 摄氏度。!"


def get_zhipu_search_mcp_tools():
    client = MultiServerMCPClient(
        {
            "search": {
                "url": "https://open.bigmodel.cn/api/mcp/web_search/sse?Authorization=0d3c7b3d55c84d6682663dbdbdb3d614.cpoJIoZ3NFaqXARQ",
                "transport": "sse",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


def get_tavily_search_tools():
    client = MultiServerMCPClient(
        {
            "search": {
                "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=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",
                "transport": "streamable_http",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


def get_playwright_mcp_tools():
    client = MultiServerMCPClient(
        {
            "playwright_mcp": {
                "command": "npx",
                "args": ["@playwright/mcp@latest"],
                "transport": "stdio",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


def get_chrome_devtools_mcp_tools():
    client = MultiServerMCPClient(
        {
            "chrome_devtools_mcp": {
                "command": "npx",
                "args": [
                    "chrome-devtools-mcp@latest",
                    "--headless=false",
                    "--isolated=true",
                ],
                "transport": "stdio",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


def get_chrome_mcp_tools():
    client = MultiServerMCPClient(
        {
            "chrome_mcp": {
                "url": "http://127.0.0.1:12306/mcp",
                "transport": "streamable_http",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


def get_mcp_server_chart_tools():
    client = MultiServerMCPClient(
        {
            "mcp_chart_server": {
                "command": "npx",
                "args": ["-y", "@antv/mcp-server-chart"],
                "transport": "stdio",
            }
        }
    )
    tools = asyncio.run(client.get_tools())
    return tools


# print(get_chrome_devtools_mcp_tools())
# tools = get_zhipu_search_mcp_tools()
# print(tools)


# https://app.tavily.com/home
os.environ["TAVILY_API_KEY"] = "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"
# # pin install langchain-tavily
from langchain_tavily import TavilySearch

toolSearch = TavilySearch(max_results=2)
