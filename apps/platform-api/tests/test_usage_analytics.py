import asyncio
import base64
import copy
import hashlib
import hmac
import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import QueryParams

from platform_api.adapters.langgraph.runtime_gateway_upstream import (
    LangGraphRuntimeGatewayUpstream,
)
from platform_api.core.context.models import (
    ActorContext,
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)
from platform_api.core.db import create_core_tables
from platform_api.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from platform_api.core.errors.handlers import register_exception_handlers
from platform_api.entrypoints.http.middleware.request_context import (
    register_request_context_middleware,
)
from platform_api.modules.audit.http_resolution import (
    AuditHttpRequest,
    resolve_http_audit,
)
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.audit.schemas import AuditResult
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.identity.models import UserRecord
from platform_api.modules.projects.models import (
    ProjectMemberRecord,
    ProjectRecord,
    TenantRecord,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)
from platform_api.modules.service_accounts.models import (
    ServiceAccountProjectGrantRecord,
    ServiceAccountRecord,
    ServiceAccountTokenRecord,
)
from platform_api.modules.usage_analytics.contracts import (
    DashboardQuery,
    RunsQuery,
    UsageDashboardV1,
    empty_dashboard,
    parse_query,
)
from platform_api.modules.usage_analytics.cursor import decode_cursor, encode_cursor
from platform_api.modules.usage_analytics.router import get_usage_service, router
from platform_api.modules.usage_analytics.service import (
    UsageAnalyticsService,
    _bounded_result,
)

SECRET = "usage-test-secret-at-least-32-bytes"
FROM, TO = "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z"


