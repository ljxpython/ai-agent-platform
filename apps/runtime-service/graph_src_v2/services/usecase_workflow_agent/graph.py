from __future__ import annotations

from typing import Any

from graph_src_v2.middlewares.multimodal import MultimodalMiddleware
from graph_src_v2.runtime.modeling import apply_model_runtime_params, resolve_model
from graph_src_v2.runtime.options import build_runtime_config, merge_trusted_auth_context
from graph_src_v2.services.usecase_workflow_agent.prompts import SYSTEM_PROMPT
from graph_src_v2.services.usecase_workflow_agent.tools import (
    build_usecase_workflow_service_config,
    build_usecase_workflow_tools,
)
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from graph_src_v2.middlewares.multimodal import MultimodalAgentState
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    build_usecase_workflow_service_config(config)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)
    tools = build_usecase_workflow_tools(model)
    system_prompt = options.system_prompt or SYSTEM_PROMPT

    return create_agent(
        model=model,
        name="usecase_workflow_agent",
        tools=tools,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "persist_approved_usecases": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                        "description": "Persisting approved use cases requires explicit human confirmation.",
                    }
                },
                description_prefix="Use case persistence pending approval",
            ),
            MultimodalMiddleware(),
        ],
        system_prompt=system_prompt,
        state_schema=MultimodalAgentState,
    )


graph = make_graph
