"""Native cron definitions; platform ownership, authorization and audit history."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from platform_api.core.db import session_scope
from platform_api.core.errors import BadRequestError, ForbiddenError, PlatformApiError
from platform_api.core.security.tokens import empty_runtime_context_hash
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.identity.actors import (
    load_service_account_actor,
    load_user_actor,
)
from platform_api.modules.projects.models import ProjectRecord
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.scheduled_tasks.schemas import Schedule, TaskCreate

MARKER = "platform_scheduled_task"
RUN_ACTION = "scheduled_task.execution"


def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sign_task(values: dict, secret: str) -> dict:
    if not secret:
        raise BadRequestError(
            code="scheduled_task_secret_missing",
            message="Runtime signing is not configured",
        )
    signature = hmac.new(
        secret.encode(), canonical(values).encode(), hashlib.sha256
    ).hexdigest()
    return {"values": values, "signature": signature}


def verify_task(envelope: dict, secret: str) -> dict:
    values = envelope.get("values") if isinstance(envelope, dict) else None
    signature = envelope.get("signature") if isinstance(envelope, dict) else None
    if not isinstance(values, dict) or not isinstance(signature, str) or not secret:
        raise ForbiddenError(
            code="scheduled_task_signature_invalid", message="Invalid task signature"
        )
    if not hmac.compare_digest(signature, sign_task(values, secret)["signature"]):
        raise ForbiddenError(
            code="scheduled_task_signature_invalid", message="Invalid task signature"
        )
    return values


async def preview(
    upstream, rule: Schedule, *, count: int = 5, now: datetime | None = None
) -> dict:
    """Use the Agent Server's cron parser, including its timezone/DST behavior."""
    now = now or datetime.now(UTC)
    if rule.schedule_type == "once":
        if rule.run_at <= now or not 1970 <= rule.run_at.year <= 2099:
            raise BadRequestError(
                code="invalid_run_at",
                message="run_at must be in the future, through year 2099",
            )
        return {
            "times": [rule.run_at.astimezone(UTC).isoformat()],
            "timezone": rule.timezone,
        }
    if rule.end_time and rule.end_time <= now:
        raise BadRequestError(
            code="invalid_end_time", message="end_time must be in the future"
        )
    # The parser endpoint is served by Runtime, not a second platform scheduler.
    return await upstream.cron_preview(
        {
            "schedule": rule.cron,
            "timezone": rule.timezone,
            "after": now.isoformat(),
            "end_time": rule.end_time.isoformat() if rule.end_time else None,
            "count": count,
        }
    )


def native_schedule(rule: Schedule) -> str:
    if rule.schedule_type == "cron":
        return rule.cron
    local = rule.run_at.astimezone(UTC)
    return f"{local.minute} {local.hour} {local.day} {local.month} * {local.second} {local.year}"


def task_item(row: dict) -> dict:
    spec = row["metadata"]["task_spec"]
    return {
        "id": row["cron_id"],
        **spec,
        "enabled": row["enabled"],
        "next_run_at": row["next_run_date"] if row["enabled"] else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "owner_id": row["metadata"]["scheduled_owner"],
        "schedule_status": "exhausted"
        if spec["schedule_type"] == "once"
        and not row["enabled"]
        and row["next_run_date"] is None
        else "active"
        if row["enabled"]
        else "paused",
    }


