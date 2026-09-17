"""The only composition root: official Deep Agents plus Runtime policy and tracing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
import hashlib
import json
import os
import asyncio
from datetime import datetime, timezone

from deepagents import create_deep_agent
from deepagents.middleware import FilesystemMiddleware
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    TodoListMiddleware,
)
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.pregel import Pregel

from runtime_service.middlewares import (
    ModelCallTimeoutMiddleware,
    RuntimeConfigMiddleware,
    DocumentToolsMiddleware,
    MessageQueueMiddleware,
)
from runtime_service.observability import with_langfuse_tracing
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeAuthError,
    RuntimeContext,
    build_model,
    fetch_model_connection,
    interrupts_for_access_policy,
    parse_runtime_context,
    reject_untrusted_configurable,
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.services.dearflow_agent.workspace.backend import (
    DearWorkspaceBackend,
    WorkspaceMiddleware,
    build_backend,
    skills_hash,
)
from deepagents.middleware import FilesystemPermission
from runtime_service.services.dearflow_agent.prompts import SYSTEM_PROMPT
from runtime_service.services.dearflow_agent.tools.human_input import request_information
from runtime_service.tools.artifacts import build_artifact_tool
from runtime_service.services.dearflow_agent.middleware.clarification import ClarificationBatchGuard
from runtime_service.services.dearflow_agent.capabilities import tool_permissions, CHART_NAMES
from runtime_service.tools.chart import build_chart_tools
from runtime_service.tools.images import ImageWorkspace
from runtime_service.services.dearflow_agent.tools.media import build_media_tools, MEDIA_TOOLS
from runtime_service.services.dearflow_agent.tools.web_guidelines import fetch_web_guidelines
from runtime_service.services.dearflow_agent.modes import resolve_mode, apply_reasoning
from runtime_service.services.dearflow_agent.tools.search import build_research_tools
from runtime_service.services.dearflow_agent.tools.github import build_github_tool
from runtime_service.services.dearflow_agent.tools.arxiv_search import build_arxiv_tool
from runtime_service.services.dearflow_agent.tools.mcp import load_mcp_tools
from runtime_service.services.dearflow_agent.subagents.researcher import researcher
from runtime_service.services.dearflow_agent.middleware.delegation import DelegationConcurrencyMiddleware
from runtime_service.services.dearflow_agent.tools.memory import build_memory_tools, MEMORY_READ_TOOLS, MEMORY_WRITE_TOOLS
from runtime_service.services.dearflow_agent.tools.skills import build_skill_tools, SKILL_READ_TOOLS, SKILL_WRITE_TOOLS
from runtime_service.services.dearflow_agent.middleware.memory import MemoryContextMiddleware
from runtime_service.services.dearflow_agent.skill_governance import SkillStorage
from runtime_service.services.dearflow_agent.workspace.backend import prepare_custom_skills
from runtime_service.services.dearflow_agent.tools.deployment import build_deployment_tool

WORK_TOOLS = ("ls", "read_file", "glob", "grep", "write_file", "edit_file", "execute")
PERMISSIONS = [
    FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
    FilesystemPermission(operations=["write"], paths=["/conversation_history/**", "/large_tool_results/**"], mode="deny"),
]
APPROVALS = {name: {"allowed_decisions": ["approve", "edit", "reject"]}
             for name in ("write_file", "edit_file", "execute", "present_artifacts", "generate_image", "edit_image", "deploy_preview", *CHART_NAMES, *MEMORY_WRITE_TOOLS, *SKILL_WRITE_TOOLS)}

_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="dearflow-research-p2",
    optional_tool_names=(*WORK_TOOLS, *CHART_NAMES, *MEDIA_TOOLS, *MEMORY_READ_TOOLS, *MEMORY_WRITE_TOOLS, *SKILL_READ_TOOLS, *SKILL_WRITE_TOOLS, "deploy_preview", "fetch_web_guidelines", "request_information", "present_artifacts", "parse_document", "search_web", "fetch_page", "github_query", "arxiv_search", "write_todos", "task"),
)
_TOOL_PERMISSIONS = tool_permissions()
_EXECUTION_KEYS = {
    "thread_id",
    "assistant_id",
    "graph_id",
    "langgraph_auth_user",
    "checkpoint_id",
    "checkpoint_ns",
    "checkpoint_map",
}


async def get_agent(config: RunnableConfig) -> Pregel:
    """Bind a thread backend for runs; introspection never creates external resources."""
    configurable = config.get("configurable") or {}
    if not isinstance(configurable, Mapping):
        raise RuntimeAuthError("runtime.auth.missing_principal")
    reject_untrusted_configurable(configurable)
    if any(str(key).startswith("_runtime_test_") for key in configurable):
        raise RuntimeAuthError("runtime.auth.test_adapter_forbidden")
    user = configurable.get("langgraph_auth_user")
    facts = verified_delegation_from_user(user) if user is not None else None
    executing = facts is not None and facts.scope.operation == "run-create"
    workspace = None
    resolved = None
    connection = None
    mode = resolve_mode(None)
    defaults = _DEFAULTS
    permissions = dict(_TOOL_PERMISSIONS)
    mcp_tools = []
    reasoning = {"reasoning": "probe_only"}
    governance = os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") == "1"
    if executing:
        thread_id = configurable.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")
        if facts.scope.assistant_id != "dearflow_agent":
            raise RuntimeAuthError("runtime.auth.invalid_principal", "assistant_id")
        context = parse_runtime_context(config.get("context"))
        mode = resolve_mode(context.execution_mode)
        if runtime_context_hash(context) != facts.context_hash:
            raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
        if facts.scope.thread_id is not None and facts.scope.thread_id != thread_id:
            raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")
        requested_mcp = tuple(name for name in (context.tools or ()) if name.startswith("mcp_"))
        # Authorize requested names before any MCP connection or schema discovery.
        defaults = replace(_DEFAULTS, optional_tool_names=(*_DEFAULTS.optional_tool_names, *requested_mcp))
        permissions.update({name: "runtime.tool.read" for name in requested_mcp})
        resolved = resolve_runtime_config(
            principal=facts.principal,
            context=context,
            policy=facts.policy,
            defaults=defaults,
            tool_permissions=permissions,
        )
        mcp_tools = await load_mcp_tools(config, facts.principal, requested_mcp, _DEFAULTS.optional_tool_names)
        connection = await fetch_model_connection(
            configurable.get("runtime_model_ref"),
            model_id=resolved.model_id,
            project_id=facts.principal.project_id,
        )
        model = build_model(resolved, connection=connection)
        model, reasoning = apply_reasoning(model, mode)
        workspace = DearWorkspaceBackend(
            facts.principal.tenant_id, facts.principal.project_id, thread_id
        )
        if governance:
            custom = await asyncio.to_thread(SkillStorage().freeze,
                (facts.principal.tenant_id, facts.principal.project_id, facts.principal.user_id), thread_id)
            await asyncio.to_thread(prepare_custom_skills, workspace, custom)
    else:
        # Schema-only client: no request is sent, and WorkspaceMiddleware rejects invocation.
        model = ChatOpenAI(model="schema-only", api_key="schema-only", max_retries=0)

    backend = build_backend(workspace)
    document_middleware = DocumentToolsMiddleware(None if workspace is None else workspace.root)
    artifact_tool = build_artifact_tool(None if workspace is None else workspace.root)
    research_tools = build_research_tools(workspace)
    github_tool = build_github_tool(workspace)
    arxiv_tool = build_arxiv_tool(workspace)
    chart_tools = [t for t in build_chart_tools(ImageWorkspace(None if workspace is None else workspace.root), include_spreadsheet=True) if t.name in CHART_NAMES]
    media_tools = build_media_tools(ImageWorkspace(None if workspace is None else workspace.root))
    available = set(defaults.optional_tool_names)
    if not governance:
        available.difference_update((*MEMORY_READ_TOOLS, *MEMORY_WRITE_TOOLS, *SKILL_READ_TOOLS, *SKILL_WRITE_TOOLS))
    if os.environ.get("RUNTIME_DEAR_PREVIEW_DEPLOY_ENABLED") != "1":
        available.discard("deploy_preview")
    if not mode.planning:
        available.discard("write_todos")
    if not mode.delegation:
        available.discard("task")
    if not os.environ.get("TAVILY_API_KEY"):
        available.difference_update({"search_web", "fetch_page"})
    internal_names = ()

    def model_builder(next_config):
        if resolved is None:
            raise RuntimeAuthError("runtime.graph.probe_only")
        return (
            model
            if next_config == resolved
            else apply_reasoning(build_model(next_config, connection=connection), mode)[0]
        )

    def middleware(tool_names: Sequence[str], *, child=False):
        return [
            RuntimeConfigMiddleware(
                defaults=defaults,
                base_model=model,
                model_builder=model_builder,
                tool_permissions=permissions,
                tool_names=tool_names,
                internal_tool_names=internal_names,
            ),
            WorkspaceMiddleware(workspace),
            ModelCallLimitMiddleware(run_limit=24 if child else mode.model_limit,
                                    thread_limit=24 if child else mode.model_limit, exit_behavior="error"),
            ToolCallLimitMiddleware(run_limit=48 if child else mode.tool_limit,
                                   thread_limit=48 if child else mode.tool_limit, exit_behavior="error"),
            # Bound the whole reasoning response, not just the time to its first token.
            ModelCallTimeoutMiddleware(timeout_seconds=120),
        ]

    agent = create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT + "\n<current_date>" + datetime.now(timezone.utc).date().isoformat() + " UTC</current_date>",
        tools=[request_information, artifact_tool, *research_tools, github_tool, arxiv_tool, fetch_web_guidelines, *chart_tools, *media_tools, *mcp_tools,
               *build_memory_tools(), *build_skill_tools(workspace, model), build_deployment_tool(workspace)],
        backend=backend,
        skills=["/skills/", "/skills/custom/"] if governance else ["/skills/"],
        permissions=PERMISSIONS,
        interrupt_on=interrupts_for_access_policy(
            context.access_policy if executing else None, APPROVALS
        ),
        subagents=[researcher(
            research_tools if mode.delegation else [],
            [
                FilesystemMiddleware(backend=backend, tools=["read_file"], _permissions=PERMISSIONS),
                *middleware(available & {"read_file", "search_web", "fetch_page"} if mode.delegation else (), child=True),
            ],
        )],
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                tools=list(WORK_TOOLS),
                _permissions=PERMISSIONS,
                max_execute_timeout=60,
            ),
            *middleware(available),
            *([TodoListMiddleware()] if mode.planning else []),
            ToolCallLimitMiddleware(tool_name="task", run_limit=10, thread_limit=10, exit_behavior="error"),
            DelegationConcurrencyMiddleware(),
            MessageQueueMiddleware(),
            ClarificationBatchGuard(),
            document_middleware,
            *([MemoryContextMiddleware(model)] if governance else []),

        ],
        context_schema=RuntimeContext,
        name="dearflow_agent",
    )
    bound = {
        key: value
        for key, value in config.items()
        if key in {"callbacks", "tags", "metadata", "run_name", "run_id"}
    }
    bound["configurable"] = {
        key: value for key, value in configurable.items() if key in _EXECUTION_KEYS
    }
    bound["recursion_limit"] = min(max(int(config.get("recursion_limit", 1000)), 1), 1000)
    agent = agent.with_config(bound)
    if not executing:
        return agent
    return with_langfuse_tracing(
        agent,
        bound,
        graph_id="dearflow_agent",
        trusted_metadata={
            "user_id": facts.principal.user_id,
            "tenant_id": facts.principal.tenant_id,
            "project_id": facts.principal.project_id,
            "model_id": resolved.model_id,
            "config_hash": resolved.config_hash,
            "prompt_version": resolved.prompt_version,
            "prompt_hash": resolved.prompt_hash,
            "policy_version": resolved.policy_version,
            "policy_hash": hashlib.sha256(json.dumps(asdict(facts.policy), sort_keys=True,
                                                     separators=(",", ":")).encode()).hexdigest(),
            "request_id": facts.request_id,
            "platform_trace_id": facts.platform_trace_id,
            "execution_mode": mode.name,
            "effective_reasoning": reasoning,
            "skills_hash": skills_hash(),
        },
    )


__all__ = ["get_agent"]
