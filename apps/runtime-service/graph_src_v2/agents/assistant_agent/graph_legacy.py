from __future__ import annotations

from typing import Any

from graph_src_v2.agents.assistant_agent.prompts import resolve_assistant_system_prompt
from graph_src_v2.agents.assistant_agent.tools import (
    build_assistant_tools,
    build_langchain_concepts_demo_tools,
)
from graph_src_v2.middlewares.multimodal import (
    MultimodalAgentState,
    MultimodalMiddleware,
)
from graph_src_v2.runtime.context import RuntimeContext
from graph_src_v2.runtime.modeling import apply_model_runtime_params, resolve_model
from graph_src_v2.runtime.options import (
    build_runtime_config,
    merge_trusted_auth_context,
)
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime


# ==================== Historical Entry ====================
# This implementation is kept for compatibility and historical reference only.
# New assistant work should use `graph.py`, which now points to the HITL-first entry.


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)

    demo_enabled = True
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)
    tools = await build_assistant_tools(options)
    if demo_enabled:
        tools.extend(build_langchain_concepts_demo_tools(model))

    return create_agent(
        model=model,
        tools=tools,
        middleware=[MultimodalMiddleware()],
        system_prompt=resolve_assistant_system_prompt(
            options.system_prompt, demo_enabled
        ),
        state_schema=MultimodalAgentState,
        context_schema=RuntimeContext,
        name="assistant",
    )


graph = make_graph
