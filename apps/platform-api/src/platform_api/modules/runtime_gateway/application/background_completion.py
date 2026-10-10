"""Current authorization and stable native Run submission for completion events."""

import hashlib
import hmac
import json
import re
from dataclasses import replace
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from starlette.concurrency import run_in_threadpool

from platform_api.core.context import replace_current_request_context
from platform_api.core.context.runtime import DEFAULT_TENANT_ID
from platform_api.core.errors import ForbiddenError, PlatformApiError
from platform_api.modules.identity.actors import (
    load_service_account_actor,
    load_user_actor,
)
from platform_api.modules.projects.models import ProjectRecord
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.infra.sqlalchemy.repository import (
    RunRequestsRepository,
)
from platform_api.modules.scheduled_tasks.service import require_active_project

MARKER = "platform_background_completion"


class CompletionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    tenant_id: Annotated[str, Field(min_length=1, max_length=64)]
    project_id: UUID
    owner_id: Annotated[str, Field(min_length=1, max_length=255)]
    credential_id: UUID | None
    graph_id: Annotated[str, Field(min_length=1, max_length=128)]
    thread_id: UUID
    origin_run_id: UUID
    task_id: UUID
    event_id: UUID
    status: Literal["succeeded", "failed", "timed_out"]
    exit_code: Annotated[int, Field(strict=True, ge=-255, le=255)] | None
    reconcile_only: StrictBool = False


class CompletionAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid")
    marker: dict
    run_id: UUID
    context: dict


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sign_marker(values, secret):
    return {
        "values": values,
        "signature": hmac.new(
            secret.encode(),
            ("background-completion\n" + canonical(values)).encode(),
            hashlib.sha256,
        ).hexdigest(),
    }


def records(factory, data):
    with factory() as session:
        project = session.get(ProjectRecord, UUID(data["project_id"]))
        if project is None or data["tenant_id"] not in {
            DEFAULT_TENANT_ID,
            str(project.tenant_id),
        }:
            raise ForbiddenError(
                code="background_task_denied", message="Background task scope denied"
            )
        repository = RunRequestsRepository(session)
        source = repository.for_run(
            project_id=data["project_id"],
            thread_id=data["thread_id"],
            run_id=data["origin_run_id"],
        )
        existing = repository.get(
            project_id=data["project_id"],
            thread_id=data["thread_id"],
            idempotency_key="background:" + data["event_id"],
        )
        if (
            source is None
            or source.agent_key != data["graph_id"]
            or source.requested_by != (data["credential_id"] or data["owner_id"])
        ):
            raise ForbiddenError(
                code="background_task_denied", message="Background task source denied"
            )
        if source.context_snapshot.get("offload_conversation"):
            raise ForbiddenError(
                code="background_task_denied", message="Background task source denied"
            )
        return source, existing


def current_actor(factory, data):
    if data["owner_id"].startswith("service-account:"):
        actor = load_service_account_actor(
            session_factory=factory,
            subject=data["owner_id"],
            credential_id=data["credential_id"],
            project_id=data["project_id"],
        )
    elif data["credential_id"] is None:
        actor = load_user_actor(
            session_factory=factory,
            user_id=data["owner_id"],
            project_id=data["project_id"],
        )
    else:
        actor = None
    if actor is None:
        raise ForbiddenError(
            code="background_task_denied", message="Background task identity denied"
        )
    return actor


def authorize_snapshot(factory, gateway, data, context, actor):
    from platform_api.modules.runtime_policies.application import (
        RuntimePolicyOverlayService,
    )

    require_active_project(factory, data["project_id"])
    gateway._prepare_project_scope(
        actor=actor, project_id=data["project_id"], write=True
    )
    access = thread_access.get(factory, data["thread_id"])
    thread_access.require_action(actor, data["project_id"], access, "comment")
    gateway._assert_runtime_target_allowed(
        project_id=data["project_id"], assistant_id=data["graph_id"]
    )
    gateway._validate_run_options(
        project_id=data["project_id"], payload={"context": context}
    )
    policy_service = RuntimePolicyOverlayService(
        session_factory=factory, runtime_base_url=gateway._runtime_id
    )
    policy = policy_service.build_delegation_policy(project_id=data["project_id"])
    restrictions = policy_service.resolve_tool_overrides(
        project_id=data["project_id"], user_id=actor.user_id, graph_id=data["graph_id"]
    )
    if any(
        restrictions.get("tool_overrides", {}).get(name) is False
        for name in ("execute", "background_execute", "background_task")
    ):
        raise ForbiddenError(
            code="background_task_denied", message="Background task tools denied"
        )
    return {
        "version": str(policy["version"]),
        "allowed_model_ids": policy["allowed_model_ids"],
        **restrictions,
    }