def test_dashboard_admission_serializes_whole_chain_and_recovers_after_timeout():
    service = UsageAnalyticsService(session_factory=None, upstream=None, secret=SECRET)

    async def verify():
        active, maximum = 0, 0

        async def execute(**kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            try:
                await asyncio.sleep(0.01)
                if kwargs["query"] == "fail":
                    raise TimeoutError()
                return kwargs["query"]
            finally:
                active -= 1

        service._dashboard = execute
        args = dict(context=None, project_id=None, requested=None)
        assert await asyncio.gather(
            *(service.dashboard(**args, query=i) for i in range(3))
        ) == [0, 1, 2]
        assert maximum == 2
        with pytest.raises(ServiceUnavailableError):
            await service.dashboard(**args, query="fail")
        assert await service.dashboard(**args, query="recovered") == "recovered"

    asyncio.run(verify())


@pytest.fixture
def environment(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'usage.db'}")
    create_core_tables(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    tenant, other, project, user, owner = (uuid4() for _ in range(5))
    with factory.begin() as session:
        session.add_all(
            [
                TenantRecord(id=tenant, slug="__default", name="Default"),
                TenantRecord(id=other, slug="other", name="Other"),
                UserRecord(
                    id=user,
                    username="analyst",
                    external_subject="analyst",
                    platform_roles_json=["platform_operator"],
                ),
                UserRecord(id=owner, username="owner", external_subject="owner"),
            ]
        )
        session.flush()
        session.add(ProjectRecord(id=project, tenant_id=tenant, name="Test project"))
        session.flush()
        session.add(
            ProjectMemberRecord(project_id=project, user_id=user, role="editor")
        )
    context = PlatformRequestContext(
        RequestContext(
            request_id="usage-request",
            trace_id="trace",
            method="GET",
            path="/api/usage/dashboard",
            started_at=0,
        ),
        TenantContext("__default"),
        ProjectContext(str(project)),
        ActorContext(
            user_id=str(user),
            platform_roles=("platform_operator",),
            project_roles={str(project): ("project_editor",)},
        ),
    )
    upstream = SimpleNamespace(usage_analytics=AsyncMock())
    service = UsageAnalyticsService(
        session_factory=factory, upstream=upstream, secret=SECRET
    )
    yield SimpleNamespace(
        service=service,
        upstream=upstream,
        context=context,
        project=str(project),
        factory=factory,
        tenant=tenant,
        other=other,
        user=user,
        owner=str(owner),
    )
    engine.dispose()


def dashboard_fixture(project):
    query = DashboardQuery.model_validate({"from": FROM, "to": TO})
    raw = empty_dashboard(query, "usage-request").model_dump(mode="json", by_alias=True)
    raw["scope"] = {"project_ids": [project], "covered_project_count": 1}
    raw["facets"] = {
        "models": {"items": [], "truncated": False},
        "agents": {"items": [], "truncated": False},
    }
    raw["tenant_id"] = "__default"
    raw["filters"] = {
        "model_id": None,
        "model_mapping": None,
        "graph_id": None,
        "purpose": None,
        "scope": None,
    }
    raw["prompt"] = "CANARY_PROMPT"
    raw["pricing_snapshot"] = {"api_key": "CANARY_KEY"}
    return raw


@pytest.mark.parametrize(
    "role,permission,expected",
    [
        ("platform_super_admin", "platform", True),
        ("platform_operator", "platform", True),
        ("platform_viewer", "platform", False),
        ("project_admin", "project", True),
        ("project_editor", "project", True),
        ("project_executor", "project", False),
        ("project_viewer", "project", False),
        ("platform_super_admin", "project", False),
    ],
)
def test_role_matrix(role, permission, expected):
    actor = ActorContext(
        user_id="actor",
        platform_roles=(role,) if role.startswith("platform") else (),
        project_roles={"p": (role,)} if role.startswith("project") else {},
    )
    code = (
        PermissionCode.PLATFORM_USAGE_READ
        if permission == "platform"
        else PermissionCode.PROJECT_USAGE_READ
    )
    assert (
        IamPolicyEngine()
        .evaluate(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=code, project_id="p" if permission == "project" else None
            ),
        )
        .allowed
        is expected
    )


@pytest.mark.parametrize(
    "query",
    [
        "from=" + FROM,
        "from=" + FROM + "&to=" + TO + "&source=web",
        "from=" + FROM + "&to=" + TO + "&from=" + FROM,
        "from=" + TO + "&to=" + FROM,
        "from=" + FROM + "&to=" + TO + "&model_id=oops",
        "from="
        + FROM
        + "&to="
        + TO
        + "&model_mapping=unmapped&model_id="
        + str(uuid4()),
        "from=" + FROM + "&to=" + TO + "&top_n=51",
    ],
)
def test_invalid_public_query(query):
    with pytest.raises(BadRequestError):
        parse_query(QueryParams(query))


def test_runs_whitelist_and_project_lists():
    with pytest.raises(BadRequestError):
        parse_query(
            QueryParams({"from": FROM, "to": TO, "granularity": "hour"}), runs=True
        )
    p = str(uuid4())
    with pytest.raises(BadRequestError):
        parse_query(
            QueryParams(
                [("from", FROM), ("to", TO), ("project_ids", p), ("project_ids", p)]
            ),
            platform=True,
        )
    query, projects = parse_query(QueryParams({"from": FROM, "to": TO}))
    assert query.granularity == "day" and projects is None


def test_dashboard_filters_reauthorization_and_private_data_projection(environment):
    env = environment
    env.upstream.usage_analytics.return_value = dashboard_fixture(env.project)
    query = DashboardQuery.model_validate({"from": FROM, "to": TO})
    result = asyncio.run(
        env.service.dashboard(
            context=env.context, project_id=env.project, requested=None, query=query
        )
    )
    assert result.scope.project_ids == [UUID(env.project)]
    assert "CANARY" not in result.model_dump_json()
    assert env.upstream.usage_analytics.call_args.args[0]["tenant_id"] == "__default"
    for mutation in (
        {"tenant_id": "other"},
        {"version": True},
        {"as_of": "2026-10-02T00:00:00"},
        {
            "filters": {
                "model_id": str(uuid4()),
                "model_mapping": None,
                "graph_id": None,
                "purpose": None,
                "scope": None,
            }
        },
        {"scope": {"project_ids": [str(uuid4())], "covered_project_count": 1}},
        {
            "window": {
                "from": FROM,
                "to": TO,
                "timezone": "UTC",
                "granularity": "day",
                "time_basis": "model_call_started_at",
            }
        },
    ):
        env.upstream.usage_analytics.return_value = {
            **dashboard_fixture(env.project),
            **mutation,
        }
        with pytest.raises(PlatformApiError) as error:
            asyncio.run(
                env.service.dashboard(
                    context=env.context,
                    project_id=env.project,
                    requested=None,
                    query=query,
                )
            )
        assert error.value.status_code == 502

    async def revoke(payload, **kwargs):
        with env.factory.begin() as session:
            session.execute(
                delete(ProjectMemberRecord).where(
                    ProjectMemberRecord.user_id == env.user
                )
            )
        return dashboard_fixture(env.project)

    env.upstream.usage_analytics.side_effect = revoke
    with pytest.raises(ForbiddenError):
        asyncio.run(
            env.service.dashboard(
                context=env.context, project_id=env.project, requested=None, query=query
            )
        )


def test_cross_tenant_deleted_project_and_empty_scope(environment):
    env = environment
    foreign = uuid4()
    with env.factory.begin() as session:
        session.add(ProjectRecord(id=foreign, tenant_id=env.other, name="Foreign"))
    query = DashboardQuery.model_validate({"from": FROM, "to": TO})
    with pytest.raises(NotFoundError):
        asyncio.run(
            env.service.dashboard(
                context=env.context,
                project_id=None,
                requested=[str(foreign)],
                query=query,
            )
        )
    env.upstream.usage_analytics.assert_not_called()
    with env.factory.begin() as session:
        session.get(ProjectRecord, UUID(env.project)).status = "deleted"
    result = asyncio.run(
        env.service.dashboard(
            context=env.context, project_id=None, requested=None, query=query
        )
    )
    assert not result.scope.project_ids and result.availability == "unavailable"
    env.upstream.usage_analytics.assert_not_called()


def test_report_size_limit_does_not_truncate_totals():
    result = SimpleNamespace(model_dump_json=lambda **kwargs: "x" * (300 * 1024 + 1))
    with pytest.raises(PlatformApiError) as error:
        _bounded_result(result)
    assert error.value.code == "usage_aggregate_range_exceeded"
    assert error.value.status_code == 422


def test_cursor_is_encrypted_scoped_and_expires():
    hidden = str(uuid4())
    cursor = encode_cursor(SECRET, "scope", {"at": FROM, "run_id": hidden}, TO)
    assert hidden.encode() not in base64.urlsafe_b64decode(cursor)
    assert decode_cursor(SECRET, "scope", cursor)[0]["run_id"] == hidden
    for wrong in (cursor[:-10] + "tampered", "not a cursor"):
        with pytest.raises(BadRequestError):
            decode_cursor(SECRET, "scope", wrong)
    with pytest.raises(BadRequestError):
        decode_cursor(SECRET, "other-actor-or-filter", cursor)
    with (
        patch("cryptography.fernet.time.time", return_value=time.time() + 1000),
        pytest.raises(BadRequestError),
    ):
        decode_cursor(SECRET, "scope", cursor)


def test_service_account_current_grant_revoked_credential_and_platform_scope(
    environment,
):
    env = environment
    account, credential = uuid4(), uuid4()
    with env.factory.begin() as session:
        session.add(
            ServiceAccountRecord(
                id=account,
                name="usage-service",
                platform_roles_json=["platform_operator"],
            )
        )
        session.flush()
        session.add_all(
            [
                ServiceAccountTokenRecord(
                    id=credential,
                    service_account_id=account,
                    name="usage",
                    token_prefix="test",
                    token_secret_hash="private",
                ),
                ServiceAccountProjectGrantRecord(
                    service_account_id=account,
                    project_id=UUID(env.project),
                    role="editor",
                ),
            ]
        )
    actor = ActorContext(
        subject=f"service-account:{account}",
        principal_type="service_account",
        authentication_type="api_key",
        credential_id=str(credential),
    )
    context = replace(env.context, actor=actor)
    query = DashboardQuery.model_validate({"from": FROM, "to": TO})
    env.upstream.usage_analytics.side_effect = lambda *a, **k: dashboard_fixture(
        env.project
    )
    result = asyncio.run(
        env.service.dashboard(
            context=context, project_id=env.project, requested=None, query=query
        )
    )
    assert result.scope.covered_project_count == 1
    result = asyncio.run(
        env.service.dashboard(
            context=context, project_id=None, requested=None, query=query
        )
    )
    assert result.scope.kind == "platform"
    with env.factory.begin() as session:
        session.execute(delete(ServiceAccountProjectGrantRecord))
    with pytest.raises(ForbiddenError):
        asyncio.run(
            env.service.dashboard(
                context=context, project_id=env.project, requested=None, query=query
            )
        )
    with env.factory.begin() as session:
        session.get(ServiceAccountTokenRecord, credential).revoked_at = datetime.now(
            UTC
        )
    with pytest.raises(ForbiddenError):
        asyncio.run(
            env.service.dashboard(
                context=context, project_id=None, requested=None, query=query
            )
        )


def test_runs_acl_short_page_and_takeover_audit(environment):
    env = environment
    private, own = str(uuid4()), str(uuid4())
    metric = dashboard_fixture(env.project)["summary"]

    def item(thread):
        return {
            **metric,
            "project_id": env.project,
            "thread_id": thread,
            "run_id": str(uuid4()),
            "graph_id": "agent",
            "first_matching_call_at": "2026-10-01T12:00:00Z",
            "last_matching_call_at": "2026-10-01T12:00:00Z",
            "prompt": "CANARY_PRIVATE",
        }

    rows = [item(private), item(own)]
    rows.sort(
        key=lambda row: (row["last_matching_call_at"], row["run_id"]), reverse=True
    )
    with env.factory.begin() as session:
        session.add_all(
            [
                ThreadAccessRecord(
                    thread_id=private,
                    project_id=env.project,
                    owner_user_id=env.owner,
                    visibility="private",
                    shared_actions={},
                    project_actions=[],
                    takeovers={},
                    provisioning_status="ready",
                ),
                ThreadAccessRecord(
                    thread_id=own,
                    project_id=env.project,
                    owner_user_id=str(env.user),
                    visibility="private",
                    shared_actions={},
                    project_actions=[],
                    takeovers={},
                    provisioning_status="ready",
                ),
            ]
        )
    raw = {
        "version": 1,
        "tenant_id": "__default",
        "project_ids": [env.project],
        "filters": dashboard_fixture(env.project)["filters"],
        "from": FROM,
        "to": TO,
        "as_of": TO,
        "cutoff": TO,
        "items": rows,
        "next_cursor": {
            "at": rows[-1]["last_matching_call_at"],
            "run_id": rows[-1]["run_id"],
        },
        "request_id": "usage-request",
    }

    async def read_page():
        return await env.service.runs(
            context=env.context,
            project_id=env.project,
            query=RunsQuery.model_validate({"from": FROM, "to": TO}),
        )

    for mutation in (
        {"as_of": "2026-10-01T00:00:00"},
        {"cutoff": "2026-10-03T00:00:00Z"},
        {"items": list(reversed(rows)), "next_cursor": None},
        {"items": [{**rows[0], "project_id": str(uuid4())}], "next_cursor": None},
    ):
        env.upstream.usage_analytics.side_effect = None
        env.upstream.usage_analytics.return_value = {**raw, **mutation}
        with pytest.raises(PlatformApiError) as error:
            asyncio.run(read_page())
        assert error.value.code == "usage_backend_invalid_response"
    env.upstream.usage_analytics.side_effect = lambda *a, **k: copy.deepcopy(raw)
    query = RunsQuery.model_validate({"from": FROM, "to": TO})
    page = asyncio.run(
        env.service.runs(context=env.context, project_id=env.project, query=query)
    )
    assert (
        len(page.items) == 1
        and str(page.items[0].thread_id) == own
        and page.next_cursor
    )
    assert (
        next(row["run_id"] for row in rows if row["thread_id"] == private)
        not in page.model_dump_json()
        and "CANARY" not in page.model_dump_json()
    )
    own_run = next(row["run_id"] for row in rows if row["thread_id"] == own)
    with env.factory.begin() as session:
        session.add(
            AuditLogRecord(
                request_id="usage-deletion-test",
                plane="runtime_gateway",
                project_id=env.project,
                action="runtime.run.item.deleted",
                target_type="run",
                target_id=own_run,
                result="success",
                method="DELETE",
                path=f"/api/langgraph/threads/{own}/runs/{own_run}",
                status_code=200,
                duration_ms=0,
                metadata_json={},
            )
        )
    deleted = asyncio.run(read_page())
    assert not deleted.items and deleted.next_cursor
    with env.factory.begin() as session:
        session.execute(
            delete(AuditLogRecord).where(
                AuditLogRecord.request_id == "usage-deletion-test"
            )
        )
    with env.factory.begin() as session:
        session.get(
            ProjectMemberRecord,
            session.scalar(
                select(ProjectMemberRecord.id).where(
                    ProjectMemberRecord.user_id == env.user
                )
            ),
        ).role = "admin"
        session.get(ThreadAccessRecord, private).takeovers = {
            str(env.user): {"expires_at": time.time() + 100}
        }
    page = asyncio.run(
        env.service.runs(context=env.context, project_id=env.project, query=query)
    )
    assert len(page.items) == 2
    with env.factory() as session:
        assert session.scalar(
            select(AuditLogRecord.id).where(
                AuditLogRecord.action == "thread.takeover.accessed"
            )
        )
    with env.factory.begin() as session:
        session.execute(delete(ThreadAccessRecord))
    page = asyncio.run(
        env.service.runs(context=env.context, project_id=env.project, query=query)
    )
    assert not page.items and page.next_cursor


def test_adapter_signs_the_final_bytes_and_uses_exact_path():
    adapter = LangGraphRuntimeGatewayUpstream(
        base_url="http://runtime",
        timeout_seconds=30,
        forwarded_headers={"authorization": "OLD JWT"},
    )
    payload = {
        "request_id": "request",
        "tenant_id": "__default",
        "project_ids": [str(uuid4())],
    }
    with patch(
        "platform_api.adapters.langgraph.runtime_client.LangGraphRuntimeClient.request_json",
        AsyncMock(return_value={}),
    ) as request:
        asyncio.run(adapter.usage_analytics(payload, secret=SECRET))
    args, kwargs = request.call_args
    assert args == ("POST", "/internal/usage/aggregate")
    assert "authorization" not in kwargs["forwarded_headers"]
    stamp = kwargs["forwarded_headers"]["x-usage-query-timestamp"]
    expected = (
        "sha256="
        + hmac.new(
            SECRET.encode(),
            f"usage-query/v1\n{stamp}\nPOST\n/internal/usage/aggregate\n".encode()
            + kwargs["body_bytes"],
            hashlib.sha256,
        ).hexdigest()
    )
    assert kwargs["forwarded_headers"]["x-usage-query-signature"] == expected
    assert json.loads(kwargs["body_bytes"]) == payload
    with (
        patch(
            "platform_api.adapters.langgraph.runtime_client.LangGraphRuntimeClient.request_json",
            AsyncMock(side_effect=TimeoutError("CANARY_PRIVATE")),
        ),
        pytest.raises(PlatformApiError) as timed_out,
    ):
        asyncio.run(adapter.usage_analytics(payload, secret=SECRET))
    assert timed_out.value.status_code == 504
    assert timed_out.value.code == "langgraph_upstream_timeout"
    assert "CANARY" not in timed_out.value.message


def test_adapter_total_deadline_bounds_a_slow_upstream():
    async def verify():
        clients = set()

        async def slow(reader, writer):
            clients.add(writer)
            await reader.read(65536)

        server = await asyncio.start_server(slow, "127.0.0.1", 0)
        adapter = LangGraphRuntimeGatewayUpstream(
            base_url=f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}",
            timeout_seconds=30,
        )
        started = time.monotonic()
        try:
            with pytest.raises(PlatformApiError) as timed_out:
                await adapter.usage_analytics({"request_id": "deadline"}, secret=SECRET)
            assert timed_out.value.status_code == 504
            assert time.monotonic() - started < 5.5
        finally:
            for writer in clients:
                writer.close()
                await writer.wait_closed()
            server.close()
            await server.wait_closed()
        with pytest.raises(PlatformApiError) as offline:
            await adapter.usage_analytics({"request_id": "offline"}, secret=SECRET)
        assert offline.value.status_code == 502

    asyncio.run(verify())


