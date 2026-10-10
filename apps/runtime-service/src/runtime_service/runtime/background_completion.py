"""Reauthorize signed completions before model, MCP or Workspace construction."""

import asyncio
import hashlib
import hmac
import json
import os
from dataclasses import replace
from functools import wraps

from runtime_service.background_tasks.delivery import callback
from runtime_service.background_tasks.repository import (
    bind_completion_run,
    completion_allowed,
)
from runtime_service.runtime.auth import verified_delegation_from_user
from runtime_service.runtime.errors import RuntimeAuthError
from runtime_service.runtime.resolver import runtime_context_hash

MARKER = "platform_background_completion"


def verify_completion_marker(marker, facts, context, thread_id, agent_key):
    try:
        values, signature = marker["values"], marker["signature"]
        secret = os.environ["PLATFORM_RUNTIME_DELEGATION_SECRET"]
        canonical = json.dumps(
            values, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        expected = hmac.new(
            secret.encode(),
            ("background-completion\n" + canonical).encode(),
            hashlib.sha256,
        ).hexdigest()
        current_hash = runtime_context_hash(context or {})
        if (
            not secret
            or not hmac.compare_digest(signature, expected)
            or values["thread_id"] != str(thread_id)
            or values["graph_id"] != agent_key
            or values["tenant_id"] != facts.principal.tenant_id
            or values["project_id"] != facts.principal.project_id
            or values["owner_id"] != facts.principal.user_id
            or values["credential_id"] != facts.credential_id
            or values["context_hash"] != current_hash
            or facts.context_hash != current_hash
            or facts.scope.operation != "run-create"
            or facts.scope.assistant_id != agent_key
            or facts.scope.thread_id != values["thread_id"]
            or (context or {}).get("offload_conversation")
        ):
            raise ValueError()
        return values
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise RuntimeAuthError("background_task_denied") from exc


def background_completion_execution(factory, *, agent_key):
    @wraps(factory)
    async def guarded(config):
        configurable = config.get("configurable") or {}
        if not isinstance(configurable, dict):
            raise RuntimeAuthError("background_task_denied")
        if MARKER not in configurable:
            return await factory(config)
        marker = configurable[MARKER]
        if "cron_id" in configurable or "platform_scheduled_task" in configurable:
            raise RuntimeAuthError("background_task_denied")
        facts = verified_delegation_from_user(configurable.get("langgraph_auth_user"))
        values = verify_completion_marker(
            marker,
            facts,
            config.get("context"),
            configurable.get("thread_id"),
            agent_key,
        )
        try:
            run_id = str(
                config.get("metadata", {}).get("run_id")
                or configurable.get("run_id")
                or ""
            )
            if not run_id:
                raise ValueError()
            row = await asyncio.to_thread(
                bind_completion_run, values["task_id"], values["event_id"], run_id
            )
            if row is None or any(
                str(row[k]) != str(values[k])
                for k in (
                    "tenant_id",
                    "project_id",
                    "owner_id",
                    "credential_id",
                    "graph_id",
                    "thread_id",
                    "origin_run_id",
                )
            ):
                raise ValueError()
            if (
                await asyncio.to_thread(
                    completion_allowed, values["task_id"], values["event_id"], run_id
                )
                is None
            ):
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise RuntimeAuthError("background_task_denied") from exc
        result = await callback(
            "background-task-authorization",
            {
                "marker": marker,
                "run_id": run_id,
                "context": config.get("context") or {},
            },
        )
        if result.get("allowed") is not True:
            raise RuntimeAuthError("background_task_denied")
        # Authorization may wait; recheck the durable Stop tombstone before construction.
        if (
            await asyncio.to_thread(
                completion_allowed, values["task_id"], values["event_id"], run_id
            )
            is None
        ):
            raise RuntimeAuthError("background_task_denied")
        user = dict(configurable["langgraph_auth_user"])
        policy = result["policy"]
        user.update(
            runtime_policy=policy,
            role=result["role"],
            policy_version=policy["version"],
            allowed_model_ids=policy["allowed_model_ids"],
            tool_overrides=policy.get("tool_overrides", {}),
            tool_policy_version=policy.get("tool_policy_version"),
        )
        user["runtime_principal"] = {
            **user["runtime_principal"],
            "role": result["role"],
        }
        configurable.update(result["configurable"], langgraph_auth_user=user)
        if result.get("access_policy") not in {
            "review",
            "workspace_write",
            "full_access",
        }:
            raise RuntimeAuthError("background_task_denied")
        config["context"] = {
            **(config.get("context") or {}),
            "access_policy": result["access_policy"],
        }
        user["runtime_context_hash"] = runtime_context_hash(config["context"])
        runtime = configurable.get("__pregel_runtime")
        if runtime and runtime.server_info:
            configurable["__pregel_runtime"] = replace(
                runtime, server_info=replace(runtime.server_info, user=user)
            )
        config["configurable"] = configurable
        return await factory(config)

    return guarded
