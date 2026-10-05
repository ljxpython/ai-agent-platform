"""Disposable cron E2E. Run with Runtime dependencies plus platform-api's src.

Requires graphharbor_cron_probe_20261005 and its dedicated Redis prefix.
Never points at or truncates the platform's active database.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import socket
import tempfile
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import uvicorn
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from langgraph_runtime_pg.cron import dispatch_due_crons
from langgraph_runtime_pg.database import connect, start_pool, truncate_all
from langgraph_runtime_pg.models import CronRow, RunRow
from langgraph_runtime_pg.production_worker import ProductionWorker
from langhost.server import create_app as runtime_app
from platform_api.adapters.langgraph.runtime_gateway_upstream import (
    LangGraphRuntimeGatewayUpstream,
)
from platform_api.core.db import session_scope
from platform_api.core.errors import UpstreamServiceError
from platform_api.core.security import create_access_token, hash_password
from platform_api.main import create_app
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.identity.models import UserRecord
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.models import (
    ProjectMemberRecord,
    ProjectRecord,
    TenantRecord,
)
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)
from platform_api.modules.service_accounts.models import (
    ServiceAccountProjectGrantRecord,
    ServiceAccountRecord,
    ServiceAccountTokenRecord,
)
from sqlalchemy import select

from runtime_service.http.crons import router

SECRET = "isolated-cron-verification-secret-32-bytes"


@asynccontextmanager
async def serve(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(15):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Server did not start")
                await asyncio.sleep(0.02)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task
        sock.close()


async def main():
    assert os.environ.get("DATABASE_URI", "").endswith(
        "/graphharbor_cron_probe_20261005"
    )
    assert (
        os.environ.get("GRAPHHARBOR_REDIS_PREFIX") == "graphharbor:cron-probe-20261005"
    )
    os.environ.update(
        {
            "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
            "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
            "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
            "GRAPHHARBOR_ENV": "production",
            "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": SECRET,
            "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER": "graphharbor",
            "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE": "graphharbor-worker",
        }
    )
    with tempfile.TemporaryDirectory(prefix="scheduled-chain-") as directory:
        base = Path(directory)
        (base / "graph.py").write_text(
            "from langgraph.graph import StateGraph, START, END\n"
            "from langgraph.types import interrupt\n"
            "from typing_extensions import TypedDict\n"
            "from runtime_service.runtime.scheduled import scheduled_execution\n"
            "class State(TypedDict):\n    messages: list\n"
            "def run(state):\n"
            "    text = state['messages'][0]['content']\n"
            "    if text == 'approval': interrupt('approve')\n"
            "    if text == 'failure': raise ValueError('probe failure')\n"
            "    return {'messages': [{'role': 'assistant', 'content': 'done'}]}\n"
            "async def factory(config):\n"
            "    g = StateGraph(State)\n"
            "    g.add_node('run', run)\n"
            "    g.add_edge(START, 'run')\n"
            "    g.add_edge('run', END)\n"
            "    return g.compile()\n"
            "graph = scheduled_execution(factory, agent_key='probe')\n"
        )
        (base / "auth.py").write_text(
            "from runtime_service.auth.platform import auth\n"
        )
        native = runtime_app(
            {"graphs": {"probe": "graph.py:graph"}, "auth": {"path": "auth.py:auth"}},
            base_dir=base,
        )

        @asynccontextmanager
        async def runtime_lifespan(app):
            await start_pool()
            await truncate_all()
            async with LifespanManager(native):
                yield

        runtime = FastAPI(lifespan=runtime_lifespan)
        runtime.include_router(router)
        runtime.mount("/", native)
        async with serve(runtime) as runtime_url:
            platform = create_app()
            settings = platform.state.settings
            settings.platform_db_enabled = settings.platform_db_auto_create = True
            settings.database_url = f"sqlite:///{base / 'platform.db'}"
            settings.bootstrap_admin_enabled = False
            settings.auth_required = True
            settings.runtime_delegation_secret = (
                settings.runtime_model_config_secret
            ) = SECRET
            settings.langgraph_upstream_url = runtime_url
            async with serve(platform) as platform_url:
                os.environ["PLATFORM_THREAD_AUTHORIZATION_URL"] = (
                    platform_url + "/api/runtime/internal/thread-authorization"
                )
                factory = platform.state.db_session_factory
                tenant, project, other_project, model = (
                    uuid4(),
                    uuid4(),
                    uuid4(),
                    uuid4(),
                )
                with session_scope(factory) as session:
                    repo = SqlAlchemyIdentityRepository(session)
                    users = [
                        repo.create_user(
                            username=name,
                            password_hash=hash_password("test-password"),
                            external_subject=name,
                            email=None,
                            is_super_admin=False,
                            platform_roles=(),
                            must_change_password=False,
                        ).id
                        for name in ("alice", "bob")
                    ]
                    session.add(TenantRecord(id=tenant, name="probe", slug="probe"))
                    session.flush()
                    session.add_all(
                        [
                            ProjectRecord(id=p, tenant_id=tenant, name=str(p))
                            for p in (project, other_project)
                        ]
                    )
                    session.flush()
                    session.add_all(
                        [
                            ProjectMemberRecord(
                                project_id=project, user_id=u, role="editor"
                            )
                            for u in users
                        ]
                    )
                    agent = AgentRecord(
                        project_id=project,
                        name="probe",
                        graph_id="probe",
                        created_by=users[0],
                        updated_by=users[0],
                    )
                    session.add(agent)
                    session.add(
                        RuntimeCatalogModelRecord(
                            id=model,
                            display_name="probe",
                            provider="openai",
                            base_url="http://unused.invalid",
                            protocol="openai",
                            model_name="probe",
                            api_key_ciphertext="unused",
                            enabled=True,
                        )
                    )
                    session.flush()
                    agent_id = agent.id
                    admin = repo.create_user(
                        username="admin",
                        password_hash=hash_password("test-password"),
                        external_subject="admin",
                        email=None,
                        is_super_admin=True,
                        platform_roles=("platform_super_admin",),
                        must_change_password=False,
                    )
                    admin_id = admin.id
                headers = {
                    "x-project-id": str(project),
                    "Authorization": "Bearer "
                    + create_access_token(
                        user_id=str(users[0]), username="alice", settings=settings
                    ),
                }
                bob_headers = {
                    **headers,
                    "Authorization": "Bearer "
                    + create_access_token(
                        user_id=str(users[1]), username="bob", settings=settings
                    ),
                }
                admin_headers = {
                    **headers,
                    "Authorization": "Bearer "
                    + create_access_token(
                        user_id=str(admin_id), username="admin", settings=settings
                    ),
                }
                worker = ProductionWorker(
                    native.state.graph_registry, owner="platform-cron-probe"
                )
                async with httpx.AsyncClient(
                    base_url=platform_url, headers=headers, timeout=20
                ) as client:
                    # Internal callbacks require an authentic, recent Runtime signature.
                    for age, signature in ((0, "forged"), (60, None), (0, None)):
                        stamp = str(int(time.time()) - age)
                        payload = {}
                        canonical = json.dumps(
                            payload, sort_keys=True, separators=(",", ":")
                        )
                        digest = hmac.new(
                            SECRET.encode(),
                            f"{stamp}\nscheduled-authorization\n{canonical}".encode(),
                            hashlib.sha256,
                        ).hexdigest()
                        response = await client.post(
                            "/api/runtime/internal/scheduled-authorization",
                            json=payload,
                            headers={
                                "Authorization": "",
                                "x-runtime-acl-timestamp": stamp,
                                "x-runtime-acl-signature": signature or digest,
                            },
                        )
                        assert response.status_code == (
                            400 if age == 0 and signature is None else 403
                        ), response.text

                    async def request(method, path, expected=200, **kwargs):
                        response = await client.request(
                            method, "/api/scheduled-tasks" + path, **kwargs
                        )
                        assert response.status_code == expected, (
                            method,
                            path,
                            response.status_code,
                            response.text,
                        )
                        return response.json() if response.content else None

                    async def create(**overrides):
                        spec = {
                            "title": "probe",
                            "prompt": "hello",
                            "agent_key": "probe",
                            "cron": "0 0 1 1 *",
                            "context": {"model_id": str(model)},
                            **overrides,
                        }
                        return await request("POST", "", 201, json=spec)

                    async def due(task):
                        async with connect() as conn:
                            row = await conn.session.get(CronRow, UUID(task["id"]))
                            row.next_run_date = datetime.now(UTC) - timedelta(seconds=1)
                        await dispatch_due_crons()
                        history = await request("GET", f"/{task['id']}/runs")
                        assert (
                            history["items"]
                            and history["items"][0]["status"] == "pending"
                        ), history
                        return history["items"][0]

                    async def execute(task, status="success", code=None):
                        run = await due(task)
                        assert await worker.run_once()
                        history = await request("GET", f"/{task['id']}/runs")
                        assert history["items"][0]["run_id"] == run["run_id"]
                        assert history["items"][0]["status"] == status, history
                        if code:
                            assert history["items"][0]["error_code"] == code, history
                        return history

                    preview = await request(
                        "POST",
                        "/preview",
                        json={"cron": "0 3 * * *", "timezone": "America/New_York"},
                    )
                    assert len(preview["times"]) == 5
                    await request(
                        "POST", "/preview", 422, json={"cron": "bad expression"}
                    )
                    task = await create()
                    await request("GET", f"/{task['id']}", 404, headers=bob_headers)
                    assert (await request("GET", "", headers=bob_headers))["total"] == 0
                    assert (
                        await request("GET", f"/{task['id']}/runs", headers=bob_headers)
                    )["total"] == 0
                    await request(
                        "GET",
                        "",
                        403,
                        headers={**headers, "x-project-id": str(other_project)},
                    )
                    original = task["next_run_at"]
                    edited = await request(
                        "PATCH",
                        f"/{task['id']}",
                        json={"title": "edited", "prompt": "changed"},
                    )
                    assert edited["next_run_at"] == original
                    await request(
                        "PATCH", f"/{task['id']}", 400, json={"cron": "invalid"}
                    )
                    await execute(task)
                    await execute(task)
                    page = await request("GET", f"/{task['id']}/runs?limit=1&offset=1")
                    assert page["total"] == 2 and len(page["items"]) == 1
                    await request("POST", f"/{task['id']}/pause")
                    async with connect() as conn:
                        (
                            await conn.session.get(CronRow, UUID(task["id"]))
                        ).next_run_date = datetime.now(UTC) - timedelta(seconds=1)
                    assert await dispatch_due_crons() == 0
                    # Rollback gate: pausing definitions stops dispatch while history stays available.
                    await request("POST", f"/{task['id']}/resume")
                    await request("POST", f"/{task['id']}/pause")
                    manual = await request(
                        "POST",
                        f"/{task['id']}/trigger",
                        202,
                        headers={"Idempotency-Key": "manual-one"},
                    )
                    retry = await request(
                        "POST",
                        f"/{task['id']}/trigger",
                        202,
                        headers={"Idempotency-Key": "manual-one"},
                    )
                    assert (
                        manual["run_id"] == retry["run_id"]
                        and manual["thread_id"] == retry["thread_id"]
                    )
                    concurrent = await asyncio.gather(
                        *[
                            request(
                                "POST",
                                f"/{task['id']}/trigger",
                                202,
                                headers={"Idempotency-Key": "manual-concurrent"},
                            )
                            for _ in range(3)
                        ]
                    )
                    assert (
                        len({r["run_id"] for r in concurrent})
                        == len({r["thread_id"] for r in concurrent})
                        == 1
                    )
                    original_create = LangGraphRuntimeGatewayUpstream.create_thread_run
                    submitted = []

                    async def lose_response(upstream, *args, **kwargs):
                        result = await original_create(upstream, *args, **kwargs)
                        submitted.append(result["run_id"])
                        raise UpstreamServiceError(
                            upstream="langgraph", message="Injected lost response"
                        )

                    with patch.object(
                        LangGraphRuntimeGatewayUpstream,
                        "create_thread_run",
                        lose_response,
                    ):
                        await request(
                            "POST",
                            f"/{task['id']}/trigger",
                            502,
                            headers={"Idempotency-Key": "lost-response"},
                        )
                    recovered = await request(
                        "POST",
                        f"/{task['id']}/trigger",
                        202,
                        headers={"Idempotency-Key": "lost-response"},
                    )
                    assert submitted == [recovered["run_id"]]
                    assert await worker.run_once()
                    await request("DELETE", f"/{task['id']}", 204)
                    history = await request("GET", f"/{task['id']}/runs")
                    assert history["total"] >= 3 and any(
                        r["run_id"] == manual["run_id"] for r in history["items"]
                    ), history
                    while await worker.run_once():
                        pass
                    once_at = (datetime.now(UTC) + timedelta(seconds=3)).replace(
                        microsecond=0
                    )
                    once = await create(
                        schedule_type="once",
                        cron=None,
                        run_at=once_at.isoformat(),
                        timezone="America/New_York",
                    )
                    await asyncio.sleep(
                        max(0, (once_at - datetime.now(UTC)).total_seconds()) + 0.1
                    )
                    await dispatch_due_crons()
                    assert await worker.run_once()
                    assert (await request("GET", f"/{once['id']}"))[
                        "schedule_status"
                    ] == "exhausted"
                    await request("POST", f"/{once['id']}/resume", 400)
                    await request("PATCH", f"/{once['id']}", json={"title": "archived"})
                    await request("DELETE", f"/{once['id']}", 204)
                    for prompt, code in (
                        ("approval", "scheduled_task_approval_required"),
                        ("failure", "scheduled_task_execution_failed"),
                    ):
                        failing = await create(prompt=prompt)
                        await execute(failing, "error", code)
                        await request("DELETE", f"/{failing['id']}", 204)
                    # Mutate current governance only after the queued Run has been accepted.
                    for cls, key, attr, value, code in (
                        (
                            UserRecord,
                            users[0],
                            "status",
                            "disabled",
                            "scheduled_task_principal_revoked",
                        ),
                        (
                            ProjectRecord,
                            project,
                            "status",
                            "deleted",
                            "project_not_found",
                        ),
                        (
                            ProjectRecord,
                            project,
                            "status",
                            "archived",
                            "project_not_found",
                        ),
                        (
                            AgentRecord,
                            agent_id,
                            "status",
                            "disabled",
                            "runtime_target_denied",
                        ),
                        (
                            RuntimeCatalogModelRecord,
                            model,
                            "enabled",
                            False,
                            "runtime_model_denied",
                        ),
                    ):
                        revoked = await create()
                        run = await due(revoked)
                        with session_scope(factory) as session:
                            row = session.get(cls, key)
                            previous = getattr(row, attr)
                            setattr(row, attr, value)
                        assert await worker.run_once()
                        with session_scope(factory) as session:
                            setattr(session.get(cls, key), attr, previous)
                        history = await request("GET", f"/{revoked['id']}/runs")
                        assert (
                            history["items"][0]["status"] == "error"
                            and history["items"][0]["error_code"] == code
                        ), history
                        with session_scope(factory) as session:
                            assert session.scalar(
                                select(AuditLogRecord).where(
                                    AuditLogRecord.target_id == run["run_id"],
                                    AuditLogRecord.result == "denied",
                                )
                            )
                            assert (
                                session.get(ThreadAccessRecord, run["thread_id"])
                                is None
                            )
                        await request("DELETE", f"/{revoked['id']}", 204)
                    revoked = await create()
                    await due(revoked)
                    with session_scope(factory) as session:
                        member = session.scalar(
                            select(ProjectMemberRecord).where(
                                ProjectMemberRecord.project_id == project,
                                ProjectMemberRecord.user_id == users[0],
                            )
                        )
                        session.delete(member)
                    assert await worker.run_once()
                    with session_scope(factory) as session:
                        session.add(
                            ProjectMemberRecord(
                                project_id=project, user_id=users[0], role="editor"
                            )
                        )
                    assert (await request("GET", f"/{revoked['id']}/runs"))["items"][0][
                        "error_code"
                    ] == "scheduled_task_project_revoked"
                    await request("DELETE", f"/{revoked['id']}", 204)
                    for mutation in ("revoke", "delete"):
                        response = await client.post(
                            "/api/langgraph/threads", json={"graph_id": "probe"}
                        )
                        assert response.status_code == 200, response.text
                        thread_id = response.json()["thread_id"]
                        reused = await create(thread_mode="reuse", thread_id=thread_id)
                        await due(reused)
                        if mutation == "delete":
                            response = await client.delete(
                                f"/api/langgraph/threads/{thread_id}"
                            )
                            assert response.status_code == 200 and response.json() == {
                                "ok": True
                            }, response.text
                        else:
                            with session_scope(factory) as session:
                                session.get(
                                    ThreadAccessRecord, thread_id
                                ).owner_user_id = str(users[1])
                        assert await worker.run_once()
                        assert (await request("GET", f"/{reused['id']}/runs"))["items"][
                            0
                        ]["error_code"] == (
                            "thread_not_found"
                            if mutation == "delete"
                            else "thread_action_denied"
                        )
                        await request("DELETE", f"/{reused['id']}", 204)
                    account_response = await client.post(
                        "/api/service-accounts",
                        headers=admin_headers,
                        json={
                            "name": "cron-machine",
                            "platform_roles": ["platform_viewer"],
                        },
                    )
                    assert account_response.status_code == 200, account_response.text
                    account_id = account_response.json()["id"]
                    credential_response = await client.post(
                        f"/api/service-accounts/{account_id}/tokens",
                        headers=admin_headers,
                        json={"name": "cron"},
                    )
                    assert credential_response.status_code == 200, (
                        credential_response.text
                    )
                    credential = credential_response.json()
                    credential_id = credential["token"]["id"]
                    sa_headers = {
                        "Authorization": "",
                        "x-platform-api-key": credential["plain_text_token"],
                        "x-project-id": str(project),
                    }
                    grant = await client.put(
                        f"/api/service-accounts/{account_id}/project-grants/{project}",
                        headers=admin_headers,
                        json={"role": "project_executor"},
                    )
                    assert grant.status_code == 200, grant.text
                    # SA signing, provisioning, manual retries and revocation use real API credentials.
                    sa_task = await request(
                        "POST",
                        "",
                        201,
                        headers=sa_headers,
                        json={
                            "title": "machine",
                            "prompt": "hello",
                            "agent_key": "probe",
                            "cron": "0 0 1 1 *",
                            "context": {"model_id": str(model)},
                        },
                    )

                    async def sa_history():
                        return await request(
                            "GET", f"/{sa_task['id']}/runs", headers=sa_headers
                        )

                    async def sa_due():
                        async with connect() as conn:
                            (
                                await conn.session.get(CronRow, UUID(sa_task["id"]))
                            ).next_run_date = datetime.now(UTC) - timedelta(seconds=1)
                        await dispatch_due_crons()

                    await sa_due()
                    assert await worker.run_once()
                    assert (await sa_history())["items"][0]["status"] == "success"
                    sa_manual = await asyncio.gather(
                        *[
                            request(
                                "POST",
                                f"/{sa_task['id']}/trigger",
                                202,
                                headers={
                                    **sa_headers,
                                    "Idempotency-Key": "machine-manual",
                                },
                            )
                            for _ in range(2)
                        ]
                    )
                    assert sa_manual[0]["run_id"] == sa_manual[1]["run_id"]
                    assert await worker.run_once()
                    for cls, key, attr, value, code in (
                        (
                            ServiceAccountRecord,
                            UUID(account_id),
                            "status",
                            "disabled",
                            "scheduled_task_principal_revoked",
                        ),
                        (
                            ServiceAccountTokenRecord,
                            UUID(credential_id),
                            "revoked_at",
                            datetime.now(UTC),
                            "scheduled_task_principal_revoked",
                        ),
                        (
                            ServiceAccountTokenRecord,
                            UUID(credential_id),
                            "expires_at",
                            datetime.now(UTC) - timedelta(seconds=1),
                            "scheduled_task_principal_revoked",
                        ),
                    ):
                        await sa_due()
                        with session_scope(factory) as session:
                            row = session.get(cls, key)
                            previous = getattr(row, attr)
                            setattr(row, attr, value)
                        assert await worker.run_once()
                        with session_scope(factory) as session:
                            setattr(session.get(cls, key), attr, previous)
                        assert (await sa_history())["items"][0]["error_code"] == code
                    await sa_due()
                    with session_scope(factory) as session:
                        grant = session.scalar(
                            select(ServiceAccountProjectGrantRecord).where(
                                ServiceAccountProjectGrantRecord.service_account_id
                                == UUID(account_id)
                            )
                        )
                        session.delete(grant)
                    assert await worker.run_once()
                    with session_scope(factory) as session:
                        session.add(
                            ServiceAccountProjectGrantRecord(
                                service_account_id=UUID(account_id),
                                project_id=project,
                                role="project_executor",
                            )
                        )
                    assert (await sa_history())["items"][0][
                        "error_code"
                    ] == "scheduled_task_project_revoked"
                    assert (await request("GET", f"/{sa_task['id']}/runs"))[
                        "total"
                    ] == 0
                    await request(
                        "DELETE", f"/{sa_task['id']}", 204, headers=sa_headers
                    )
                    assert (await request("GET", ""))["total"] == 0
                    async with connect() as conn:
                        runs = (await conn.session.scalars(select(RunRow))).all()
                        print(
                            {
                                "result": "passed",
                                "native_runs": len(runs),
                                "success": sum(r.status == "success" for r in runs),
                                "error": sum(r.status == "error" for r in runs),
                                "database": "graphharbor_cron_probe_20261005",
                            }
                        )


if __name__ == "__main__":
    asyncio.run(main())
