"""The only composition root: official Deep Agents plus Runtime policy and tracing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from deepagents import create_deep_agent
from deepagents.middleware import FilesystemMiddleware
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.pregel import Pregel

from runtime_service.middlewares import (
    ModelCallTimeoutMiddleware,
    RuntimeConfigMiddleware,
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
from runtime_service.services.demo.showcase_demo.backend import (
    DockerWorkspaceBackend,
    WorkspaceMiddleware,
    build_backend,
)
from runtime_service.services.demo.showcase_demo.prompts import SYSTEM_PROMPT
from runtime_service.services.demo.showcase_demo.subagents import (
    APPROVALS,
    PERMISSIONS,
    WORK_TOOLS,
    build_subagents,
)
from runtime_service.services.demo.showcase_demo.tools import fetch_documentation

_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="showcase-demo-v2",
    optional_tool_names=(*WORK_TOOLS, "task", "write_todos", "fetch_documentation"),
)
_TOOL_PERMISSIONS = {
    **{
        name: "runtime.tool.read"
        for name in ("ls", "read_file", "glob", "grep", "fetch_documentation")
    },
    **{
        name: "runtime.tool.write"
        for name in ("write_file", "edit_file", "write_todos")
    },
    "execute": "runtime.tool.execute",
    "task": "runtime.tool.delegate",
}
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
    if executing:
        thread_id = configurable.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")
        context = parse_runtime_context(config.get("context"))
        if runtime_context_hash(context) != facts.context_hash:
            raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
        if facts.scope.thread_id is not None and facts.scope.thread_id != thread_id:
            raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")
        resolved = resolve_runtime_config(
            principal=facts.principal,
            context=context,
            policy=facts.policy,
            defaults=_DEFAULTS,
            tool_permissions=_TOOL_PERMISSIONS,
        )
        connection = await fetch_model_connection(
            configurable.get("runtime_model_ref"),
            model_id=resolved.model_id,
            project_id=facts.principal.project_id,
        )
        model = build_model(resolved, connection=connection)
        workspace = DockerWorkspaceBackend(
            facts.principal.tenant_id, facts.principal.project_id, thread_id
        )
    else:
        # Schema-only client: no request is sent, and WorkspaceMiddleware rejects invocation.
        model = ChatOpenAI(model="schema-only", api_key="schema-only", max_retries=0)

    backend = build_backend(workspace)

    def model_builder(next_config):
        if resolved is None:
            raise RuntimeAuthError("runtime.graph.probe_only")
        return (
            model
            if next_config == resolved
            else build_model(next_config, connection=connection)
        )

    def middleware(tool_names: Sequence[str]):
        return [
            RuntimeConfigMiddleware(
                defaults=_DEFAULTS,
                base_model=model,
                model_builder=model_builder,
                tool_permissions=_TOOL_PERMISSIONS,
                tool_names=tool_names,
            ),
            WorkspaceMiddleware(workspace),
            ModelCallLimitMiddleware(run_limit=12, exit_behavior="error"),
            ToolCallLimitMiddleware(run_limit=24, exit_behavior="error"),
            ModelCallTimeoutMiddleware(timeout_seconds=30),
        ]

    agent = create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[fetch_documentation],
        backend=backend,
        skills=["/skills/"],
        permissions=PERMISSIONS,
        interrupt_on=APPROVALS,
        subagents=build_subagents(model, backend, middleware),
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                tools=list(WORK_TOOLS),
                _permissions=PERMISSIONS,
                max_execute_timeout=60,
            ),
            *middleware(_DEFAULTS.optional_tool_names),
            TodoListMiddleware(),
        ],
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
    bound["recursion_limit"] = min(config.get("recursion_limit", 100), 100)
    agent = agent.with_config(bound)
    if not executing:
        return agent
    return with_langfuse_tracing(
        agent,
        bound,
        graph_id="showcase_demo",
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
