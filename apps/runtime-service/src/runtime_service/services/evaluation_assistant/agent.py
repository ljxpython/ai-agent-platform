"""Composition root for the managed, read-only evaluation assistant."""

from collections.abc import Mapping

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel

from runtime_service.errors import RuntimeAuthError
from runtime_service.middlewares import (
    ExecutionBudgetMiddleware,
    ModelCallTimeoutMiddleware,
    ModelErrorMiddleware,
    ModelResilienceMiddleware,
    PiiRedactionMiddleware,
    RuntimeConfigMiddleware,
    TimeoutWrapupMiddleware,
    TokenBudgetMiddleware,
)
from runtime_service.observability import with_langfuse_tracing
from runtime_service.observability.startup import StartupDiagnostics
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    build_fallback_model,
    build_model,
    fetch_model_bundle,
    parse_runtime_context,
    reject_untrusted_configurable,
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.runtime.pii import load_pii_redaction_config, pii_config_for_facts
from runtime_service.runtime.run_budget import RUN_BUDGET_KEY, read_run_budget
from runtime_service.services.evaluation_assistant.prompts import SYSTEM_PROMPT
from runtime_service.services.evaluation_assistant.tools import (
    make_tools,
    platform_evidence,
)
from runtime_service.services.evaluation_assistant.workflow import build_graph

TOOL_NAMES = ("decimal_calculate", "read_evidence", "validate_test_plan")
DEFAULTS = AgentDefaults(
    model_id="deepseek:DeepSeek-V4-Flash",
    system_prompt=SYSTEM_PROMPT,
    prompt_version="evaluation-assistant-v1",
    optional_tool_names=TOOL_NAMES,
)


async def get_agent(config: RunnableConfig) -> Pregel:
    with StartupDiagnostics("evaluation_assistant") as startup:
        return await build_agent(config, startup)


async def build_agent(config, startup):
    configurable = config.get("configurable") or {}
    if not isinstance(configurable, Mapping):
        raise RuntimeAuthError("runtime.auth.missing_principal")
    reject_untrusted_configurable(configurable)
    load_pii_redaction_config()
    if configurable and set(configurable) <= {
        "graph_id",
        "thread_id",
        "checkpoint_id",
        "checkpoint_ns",
    }:
        return build_graph(probe_only=True)
    facts = verified_delegation_from_user(configurable.get("langgraph_auth_user"))
    startup.authorize(config, facts)
    context = parse_runtime_context(config.get("context"))
    if config.get("context") is not None and facts.context_hash != runtime_context_hash(
        context
    ):
        raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
    run_budget = read_run_budget(config, required=facts.scope.operation == "run-create")
    resolved = resolve_runtime_config(
        principal=facts.principal,
        context=context,
        policy=facts.policy,
        defaults=DEFAULTS,
    )
    pii = pii_config_for_facts(facts, configurable.get("thread_id"))
    startup.metadata["model_id"] = resolved.model_id

    async def read_current(state, **kwargs):
        return await platform_evidence(
            facts,
            configurable["thread_id"],
            state["work_item_id"],
            state["job_id"],
            **kwargs,
        )

    async def model_agent_for(state, *, writer=None):
        async def read_bound(**kwargs):
            return await read_current(state, **kwargs)

        bundle = await fetch_model_bundle(
            configurable.get("runtime_model_ref"),
            model_id=resolved.model_id,
            project_id=facts.principal.project_id,
            allowed_model_ids=facts.policy.allowed_model_ids,
        )
        if not bundle.primary:
            raise RuntimeAuthError("evaluation.managed_model_required")

        def model_builder(candidate):
            return build_model(
                candidate,
                connection=bundle.primary,
                **({"max_retries": 0} if bundle.policy.enabled else {}),
            )

        model = model_builder(resolved)
        return create_agent(
            model=model,
            tools=make_tools(read_bound),
            system_prompt=SYSTEM_PROMPT,
            middleware=[
                TokenBudgetMiddleware(writer=writer),
                RuntimeConfigMiddleware(
                    principal=facts.principal,
                    policy=facts.policy,
                    defaults=DEFAULTS,
                    base_model=model,
                    model_builder=model_builder,
                ),
                ExecutionBudgetMiddleware(
                    run_limit=8,
                    exit_behavior="end",
                    graph_key="evaluation_assistant_model",
                    writer=writer,
                ),
                TimeoutWrapupMiddleware(
                    run_budget, writer=writer, graph_key="evaluation_assistant_model"
                ),
                ModelErrorMiddleware(startup.metadata),
                *(
                    [
                        ModelResilienceMiddleware(
                            bundle.policy,
                            build_fallback_model(resolved, bundle),
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
                *([PiiRedactionMiddleware(pii)] if pii.enabled else []),
            ],
            context_schema=RuntimeContext,
            name="evaluation_assistant_model",
            checkpointer=True,
        )

    bound_config = dict(config)
    bound_config["configurable"] = {
        k: v
        for k, v in configurable.items()
        if k
        not in {
            "_runtime_model",
            "_runtime_test_local_auth",
            RUN_BUDGET_KEY,
        }
    }
    bound_config.pop("run_id", None)
    graph = build_graph(
        model_agent_for,
        read_current=read_current,
        model_config=bound_config,
        runtime_context=context,
    )
    return with_langfuse_tracing(
        graph,
        bound_config,
        graph_id="evaluation_assistant",
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
