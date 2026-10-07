"""Scheduled Runs reauthorize once, before constructing a graph or its tools."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import replace
from functools import wraps

import httpx

from runtime_service.auth.acl_client import post_acl
from runtime_service.runtime.auth import verified_delegation_from_user
from runtime_service.runtime.errors import RuntimeAuthError
from runtime_service.runtime.resolver import (
    persisted_context_hash_v4,
    runtime_context_hash,
)

logger = logging.getLogger(__name__)
MARKER = "platform_scheduled_task"


async def _callback(payload):
    endpoint = os.environ.get("PLATFORM_THREAD_AUTHORIZATION_URL", "")
    if not endpoint.endswith("/thread-authorization"):
        raise RuntimeAuthError("scheduled_task_authorization_unavailable")
    endpoint = (
        endpoint.removesuffix("/thread-authorization") + "/scheduled-authorization"
    )
    secret = os.environ.get("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    if not secret:
        raise RuntimeAuthError("scheduled_task_authorization_unavailable")
    stamp = str(int(time.time()))
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    signature = hmac.new(
        secret.encode(),
        f"{stamp}\nscheduled-authorization\n{canonical}".encode(),
        hashlib.sha256,
    ).hexdigest()
    try:
        response = await post_acl(
            endpoint,
            payload,
            {"x-runtime-acl-timestamp": stamp, "x-runtime-acl-signature": signature},
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or type(result.get("allowed")) is not bool:
            raise ValueError("Invalid authorization response")
        return result
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeAuthError("scheduled_task_authorization_unavailable") from exc


async def _report(payload, error_code=None):
    try:
        await _callback(
            {
                **payload,
                "outcome": "error" if error_code else "success",
                "error_code": error_code,
            }
        )
    except RuntimeAuthError:
        # The durable native Run remains the fallback record if Platform is down.
        logger.warning(
            "Scheduled execution audit unavailable run_id=%s", payload["run_id"]
        )


class _ScheduledGraph:
    def __init__(self, graph, payload):
        self.graph, self.payload = graph, payload

    def __getattr__(self, name):
        return getattr(self.graph, name)

    @property
    def checkpointer(self):
        return self.graph.checkpointer

    @checkpointer.setter
    def checkpointer(self, value):
        self.graph.checkpointer = value

    async def ainvoke(self, *args, **kwargs):
        try:
            result = await self.graph.ainvoke(*args, **kwargs)
            if getattr(result, "interrupts", ()) or (
                isinstance(result, dict) and result.get("__interrupt__")
            ):
                await _report(self.payload, "scheduled_task_approval_required")
                raise RuntimeAuthError("scheduled_task_approval_required")
            await _report(self.payload)
            return result
        except Exception as exc:
            if (
                not isinstance(exc, RuntimeAuthError)
                or str(exc) != "scheduled_task_approval_required"
            ):
                await _report(self.payload, "scheduled_task_execution_failed")
            raise

    async def astream_events(self, *args, **kwargs):
        try:
            return _ScheduledStream(
                await self.graph.astream_events(*args, **kwargs), self.payload
            )
        except Exception:
            await _report(self.payload, "scheduled_task_execution_failed")
            raise


class _ScheduledStream:
    """Preserve LangGraph v3 streaming and turn unattended interrupts into errors."""

    def __init__(self, stream, payload):
        self.stream, self.payload = stream, payload

    async def __aenter__(self):
        try:
            await self.stream.__aenter__()
        except Exception:
            await _report(self.payload, "scheduled_task_execution_failed")
            raise
        return self

    async def __aexit__(self, kind, exc, tb):
        try:
            if exc is not None and str(exc) != "scheduled_task_approval_required":
                await _report(self.payload, "scheduled_task_execution_failed")
            return await self.stream.__aexit__(kind, exc, tb)
        except Exception:
            await _report(self.payload, "scheduled_task_execution_failed")
            raise

    def __aiter__(self):
        return self.stream.__aiter__()

    async def output(self):
        return await self.stream.output()

    async def interrupts(self):
        interrupts = await self.stream.interrupts()
        if interrupts:
            await _report(self.payload, "scheduled_task_approval_required")
            raise RuntimeAuthError("scheduled_task_approval_required")
        await _report(self.payload)
        return interrupts


def scheduled_execution(factory, *, agent_key):
    @wraps(factory)
    async def guarded(config):
        configurable = config.get("configurable") or {}
        if "cron_id" not in configurable and MARKER not in configurable:
            return await factory(config)
        marker = configurable.get(MARKER)
        if not isinstance(marker, dict) or not configurable.get("cron_id"):
            raise RuntimeAuthError("scheduled_task_signature_invalid")
        facts = verified_delegation_from_user(configurable.get("langgraph_auth_user"))
        thread_id = configurable.get("thread_id")
        if (
            facts.scope.operation != "run-create"
            or facts.scope.assistant_id != agent_key
            or (facts.scope.thread_id and facts.scope.thread_id != thread_id)
        ):
            raise RuntimeAuthError("scheduled_task_scope_denied")
        context = config.get("context") or {}
        if isinstance(context, dict) and context.get("offload_conversation") is True:
            raise RuntimeAuthError("scheduled_task_context_offload_forbidden")
        current_hash = runtime_context_hash(context)
        if facts.context_hash not in {current_hash, persisted_context_hash_v4(context)}:
            raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
        payload = {
            "tenant_id": facts.principal.tenant_id,
            "project_id": facts.principal.project_id,
            "owner_id": facts.principal.user_id,
            "credential_id": facts.credential_id,
            "agent_key": agent_key,
            "task_id": configurable["cron_id"],
            "run_id": config.get("metadata", {}).get("run_id"),
            "thread_id": thread_id,
            "task": marker,
            "context": context,
            "trigger": configurable.get("scheduled_trigger", "scheduled"),
        }
        result = await _callback(payload)
        if not result["allowed"]:
            raise RuntimeAuthError(result.get("error_code", "scheduled_task_denied"))
        user = dict(configurable["langgraph_auth_user"])
        # Only upgrade after the signed platform callback reauthorizes the saved cron.
        user["runtime_context_hash"] = current_hash
        user["runtime_policy"] = result["policy"]
        user["runtime_principal"] = {
            **user["runtime_principal"],
            "role": result["role"],
        }
        user["role"] = result["role"]
        user.update(
            policy_version=result["policy"]["version"],
            allowed_model_ids=result["policy"]["allowed_model_ids"],
            tool_overrides=result["policy"].get("tool_overrides", {}),
            tool_policy_version=result["policy"].get("tool_policy_version"),
        )
        configurable.update(result["configurable"], langgraph_auth_user=user)
        runtime = configurable.get("__pregel_runtime")
        if runtime and runtime.server_info:
            configurable["__pregel_runtime"] = replace(
                runtime, server_info=replace(runtime.server_info, user=user)
            )
        config["configurable"] = configurable
        try:
            return _ScheduledGraph(await factory(config), payload)
        except Exception:
            await _report(payload, "scheduled_task_execution_failed")
            raise

    return guarded
