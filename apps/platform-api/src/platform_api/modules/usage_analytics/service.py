"""Authorize governance totals separately from current Thread content access."""

import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import or_, select, tuple_
from starlette.concurrency import run_in_threadpool

from platform_api.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.identity.actors import (
    load_service_account_actor,
    load_user_actor,
)
from platform_api.modules.projects.models import ProjectRecord, TenantRecord
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)
from platform_api.modules.usage_analytics.contracts import (
    Filters,
    UsageDashboardV1,
    UsageRun,
    UsageRunPageV1,
    empty_dashboard,
)
from platform_api.modules.usage_analytics.cursor import (
    binding,
    decode_cursor,
    encode_cursor,
)

_utc_timestamp = TypeAdapter(datetime)


def _timestamp(value):
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("ISO timestamp required")
    parsed = _utc_timestamp.validate_python(value)
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("UTC timestamp required")
    return parsed


def _bounded_result(result):
    if len(result.model_dump_json(by_alias=True).encode()) > 300 * 1024:
        raise PlatformApiError(
            code="usage_aggregate_range_exceeded",
            status_code=422,
            message="Usage response exceeds limit; reduce the query range",
        )
    return result


def _invalid_upstream():
    return PlatformApiError(
        code="usage_backend_invalid_response",
        status_code=502,
        message="Runtime returned an invalid usage projection",
    )


def _label(value):
    return " ".join(value.split())[:255]


