from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent
from runtime_service.agents.research_agent.prompts import SYSTEM_PROMPT
from runtime_service.agents.research_agent.tools import (
    aget_research_private_tools,
    build_research_runtime_tools,
    list_research_agent_skills,
    list_research_subagents,
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


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)

    private_config = dict(read_configurable(config))
    tools = await build_tools(options)
    tools.extend(build_research_runtime_tools())
    tools.extend(await aget_research_private_tools(private_config))

    subagents: list[SubAgent | CompiledSubAgent] = list(list_research_subagents())
    multimodal_middleware = MultimodalMiddleware(
        parser_model_id=str(
            private_config.get("research_multimodal_parser_model_id")
            or "iflow_qwen3-vl-plus"
        ),
        detail_mode=_parse_bool(
            private_config.get("research_multimodal_detail_mode"), False
        ),
        detail_text_max_chars=_parse_int(
            private_config.get("research_multimodal_detail_text_max_chars"), 2000
        ),
    )

    return create_deep_agent(
        name="research-demo",
        model=model,
        tools=tools,
        middleware=[multimodal_middleware],
        system_prompt=options.system_prompt or SYSTEM_PROMPT,
        backend=FilesystemBackend(
            root_dir=await _aresolve_filesystem_backend_root_dir(
                private_config, agent_name="research-demo"
            ),
            virtual_mode=False,
        ),
        skills=list_research_agent_skills(),
        subagents=subagents,
        context_schema=RuntimeContext,
    )


graph = make_graph
