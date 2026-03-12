from __future__ import annotations

from typing import Any

from graph_src_v2.agents.assistant_agent.tools import (
    build_langchain_concepts_demo_tools,
    draft_release_plan,
    lookup_internal_knowledge,
    send_demo_email,
)
from graph_src_v2.middlewares.multimodal import (
    MultimodalAgentState,
    MultimodalMiddleware,
)
from graph_src_v2.runtime.modeling import apply_model_runtime_params, resolve_model
from graph_src_v2.runtime.options import (
    build_runtime_config,
    merge_trusted_auth_context,
)
from graph_src_v2.tools.registry import build_tools
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph_sdk.runtime import ServerRuntime


@tool(
    "submit_high_impact_action",
    description="Submit a high-impact action request for approval before execution.",
)
def submit_high_impact_action(action: str, details: str) -> str:
    return f"Approved execution request: action={action}; details={details}"


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)
    tools = await build_tools(options)
    tools.extend(
        [
            lookup_internal_knowledge,
            draft_release_plan,
            send_demo_email,
        ]
    )
    tools.extend(build_langchain_concepts_demo_tools(model))
    tools.append(submit_high_impact_action)

    middleware = [
        HumanInTheLoopMiddleware(
            interrupt_on={
                "submit_high_impact_action": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                    "description": "High-impact action requires human review.",
                }
            },
            description_prefix="Tool execution pending approval",
        ),
        MultimodalMiddleware(),
    ]

    return create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        system_prompt=options.system_prompt,
        state_schema=MultimodalAgentState,
        name="assistant",
    )


graph = make_graph
