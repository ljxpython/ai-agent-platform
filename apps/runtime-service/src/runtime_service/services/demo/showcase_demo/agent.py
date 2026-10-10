"""The only composition root: official Deep Agents plus Runtime policy and tracing."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from functools import partial

from deepagents import create_deep_agent
from deepagents.middleware import FilesystemMiddleware
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
    context_management_enabled,
    resolve_wrapup_after_seconds,
)
from runtime_service.middlewares.images import ImageToolsMiddleware
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
from runtime_service.runtime.capabilities import SHOWCASE_TOOLS
from runtime_service.runtime.run_budget import read_run_budget
from runtime_service.services.demo.showcase_demo.backend import (
    WorkspaceMiddleware,
    build_backend,
    create_workspace,
)
from runtime_service.services.demo.showcase_demo.chart import build_chart_tools
from runtime_service.services.demo.showcase_demo.prompts import SYSTEM_PROMPT
from runtime_service.services.demo.showcase_demo.subagents import (
    APPROVALS,
    PERMISSIONS,
    READ_TOOLS,
    WORK_TOOLS,
    build_subagents,
)
from runtime_service.services.demo.showcase_demo.tools import fetch_documentation
from runtime_service.tools.artifacts import build_artifact_tool
from runtime_service.tools.background import build_background_tools
from runtime_service.tools.errors import on_tool_error
from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.background import BackgroundBinding

_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="showcase-demo-v3",
    max_tokens=4096,
    optional_tool_names=SHOWCASE_TOOLS,
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


async def get_agent(config: RunnableConfig) -> Pregel:
    with StartupDiagnostics("showcase_demo") as startup:
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
    if executing:
        thread_id = configurable.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")
        startup.authorize(config, facts)
        with startup.phase("factory.context_resolution"):
            context = parse_runtime_context(config.get("context"))
            if context.offload_conversation and not context_management_enabled():
                raise RuntimeAuthError("runtime.context.offload_disabled")
            if runtime_context_hash(context) != facts.context_hash:
                raise RuntimeAuthError(
                    "runtime.auth.context_hash_mismatch", "context_hash"
                )
            if facts.scope.thread_id is not None and facts.scope.thread_id != thread_id:
                raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")
            run_budget = read_run_budget(config)
            resolved = resolve_runtime_config(
                principal=facts.principal,
                context=context,
                policy=facts.policy,
                defaults=_DEFAULTS,
            )
        startup.metadata["model_id"] = resolved.model_id
        with startup.phase("factory.model_connection"):
            bundle = await fetch_model_bundle(
                configurable.get("runtime_model_ref"),
                model_id=resolved.model_id,
                project_id=facts.principal.project_id,
                allowed_model_ids=facts.policy.allowed_model_ids,
            )
            connection = bundle.primary
        with startup.phase("factory.model_build"):
            model = build_model(resolved, connection=connection, max_retries=0)
            fallback_model = build_fallback_model(resolved, bundle)
        with startup.phase("factory.workspace"):
            workspace = create_workspace(
                facts.principal.tenant_id, facts.principal.project_id, thread_id
            )
    else:
        # Schema-only client: no request is sent, and WorkspaceMiddleware rejects invocation.
        bundle = ModelConnectionBundle()
        fallback_model = None
        model = ChatOpenAI(model="schema-only", api_key="schema-only", max_retries=0)

    auxiliary_model = (
        build_model(resolved, connection=connection)
        if (resolved and bundle.policy.enabled)
        else model
    )

    backend = build_backend(workspace)
    image_workspace = ImageWorkspace(
        None if workspace is None else workspace.cwd / "workspace"
    )
    image_middleware = ImageToolsMiddleware(image_workspace)
    document_middleware = DocumentToolsMiddleware(
        None if workspace is None else workspace.cwd / "workspace"
    )
    chart_tools = build_chart_tools(image_workspace)
    image_names = tuple(tool.name for tool in image_middleware.tools)
    document_names = tuple(tool.name for tool in document_middleware.tools)

    def model_builder(next_config):
        if resolved is None:
            raise RuntimeAuthError("runtime.graph.probe_only")
        return (
            model
            if next_config == resolved
            else build_model(next_config, connection=connection, max_retries=0)
        )

    def _env_int(name: str, default: int) -> int:
        import os

        raw = os.getenv(name, "").strip()
        return int(raw) if raw.isdigit() and int(raw) > 0 else default

    def middleware(
        tool_names: Sequence[str],
        *,
        child: bool = False,
        readonly: bool = False,
        tail=(),
    ):
        metadata = {**startup.metadata, "scope": "subagent" if child else "primary"}
        offloading = (
            [
                ConversationOffloadingMiddleware(
                    model,
                    backend,
                    output_budget_tokens=(
                        resolved.max_tokens
                        if resolved.max_tokens is not None
                        else (4096 if context.offload_conversation else None)
                    ),
                    manual=bool(not child and context.offload_conversation),
                )
            ]
            if context_management_enabled() and executing
            else []
        )
        return [
            *(
                [ModelResilienceSummarizationMiddleware(auxiliary_model, backend)]
                if bundle.policy.enabled
                else []
            ),
            RuntimeConfigMiddleware(
                defaults=_DEFAULTS,
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
                run_limit=_env_int("AGENT_MODEL_CALL_LIMIT_PER_RUN", 50),
                thread_limit=_env_int("AGENT_MODEL_CALL_LIMIT_PER_THREAD", 500),
                exit_behavior="error",
                scope="subagent" if child else "primary",
                graph_key="showcase_demo",
            ),
            ToolCallLimitMiddleware(
                run_limit=_env_int("AGENT_TOOL_CALL_LIMIT_PER_RUN", 100),
                thread_limit=_env_int("AGENT_TOOL_CALL_LIMIT_PER_THREAD", 1000),
                exit_behavior="error",
            ),
            *(
                [
                    TimeoutWrapupMiddleware(
                        run_budget
                        if run_budget is not None
                        else resolve_wrapup_after_seconds(),
                        graph_key="showcase_demo",
                    )
                ]
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
            RuntimeModelRetryMiddleware(metadata, delegated=readonly),
            ModelErrorMiddleware(
                startup.metadata, scope="subagent" if child else "primary"
            ),
            ModelCallTimeoutMiddleware(
                bundle.policy.attempt_timeout_seconds if bundle.policy.enabled else None
            ),
            ToolErrorMiddleware(
                on_error=partial(on_tool_error, readonly_roles={"research"})
            ),
            *([] if child else [DelegatedTaskRetryMiddleware({"research"}, metadata)]),
            *tail,
            *([ContextBudgetMiddleware(offloading[0])] if offloading else []),
        ]

    with startup.phase("factory.agent_compile"):
        agent = create_deep_agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[
                fetch_documentation,
                build_artifact_tool(image_workspace.root),
                *build_background_tools(
                    None
                    if workspace is None
                    else BackgroundBinding(
                        workspace.cwd / "workspace",
                        os.getenv("RUNTIME_SHOWCASE_IMAGE", "python:3.13-slim"),
                        workspace.scope,
                        "showcase_demo",
                    ),
                    completion=bool(configurable.get("platform_background_completion")),
                ),
            ],
            backend=backend,
            skills=["/skills/"],
            permissions=PERMISSIONS,
            interrupt_on=interrupts_for_access_policy(
                context.access_policy if executing else None,
                {
                    **APPROVALS,
                    "background_execute": {
                        "allowed_decisions": ["approve", "edit", "reject"]
                    },
                    "cancel_background_task": {
                        "allowed_decisions": ["approve", "reject"]
                    },
                    "present_artifacts": {
                        "allowed_decisions": ["approve", "edit", "reject"]
                    },
                },
            ),
            subagents=build_subagents(
                model,
                backend,
                lambda names: middleware(
                    names, child=True, readonly=set(names) <= set(READ_TOOLS)
                ),
                chart_tools,
                context.access_policy if executing else None,
            ),
            middleware=[
                FilesystemMiddleware(
                    backend=backend,
                    tools=list(WORK_TOOLS),
                    _permissions=PERMISSIONS,
                    max_execute_timeout=60,
                ),
                *middleware(
                    (*_DEFAULTS.optional_tool_names, *image_names, *document_names),
                    tail=[
                        image_middleware,
                        document_middleware,
                        TodoListMiddleware(),
                        MessageQueueMiddleware(),
                    ],
                ),
            ],
            state_schema=ConversationOffloadingMiddleware.state_schema,
            context_schema=RuntimeContext,
            name="showcase_demo",
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
        graph_id="showcase_demo",
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
            "request_id": facts.request_id,
            "platform_trace_id": facts.platform_trace_id,
        },
    )


__all__ = ["get_agent"]
