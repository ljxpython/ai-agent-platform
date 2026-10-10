"""Composition root for the model-backed workflow agent."""

from __future__ import annotations

from collections.abc import Mapping

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.middlewares import (
    ExecutionBudgetMiddleware,
    ModelCallTimeoutMiddleware,
    ModelErrorMiddleware,
    ModelResilienceMiddleware,
    PlanModeMiddleware,
    RuntimeConfigMiddleware,
    TimeoutWrapupMiddleware,
    TokenBudgetMiddleware,
    resolve_wrapup_after_seconds,
)
from runtime_service.observability import with_langfuse_tracing
from runtime_service.observability.startup import StartupDiagnostics
from runtime_service.runtime import (
    AgentDefaults,
    ModelConnectionBundle,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeScope,
    build_fallback_model,
    build_model,
    fetch_model_bundle,
    parse_runtime_context,
    reject_untrusted_configurable,
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.runtime.capabilities import REFERENCE_TOOLS
from runtime_service.runtime.errors import RuntimeAuthError, RuntimeResolutionError
from runtime_service.runtime.run_budget import RUN_BUDGET_KEY, read_run_budget
from runtime_service.services.demo.workflow_demo.workflow import build_graph


@tool
def read_reference(topic: str) -> str:
    """Return a short reference note for a named topic."""

    return f"reference note: {topic.strip()}"


_DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=(
        "You are Workflow Demo, a real model-backed Runtime Agent. "
        "Answer the user's current question clearly and naturally."
    ),
    prompt_version="workflow-demo-v2",
    optional_tool_names=REFERENCE_TOOLS,
)


def _local_test_facts() -> VerifiedDelegation:
    return VerifiedDelegation(
        RuntimePrincipal(
            "local-user",
            "local-tenant",
            "workflow-project",
            "developer",
            ("runtime.tool.read",),
        ),
        RuntimePolicy(
            "workflow-demo-local-v2",
            (_DEFAULTS.model_id,),
            (),
            "local-tools-v2",
        ),
        RuntimeScope("local-tenant", "workflow-project"),
        "",
    )


def _configurable(config: RunnableConfig) -> Mapping[str, object]:
    value = config.get("configurable") or {}
    if not isinstance(value, Mapping):
        raise RuntimeAuthError("runtime.auth.missing_principal")
    reject_untrusted_configurable(value)
    return value


def _facts(config: RunnableConfig) -> tuple[VerifiedDelegation, bool]:
    configurable = _configurable(config)
    local = configurable.get("_runtime_test_local_auth") is True
    candidate = configurable.get("_runtime_model")
    auth_user = configurable.get("langgraph_auth_user")
    if auth_user is not None:
        return verified_delegation_from_user(auth_user), False
    if local or candidate is not None:
        return _local_test_facts(), True
    raise RuntimeAuthError("runtime.auth.missing_principal")


def _runtime_model(config: RunnableConfig, *, local: bool) -> BaseChatModel | None:
    candidate = _configurable(config).get("_runtime_model")
    if candidate is None:
        return None
    if not local:
        raise RuntimeAuthError("runtime.auth.test_adapter_forbidden")
    if not isinstance(candidate, BaseChatModel):
        raise RuntimeResolutionError(
            "runtime.model.invalid_test_adapter", "_runtime_model"
        )
    return candidate


async def get_agent(config: RunnableConfig) -> Pregel:
    with StartupDiagnostics("workflow_demo") as startup:
        return await _build_agent(config, startup)