def test_frozen_hmac_vector_matches_adapter():
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "docs/projects/20261011-token-usage-dashboard/fixtures/hmac-vector.json"
        ).read_text()
    )
    adapter = LangGraphRuntimeGatewayUpstream(
        base_url="http://runtime", timeout_seconds=30
    )
    with (
        patch(
            "time.time",
            return_value=int(fixture["timestamp"]),
        ),
        patch(
            "platform_api.adapters.langgraph.runtime_client.LangGraphRuntimeClient.request_json",
            AsyncMock(return_value={}),
        ) as request,
    ):
        asyncio.run(
            adapter.usage_analytics(
                json.loads(fixture["body_utf8"]), secret=fixture["secret_for_test_only"]
            )
        )
    assert request.call_args.kwargs["body_bytes"].decode() == fixture["body_utf8"]
    assert (
        request.call_args.kwargs["forwarded_headers"]["x-usage-query-signature"]
        == fixture["signature"]
    )


def test_public_routes_headers_and_audit_actions(environment):
    env = environment
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    app.dependency_overrides[get_usage_service] = lambda: env.service

    @app.middleware("http")
    async def context(request: Request, call_next):
        request.state.platform_context = env.context
        request.state.request_id = "usage-request"
        return await call_next(request)

    register_request_context_middleware(app)

    env.upstream.usage_analytics.side_effect = lambda *a, **k: dashboard_fixture(
        env.project
    )

    async def verify():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://api"
        ) as client:
            response = await client.get(
                "/api/usage/dashboard", params={"from": FROM, "to": TO}
            )
            assert (
                response.status_code == 200
                and response.headers["cache-control"] == "no-store"
            )
            UsageDashboardV1.model_validate(response.json())
            bad = await client.get(
                f"/api/projects/{env.project}/usage/runs",
                params={"from": FROM, "to": TO, "rank_by": "known_cost_usd"},
            )
            assert bad.status_code == 400 and bad.headers["cache-control"] == "no-store"

    asyncio.run(verify())
    for path, action in [
        ("/api/usage/dashboard", "platform.usage.read"),
        (f"/api/projects/{env.project}/usage/dashboard", "project.usage.read"),
        (f"/api/projects/{env.project}/usage/runs", "usage.runs.read"),
    ]:
        request = AuditHttpRequest(
            method="GET",
            path=path,
            query_params={},
            query_string=None,
            state_project_id=None,
            client_ip=None,
            user_agent=None,
            response_content_length=None,
            metadata={"usage_from": FROM, "api_key": "CANARY"},
        )
        resolved = resolve_http_audit(
            request=request,
            response_payload=None,
            actor_user_id=str(env.user),
            status_code=200,
            result=AuditResult.SUCCESS,
        )
        assert (
            resolved.action == action
            and resolved.metadata["usage_from"] == FROM
            and "api_key" not in resolved.metadata
        )
