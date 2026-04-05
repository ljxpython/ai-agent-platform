from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent
from runtime_service.agents.deepagent_agent.prompts import SYSTEM_PROMPT
from runtime_service.agents.deepagent_agent.tools import (
    list_deepagent_skills,
    list_subagents,
)
from runtime_service.middlewares.multimodal import MultimodalMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import apply_model_runtime_params, resolve_model
from runtime_service.runtime.options import (
    build_runtime_config,
    merge_trusted_auth_context,
    read_configurable,
)
from runtime_service.tools.registry import build_tools
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime


def _resolve_filesystem_backend_root_dir_path(
    private_config: dict[str, Any], *, agent_name: str
) -> Path:
    override = private_config.get("deepagents_backend_root_dir")
    if isinstance(override, str) and override.strip():
        path = Path(override).expanduser()
    else:
        path = (
            Path(tempfile.gettempdir())
            / "ai-agent-platform"
            / "deepagents"
            / agent_name
        )
    return path


async def _aresolve_filesystem_backend_root_dir(
    private_config: dict[str, Any], *, agent_name: str
) -> str:
    path = _resolve_filesystem_backend_root_dir_path(
        private_config, agent_name=agent_name
    )
    await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
    return str(path)


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    private_config = dict(read_configurable(config))
    tools = await build_tools(options)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)
    subagents: list[SubAgent | CompiledSubAgent] = list(list_subagents())

    return create_deep_agent(
        name="deepagent-demo",
        model=model,
        tools=tools,
        middleware=[MultimodalMiddleware()],
        system_prompt=options.system_prompt or SYSTEM_PROMPT,
        backend=FilesystemBackend(
            root_dir=await _aresolve_filesystem_backend_root_dir(
                private_config, agent_name="deepagent-demo"
            ),
            virtual_mode=False,
        ),
        skills=list_deepagent_skills(),
        subagents=subagents,
        context_schema=RuntimeContext,
    )


graph = make_graph