async def _build_agent(config: RunnableConfig, startup: StartupDiagnostics) -> Pregel:
    """Build the real model-backed workflow Agent with optional HITL routing."""

    configurable = _configurable(config)
    if configurable and set(configurable) <= {
        "graph_id",
        "thread_id",
        "checkpoint_id",
        "checkpoint_ns",
    }:

        async def unavailable_model(_state):
            raise RuntimeAuthError("runtime.graph.probe_only")

        return build_graph(unavailable_model, probe_only=True)

    facts, local = _facts(config)
    startup.authorize(config, facts)
    with startup.phase("factory.context_resolution"):
        run_budget = read_run_budget(
            config, required=not local and facts.scope.operation == "run-create"
        )
        context = parse_runtime_context(config.get("context"))
        raw_context = config.get("context")
        if raw_context is not None and facts.context_hash != runtime_context_hash(
            context
        ):
            raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
        resolved = resolve_runtime_config(
            principal=facts.principal,
            context=context,
            policy=facts.policy,
            defaults=_DEFAULTS,
        )
    startup.metadata["model_id"] = resolved.model_id
    injected = _runtime_model(config, local=local)

    async def model_agent_for(state: Mapping[str, object], *, writer=None) -> object:
        with startup.phase("node.model_prepare"):
            bundle = (
                ModelConnectionBundle()
                if injected is not None
                else await fetch_model_bundle(
                    state.get("_runtime_model_ref")
                    or configurable.get("runtime_model_ref"),
                    model_id=resolved.model_id,
                    project_id=facts.principal.project_id,
                    allowed_model_ids=facts.policy.allowed_model_ids,
                )
            )
            model = injected or build_model(
                resolved,
                connection=bundle.primary,
                **({"max_retries": 0} if bundle.policy.enabled else {}),
            )
            fallback_model = build_fallback_model(resolved, bundle)

            def model_builder(candidate):
                return injected or build_model(
                    candidate,
                    connection=bundle.primary,
                    **({"max_retries": 0} if bundle.policy.enabled else {}),
                )

        return create_agent(
            model=model,
            tools=[read_reference],
            system_prompt=_DEFAULTS.system_prompt,
            middleware=[
                TokenBudgetMiddleware(writer=writer),
                RuntimeConfigMiddleware(
                    principal=facts.principal,
                    policy=facts.policy,
                    defaults=_DEFAULTS,
                    base_model=model,
                    local_fallback=local,
                    model_builder=model_builder,
                ),
                PlanModeMiddleware([read_reference]),
                ExecutionBudgetMiddleware(
                    run_limit=10,
                    exit_behavior="end",
                    graph_key="workflow_demo_model",
                    writer=writer,
                    wrapup_requested=bool(state.get("runtime_budget_wrapup")),
                ),
                TimeoutWrapupMiddleware(
                    run_budget
                    if run_budget is not None
                    else resolve_wrapup_after_seconds(),
                    writer=writer,
                    graph_key="workflow_demo_model",
                ),
                ModelErrorMiddleware(startup.metadata),
                *(
                    [
                        ModelResilienceMiddleware(
                            bundle.policy,
                            fallback_model,
                            primary_model_id=resolved.model_id,
                        )
                    ]
                    if bundle.policy.enabled
                    else []
                ),
                ModelCallTimeoutMiddleware(
                    bundle.policy.attempt_timeout_seconds
                    if bundle.policy.enabled
                    else None
                ),
            ],
            context_schema=RuntimeContext,
            name="workflow_demo_model",
            checkpointer=True,
        )

    bound_config = dict(config)
    bound_configurable = dict(bound_config.get("configurable") or {})
    bound_configurable.pop("_runtime_model", None)
    bound_configurable.pop("_runtime_test_local_auth", None)
    bound_configurable.pop(RUN_BUDGET_KEY, None)
    bound_config["configurable"] = bound_configurable
    bound_metadata = dict(bound_config.get("metadata") or {})
    bound_config["metadata"] = bound_metadata
    bound_config.pop("run_id", None)
    with startup.phase("factory.agent_compile"):
        graph = build_graph(
            model_agent_for,
            model_config=bound_config,
            runtime_context=context,
        )
    return with_langfuse_tracing(
        graph,
        bound_config,
        graph_id="workflow_demo",
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
