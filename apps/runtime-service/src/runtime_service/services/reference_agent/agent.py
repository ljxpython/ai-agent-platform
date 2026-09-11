"""Composition root for the Runtime-aware reference agent."""

from __future__ import annotations

from collections.abc import Mapping

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.pregel import Pregel

from runtime_service.middlewares import (
    MessageQueueMiddleware,
    ModelCallTimeoutMiddleware,
    RuntimeConfigMiddleware,
)
from runtime_service.observability import with_langfuse_tracing
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeScope,
    build_model,
    parse_runtime_context,
    reject_untrusted_configurable,
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.runtime.errors import RuntimeAuthError
from runtime_service.runtime.modeling import fetch_model_connection
from runtime_service.services.reference_agent.prompts import SYSTEM_PROMPT
from runtime_service.services.reference_agent.tools import read_reference

_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="reference-agent-v3",
    optional_tool_names=("read_reference",),
)
_TOOL_PERMISSIONS = {"read_reference": "runtime.tool.read"}


def _local_test_facts() -> VerifiedDelegation:
    return VerifiedDelegation(
        RuntimePrincipal(
            "local-user",
            "local-tenant",
            "reference-project",
            "developer",
            ("runtime.tool.read",),
        ),
        RuntimePolicy(
            "reference-agent-local-v1",
            ("deepseek:DeepSeek-V4-Flash",),
            ("read_reference",),
        ),
        RuntimeScope("local-tenant", "reference-project"),
        "",
    )


def _runtime_model(config: RunnableConfig) -> BaseChatModel | None:
    configurable = config.get("configurable") or {}
    candidate = (
        configurable.get("_runtime_model")
        if isinstance(configurable, Mapping)
        else None
    )
    return candidate if isinstance(candidate, BaseChatModel) else None


def _runtime_fallback_model(config: RunnableConfig) -> BaseChatModel | None:
    configurable = config.get("configurable") or {}
    candidate = (
        configurable.get("_runtime_fallback_model")
        if isinstance(configurable, Mapping)
        else None
    )
    return candidate if isinstance(candidate, BaseChatModel) else None


def _build_runtime_model(config: object, connection: Mapping[str, str] | None) -> BaseChatModel:
    if connection is None:
        return build_model(config)  # type: ignore[arg-type]
    return build_model(config, connection=connection)  # type: ignore[arg-type]


def _runtime_facts(config: RunnableConfig) -> VerifiedDelegation:
    configurable = config.get("configurable") or {}
    if not isinstance(configurable, Mapping):
        raise RuntimeAuthError("runtime.auth.missing_principal")
    reject_untrusted_configurable(configurable)
    auth_user = configurable.get("langgraph_auth_user")
    if auth_user is not None:
        return verified_delegation_from_user(auth_user)
    if configurable.get("_runtime_model") is not None:
        return _local_test_facts()
    raise RuntimeAuthError("runtime.auth.missing_principal")


async def _runtime_model_connection(
    config: RunnableConfig,
    *,
    model_id: str,
    project_id: str,
) -> dict[str, str] | None:
    """Fetch the selected model connection; only the opaque reference crosses GraphHarbor."""
    configurable = config.get("configurable") or {}
    if not isinstance(configurable, Mapping):
        return None
    return await fetch_model_connection(
        configurable.get("runtime_model_ref"),
        model_id=model_id,
        project_id=project_id,
    )


def _runtime_identity_and_policy(
    config: RunnableConfig,
) -> tuple[RuntimePrincipal, RuntimePolicy]:
    facts = _runtime_facts(config)
    return facts.principal, facts.policy


async def get_agent(config: RunnableConfig) -> Pregel:
    """Resolve Runtime values and return the compiled reference graph."""

    configurable = config.get("configurable") or {}
    probe_only = bool(configurable) and set(configurable) <= {
        "graph_id", "thread_id", "checkpoint_id", "checkpoint_ns",
    }
    runtime_model = _runtime_model(config)
    local_test_auth = (
        isinstance(configurable, Mapping)
        and configurable.get("_runtime_test_local_auth") is True
    )
    facts = None if probe_only else _runtime_facts(config)
    principal, policy = (facts.principal, facts.policy) if facts else (None, None)
    connection = None
    resolved = None
    if facts:
        raw_context = config.get("context")
        context = parse_runtime_context(raw_context)
        if raw_context is not None and facts.context_hash != runtime_context_hash(context):
            raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
        resolved = resolve_runtime_config(
            principal=principal,
            context=context,
            policy=policy,
            defaults=_DEFAULTS,
            tool_permissions=_TOOL_PERMISSIONS,
        )
        connection = None if runtime_model is not None else await _runtime_model_connection(
            config, model_id=resolved.model_id, project_id=principal.project_id,
        )
    model = (
        ChatOpenAI(model="schema-only", api_key="schema-only", max_retries=0)
        if probe_only else runtime_model or _build_runtime_model(resolved, connection)
    )
    fallback_model = _runtime_fallback_model(config) if runtime_model is not None else None
    model_retry_enabled = (
        runtime_model is not None
        and isinstance(configurable, Mapping)
        and configurable.get("_runtime_model_retry") is True
    )

    def _tool_error(exc: Exception, request) -> str | None:
        if isinstance(exc, (ConnectionError, ValueError)):
            return (
                f"Tool `{request.tool_call['name']}` failed with {type(exc).__name__}; "
                "fix the input and retry."
            )
        return None

    def model_builder(next_config):
        next_connection = connection if resolved and next_config.model_id == resolved.model_id else None
        return _build_runtime_model(next_config, next_connection)

    middleware = [
        RuntimeConfigMiddleware(
            principal=principal,
            policy=policy,
            defaults=_DEFAULTS,
            base_model=model,
            model_builder=model_builder,
            tool_permissions=_TOOL_PERMISSIONS,
            local_fallback=runtime_model is not None or local_test_auth,
            probe_only=probe_only,
        ),
        ModelCallLimitMiddleware(run_limit=10, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=10, exit_behavior="error"),
        ToolErrorMiddleware(on_error=_tool_error, tools=["read_reference"]),
        ToolRetryMiddleware(
            max_retries=1,
            tools=["read_reference"],
            retry_on=(ConnectionError,),
            on_failure="error",
            initial_delay=0,
            jitter=False,
        ),
        *(
            [ModelFallbackMiddleware(fallback_model)]
            if fallback_model is not None
            else []
        ),
        *(
            [
                ModelRetryMiddleware(
                    max_retries=1,
                    retry_on=(ConnectionError,),
                    on_failure="error",
                    initial_delay=0,
                    jitter=False,
                )
            ]
            if model_retry_enabled
            else []
        ),
        ModelCallTimeoutMiddleware(timeout_seconds=30),
        MessageQueueMiddleware(),
    ]
    agent = create_agent(
        model=model,
        tools=[read_reference],
        system_prompt=_DEFAULTS.system_prompt,
        middleware=middleware,
        context_schema=RuntimeContext,
        name="reference_agent",
    )

    if probe_only:
        return agent

    bound_config = dict(config)
    configurable = dict(bound_config.get("configurable") or {})
    configurable.pop("_runtime_model", None)
    configurable.pop("_runtime_fallback_model", None)
    configurable.pop("_runtime_model_retry", None)
    bound_config["configurable"] = configurable
    return with_langfuse_tracing(
        agent,
        bound_config,
        graph_id="reference_agent",
        trusted_metadata={
            "user_id": principal.user_id,
            "tenant_id": principal.tenant_id,
            "project_id": principal.project_id,
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
