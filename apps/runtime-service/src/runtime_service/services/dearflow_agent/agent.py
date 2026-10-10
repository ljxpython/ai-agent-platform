"""The only composition root: official Deep Agents plus Runtime policy and tracing."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from datetime import UTC, datetime
from functools import partial

from deepagents import create_deep_agent
from deepagents.middleware import FilesystemMiddleware, FilesystemPermission
from langchain.agents.middleware import (
    TodoListMiddleware,
    ToolCallLimitMiddleware,
    ToolErrorMiddleware,
)
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.pregel import Pregel

from runtime_service.middlewares import (
    ContextBudgetMiddleware,
    ConversationOffloadingMiddleware,
    DocumentToolsMiddleware,
    ExecutionBudgetMiddleware,
    MaintenanceSafeToolCallsMiddleware,
    MessageQueueMiddleware,
    ModelCallTimeoutMiddleware,
    ModelErrorMiddleware,
    ModelResilienceMiddleware,
    ModelResilienceSummarizationMiddleware,
    RuntimeConfigMiddleware,
    TimeoutWrapupMiddleware,
    TokenBudgetMiddleware,
    context_management_enabled,
    resolve_wrapup_after_seconds,
)
from runtime_service.middlewares.retry import (
    DelegatedTaskRetryMiddleware,
    RuntimeModelRetryMiddleware,
)
from runtime_service.observability import with_langfuse_tracing
from runtime_service.observability.startup import StartupDiagnostics
from runtime_service.runtime import (
    AgentDefaults,
    ModelConnectionBundle,
    RuntimeAuthError,
    RuntimeContext,
    build_fallback_model,
    build_model,
    fetch_model_bundle,
    interrupts_for_access_policy,
    parse_runtime_context,
    reject_untrusted_configurable,
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.runtime.run_budget import read_run_budget
from runtime_service.services.dearflow_agent.capabilities import (
    CHART_NAMES,
    DEAR_TOOLS,
    MEMORY_READ_TOOLS,
    MEMORY_WRITE_TOOLS,
    SKILL_READ_TOOLS,
    SKILL_WRITE_TOOLS,
    WORK_TOOLS,
    configured_mcp_names,
)
from runtime_service.services.dearflow_agent.memory_access import memory_allowed
from runtime_service.services.dearflow_agent.middleware.clarification import (
    ClarificationBatchGuard,
)
from runtime_service.services.dearflow_agent.middleware.delegation import (
    DelegationConcurrencyMiddleware,
)
from runtime_service.services.dearflow_agent.middleware.memory import (
    MemoryContextMiddleware,
)
from runtime_service.services.dearflow_agent.middleware.skills import (
    ExecutionSkillsMiddleware,
)
from runtime_service.services.dearflow_agent.modes import apply_reasoning, resolve_mode
from runtime_service.services.dearflow_agent.prompts import SYSTEM_PROMPT
from runtime_service.services.dearflow_agent.subagents.researcher import researcher
from runtime_service.services.dearflow_agent.tools.arxiv_search import build_arxiv_tool
from runtime_service.services.dearflow_agent.tools.deployment import (
    build_deployment_tool,
)
from runtime_service.services.dearflow_agent.tools.github import build_github_tool
from runtime_service.services.dearflow_agent.tools.human_input import (
    request_information,
)
from runtime_service.services.dearflow_agent.tools.mcp import load_mcp_tools
from runtime_service.services.dearflow_agent.tools.media import build_media_tools
from runtime_service.services.dearflow_agent.tools.memory import build_memory_tools
from runtime_service.services.dearflow_agent.tools.search import build_research_tools
from runtime_service.services.dearflow_agent.tools.skills import build_skill_tools
from runtime_service.services.dearflow_agent.tools.web_guidelines import (
    fetch_web_guidelines,
)
from runtime_service.services.dearflow_agent.workspace.backend import (
    DearWorkspaceBackend,
    WorkspaceMiddleware,
    build_backend,
    skills_hash,
)
from runtime_service.tools.artifacts import build_artifact_tool
from runtime_service.tools.chart import build_chart_tools
from runtime_service.tools.errors import on_tool_error
from runtime_service.tools.images import ImageWorkspace

PERMISSIONS = [
    FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny"),
    FilesystemPermission(
        operations=["write"],
        paths=["/conversation_history/**", "/large_tool_results/**"],
        mode="deny",
    ),
]
APPROVALS = {
    name: {"allowed_decisions": ["approve", "edit", "reject"]}
    for name in (
        "write_file",
        "edit_file",
        "execute",
        "present_artifacts",
        "generate_image",
        "edit_image",
        "deploy_preview",
        *CHART_NAMES,
        *MEMORY_WRITE_TOOLS,
        *SKILL_WRITE_TOOLS,
    )
}

_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="dearflow-research-p2",
    max_tokens=4096,
    optional_tool_names=(*DEAR_TOOLS, *configured_mcp_names()),
)
_EXECUTION_KEYS = {
    "thread_id",
    "assistant_id",
    "graph_id",
    "langgraph_auth_user",
    "checkpoint_id",
    "checkpoint_ns",
    "checkpoint_map",
}


def _get_env_limit(key: str, fallback: int) -> int:
    try:
        val = os.getenv(key)
        if val is not None and val.strip():
            parsed = int(val.strip())
            return parsed if parsed > 0 else fallback
    except (ValueError, TypeError):
        pass
    return fallback


async def get_agent(config: RunnableConfig) -> Pregel:
    with StartupDiagnostics("dearflow_agent") as startup:
        return await _build_agent(config, startup)


async def _build_agent(config: RunnableConfig, startup: StartupDiagnostics) -> Pregel:
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
    run_budget = None
    workspace = None
    resolved = None
    connection = None
    bundle = ModelConnectionBundle()
    fallback_model = None
    auxiliary_model = None
    mode = resolve_mode(None)
    defaults = replace(
        _DEFAULTS, optional_tool_names=(*DEAR_TOOLS, *configured_mcp_names())
    )
    mcp_tools = []
    reasoning = {"reasoning": "probe_only"}
    governance = os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") == "1"
    memory_enabled = False
    if executing:
        thread_id = configurable.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")
        if facts.scope.assistant_id != "dearflow_agent":
            raise RuntimeAuthError("runtime.auth.invalid_principal", "assistant_id")
        startup.authorize(config, facts)
        with startup.phase("factory.context_resolution"):
            context = parse_runtime_context(config.get("context"))
            if context.offload_conversation and not context_management_enabled():
                raise RuntimeAuthError("runtime.context.offload_disabled")
            mode = resolve_mode(context.execution_mode)
            if runtime_context_hash(context) != facts.context_hash:
                raise RuntimeAuthError(
                    "runtime.auth.context_hash_mismatch", "context_hash"
                )
            if facts.scope.thread_id is not None and facts.scope.thread_id != thread_id:
                raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")
            run_budget = read_run_budget(config)
        with startup.phase("factory.memory_policy"):
            memory_enabled = (
                governance
                and not context.offload_conversation
                and await memory_allowed(user, thread_id)
            )
        requested_mcp = tuple(
            n for n in configured_mcp_names() if n not in facts.policy.denied_tool_names
        )
        # Authorize requested names before any MCP connection or schema discovery.
        resolved = resolve_runtime_config(
            principal=facts.principal,
            context=context,
            policy=facts.policy,
            defaults=defaults,
        )
        startup.metadata["model_id"] = resolved.model_id
        with startup.phase("factory.mcp_tools"):
            if not context.offload_conversation:
                mcp_tools = await load_mcp_tools(
                    config, facts.principal, requested_mcp, DEAR_TOOLS
                )
        with startup.phase("factory.model_connection"):
            bundle = await fetch_model_bundle(
                configurable.get("runtime_model_ref"),
                model_id=resolved.model_id,
                project_id=facts.principal.project_id,
                allowed_model_ids=facts.policy.allowed_model_ids,
            )
            connection = bundle.primary
        with startup.phase("factory.model_build"):
            fallback_model = build_fallback_model(resolved, bundle)
            model = build_model(resolved, connection=connection, max_retries=0)
            model, reasoning = apply_reasoning(model, mode)
            auxiliary_model = (
                apply_reasoning(
                    build_model(resolved, connection=connection, max_retries=0), mode
                )[0]
                if governance
                else model
            )
        with startup.phase("factory.workspace"):
            workspace = DearWorkspaceBackend(
                facts.principal.tenant_id, facts.principal.project_id, thread_id
            )
    else:
        # Schema-only client: no request is sent, and WorkspaceMiddleware rejects invocation.
        model = ChatOpenAI(model="schema-only", api_key="schema-only", max_retries=0)
        auxiliary_model = model

    backend = build_backend(workspace)
    document_middleware = DocumentToolsMiddleware(
        None if workspace is None else workspace.root
    )
    artifact_tool = build_artifact_tool(None if workspace is None else workspace.root)
    research_tools = build_research_tools(workspace)
    github_tool = build_github_tool(workspace)
    arxiv_tool = build_arxiv_tool(workspace)
    chart_tools = [
        t
        for t in build_chart_tools(
            ImageWorkspace(None if workspace is None else workspace.root),
            include_spreadsheet=True,
        )
        if t.name in CHART_NAMES
    ]
    media_tools = build_media_tools(
        ImageWorkspace(None if workspace is None else workspace.root)
    )
    available = set(defaults.optional_tool_names)
    if not governance:
        available.difference_update(
            (
                *MEMORY_READ_TOOLS,
                *MEMORY_WRITE_TOOLS,
                *SKILL_READ_TOOLS,
                *SKILL_WRITE_TOOLS,
            )
        )
    if not memory_enabled:
        available.difference_update((*MEMORY_READ_TOOLS, *MEMORY_WRITE_TOOLS))
    if os.environ.get("RUNTIME_DEAR_PREVIEW_DEPLOY_ENABLED") != "1":
        available.discard("deploy_preview")
    if not mode.planning:
        available.discard("write_todos")
    if not mode.delegation:
        available.discard("task")
    if not os.environ.get("TAVILY_API_KEY"):
        available.discard("search_web")
    if not (
        os.environ.get("TAVILY_API_KEY")
        or os.environ.get("JINA_API_KEY")
        or os.environ.get("JINA_KEY")
    ):
        available.discard("fetch_page")

    if executing:
        available.difference_update(configured_mcp_names())
        available.update(tool.name for tool in mcp_tools)
        resolved = resolve_runtime_config(
            principal=facts.principal,
            context=context,
            policy=facts.policy,
            defaults=defaults,
            available_tool_names=frozenset(available),
        )

    def model_builder(next_config):
        if resolved is None:
            raise RuntimeAuthError("runtime.graph.probe_only")
        return (
            model
            if next_config == resolved
            else apply_reasoning(
                build_model(next_config, connection=connection, max_retries=0), mode
            )[0]
        )

    def middleware(tool_names: Sequence[str], *, child=False, tail=()):
        metadata = {**startup.metadata, "scope": "subagent" if child else "primary"}
        env_run_tool = _get_env_limit("AGENT_TOOL_CALL_LIMIT_PER_RUN", -1)
        env_thread_tool = _get_env_limit("AGENT_TOOL_CALL_LIMIT_PER_THREAD", -1)
        env_run_model = _get_env_limit("AGENT_MODEL_CALL_LIMIT_PER_RUN", -1)
        env_thread_model = _get_env_limit("AGENT_MODEL_CALL_LIMIT_PER_THREAD", -1)

        base_run_tool = env_run_tool if env_run_tool > 0 else mode.tool_limit
        base_thread_tool = (
            env_thread_tool if env_thread_tool > 0 else mode.tool_limit * 10
        )
        base_run_model = env_run_model if env_run_model > 0 else mode.model_limit
        base_thread_model = (
            env_thread_model if env_thread_model > 0 else mode.model_limit * 10
        )

        run_tool = min(48, base_run_tool) if child else base_run_tool
        thread_tool = min(48, base_thread_tool) if child else base_thread_tool
        run_model = min(24, base_run_model) if child else base_run_model
        thread_model = min(24, base_thread_model) if child else base_thread_model

        offloading = (
            [
                ConversationOffloadingMiddleware(
                    model,
                    backend,
                    output_budget_tokens=(
                        resolved.max_tokens
                        if resolved.max_tokens is not None
                        else (
                            4096
                            if (executing and context.offload_conversation)
                            else None
                        )
                    ),
                    manual=bool(
                        not child and executing and context.offload_conversation
                    ),
                )
            ]
            if context_management_enabled() and executing
            else []
        )
        wrapup_target = (
            run_budget if run_budget is not None else resolve_wrapup_after_seconds()
        )
        return [
            TokenBudgetMiddleware(root=not child),
            *(
                [ModelResilienceSummarizationMiddleware(auxiliary_model, backend)]
                if bundle.policy.enabled
                else []
            ),
            RuntimeConfigMiddleware(
                defaults=defaults,
                base_model=model,
                model_builder=model_builder,
                tool_names=tool_names,
            ),
            *offloading,
            *([MaintenanceSafeToolCallsMiddleware()] if offloading else []),
            WorkspaceMiddleware(
                workspace,
                resolved.config_hash if resolved else None,
                metadata=metadata,
            ),
            ExecutionBudgetMiddleware(
                run_limit=run_model,
                thread_limit=thread_model,
                exit_behavior="error",
                scope="subagent" if child else "primary",
                graph_key="dearflow_agent",
            ),
            ToolCallLimitMiddleware(
                run_limit=run_tool,
                thread_limit=thread_tool,
                exit_behavior="error",
            ),
            # Bound the whole reasoning response, not just the time to its first token.
            *(
                [TimeoutWrapupMiddleware(wrapup_target, graph_key="dearflow_agent")]
                if not child
                else []
            ),
            *(
                [
                    ModelResilienceMiddleware(
                        bundle.policy,
                        fallback_model,
                        primary_model_id=resolved.model_id,
                        context_recovery=True,
                    )
                ]
                if bundle.policy.enabled
                else []
            ),
            RuntimeModelRetryMiddleware(metadata, delegated=child),
            ModelErrorMiddleware(
                startup.metadata, scope="subagent" if child else "primary"
            ),
            ModelCallTimeoutMiddleware(
                bundle.policy.attempt_timeout_seconds if bundle.policy.enabled else None
            ),
            ToolErrorMiddleware(
                on_error=partial(on_tool_error, readonly_roles={"general-purpose"})
            ),
            *(
                []
                if child
                else [DelegatedTaskRetryMiddleware({"general-purpose"}, metadata)]
            ),
            *tail,
            *([ContextBudgetMiddleware(offloading[0])] if offloading else []),
        ]

    with startup.phase("factory.agent_compile"):
        agent = create_deep_agent(
            model=model,
            system_prompt=SYSTEM_PROMPT
            + "\n<current_date>"
            + datetime.now(UTC).date().isoformat()
            + " UTC</current_date>",
            tools=[
                request_information,
                artifact_tool,
                *research_tools,
                github_tool,
                arxiv_tool,
                fetch_web_guidelines,
                *chart_tools,
                *media_tools,
                *mcp_tools,
                *(build_memory_tools() if memory_enabled else []),
                *build_skill_tools(workspace, auxiliary_model),
                build_deployment_tool(workspace),
            ],
            backend=backend,
            skills=None,
            permissions=PERMISSIONS,
            interrupt_on=interrupts_for_access_policy(
                context.access_policy if executing else None, APPROVALS
            ),
            subagents=[
                researcher(
                    research_tools if mode.delegation else [],
                    [
                        FilesystemMiddleware(
                            backend=backend,
                            tools=["read_file"],
                            _permissions=PERMISSIONS,
                        ),
                        *middleware(
                            available & {"read_file", "search_web", "fetch_page"}
                            if mode.delegation
                            else (),
                            child=True,
                        ),
                    ],
                )
            ],
            middleware=[
                ExecutionSkillsMiddleware(
                    workspace, backend, custom_enabled=governance
                ),
                FilesystemMiddleware(
                    backend=backend,
                    tools=list(WORK_TOOLS),
                    _permissions=PERMISSIONS,
                    max_execute_timeout=60,
                ),
                *middleware(
                    available,
                    tail=[
                        *([TodoListMiddleware()] if mode.planning else []),
                        ToolCallLimitMiddleware(
                            tool_name="task",
                            run_limit=10,
                            thread_limit=10,
                            exit_behavior="error",
                        ),
                        DelegationConcurrencyMiddleware(),
                        MessageQueueMiddleware(),
                        ClarificationBatchGuard(),
                        document_middleware,
                        *(
                            [MemoryContextMiddleware(auxiliary_model or model)]
                            if memory_enabled
                            else []
                        ),
                    ],
                ),
            ],
            state_schema=ConversationOffloadingMiddleware.state_schema,
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
    bound["recursion_limit"] = min(
        max(int(config.get("recursion_limit", 1000)), 1), 1000
    )
    agent = agent.with_config(bound)
    if not executing:
        return agent
    return with_langfuse_tracing(
        agent,
        bound,
        graph_id="dearflow_agent",
        startup=startup,
        trusted_metadata={
            "user_id": facts.principal.user_id,
            "tenant_id": facts.principal.tenant_id,
            "project_id": facts.principal.project_id,
            "model_id": resolved.model_id,
            "config_hash": resolved.config_hash,
            "prompt_version": resolved.prompt_version,
            "prompt_hash": resolved.prompt_hash,
            "policy_version": resolved.policy_version,
            "policy_hash": hashlib.sha256(
                json.dumps(
                    asdict(facts.policy), sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
            "request_id": facts.request_id,
            "platform_trace_id": facts.platform_trace_id,
            "execution_mode": mode.name,
            "effective_reasoning": reasoning,
            "skills_hash": skills_hash(),
        },
    )


__all__ = ["get_agent"]