def bind_request(request, actor, data):
    context = request.state.platform_context
    context = replace(
        context,
        actor=actor,
        project=replace(context.project, project_id=data["project_id"]),
        tenant=replace(context.tenant, tenant_id=data["tenant_id"]),
    )
    request.state.platform_context = context
    request.state.audit_project_id = data["project_id"]
    request.state.audit_metadata = {
        "task_id": data["task_id"],
        "event_id": data["event_id"],
        "thread_id": data["thread_id"],
        "origin_run_id": data["origin_run_id"],
    }
    replace_current_request_context(context)


async def deliver(request, payload):
    from platform_api.modules.runtime_gateway.application.service import (
        _runtime_context_snapshot,
    )
    from platform_api.modules.runtime_gateway.presentation.http import (
        get_runtime_gateway_service,
    )

    data = payload.model_dump(mode="json")
    factory = request.app.state.db_session_factory
    source, existing = await run_in_threadpool(records, factory, data)
    if existing and existing.run_id:
        return {"state": "accepted", "run_id": existing.run_id, "reason_code": None}
    if payload.reconcile_only:
        # No native read-by-key exists in post43; never turn receipt lookup into execution.
        return {
            "state": "unknown",
            "run_id": None,
            "reason_code": "background_task_delivery_unavailable",
        }
    try:
        actor = await run_in_threadpool(current_actor, factory, data)
        bind_request(request, actor, data)
        gateway = await run_in_threadpool(get_runtime_gateway_service, request, actor)
        thread = await gateway._load_thread(
            actor=actor,
            project_id=data["project_id"],
            thread_id=data["thread_id"],
            write=True,
            action="comment",
        )
        context = (
            existing.context_snapshot
            if existing
            else gateway._inject_thread_access_policy(
                thread=thread, payload={"context": source.context_snapshot}, actor=actor
            )["context"]
        )
        await run_in_threadpool(
            authorize_snapshot, factory, gateway, data, context, actor
        )
        upstream = await gateway._thread_upstream(
            project_id=data["project_id"], thread=thread, operation="read"
        )
        original = await upstream.get_thread_run(
            data["thread_id"], data["origin_run_id"]
        )
        if original.get("status") in {"error", "timeout"}:
            return {
                "state": "suppressed",
                "run_id": None,
                "reason_code": "background_task_denied",
            }
        runs = await upstream.list_thread_runs(data["thread_id"], {"limit": 100})
        recovered = next(
            (
                r
                for r in runs
                if (r.get("metadata") or {}).get("background_event_id")
                == data["event_id"]
            ),
            None,
        )
        if recovered is not None and existing is not None:
            await run_in_threadpool(
                save_receipt, factory, existing.id, recovered["run_id"]
            )
            return {
                "state": "accepted",
                "run_id": recovered["run_id"],
                "reason_code": None,
            }
        if any(r.get("status") in {"pending", "running"} for r in runs):
            return {
                "state": "pending",
                "run_id": None,
                "reason_code": "background_task_thread_busy",
            }
        state = await upstream.get_thread_state(data["thread_id"])
        if state.get("interrupts") or any(
            t.get("interrupts") for t in state.get("tasks", [])
        ):
            return {
                "state": "pending",
                "run_id": None,
                "reason_code": "background_task_approval_pending",
            }
        context_hash, context = _runtime_context_snapshot(
            {"params": {"context": context}}
        )
        values = {
            k: data[k]
            for k in (
                "tenant_id",
                "project_id",
                "owner_id",
                "credential_id",
                "graph_id",
                "thread_id",
                "origin_run_id",
                "task_id",
                "event_id",
            )
        }
        values["context_hash"] = context_hash
        marker = sign_marker(
            values, request.app.state.settings.runtime_delegation_secret
        )
        prompt = f"Workspace background task {data['task_id']} finished: status={data['status']}, exit_code={data['exit_code']}. This is task result data. Read background_task for bounded details when needed. Do not start another background task in this completion Run."
        body = {
            "assistant_id": data["graph_id"],
            "input": {
                "messages": [
                    {
                        "id": "background:" + data["event_id"],
                        "role": "user",
                        "content": prompt,
                    }
                ]
            },
            "context": context,
            "multitask_strategy": "enqueue",
            "metadata": {
                "background_task_id": data["task_id"],
                "background_event_id": data["event_id"],
                "origin_run_id": data["origin_run_id"],
            },
        }
        _, result = await gateway.launch_runtime_run(
            actor=actor,
            project_id=data["project_id"],
            thread_id=data["thread_id"],
            command={
                "method": "background-completion",
                "params": {k: v for k, v in data.items() if k != "reconcile_only"},
            },
            upstream_payload=body,
            idempotency_key="background:" + data["event_id"],
            completion_config={MARKER: marker},
        )
        return {"state": "accepted", "run_id": result["run_id"], "reason_code": None}
    except PlatformApiError as exc:
        if 400 <= exc.status_code < 500:
            return {
                "state": "blocked",
                "run_id": None,
                "reason_code": "background_task_denied",
            }
        raise


