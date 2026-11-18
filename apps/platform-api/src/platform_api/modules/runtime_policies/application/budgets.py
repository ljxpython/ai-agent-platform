"""Budget authorization, versioned policy writes and signed Runtime access."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from platform_api.core.errors import (
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.projects.models import ProjectRecord, TenantRecord
from platform_api.modules.runtime_policies.application.budget_transport import encode
from platform_api.modules.runtime_policies.domain.budgets import (
    BudgetPolicy,
    BudgetResponse,
    period,
)
from platform_api.modules.runtime_policies.infra.sqlalchemy.budgets import (
    BudgetPolicyRecord,
    BudgetTenantRecord,
)


def unavailable():
    return ServiceUnavailableError(
        code="BUDGET_ACCOUNTING_UNAVAILABLE", message="预算账务暂不可核实，请稍后重试"
    )


class BudgetService:
    def __init__(self, factory, settings):
        self.factory = factory
        self.settings = settings

    def _tenant(self, session, tenant):
        record = session.scalar(
            select(TenantRecord).where(
                TenantRecord.slug == tenant, TenantRecord.status == "active"
            )
        )
        if record is None:
            raise ForbiddenError(
                code="budget_tenant_denied", message="Tenant unavailable"
            )
        return record

    def authorize(self, context, project_id=None, *, write=False):
        from platform_api.modules.identity.actors import (
            load_service_account_actor,
            load_user_actor,
        )

        actor = context.actor
        if actor.principal_type == "service_account":
            actor = load_service_account_actor(
                session_factory=self.factory,
                subject=actor.subject or "",
                credential_id=actor.credential_id,
                project_id=project_id or str(UUID(int=0)),
            )
        else:
            actor = load_user_actor(
                session_factory=self.factory,
                user_id=actor.user_id or "",
                project_id=project_id,
            )
        if actor is None:
            raise ForbiddenError(
                code="budget_identity_inactive", message="Identity unavailable"
            )
        permission = (
            (
                PermissionCode.PROJECT_RUNTIME_WRITE
                if write
                else PermissionCode.PROJECT_USAGE_READ
            )
            if project_id
            else (
                PermissionCode.PLATFORM_SUPER_ADMIN_MANAGE
                if write
                else PermissionCode.PLATFORM_USAGE_READ
            )
        )
        IamPolicyEngine().require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=permission, project_id=project_id
            ),
        )
        with self.factory() as session:
            tenant = self._tenant(session, context.tenant.tenant_id)
            if project_id:
                project = session.get(ProjectRecord, UUID(project_id))
                if (
                    project is None
                    or project.tenant_id != tenant.id
                    or project.status != "active"
                    or project.deleted_at
                ):
                    raise NotFoundError(
                        code="budget_project_not_found", message="Project unavailable"
                    )
        return actor

    def _lock(self, session, tenant):
        self._tenant(session, tenant)
        insert = (
            pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
        )
        session.execute(
            insert(BudgetTenantRecord)
            .values(
                tenant_id=tenant,
                revision=0,
                synced_revision=-1,
                updated_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=["tenant_id"])
        )
        return session.scalar(
            select(BudgetTenantRecord)
            .where(BudgetTenantRecord.tenant_id == tenant)
            .with_for_update()
        )

    def _snapshot(self, session, tenant):
        state = self._lock(session, tenant)
        policies = list(
            session.scalars(
                select(BudgetPolicyRecord)
                .where(BudgetPolicyRecord.tenant_id == tenant)
                .order_by(BudgetPolicyRecord.id)
            )
        )
        return {
            "tenant_id": tenant,
            "revision": state.revision,
            "policies": [p.payload for p in policies],
        }

    def snapshot(self, tenant, project_id=None):
        with self.factory.begin() as session:
            scope = self._tenant(session, tenant)
            if project_id:
                project = session.get(ProjectRecord, UUID(project_id))
                if (
                    project is None
                    or project.tenant_id != scope.id
                    or project.status != "active"
                ):
                    raise ForbiddenError(
                        code="budget_project_denied", message="Project unavailable"
                    )
            return self._snapshot(session, tenant)

    def runtime(self, snapshot, *, mode="sync", project_id=None):
        path = "/internal/budgets/query"
        body, headers = encode(
            self.settings.runtime_delegation_secret,
            path,
            {"snapshot": snapshot, "mode": mode, "project_id": project_id},
        )
        try:
            with httpx.Client(
                timeout=6, trust_env=False, follow_redirects=False
            ) as client:
                response = client.post(
                    self.settings.langgraph_upstream_url.rstrip("/") + path,
                    content=body,
                    headers=headers,
                )
                response.raise_for_status()
                value = response.json()
            result = BudgetResponse.model_validate(value)
            if (
                result.tenant_id != snapshot["tenant_id"]
                or result.revision != snapshot["revision"]
                or result.capabilities.get("gateway_budget") is not True
                or result.capabilities.get("usage") is not True
            ):
                raise ValueError("budget_runtime_incompatible")
            active = {
                p["id"]: p
                for p in snapshot["policies"]
                if not p.get("deleted_at")
                and (project_id is None or p.get("project_id") in (None, project_id))
            }
            seen = set()
            for state in result.states:
                policy = active.get(str(state.policy_id))
                if (
                    policy is None
                    or state.policy_id in seen
                    or state.definition_version != policy["definition_version"]
                ):
                    raise ValueError("budget_state_invalid")
                seen.add(state.policy_id)
                if period(policy["duration"]["unit"], state.as_of) != (
                    state.window_start,
                    state.window_end,
                ):
                    raise ValueError("budget_window_invalid")
                exceeded = Decimal(state.known_spend) >= Decimal(
                    policy["budget_amount"]
                )
                if state.is_exceeded != (
                    exceeded
                    if state.accounting_status == "complete" or exceeded
                    else None
                ):
                    raise ValueError("budget_threshold_invalid")
            if mode != "status" and len(seen) != len(active):
                raise ValueError("budget_states_missing")
            return result.model_dump(mode="json")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise unavailable() from None

    def sync(self, tenant):
        snapshot = self.snapshot(tenant)
        try:
            result = self.runtime(snapshot)
        except PlatformApiError:
            with self.factory.begin() as session:
                row = session.get(BudgetTenantRecord, tenant)
                row.last_error = "budget_sync_failed"
            return False
        with self.factory.begin() as session:
            row = session.get(BudgetTenantRecord, tenant, with_for_update=True)
            row.synced_revision = max(row.synced_revision, snapshot["revision"])
            row.last_error = None
        return result

    def save(self, context, body, policy_id=None, *, delete=False):
        tenant = context.tenant.tenant_id
        existing = None
        if policy_id:
            with self.factory() as session:
                existing = session.get(BudgetPolicyRecord, str(policy_id))
                if (
                    existing is None
                    or existing.tenant_id != tenant
                    or existing.payload.get("deleted_at")
                ):
                    raise NotFoundError(
                        code="budget_policy_not_found",
                        message="Budget policy unavailable",
                    )
                previous = BudgetPolicy.model_validate(existing.payload)
            self.authorize(
                context,
                str(previous.project_id) if previous.project_id else None,
                write=True,
            )
        if not delete:
            self.authorize(
                context, str(body.project_id) if body.project_id else None, write=True
            )
        # Refuse enabling a restriction unless the Runtime deployment advertises support.
        if not delete and body.action == "REJECT":
            self.runtime(self.snapshot(tenant))
        now = datetime.now(UTC)
        with self.factory.begin() as session:
            state = self._lock(session, tenant)
            if policy_id:
                record = session.get(
                    BudgetPolicyRecord, str(policy_id), populate_existing=True
                )
                if record is None or record.payload.get("deleted_at"):
                    raise NotFoundError(
                        code="budget_policy_not_found",
                        message="Budget policy unavailable",
                    )
                if record.payload != existing.payload:
                    raise PlatformApiError(
                        status_code=409,
                        code="budget_policy_changed",
                        message="预算已更新，请刷新后重试",
                    )
                old = BudgetPolicy.model_validate(record.payload)
                definition_changed = not delete and (
                    body.scope,
                    body.project_id,
                    body.duration,
                ) != (old.scope, old.project_id, old.duration)
                policy = (
                    old.model_copy(
                        update={
                            "deleted_at": now,
                            "updated_at": now,
                            "version": old.version + 1,
                        }
                    )
                    if delete
                    else BudgetPolicy(
                        **body.model_dump(),
                        id=old.id,
                        version=old.version + 1,
                        definition_version=old.definition_version
                        + int(definition_changed),
                        created_at=old.created_at,
                        definition_started_at=now
                        if definition_changed
                        else old.definition_started_at,
                        updated_at=now,
                    )
                )
                record.payload = policy.model_dump(mode="json")
            else:
                count = session.scalar(
                    select(func.count())
                    .select_from(BudgetPolicyRecord)
                    .where(BudgetPolicyRecord.tenant_id == tenant)
                )
                if count >= 200:
                    raise PlatformApiError(
                        status_code=409,
                        code="budget_policy_limit",
                        message="Budget policy history limit reached",
                    )
                policy = BudgetPolicy(
                    **body.model_dump(),
                    id=uuid4(),
                    version=1,
                    definition_version=1,
                    created_at=now,
                    definition_started_at=now,
                    updated_at=now,
                )
                session.add(
                    BudgetPolicyRecord(
                        id=str(policy.id),
                        tenant_id=tenant,
                        payload=policy.model_dump(mode="json"),
                    )
                )
            state.revision += 1
            state.updated_at = now
        applied = self.sync(tenant)
        return {
            "policy": policy.model_dump(mode="json"),
            "sync_status": "applied" if applied else "pending",
        }

    def list(self, context, project_id=None):
        self.authorize(context, project_id)
        snapshot = self.snapshot(context.tenant.tenant_id)
        try:
            states = {
                s["policy_id"]: s for s in self.runtime(snapshot, mode="sync")["states"]
            }
        except PlatformApiError:
            states = {}
        items = []
        for p in snapshot["policies"]:
            if p.get("deleted_at") or (
                project_id and p.get("project_id") != project_id
            ):
                continue
            start, end = period(p["duration"]["unit"], datetime.now(UTC))
            state = states.get(
                p["id"],
                {
                    "accounting_status": "reconciling",
                    "current_spend": None,
                    "known_spend": None,
                    "is_exceeded": None,
                    "window_start": start.isoformat(),
                    "window_end": end.isoformat(),
                    "as_of": None,
                },
            )
            items.append(
                {
                    **p,
                    **state,
                    "sync_status": "applied" if p["id"] in states else "pending",
                }
            )
        return {"items": items, "revision": snapshot["revision"]}

    def preflight(self, tenant, project_id):
        snapshot = self.snapshot(tenant, project_id)
        applicable = [
            p
            for p in snapshot["policies"]
            if not p.get("deleted_at") and p.get("project_id") in (None, project_id)
        ]
        if not applicable:
            return
        result = self.runtime(snapshot, mode="check", project_id=project_id)
        states = {s["policy_id"]: s for s in result["states"]}
        resets = []
        incomplete = False
        for p in applicable:
            if p["action"] != "REJECT":
                continue
            state = states.get(p["id"])
            if not state:
                incomplete = True
                continue
            if state["is_exceeded"]:
                resets.append(datetime.fromisoformat(state["window_end"]))
            if state["accounting_status"] != "complete":
                incomplete = True
        if resets:
            reset = min(resets)
            error = PlatformApiError(
                status_code=429,
                code="BUDGET_LIMIT_EXCEEDED",
                message="预算已用尽，后续模型调用已停止",
                extra={"resets_at": reset.isoformat()},
            )
            error.headers = {
                "Retry-After": str(
                    max(1, int((reset - datetime.now(UTC)).total_seconds()))
                )
            }
            raise error
        if incomplete:
            raise unavailable()
