"""Shared HMAC internal callback client and agent builder for evaluation expert graphs."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException
from langchain_openai import ChatOpenAI
from langgraph.pregel import Pregel

from runtime_service.errors import RuntimeAuthError
from runtime_service.middlewares import (
    ExecutionBudgetMiddleware,
    MessageQueueMiddleware,
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
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.runtime.pii import pii_config_for_facts
from runtime_service.runtime.run_budget import RUN_BUDGET_KEY, read_run_budget


def eval_internal_post(
    purpose: str, path: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Call platform-api /api/evaluation/internal/* via HMAC signature."""
    endpoint = urlsplit(os.getenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", ""))
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    if not endpoint.hostname or not secret:
        raise ToolException("eval_platform_internal_unconfigured")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    stamp = str(int(time.time()))
    sig = hmac.new(
        secret.encode(),
        b"\n".join([purpose.encode(), stamp.encode(), body]),
        hashlib.sha256,
    ).hexdigest()
    url = urlunsplit((endpoint.scheme, endpoint.netloc, path, "", ""))
    try:
        with httpx.Client(
            timeout=15, follow_redirects=False, trust_env=False
        ) as client:
            resp = client.post(
                url,
                content=body,
                headers={
                    "content-type": "application/json",
                    "x-eval-time": stamp,
                    "x-eval-signature": sig,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            err_body = exc.response.json()
            err_obj = err_body.get("error") if isinstance(err_body, dict) else None
            if isinstance(err_obj, dict) and err_obj.get("message"):
                detail = str(err_obj["message"])
            elif isinstance(err_body, dict) and err_body.get("detail"):
                detail = str(err_body["detail"])
        except ValueError:
            detail = exc.response.text[:300]
        msg = (
            f"HTTP {exc.response.status_code}: {detail}"
            if detail
            else f"HTTP {exc.response.status_code}"
        )
        raise ToolException(msg) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolException(f"eval_internal_unavailable:{type(exc).__name__}") from exc


async def build_eval_expert_graph(
    config: RunnableConfig,
    *,
    graph_id: str,
    defaults: AgentDefaults,
    tools_factory,
    extra_middleware: Sequence[Any] = (),
    state_schema: Any = None,
) -> Pregel:
    """Shared LangGraph composition root for evaluation expert agents."""
    with StartupDiagnostics(graph_id) as startup:
        configurable = config.get("configurable") or {}
        if (
            not isinstance(configurable, Mapping)
            or "langgraph_auth_user" not in configurable
        ):
            return create_agent(
                model=ChatOpenAI(
                    model="schema-only", api_key="schema-only", max_retries=0
                ),
                tools=[],
                system_prompt=defaults.system_prompt,
                context_schema=RuntimeContext,
                name=graph_id,
            )
        facts = verified_delegation_from_user(configurable.get("langgraph_auth_user"))
        startup.authorize(config, facts)
        context = parse_runtime_context(config.get("context"))
        if config.get(
            "context"
        ) is not None and facts.context_hash != runtime_context_hash(context):
            raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
        resolved = resolve_runtime_config(
            principal=facts.principal,
            context=context,
            policy=facts.policy,
            defaults=defaults,
        )
        bundle = await fetch_model_bundle(
            configurable.get("runtime_model_ref"),
            model_id=resolved.model_id,
            project_id=facts.principal.project_id,
            allowed_model_ids=facts.policy.allowed_model_ids,
        )
        if not bundle.primary:
            raise RuntimeAuthError("eval_expert.managed_model_required")

        def model_builder(candidate):
            return build_model(candidate, connection=bundle.primary, max_retries=0)

        model = model_builder(resolved)
        pii = pii_config_for_facts(facts, configurable.get("thread_id"))
        budget = read_run_budget(config, required=facts.scope.operation == "run-create")
        startup.metadata["model_id"] = resolved.model_id
        middleware = [
            RuntimeConfigMiddleware(
                principal=facts.principal,
                policy=facts.policy,
                defaults=defaults,
                base_model=model,
                model_builder=model_builder,
            ),
            TokenBudgetMiddleware(exit_behavior="end"),
            ExecutionBudgetMiddleware(
                run_limit=24, exit_behavior="end", graph_key=graph_id
            ),
            ToolCallLimitMiddleware(run_limit=32, exit_behavior="error"),
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
            TimeoutWrapupMiddleware(budget, graph_key=graph_id),
            ModelErrorMiddleware(startup.metadata),
            ModelCallTimeoutMiddleware(
                bundle.policy.attempt_timeout_seconds if bundle.policy.enabled else None
            ),
            MessageQueueMiddleware(),
            *([PiiRedactionMiddleware(pii)] if pii.enabled else []),
            *extra_middleware,
        ]
        try:
            tools: Sequence[BaseTool] = tools_factory(facts, config)
        except TypeError:
            tools = tools_factory(facts)
        agent_kwargs: dict[str, Any] = {
            "model": model,
            "tools": list(tools),
            "system_prompt": defaults.system_prompt,
            "middleware": middleware,
            "context_schema": RuntimeContext,
            "name": graph_id,
        }
        if state_schema is not None:
            agent_kwargs["state_schema"] = state_schema
        agent = create_agent(**agent_kwargs)
        bound = dict(config)
        bound["configurable"] = {
            key: value for key, value in configurable.items() if key != RUN_BUDGET_KEY
        }
        return with_langfuse_tracing(
            agent,
            bound,
            graph_id=graph_id,
            startup=startup,
            trusted_metadata={
                "user_id": facts.principal.user_id,
                "tenant_id": facts.principal.tenant_id,
                "project_id": facts.principal.project_id,
                "model_id": resolved.model_id,
                "request_id": facts.request_id,
                "platform_trace_id": facts.platform_trace_id,
            },
        )