class UsageAnalyticsService:
    def __init__(self, *, session_factory, upstream, secret, query_slots=None):
        self.factory = session_factory
        self.upstream = upstream
        self.secret = secret
        self.query_slots = query_slots or asyncio.Semaphore(2)

    def _authorize(self, context, project_id, requested, query):
        if self.factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        actor = context.actor
        if actor.principal_type == "service_account":
            current = load_service_account_actor(
                session_factory=self.factory,
                subject=actor.subject or "",
                credential_id=actor.credential_id,
                project_id=project_id or str(UUID(int=0)),
            )
        else:
            current = load_user_actor(
                session_factory=self.factory,
                user_id=actor.user_id or "",
                project_id=project_id,
            )
        if current is None:
            raise ForbiddenError(
                code="usage_identity_not_active",
                message="Usage identity is no longer active",
            )
        permission = (
            PermissionCode.PROJECT_USAGE_READ
            if project_id
            else PermissionCode.PLATFORM_USAGE_READ
        )
        IamPolicyEngine().require(
            actor=current,
            authorization=AuthorizationRequest(
                permission=permission, project_id=project_id
            ),
        )
        tenant_key = context.tenant.tenant_id
        with self.factory() as session:
            # The execution context uses the default slug, while projects store its UUID.
            tenant = session.scalar(
                select(TenantRecord).where(TenantRecord.slug == tenant_key)
            )
            if tenant is None or tenant.status != "active":
                raise ForbiddenError(
                    code="usage_tenant_scope_denied",
                    message="Usage tenant is unavailable",
                )
            stmt = (
                select(ProjectRecord.id, ProjectRecord.name)
                .where(
                    ProjectRecord.tenant_id == tenant.id,
                    ProjectRecord.status == "active",
                    ProjectRecord.deleted_at.is_(None),
                )
                .order_by(ProjectRecord.id)
            )
            selected = [project_id] if project_id else requested
            if selected:
                stmt = stmt.where(
                    ProjectRecord.id.in_([UUID(value) for value in selected])
                )
            rows = session.execute(stmt.limit(201)).all()
            if len(rows) > 200:
                raise BadRequestError(
                    code="invalid_usage_analytics_query",
                    message="Select at most 200 projects",
                )
            projects = {str(row.id): _label(row.name) for row in rows}
            if selected and set(projects) != set(selected):
                raise NotFoundError(
                    code="usage_project_not_found",
                    message="Usage project scope is unavailable",
                )
            graph_id = None
            if query.agent_id:
                if len(projects) != 1:
                    raise BadRequestError(
                        code="invalid_usage_analytics_query",
                        message="Agent filter requires one project",
                    )
                graph_id = session.scalar(
                    select(AgentRecord.graph_id).where(
                        AgentRecord.id == query.agent_id,
                        AgentRecord.project_id == UUID(next(iter(projects))),
                        AgentRecord.status == "active",
                    )
                )
                if graph_id is None:
                    raise NotFoundError(
                        code="usage_agent_not_found",
                        message="Usage Agent is unavailable",
                    )
        return current, projects, graph_id

    def _payload(self, context, actor, projects, graph_id, query):
        data = query.model_dump(
            mode="json", by_alias=True, exclude={"agent_id", "cursor"}
        )
        return {
            "version": 1,
            "actor_id": actor.user_id or actor.subject,
            "credential_id": actor.credential_id,
            "tenant_id": context.tenant.tenant_id,
            "project_ids": sorted(projects),
            "request_id": context.request.request_id,
            **data,
            "graph_id": graph_id,
        }

    def _check_envelope(self, raw, payload):
        if (
            not isinstance(raw, dict)
            or type(raw.get("version")) is not int
            or raw.get("version") != 1
            or raw.get("tenant_id") != payload["tenant_id"]
            or raw.get("request_id") != payload["request_id"]
        ):
            raise _invalid_upstream()
        _timestamp(raw["as_of"])
        filters = Filters.model_validate(raw["filters"]).model_dump(mode="json")
        if filters != {key: payload.get(key) for key in Filters.model_fields}:
            raise _invalid_upstream()

    def _names(self, projects, model_keys, agent_keys):
        if any(project not in projects for project, _ in agent_keys):
            raise _invalid_upstream()
        model_ids = [UUID(key) for key in model_keys if key != "unmapped"]
        with self.factory() as session:
            models = (
                session.execute(
                    select(
                        RuntimeCatalogModelRecord.id,
                        RuntimeCatalogModelRecord.display_name,
                    ).where(
                        RuntimeCatalogModelRecord.id.in_(model_ids),
                        or_(
                            RuntimeCatalogModelRecord.scope_type == "platform",
                            RuntimeCatalogModelRecord.project_id.in_(
                                [UUID(p) for p in projects]
                            ),
                        ),
                    )
                ).all()
                if model_ids
                else []
            )
            agents = (
                session.execute(
                    select(
                        AgentRecord.id,
                        AgentRecord.project_id,
                        AgentRecord.graph_id,
                        AgentRecord.name,
                    ).where(
                        tuple_(AgentRecord.project_id, AgentRecord.graph_id).in_(
                            [(UUID(p), g) for p, g in agent_keys]
                        )
                    )
                ).all()
                if agent_keys
                else []
            )
        return {str(row.id): _label(row.display_name) for row in models}, {
            (str(row.project_id), row.graph_id): (str(row.id), _label(row.name))
            for row in agents
        }

    def _dashboard_projection(self, raw, payload, projects, kind):
        self._check_envelope(raw, payload)
        if set(raw["scope"]["project_ids"]) != set(projects) or raw["scope"][
            "covered_project_count"
        ] != len(projects):
            raise _invalid_upstream()
        expected = {
            key: payload[key] for key in ("from", "to", "timezone", "granularity")
        }
        actual = raw["window"]
        if (
            any(
                datetime.fromisoformat(actual[k]) != datetime.fromisoformat(expected[k])
                for k in ("from", "to")
            )
            or any(actual[k] != expected[k] for k in ("timezone", "granularity"))
            or actual["time_basis"] != "model_call_started_at"
        ):
            raise _invalid_upstream()
        if (
            raw["breakdown"]["group_by"] != payload["group_by"]
            or raw["breakdown"]["rank_by"] != payload["rank_by"]
            or len(raw["breakdown"]["items"]) > payload["top_n"]
        ):
            raise _invalid_upstream()
        model_keys = list(raw["facets"]["models"]["items"])
        agent_keys = [
            (row["project_id"], row["graph_id"])
            for row in raw["facets"]["agents"]["items"]
        ]
        groups = raw["breakdown"]["items"]
        if payload["group_by"] == "model":
            model_keys += [row["key"] for row in groups]
        if payload["group_by"] == "agent":
            agent_keys += [tuple(row["key"].split("/", 1)) for row in groups]
        if len(model_keys) > 250 or len(agent_keys) > 250:
            raise _invalid_upstream()
        models, agents = self._names(projects, set(model_keys), set(agent_keys))
        for row in groups:
            key = row["key"]
            row["label"] = key
            if payload["group_by"] == "project":
                if key not in projects:
                    raise _invalid_upstream()
                row.update(label=projects[key], project_id=key)
            elif payload["group_by"] == "model":
                row["label"] = (
                    "未映射模型"
                    if key == "unmapped"
                    else models.get(key, "已删除或不可见模型")
                )
            elif payload["group_by"] == "agent":
                project, graph = key.split("/", 1)
                agent_id, name = agents.get((project, graph), (None, "已删除 Agent"))
                row.update(label=name, project_id=project, agent_id=agent_id)
            elif (
                payload["group_by"] == "purpose"
                and key
                not in {
                    "agent",
                    "summarization",
                    "memory_extraction",
                    "vision",
                    "other",
                }
                or payload["group_by"] == "scope"
                and key not in {"primary", "subagent", "auxiliary"}
            ):
                raise _invalid_upstream()
        raw["scope"]["kind"] = kind
        raw["facets"] = {
            "projects": {
                "items": [
                    {"id": key, "label": label} for key, label in projects.items()
                ],
                "truncated": False,
            },
            "models": {
                "items": [
                    {
                        "id": key,
                        "label": "未映射模型"
                        if key == "unmapped"
                        else models.get(key, "已删除或不可见模型"),
                    }
                    for key in raw["facets"]["models"]["items"]
                ],
                "truncated": raw["facets"]["models"]["truncated"],
            },
            "agents": {
                "items": [
                    {
                        **row,
                        "agent_id": agents.get(
                            (row["project_id"], row["graph_id"]), (None, None)
                        )[0],
                        "label": agents.get(
                            (row["project_id"], row["graph_id"]), (None, "已删除 Agent")
                        )[1],
                    }
                    for row in raw["facets"]["agents"]["items"]
                ],
                "truncated": raw["facets"]["agents"]["truncated"],
            },
        }
        result = UsageDashboardV1.model_validate(raw)
        prior = result.previous_window.window
        if (
            prior.end != result.window.start
            or result.window.start - prior.start
            != result.window.end - result.window.start
            or prior.timezone != result.window.timezone
            or prior.granularity != result.window.granularity
        ):
            raise _invalid_upstream()
        if any(
            point.start < result.window.start
            or point.end > result.window.end
            or point.end <= point.start
            for point in result.series
        ) or len({row.key for row in result.breakdown.items}) != len(groups):
            raise _invalid_upstream()
        if result.series and (
            result.series[0].start != result.window.start
            or result.series[-1].end != result.window.end
            or any(
                a.end != b.start
                for a, b in zip(result.series, result.series[1:], strict=False)
            )
        ):
            raise _invalid_upstream()
        partition = result.breakdown.items + (
            [result.breakdown.other] if result.breakdown.other else []
        )
        for rows in (result.series, partition):
            if (
                sum(row.coverage.observed_call_count for row in rows)
                != result.summary.coverage.observed_call_count
            ):
                raise _invalid_upstream()
            for key in type(result.summary.known_tokens).model_fields:
                total = getattr(result.summary.known_tokens, key)
                if (
                    total is not None
                    and sum(getattr(row.known_tokens, key) or 0 for row in rows)
                    != total
                ):
                    raise _invalid_upstream()
            cost = result.summary.cost.known_cost_usd
            if cost is not None and sum(
                (Decimal(row.cost.known_cost_usd or "0") for row in rows), Decimal(0)
            ) != Decimal(cost):
                raise _invalid_upstream()
        return _bounded_result(result)

    async def dashboard(self, *, context, project_id, requested, query):
        try:
            async with asyncio.timeout(5), self.query_slots:
                return await self._dashboard(
                    context=context,
                    project_id=project_id,
                    requested=requested,
                    query=query,
                )
        except TimeoutError as exc:
            raise ServiceUnavailableError(
                code="usage_query_capacity_exhausted",
                message="Usage query capacity is temporarily unavailable",
            ) from exc

    async def _dashboard(self, *, context, project_id, requested, query):
        actor, projects, graph_id = await run_in_threadpool(
            self._authorize, context, project_id, requested, query
        )
        if not projects:
            await run_in_threadpool(
                self._authorize, context, project_id, requested, query
            )
            return empty_dashboard(query, context.request.request_id)
        payload = self._payload(context, actor, projects, graph_id, query)
        raw = await self.upstream.usage_analytics(payload, secret=self.secret)
        _, current_projects, current_graph = await run_in_threadpool(
            self._authorize, context, project_id, requested, query
        )
        if set(current_projects) != set(projects) or current_graph != graph_id:
            raise ForbiddenError(
                code="usage_scope_changed",
                message="Usage permission scope changed; refresh the query",
            )
        try:
            return await run_in_threadpool(
                self._dashboard_projection,
                raw,
                payload,
                current_projects,
                "project" if project_id else "platform",
            )
        except (
            ValidationError,
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise _invalid_upstream() from exc

    def _visible_runs(self, actor, project_id, candidates):
        ids = {str(item.thread_id) for item in candidates}
        with self.factory.begin() as session:
            deleted_runs = set(
                session.scalars(
                    select(AuditLogRecord.target_id).where(
                        AuditLogRecord.project_id == project_id,
                        AuditLogRecord.action.in_(
                            {"run.deleted", "runtime.run.item.deleted"}
                        ),
                        AuditLogRecord.result == "success",
                        AuditLogRecord.target_id.in_(
                            {str(row.run_id) for row in candidates}
                        ),
                    )
                )
            )
            records = session.scalars(
                select(ThreadAccessRecord).where(
                    ThreadAccessRecord.project_id == project_id,
                    ThreadAccessRecord.thread_id.in_(ids),
                    ThreadAccessRecord.provisioning_status == "ready",
                )
            )
            visible = set()
            for row in records:
                metadata = thread_access.record_metadata(row)
                if thread_access.allowed(actor, project_id, metadata, "read"):
                    visible.add(row.thread_id)
                    if (
                        metadata["visibility"] == "private"
                        and not thread_access.is_owner(actor, metadata)
                        and thread_access.is_manager(actor, project_id)
                    ):
                        thread_access._audit(
                            session,
                            actor=actor,
                            project_id=project_id,
                            thread_id=row.thread_id,
                            action="thread.takeover.accessed",
                            reason="time-limited private Thread usage access",
                        )
        return [
            row
            for row in candidates
            if str(row.thread_id) in visible and str(row.run_id) not in deleted_runs
        ]

    async def runs(self, *, context, project_id, query):
        actor, projects, graph_id = await run_in_threadpool(
            self._authorize, context, project_id, None, query
        )
        scope = binding(
            actor=actor,
            tenant_id=context.tenant.tenant_id,
            project_id=project_id,
            query=query,
        )
        payload = self._payload(context, actor, projects, graph_id, query)
        if query.cursor:
            payload["cursor"], payload["cutoff"] = decode_cursor(
                self.secret, scope, query.cursor
            )
        raw = await self.upstream.usage_analytics(
            payload, secret=self.secret, runs=True
        )
        current, current_projects, current_graph = await run_in_threadpool(
            self._authorize, context, project_id, None, query
        )
        if set(current_projects) != set(projects) or current_graph != graph_id:
            raise ForbiddenError(
                code="usage_scope_changed",
                message="Usage permission scope changed; refresh the query",
            )
        try:
            self._check_envelope(raw, payload)
            if (
                raw["project_ids"] != [project_id]
                or datetime.fromisoformat(raw["from"]) != query.start
                or datetime.fromisoformat(raw["to"]) != query.end
                or len(raw["items"]) > query.limit
            ):
                raise _invalid_upstream()
            if payload.get("cutoff") and raw["cutoff"] != payload["cutoff"]:
                raise _invalid_upstream()
            as_of, cutoff = _timestamp(raw["as_of"]), _timestamp(raw["cutoff"])
            if cutoff > as_of or not payload.get("cutoff") and cutoff != as_of:
                raise _invalid_upstream()
            candidates = [
                UsageRun.model_validate({**row, "agent_name": ""})
                for row in raw["items"]
            ]
            if len({row.run_id for row in candidates}) != len(candidates) or any(
                str(row.project_id) != project_id
                or not query.start
                <= row.first_matching_call_at
                <= row.last_matching_call_at
                < query.end
                or row.last_matching_call_at > cutoff
                or graph_id is not None
                and row.graph_id != graph_id
                for row in candidates
            ):
                raise _invalid_upstream()
            positions = [(row.last_matching_call_at, row.run_id) for row in candidates]
            if positions != sorted(positions, reverse=True) or (
                payload.get("cursor")
                and any(
                    position
                    >= (
                        _timestamp(payload["cursor"]["at"]),
                        UUID(payload["cursor"]["run_id"]),
                    )
                    for position in positions
                )
            ):
                raise _invalid_upstream()
            if raw["next_cursor"] is not None:
                cursor = raw["next_cursor"]
                if (
                    not candidates
                    or set(cursor) != {"at", "run_id"}
                    or UUID(cursor["run_id"]) != candidates[-1].run_id
                    or datetime.fromisoformat(cursor["at"])
                    != candidates[-1].last_matching_call_at
                ):
                    raise _invalid_upstream()
            rows = await run_in_threadpool(
                self._visible_runs, current, project_id, candidates
            )
            _, agents = await run_in_threadpool(
                self._names,
                current_projects,
                [],
                {(str(row.project_id), row.graph_id) for row in rows},
            )
            for row in rows:
                agent_id, row.agent_name = agents.get(
                    (project_id, row.graph_id), (None, "已删除 Agent")
                )
                row.agent_id = UUID(agent_id) if agent_id else None
            cursor = (
                encode_cursor(self.secret, scope, raw["next_cursor"], raw["cutoff"])
                if raw["next_cursor"]
                else None
            )
            return _bounded_result(
                UsageRunPageV1.model_validate(
                    {
                        "version": 1,
                        "items": rows,
                        "next_cursor": cursor,
                        "as_of": raw["as_of"],
                        "request_id": context.request.request_id,
                    }
                )
            )
        except (
            ValidationError,
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ) as exc:
            raise _invalid_upstream() from exc