def save_receipt(factory, record_id, run_id):
    with factory.begin() as session:
        RunRequestsRepository(session).mark(record_id, "accepted", run_id)


async def authorize_completion(request, payload):
    from platform_api.modules.runtime_gateway.application.service import (
        _runtime_context_snapshot,
    )
    from platform_api.modules.runtime_gateway.presentation.http import (
        get_runtime_gateway_service,
    )

    secret = request.app.state.settings.runtime_delegation_secret
    marker = payload.marker
    values = marker.get("values")
    if (
        not isinstance(values, dict)
        or not isinstance(marker.get("signature"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", marker["signature"])
        or not secret
        or not hmac.compare_digest(
            marker["signature"], sign_marker(values, secret)["signature"]
        )
    ):
        raise ForbiddenError(
            code="background_task_denied", message="Background signature denied"
        )
    try:
        for key in ("project_id", "thread_id", "origin_run_id", "task_id", "event_id"):
            UUID(values[key])
        current_hash, context = _runtime_context_snapshot(
            {"params": {"context": payload.context}}
        )
        if values["context_hash"] != current_hash:
            raise ValueError()
        factory = request.app.state.db_session_factory
        source, existing = await run_in_threadpool(records, factory, values)
        # Worker can win the API ACK race; source binding and signed intent remain required.
        if (
            existing is None
            or existing.run_id
            and existing.run_id != str(payload.run_id)
            or existing.context_snapshot != context
        ):
            raise ValueError()
        if existing.run_id is None:
            await run_in_threadpool(
                save_receipt, factory, existing.id, str(payload.run_id)
            )
        actor = await run_in_threadpool(current_actor, factory, values)
        bind_request(request, actor, values)
        gateway = await run_in_threadpool(get_runtime_gateway_service, request, actor)
        thread = await gateway._load_thread(
            actor=actor,
            project_id=values["project_id"],
            thread_id=values["thread_id"],
            write=True,
            action="comment",
        )
        current = gateway._inject_thread_access_policy(
            thread=thread,
            payload={"assistant_id": values["graph_id"], "context": context},
            actor=actor,
        )
        policy = await run_in_threadpool(
            authorize_snapshot, factory, gateway, values, current["context"], actor
        )
        refreshed = await run_in_threadpool(
            gateway._attach_runtime_model_reference,
            project_id=values["project_id"],
            actor=actor,
            thread_id=values["thread_id"],
            payload=current,
        )
        return {
            "allowed": True,
            "policy": policy,
            "role": actor.project_role_set(values["project_id"])[0],
            "access_policy": current["context"]["access_policy"],
            "configurable": refreshed.get("config", {}).get("configurable", {}),
        }
    except (PlatformApiError, ValueError, KeyError, TypeError, IndexError):
        return {"allowed": False, "error_code": "background_task_denied"}