class ScheduledTasksService:
    def __init__(self, gateway, *, tenant_id: str, secret: str):
        self.gateway = gateway
        self.tenant_id = tenant_id
        self.secret = secret

    async def _upstream(
        self,
        *,
        actor,
        project_id: str,
        write: bool,
        payload: dict | None = None,
        thread_id: str | None = None,
        origin_ref: str | None = None,
    ):
        await run_in_threadpool(
            self.gateway._prepare_project_scope,
            actor=actor,
            project_id=project_id,
            write=write,
        )
        headers = await run_in_threadpool(
            self.gateway._delegation_headers_factory,
            project_id=project_id,
            agent_key=(payload or {}).get("assistant_id", ""),
            thread_id=thread_id,
            context_hash=empty_runtime_context_hash()
            if payload is None
            else self._context_hash(payload),
            operation="run-create"
            if payload
            else "cron-write"
            if write
            else "cron-read",
            **({"origin_ref": origin_ref} if origin_ref else {}),
        )
        return self.gateway._upstream.with_forwarded_headers(headers)

    @staticmethod
    def _context_hash(payload):
        from platform_api.modules.runtime_gateway.application.service import (
            _runtime_context_snapshot,
        )

        return _runtime_context_snapshot({"params": payload})[0]

    @staticmethod
    def _owner(actor):
        return actor.user_id or actor.subject

    async def get_native(
        self, *, actor, project_id: str, task_id: str, write: bool = False
    ):
        UUID(task_id)
        upstream = await self._upstream(actor=actor, project_id=project_id, write=write)
        row = await upstream.cron_request("GET", task_id)
        metadata = row.get("metadata", {})
        if (
            metadata.get("project_id") != project_id
            or metadata.get("scheduled_owner") != self._owner(actor)
            or metadata.get("scheduled_tenant") != self.tenant_id
        ):
            raise ForbiddenError(
                code="scheduled_task_denied", message="Task is unavailable"
            )
        return row

    async def list(
        self,
        *,
        actor,
        project_id: str,
        limit: int,
        offset: int,
        enabled: bool | None = None,
    ):
        upstream = await self._upstream(actor=actor, project_id=project_id, write=False)
        filters = {
            "metadata": {
                "project_id": project_id,
                "scheduled_owner": self._owner(actor),
                "scheduled_tenant": self.tenant_id,
            }
        }
        if enabled is not None:
            filters["enabled"] = enabled
        rows = await upstream.cron_request(
            "POST", "search", payload={**filters, "limit": limit, "offset": offset}
        )
        total = await upstream.cron_request("POST", "count", payload=filters)
        return {
            "items": [task_item(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def _payload(
        self, *, actor, project_id: str, spec: TaskCreate, validate_time=True
    ):
        await run_in_threadpool(
            self.gateway._prepare_project_scope,
            actor=actor,
            project_id=project_id,
            write=True,
        )
        await run_in_threadpool(
            require_active_project, self.gateway._session_factory, project_id
        )
        if validate_time:
            upstream = await self._upstream(
                actor=actor, project_id=project_id, write=False
            )
            await preview(upstream, spec)
        payload = self.gateway._inject_project_scope(
            project_id=project_id,
            payload={
                "assistant_id": spec.agent_key,
                "input": {"messages": [{"role": "user", "content": spec.prompt}]},
                "context": spec.context,
            },
        )
        payload = await run_in_threadpool(
            self.gateway._inject_project_default_model,
            project_id=project_id,
            payload=payload,
        )
        await run_in_threadpool(
            self.gateway._assert_runtime_target_allowed,
            project_id=project_id,
            assistant_id=spec.agent_key,
        )
        await run_in_threadpool(
            self.gateway._validate_run_options, project_id=project_id, payload=payload
        )
        if spec.thread_mode == "reuse":
            thread = await self.gateway._load_thread(
                actor=actor,
                project_id=project_id,
                thread_id=spec.thread_id,
                write=True,
                action="comment",
            )
            payload = self.gateway._inject_thread_access_policy(
                thread=thread, payload=payload, actor=actor
            )
        else:
            payload["context"] = {
                **payload.get("context", {}),
                "access_policy": "review",
            }
        values = {
            "v": 1,
            "tenant_id": self.tenant_id,
            "project_id": project_id,
            "owner_id": self._owner(actor),
            "credential_id": actor.credential_id,
            "agent_key": spec.agent_key,
            "thread_mode": spec.thread_mode,
            "thread_id": spec.thread_id,
        }
        config = dict(payload.get("config") or {})
        config["configurable"] = {
            **config.get("configurable", {}),
            MARKER: sign_task(values, self.secret),
        }
        payload.update(
            config=config,
            schedule=native_schedule(spec),
            timezone="UTC" if spec.schedule_type == "once" else spec.timezone,
            end_time=spec.end_time.isoformat() if spec.end_time else None,
            on_run_completed="keep",
            enabled=spec.enabled,
            multitask_strategy="enqueue",
            metadata={
                "project_id": project_id,
                "scheduled_owner": self._owner(actor),
                "scheduled_tenant": self.tenant_id,
                "task_spec": spec.model_dump(mode="json"),
            },
        )
        return payload

    async def create(self, *, actor, project_id: str, spec: TaskCreate):
        payload = await self._payload(actor=actor, project_id=project_id, spec=spec)
        origin_ref = await self._reserve_completion_origin(actor, project_id, spec)
        upstream = await self._upstream(
            actor=actor,
            project_id=project_id,
            write=True,
            payload=payload,
            thread_id=spec.thread_id,
            origin_ref=origin_ref,
        )
        row = await upstream.cron_request(
            "POST", payload=payload, thread_id=spec.thread_id
        )
        await self._bind_completion_schedule(origin_ref, row["cron_id"])
        return task_item(row)

    async def _reserve_completion_origin(self, actor, project_id, spec):
        if not self.gateway._completion_enabled:
            return None
        from platform_api.modules.runtime_gateway.infra.sqlalchemy.completion_repository import (
            reserve_origin,
        )

        def reserve():
            with session_scope(self.gateway._session_factory) as session:
                return reserve_origin(
                    session,
                    project_id=project_id,
                    thread_id=spec.thread_id,
                    agent_key=spec.agent_key,
                    requested_by=actor.user_id
                    if actor.principal_type == "user"
                    else None,
                    runtime_id="default",
                    source_kind="schedule",
                    thread_mode=spec.thread_mode,
                    state="active",
                )

        return await run_in_threadpool(reserve)

    async def _bind_completion_schedule(self, origin_ref, task_id):
        if not origin_ref:
            return
        from platform_api.modules.runtime_gateway.infra.sqlalchemy.completion_repository import (
            get_origin,
        )

        def bind():
            with session_scope(self.gateway._session_factory) as session:
                get_origin(session, origin_ref).source_id = task_id
                get_origin(session, origin_ref).state = "active"

        await run_in_threadpool(bind)

    async def update(self, *, actor, project_id: str, task_id: str, changes: dict):
        row = await self.get_native(
            actor=actor, project_id=project_id, task_id=task_id, write=True
        )
        try:
            spec = TaskCreate.model_validate(
                {**row["metadata"]["task_spec"], **changes, "enabled": row["enabled"]}
            )
        except ValidationError as exc:
            raise BadRequestError(
                code="invalid_scheduled_task", message="Invalid task update"
            ) from exc
        changed_time = bool({"cron", "run_at", "timezone", "end_time"} & changes.keys())
        payload = await self._payload(
            actor=actor, project_id=project_id, spec=spec, validate_time=changed_time
        )
        origin_ref = await self._reserve_completion_origin(actor, project_id, spec)
        upstream = await self._upstream(
            actor=actor,
            project_id=project_id,
            write=True,
            payload=payload,
            thread_id=spec.thread_id,
            origin_ref=origin_ref,
        )
        if not {"cron", "run_at", "timezone"} & changes.keys():
            payload.pop("schedule")
            payload.pop("timezone")
        payload["thread_id"] = spec.thread_id
        updated = await upstream.cron_request("PATCH", task_id, payload=payload)
        await self._bind_completion_schedule(origin_ref, task_id)
        return task_item(updated)

    async def set_enabled(self, *, actor, project_id: str, task_id: str, enabled: bool):
        row = await self.get_native(
            actor=actor, project_id=project_id, task_id=task_id, write=True
        )
        if enabled and row["metadata"]["task_spec"]["schedule_type"] == "once":
            spec = TaskCreate.model_validate(row["metadata"]["task_spec"])
            await preview(
                await self._upstream(actor=actor, project_id=project_id, write=False),
                spec,
            )
        upstream = await self._upstream(actor=actor, project_id=project_id, write=True)
        return task_item(
            await upstream.cron_request("PATCH", task_id, payload={"enabled": enabled})
        )

    async def delete(self, *, actor, project_id: str, task_id: str):
        await self.get_native(
            actor=actor, project_id=project_id, task_id=task_id, write=True
        )
        upstream = await self._upstream(actor=actor, project_id=project_id, write=True)
        await upstream.cron_request("DELETE", task_id)

    async def trigger(
        self, *, actor, project_id: str, task_id: str, idempotency_key: str
    ):
        row = await self.get_native(
            actor=actor, project_id=project_id, task_id=task_id, write=True
        )
        spec = TaskCreate.model_validate(row["metadata"]["task_spec"])
        # Manual execution uses the same stored input and current managed Run gateway.
        thread_id = spec.thread_id
        if not thread_id:
            # A deterministic reservation lets retries reuse the same Thread.
            from uuid import NAMESPACE_URL, uuid5

            reservation = str(
                uuid5(NAMESPACE_URL, f"scheduled:{task_id}:{idempotency_key}")
            )
            access = await run_in_threadpool(
                thread_access.get, self.gateway._session_factory, reservation
            )
            pending = await run_in_threadpool(
                thread_access.pending_actor,
                self.gateway._session_factory,
                thread_id=reservation,
                project_id=project_id,
                actor=actor,
            )
            if not access or pending:
                thread = await self.gateway.create_thread(
                    actor=actor,
                    project_id=project_id,
                    payload={"graph_id": spec.agent_key},
                    reserved_thread_id=reservation,
                )
                thread_id = thread["thread_id"]
            else:
                thread_id = reservation
        payload = dict(row["payload"])
        payload = {
            key: payload[key]
            for key in ("assistant_id", "input", "context")
            if key in payload
        }
        payload["multitask_strategy"] = "enqueue"
        payload["metadata"] = {
            "cron_id": task_id,
            "trigger": "manual",
            "project_id": project_id,
            "scheduled_owner": self._owner(actor),
            "scheduled_tenant": self.tenant_id,
        }
        marker = row["payload"]["config"]["configurable"][MARKER]
        key = f"scheduled:{task_id}:{hashlib.sha256(idempotency_key.encode()).hexdigest()}"
        result = await self.gateway.create_thread_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            payload=payload,
            idempotency_key=key,
            scheduled_config={
                MARKER: marker,
                "cron_id": task_id,
                "scheduled_trigger": "manual",
            },
        )
        await run_in_threadpool(
            record_execution,
            self.gateway._session_factory,
            tenant_id=self.tenant_id,
            project_id=project_id,
            owner_id=self._owner(actor),
            task_id=task_id,
            run_id=result["run_id"],
            thread_id=thread_id,
            trigger="manual",
            status="pending",
        )
        return result

    async def history(
        self, *, actor, project_id: str, task_id: str, limit: int, offset: int
    ):
        upstream = await self._upstream(actor=actor, project_id=project_id, write=False)
        result = await upstream.cron_runs(task_id, limit=limit, offset=offset)
        records = await run_in_threadpool(
            execution_errors,
            self.gateway._session_factory,
            tenant_id=self.tenant_id,
            project_id=project_id,
            owner_id=self._owner(actor),
            task_id=task_id,
            run_ids=[item["run_id"] for item in result["items"]],
        )
        for item in result["items"]:
            item["error_code"] = records.get(item["run_id"]) or item.get("error_code")
        return result


def record_execution(
    factory,
    *,
    tenant_id,
    project_id,
    owner_id,
    task_id,
    run_id,
    thread_id,
    status,
    trigger="scheduled",
    error_code=None,
):
    with session_scope(factory) as session:
        session.add(
            AuditLogRecord(
                request_id=run_id,
                plane="runtime_gateway",
                action=RUN_ACTION,
                target_type="scheduled_run",
                target_id=run_id,
                actor_subject=owner_id,
                tenant_id=tenant_id,
                project_id=project_id,
                result="denied" if error_code else "success",
                method="POST",
                path="/api/runtime/internal/scheduled-authorization",
                status_code=403 if error_code else 200,
                duration_ms=0,
                metadata_json={
                    "cron_id": task_id,
                    "run_id": run_id,
                    "thread_id": thread_id,
                    "trigger": trigger,
                    "status": status,
                    "error_code": error_code,
                },
            )
        )


def execution_errors(factory, *, tenant_id, project_id, owner_id, task_id, run_ids):
    with session_scope(factory) as session:
        rows = session.scalars(
            select(AuditLogRecord)
            .where(
                AuditLogRecord.action == RUN_ACTION,
                AuditLogRecord.tenant_id == tenant_id,
                AuditLogRecord.project_id == project_id,
                AuditLogRecord.actor_subject == owner_id,
                AuditLogRecord.metadata_json["cron_id"].as_string() == task_id,
                AuditLogRecord.target_id.in_(run_ids),
                AuditLogRecord.result == "denied",
            )
            .order_by(AuditLogRecord.created_at, AuditLogRecord.id)
        ).all()
        return {row.target_id: row.metadata_json["error_code"] for row in rows}


def require_active_project(factory, project_id):
    with factory() as session:
        project = session.get(ProjectRecord, UUID(project_id))
        if project is None or project.status != "active":
            raise ForbiddenError(
                code="scheduled_task_project_inactive",
                message="Task project is unavailable",
            )


def authorize_execution(factory, gateway, payload: dict, secret: str) -> dict:
    """One Runtime callback before graph construction; current platform data wins."""
    from sqlalchemy.exc import IntegrityError

    from platform_api.modules.runtime_policies.application import (
        RuntimePolicyOverlayService,
    )

    fields = {
        key: payload[key]
        for key in (
            "tenant_id",
            "project_id",
            "owner_id",
            "task_id",
            "run_id",
            "thread_id",
        )
    }
    fields["trigger"] = payload.get("trigger", "scheduled")
    try:
        values = verify_task(payload["task"], secret)
        if any(
            values.get(key) != payload.get(key)
            for key in (
                "tenant_id",
                "project_id",
                "owner_id",
                "credential_id",
                "agent_key",
            )
        ):
            raise ForbiddenError(
                code="scheduled_task_scope_denied", message="Task scope mismatch"
            )
        if (
            values.get("thread_mode") == "reuse"
            and values.get("thread_id") != payload["thread_id"]
        ):
            raise ForbiddenError(
                code="scheduled_task_thread_denied", message="Task thread mismatch"
            )
        if payload.get("outcome") == "success":
            record_execution(factory, **fields, status="success")
            return {"allowed": True}
        if payload.get("error_code") is not None:
            code = payload["error_code"]
            if code not in {
                "scheduled_task_approval_required",
                "scheduled_task_execution_failed",
            }:
                raise BadRequestError(
                    code="invalid_scheduled_error", message="Invalid execution error"
                )
            record_execution(factory, **fields, status="error", error_code=code)
            return {"allowed": False, "error_code": code}
        loader = (
            load_service_account_actor
            if payload["owner_id"].startswith("service-account:")
            else load_user_actor
        )
        actor = loader(
            session_factory=factory,
            project_id=payload["project_id"],
            **(
                {
                    "subject": payload["owner_id"],
                    "credential_id": payload.get("credential_id"),
                }
                if loader is load_service_account_actor
                else {"user_id": payload["owner_id"]}
            ),
        )
        if actor is None:
            raise ForbiddenError(
                code="scheduled_task_principal_revoked",
                message="Task principal is unavailable",
            )
        if not actor.project_role_set(payload["project_id"]):
            raise ForbiddenError(
                code="scheduled_task_project_revoked",
                message="Task project membership is unavailable",
            )
        gateway._prepare_project_scope(
            actor=actor, project_id=payload["project_id"], write=True
        )
        require_active_project(factory, payload["project_id"])
        gateway._assert_runtime_target_allowed(
            project_id=payload["project_id"], assistant_id=payload["agent_key"]
        )
        run_payload = {
            "assistant_id": payload["agent_key"],
            "context": payload["context"],
        }
        if payload["context"].get("plan_mode") is True:
            raise BadRequestError(
                code="plan_mode_scheduled_forbidden",
                message="Unattended runs cannot request planning",
            )
        gateway._validate_run_options(
            project_id=payload["project_id"], payload=run_payload
        )
        access = thread_access.get(factory, payload["thread_id"])
        if not access and values.get("thread_mode") == "fresh":
            with factory() as session:
                deleted = session.scalar(
                    select(AuditLogRecord.id)
                    .where(
                        AuditLogRecord.action == "thread.deleted",
                        AuditLogRecord.target_id == payload["thread_id"],
                        AuditLogRecord.project_id == payload["project_id"],
                    )
                    .limit(1)
                )
            if deleted:
                raise ForbiddenError(
                    code="scheduled_task_thread_deleted",
                    message="Task thread was deleted",
                )
            try:
                access = thread_access.register(
                    factory,
                    actor=actor,
                    project_id=payload["project_id"],
                    thread_id=payload["thread_id"],
                )
            except IntegrityError:
                access = thread_access.get(factory, payload["thread_id"])
            thread_access.mark_provisioned(factory, payload["thread_id"])
        thread_access.require_action(actor, payload["project_id"], access, "comment")
        run_payload = gateway._attach_runtime_model_reference(
            project_id=payload["project_id"],
            actor=actor,
            thread_id=payload["thread_id"],
            payload=run_payload,
        )
        policy_service = RuntimePolicyOverlayService(
            session_factory=factory, runtime_base_url=gateway._runtime_id
        )
        policy = policy_service.build_delegation_policy(
            project_id=payload["project_id"]
        )
        restrictions = policy_service.resolve_tool_overrides(
            project_id=payload["project_id"],
            user_id=actor.user_id,
            graph_id=payload["agent_key"],
        )
        record_execution(factory, **fields, status="running")
        return {
            "allowed": True,
            "configurable": run_payload.get("config", {}).get("configurable", {}),
            "role": actor.project_role_set(payload["project_id"])[0],
            "policy": {
                "version": str(policy["version"]),
                "allowed_model_ids": policy["allowed_model_ids"],
                **restrictions,
            },
        }
    except PlatformApiError as exc:
        record_execution(factory, **fields, status="error", error_code=exc.code)
        return {"allowed": False, "error_code": exc.code}
