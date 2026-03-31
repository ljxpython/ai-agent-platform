from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from runtime_service.middlewares.multimodal import (
    MultimodalMiddleware,
)
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import apply_model_runtime_params, resolve_model
from runtime_service.runtime.options import (
    build_runtime_config,
    context_to_mapping,
    merge_trusted_auth_context,
    read_configurable,
)
from runtime_service.services.test_case_service.middleware import (
    TestCaseDocumentPersistenceMiddleware,
)
from runtime_service.services.test_case_service.prompts import SYSTEM_PROMPT
from runtime_service.services.test_case_service.schemas import (
    build_test_case_service_config,
    get_service_root,
)
from runtime_service.services.test_case_service.tool_runtime_context_middleware import (
    ToolRuntimeContextSanitizerMiddleware,
)
from runtime_service.services.test_case_service.tools import (
    build_test_case_service_tools,
)
from runtime_service.tools.registry import build_tools
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime


def _resolve_backend_root_dir_path(
    private_config: dict[str, Any], *, agent_name: str
) -> Path:
    """解析 FilesystemBackend 的根目录。

    优先使用 configurable 中的显式覆盖，否则使用服务私有 skills 目录。
    skills 目录位于服务包内，与 SKILL.md 文件共处同一位置。
    """
    override = private_config.get("test_case_backend_root_dir")
    if isinstance(override, str) and override.strip():
        return Path(override).expanduser()
    # Align with Deep Agents skills docs: backend root points to a directory that
    # contains a "/skills/" folder. For this service, that's the service package root.
    return get_service_root()


async def _aresolve_backend_root_dir(
    private_config: dict[str, Any], *, agent_name: str
) -> str:
    path = _resolve_backend_root_dir_path(private_config, agent_name=agent_name)
    # Avoid blocking the event loop (LangGraph/blockbuster will flag os.mkdir).
    await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
    return str(path)


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime

    # 1. 运行时解析（公共层）
    runtime_context = merge_trusted_auth_context(config, {})
    private_config = dict(read_configurable(config))
    service_config = build_test_case_service_config(config)
    explicit_model_id = (
        context_to_mapping(runtime_context).get("model_id")
        or private_config.get("model_id")
        or os.getenv("MODEL_ID")
    )
    effective_config: RunnableConfig | dict[str, Any] = config
    if not isinstance(explicit_model_id, str) or not explicit_model_id.strip():
        next_config = dict(config)
        next_config["configurable"] = {
            **private_config,
            "model_id": service_config.default_model_id,
        }
        effective_config = next_config
        private_config = dict(read_configurable(effective_config))
        service_config = build_test_case_service_config(effective_config)
    options = build_runtime_config(effective_config, runtime_context)

    # 2. 模型装配（公共层）
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)

    # 3. 工具装配（仅平台公共工具，服务无私有工具）
    tools = await build_tools(options)
    tools.extend(build_test_case_service_tools(service_config))

    # 4. 多模态中间件（图片/PDF 解析，横切能力）
    multimodal_middleware = MultimodalMiddleware(
        parser_model_id=service_config.multimodal_parser_model_id,
        detail_mode=service_config.multimodal_detail_mode,
        detail_text_max_chars=service_config.multimodal_detail_text_max_chars,
    )
    document_persistence_middleware = TestCaseDocumentPersistenceMiddleware(service_config)
    tool_runtime_context_middleware = ToolRuntimeContextSanitizerMiddleware()

    # 5. FilesystemBackend：root 指向服务 skills 目录
    #    virtual_mode=True：skills 从磁盘读取，运行时中间产物保存在内存
    backend_root = await _aresolve_backend_root_dir(
        private_config, agent_name="test_case_agent"
    )
    backend = FilesystemBackend(root_dir=backend_root, virtual_mode=True)

    # 6. skills 路径："/skills/" 表示加载 backend root 下 skills 目录
    #    create_deep_agent 内部自动构建 SkillsMiddleware(backend=backend, sources=skills)
    skills = ["/skills/"]

    # 7. 系统提示词：将运行时覆盖作为“前置补充”，服务 prompt 始终生效。
    # 避免全局 SYSTEM_PROMPT 覆盖掉本服务的 skills/工作流约束。
    system_prompt = (
        f"{options.system_prompt}\n\n{SYSTEM_PROMPT}" if options.system_prompt else SYSTEM_PROMPT
    )

    return create_deep_agent(
        name="test_case_agent",
        model=model,
        tools=tools,
        middleware=[
            multimodal_middleware,
            document_persistence_middleware,
            tool_runtime_context_middleware,
        ],
        system_prompt=system_prompt,
        backend=backend,
        skills=skills,
        context_schema=RuntimeContext,
    )


graph = make_graph
