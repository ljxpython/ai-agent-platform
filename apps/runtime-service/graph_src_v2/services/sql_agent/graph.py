from __future__ import annotations

from typing import Any

from graph_src_v2.runtime.modeling import apply_model_runtime_params, resolve_model
from graph_src_v2.runtime.options import build_runtime_config, merge_trusted_auth_context
from graph_src_v2.services.sql_agent.chart_mcp import aget_mcp_server_chart_tools
from graph_src_v2.services.sql_agent.prompts import build_sql_agent_system_prompt
from graph_src_v2.services.sql_agent.schemas import DEFAULT_DATABASE_NAME
from graph_src_v2.services.sql_agent.tools import (
    build_sql_agent_service_config,
    build_sql_agent_tools,
)
from graph_src_v2.tools.registry import build_tools
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    service_config = build_sql_agent_service_config(config)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)

    tools = await build_tools(options)
    tools.extend(await build_sql_agent_tools(model, config=config))
    try:
        tools.extend(await aget_mcp_server_chart_tools())
    except Exception:
        pass

    custom_instructions = options.system_prompt or None
    system_prompt = build_sql_agent_system_prompt(
        dialect="sqlite",
        top_k=service_config.top_k,
        database_name=DEFAULT_DATABASE_NAME,
        custom_instructions=custom_instructions,
    )

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        name="sql_agent",
    )


graph = make_graph
