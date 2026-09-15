"""The only composition root: official Deep Agents plus Runtime policy and tracing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
import hashlib
import json
import os
from importlib.resources import files

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
)
from deepagents.middleware import FilesystemPermission
from runtime_service.services.dearflow_agent.prompts import SYSTEM_PROMPT
from runtime_service.services.dearflow_agent.tools.human_input import request_information
from runtime_service.services.dearflow_agent.tools.artifacts import build_artifact_tool
from runtime_service.services.dearflow_agent.middleware.clarification import ClarificationBatchGuard
from runtime_service.services.dearflow_agent.capabilities import tool_permissions
from runtime_service.services.dearflow_agent.modes import resolve_mode, apply_reasoning
from runtime_service.services.dearflow_agent.tools.search import build_research_tools
from runtime_service.services.dearflow_agent.tools.mcp import load_mcp_tools
from runtime_service.services.dearflow_agent.subagents.researcher import researcher
from runtime_service.services.dearflow_agent.middleware.delegation import DelegationConcurrencyMiddleware

WORK_TOOLS = ("ls", "read_file", "glob", "grep", "write_file", "edit_file", "execute")
PERMISSIONS = [
    FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
    FilesystemPermission(operations=["write"], paths=["/conversation_history/**", "/large_tool_results/**"], mode="deny"),
]
APPROVALS = {name: {"allowed_decisions": ["approve", "edit", "reject"]}
             for name in ("write_file", "edit_file", "execute", "present_artifacts")}

_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="dearflow-research-p2",
    optional_tool_names=(*WORK_TOOLS, "request_information", "present_artifacts", "parse_document", "search_web", "fetch_page", "write_todos", "task"),
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
    else:
        # Schema-only client: no request is sent, and WorkspaceMiddleware rejects invocation.
        model = ChatOpenAI(model="schema-only", api_key="schema-only", max_retries=0)

    backend = build_backend(workspace)
    document_middleware = DocumentToolsMiddleware(None if workspace is None else workspace.root)
    artifact_tool = build_artifact_tool(None if workspace is None else workspace.root)
    research_tools = build_research_tools(workspace)
    available = set(defaults.optional_tool_names)
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
            ModelCallTimeoutMiddleware(timeout_seconds=30),
        ]

    agent = create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[request_information, artifact_tool, *research_tools, *mcp_tools],
        backend=backend,
        skills=["/skills/"],
        permissions=PERMISSIONS,
        interrupt_on=APPROVALS,
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
            ToolCallLimitMiddleware(tool_name="task", run_limit=8, thread_limit=8, exit_behavior="error"),
            DelegationConcurrencyMiddleware(),
            MessageQueueMiddleware(),
            ClarificationBatchGuard(),
            document_middleware,

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
    bound["recursion_limit"] = min(config.get("recursion_limit", 100), 100)
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
            "skills_hash": hashlib.sha256(files("runtime_service.services.dearflow_agent").joinpath("skills/runtime-smoke/SKILL.md").read_bytes()).hexdigest(),
        },
    )


__all__ = ["get_agent"]
