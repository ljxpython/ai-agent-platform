"""Isolated HTTP/PG/Redis acceptance with the released GraphHarbor packages.

Run with runtime-service and platform-api src on PYTHONPATH. This script only
truncates its dedicated test database; it never loads a deployment .env.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from langgraph_runtime_pg.checkpoint import get_checkpointer
from langgraph_runtime_pg.database import connect, start_pool, truncate_all
from langgraph_runtime_pg.models import RunLeaseRow, RunRow, RuntimeEventRow
from langgraph_runtime_pg.production_worker import ProductionWorker
from langhost.server import create_app as runtime_app
from platform_api.core.db import session_scope
from platform_api.core.security import create_access_token, hash_password
from platform_api.main import create_app
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.models import (
    ProjectMemberRecord,
    ProjectRecord,
    TenantRecord,
)
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)
from sqlalchemy import func, select
from verify_scheduled_tasks import serve

ROOT = Path(__file__).resolve().parents[1]
DB_NAME = "agent_run_budget_e2e_20261006_e7dd"
PREFIX = "graphharbor:run-budget-e2e:e7dd"
KEY = "__graphharbor_run_budget"
SECRET = "isolated-run-budget-verification-secret-32-bytes"


async def main():
    assert os.environ.get("DATABASE_URI", "").endswith("/" + DB_NAME)
    assert os.environ.get("GRAPHHARBOR_REDIS_PREFIX") == PREFIX
    os.environ.update(
        {
            "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
            "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
            "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
            "GRAPHHARBOR_ENV": "production",
            "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": SECRET,
            "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER": "graphharbor",
            "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE": "graphharbor-worker",
            "GRAPHHARBOR_RUN_TIMEOUT_SECONDS": "30",
            "AGENT_RUN_WRAPUP_RESERVE_SECONDS": "10",
            "GRAPHHARBOR_RETRY_BASE_SECONDS": "0.1",
            "LANGSMITH_TRACING": "false",
        }
    )
    results = []
    with tempfile.TemporaryDirectory(prefix="run-budget-e2e-") as directory:
        base = Path(directory)
        os.environ["RUN_BUDGET_PROBE_WORKSPACE"] = str(base / "workspaces")
        shutil.copyfile(
            ROOT / "apps/runtime-service/tests/acceptance_app/run_budget_probe.py",
            base / "graph.py",
        )
        (base / "auth.py").write_text(
            "from runtime_service.auth.platform import auth\n", encoding="utf-8"
        )
        worker_config = base / "langgraph.json"
        worker_config.write_text(
            json.dumps({"graphs": {"budget_probe": "graph.py:get_agent"}}),
            encoding="utf-8",
        )
        native = runtime_app(
            {
                "graphs": {"budget_probe": "graph.py:get_agent"},
                "auth": {"path": "auth.py:auth"},
            },
            base_dir=base,
        )

        @asynccontextmanager
        async def lifespan(app):
            await start_pool()
            await truncate_all()
            async with LifespanManager(native, startup_timeout=60):
                native.state.graph_registry.attach_checkpointer(get_checkpointer())
                yield

        runtime = FastAPI(lifespan=lifespan)
        runtime.mount("/", native)
        async with serve(runtime, startup_timeout_seconds=60) as runtime_url:
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger(
                "platform_api.entrypoints.http.middleware.request_context"
            ).setLevel(logging.WARNING)
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
            async with serve(platform, startup_timeout_seconds=60) as platform_url:
                os.environ["PLATFORM_THREAD_AUTHORIZATION_URL"] = (
                    platform_url + "/api/runtime/internal/thread-authorization"
                )
                tenant, project, model = uuid4(), uuid4(), uuid4()
                with session_scope(platform.state.db_session_factory) as session:
                    user = SqlAlchemyIdentityRepository(session).create_user(
                        username="budget-user",
                        password_hash=hash_password("test-password"),
                        external_subject="budget-user",
                        email=None,
                        is_super_admin=False,
                        platform_roles=(),
                        must_change_password=False,
                    )
                    user_id = user.id
                    session.add(TenantRecord(id=tenant, name="budget", slug="budget"))
                    session.flush()
                    session.add(
                        ProjectRecord(id=project, tenant_id=tenant, name="budget")
                    )
                    session.flush()
                    session.add(
                        ProjectMemberRecord(
                            project_id=project, user_id=user_id, role="editor"
                        )
                    )
                    session.add(
                        AgentRecord(
                            project_id=project,
                            name="budget",
                            graph_id="budget_probe",
                            created_by=user_id,
                            updated_by=user_id,
                        )
                    )
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
                headers = {
                    "x-project-id": str(project),
                    "Authorization": "Bearer "
                    + create_access_token(
                        user_id=str(user_id), username="budget-user", settings=settings
                    ),
                }
                worker = ProductionWorker(
                    native.state.graph_registry, owner="budget-e2e"
                )
                # Warm schema construction before using subsecond model/short run limits.
                async with native.state.graph_registry.open("budget_probe", {}):
                    pass

                @asynccontextmanager
                async def worker_process(**overrides):
                    with (base / "worker.log").open("ab") as log:
                        process = await asyncio.create_subprocess_exec(
                            sys.executable,
                            "-c",
                            "import asyncio,sys; from pathlib import Path; "
                            "from langgraph_runtime_pg.production_worker import run_worker; "
                            "asyncio.run(run_worker(Path(sys.argv[1])))",
                            str(worker_config),
                            env={**os.environ, **overrides},
                            stdout=log,
                            stderr=log,
                        )
                        try:
                            yield process
                        finally:
                            if process.returncode is None:
                                process.terminate()
                                try:
                                    await asyncio.wait_for(process.wait(), 15)
                                except TimeoutError:
                                    process.kill()
                                    await process.wait()

                async with httpx.AsyncClient(
                    base_url=platform_url + "/api/langgraph",
                    headers=headers,
                    timeout=20,
                    trust_env=False,
                ) as client:

                    async def request(method, path, expected=200, **kwargs):
                        response = await client.request(method, path, **kwargs)
                        assert response.status_code == expected, (
                            method,
                            path,
                            response.status_code,
                            response.text,
                        )
                        assert (
                            KEY not in response.text
                            and "deadline_monotonic" not in response.text
                        )
                        return response.json() if response.content else None

                    async def submit(text, *, thread_id=None, key=None):
                        if thread_id is None:
                            thread = await request(
                                "POST", "/threads", json={"graph_id": "budget_probe"}
                            )
                            thread_id = thread["thread_id"]
                        path = "/threads/" + thread_id
                        payload = {
                            "assistant_id": "budget_probe",
                            "context": {"model_id": str(model)},
                            "input": {"messages": [{"role": "user", "content": text}]},
                            "durability": "sync",
                        }
                        run = await request(
                            "POST",
                            path + "/runs",
                            json=payload,
                            headers={"Idempotency-Key": key or str(uuid4())},
                        )
                        return path, run["run_id"], payload

                    async def inspect(path, run_id, status):
                        run = await request("GET", path + "/runs/" + run_id)
                        assert run["status"] == status, run
                        await request("GET", path + "/runs")
                        state = await request("GET", path + "/state")
                        await request("POST", path + "/history", json={"limit": 10})
                        async with connect() as conn:
                            row = await conn.session.get(RunRow, UUID(run_id))
                            assert (
                                await conn.session.get(RunLeaseRow, UUID(run_id))
                                is None
                            )
                            terminal_count = await conn.session.scalar(
                                select(func.count())
                                .select_from(RuntimeEventRow)
                                .where(
                                    RuntimeEventRow.run_id == UUID(run_id),
                                    RuntimeEventRow.terminal.is_(True),
                                )
                            )
                            assert terminal_count == 1
                            events = (
                                await conn.session.scalars(
                                    select(RuntimeEventRow).where(
                                        RuntimeEventRow.run_id == UUID(run_id)
                                    )
                                )
                            ).all()
                            assert KEY not in str([event.payload for event in events])
                            stored = dict(row.kwargs[KEY])
                        assert (
                            base / "workspaces" / f"{path.rsplit('/', 1)[1]}.txt"
                        ).read_text() == "verified progress"
                        print(
                            json.dumps(
                                {
                                    "run_id": run_id,
                                    "thread_id": run["thread_id"],
                                    "status": status,
                                    "budget": stored,
                                    "terminal_events": terminal_count,
                                }
                            ),
                            flush=True,
                        )
                        return state, stored

                    async def stored_budget(run_id):
                        async with connect() as conn:
                            row = await conn.session.get(RunRow, UUID(run_id))
                            return dict(row.kwargs.get(KEY, {}))

                    async def wait_checkpoint(path, process):
                        async with asyncio.timeout(180):
                            while True:
                                assert process.returncode is None, (
                                    base / "worker.log"
                                ).read_text()[-5000:]
                                state = await request("GET", path + "/state")
                                if (
                                    state.get("values", {}).get("marker")
                                    == "checkpointed"
                                ):
                                    return
                                await asyncio.sleep(0.1)

                    async def wait_terminal(path, run_id, process):
                        async with asyncio.timeout(180):
                            while True:
                                assert process.returncode is None, (
                                    base / "worker.log"
                                ).read_text()[-5000:]
                                run = await request("GET", path + "/runs/" + run_id)
                                if run["status"] in {
                                    "success",
                                    "error",
                                    "timeout",
                                    "interrupted",
                                }:
                                    return run
                                await asyncio.sleep(0.1)

                    for text, status in (
                        ("short", "success"),
                        ("wrapup", "success"),
                        ("slow", "timeout"),
                        ("model-timeout", "error"),
                    ):
                        path, run_id, payload = await submit(
                            text, key="idempotent-" + text
                        )
                        duplicate = await request(
                            "POST",
                            path + "/runs",
                            json=payload,
                            headers={"Idempotency-Key": "idempotent-" + text},
                        )
                        assert duplicate["run_id"] == run_id
                        assert await worker.run_once()
                        state, _stored = await inspect(path, run_id, status)
                        if text in {"short", "wrapup"}:
                            assert f"wrapup={text == 'wrapup'}" in str(
                                state["values"]["messages"]
                            )
                        else:
                            assert state["values"]["marker"] == "checkpointed"
                            assert not state["values"].get("finished")
                        results.append(
                            {"scenario": text, "run_id": run_id, "status": status}
                        )

                    path, old_id, payload = await submit("approval")
                    assert await worker.run_once()
                    state, old_budget = await inspect(path, old_id, "interrupted")
                    interrupt_id = state["tasks"][0]["interrupts"][0]["id"]
                    await asyncio.sleep(
                        max(
                            0,
                            (
                                datetime.fromisoformat(old_budget["deadline_at"])
                                - datetime.now(UTC)
                            ).total_seconds(),
                        )
                        + 0.1
                    )
                    resumed = await request(
                        "POST",
                        path + "/runs",
                        json={
                            "assistant_id": "budget_probe",
                            "command": {"resume": {interrupt_id: "approve"}},
                        },
                    )
                    assert resumed["run_id"] != old_id
                    assert await worker.run_once()
                    state, new_budget = await inspect(
                        path, resumed["run_id"], "success"
                    )
                    assert new_budget["started_at"] > old_budget["deadline_at"]
                    results.append(
                        {
                            "scenario": "hitl-new-run",
                            "run_id": resumed["run_id"],
                            "status": "success",
                        }
                    )

                    # SIGTERM a real Worker, then reclaim the same Run in a new process.
                    path, run_id, payload = await submit("restart")
                    async with worker_process(
                        GRAPHHARBOR_RUN_TIMEOUT_SECONDS="30",
                        GRAPHHARBOR_SHUTDOWN_DRAIN_SECONDS="0.05",
                    ) as process:
                        await wait_checkpoint(path, process)
                        first_pid = process.pid
                        process.terminate()
                        assert await asyncio.wait_for(process.wait(), 15) == 0
                    pending = await request("GET", path + "/runs/" + run_id)
                    assert pending["status"] == "pending"
                    async with connect() as conn:
                        before = dict(
                            (await conn.session.get(RunRow, UUID(run_id))).kwargs[KEY]
                        )
                    calls = (base / "workspaces" / f"{run_id}.factory").read_text()
                    await asyncio.sleep(
                        max(
                            0,
                            (
                                datetime.fromisoformat(before["deadline_at"])
                                - datetime.now(UTC)
                            ).total_seconds(),
                        )
                        + 0.1
                    )
                    async with worker_process(
                        GRAPHHARBOR_RUN_TIMEOUT_SECONDS="20",
                        AGENT_RUN_WRAPUP_RESERVE_SECONDS="5",
                    ) as process:
                        second_pid = process.pid
                        assert (await wait_terminal(path, run_id, process))[
                            "status"
                        ] == "timeout"
                    assert first_pid != second_pid
                    state, after = await inspect(path, run_id, "timeout")
                    assert after["started_at"] > before["deadline_at"]
                    assert after["timeout_seconds"] == 20
                    assert (
                        base / "workspaces" / f"{run_id}.factory"
                    ).read_text() == calls + "opened\n"
                    results.append(
                        {
                            "scenario": "restart-fresh-attempt",
                            "run_id": run_id,
                            "status": "timeout",
                            "worker_pids": [first_pid, second_pid],
                        }
                    )

                    jobs = [await submit(text) for text in ("slow", "short", "short")]
                    workers = [
                        ProductionWorker(
                            native.state.graph_registry, owner=f"parallel-{i}"
                        )
                        for i in range(3)
                    ]
                    assert all(
                        await asyncio.gather(*(item.run_once() for item in workers))
                    )
                    for i, (path, run_id, payload) in enumerate(jobs):
                        await inspect(path, run_id, "timeout" if i == 0 else "success")
                    results.append(
                        {"scenario": "three-thread-isolation", "status": "passed"}
                    )

                    path, run_id, payload = await submit("slow")
                    execution = asyncio.create_task(worker.run_once())
                    stream_path = path + "/runs/" + run_id + "/stream"
                    async with client.stream("GET", stream_path) as stream:
                        assert stream.status_code == 200
                        async for line in stream.aiter_lines():
                            assert KEY not in line and "deadline_monotonic" not in line
                            if line.startswith("data:"):
                                break
                    assert await execution
                    _state, before = await inspect(path, run_id, "timeout")
                    replay = await client.get(stream_path)
                    assert replay.status_code == 200
                    assert "timeout" in replay.text and KEY not in replay.text
                    runs = await request("GET", path + "/runs")
                    assert len(runs) == 1 and runs[0]["run_id"] == run_id
                    next_path, next_id, _ = await submit(
                        "short", thread_id=path.rsplit("/", 1)[1]
                    )
                    assert await worker.run_once()
                    _state, after = await inspect(next_path, next_id, "success")
                    assert after["started_at"] > before["deadline_at"]
                    results.append(
                        {
                            "scenario": "sse-disconnect-rejoin-next-run",
                            "status": "passed",
                            "run_id": run_id,
                        }
                    )

                    for offset in (-0.15, 0, 0.15):
                        path, run_id, _ = await submit("slow")
                        execution = asyncio.create_task(worker.run_once())
                        async with asyncio.timeout(10):
                            while not (budget := await stored_budget(run_id)):
                                await asyncio.sleep(0.02)
                        remaining = (
                            datetime.fromisoformat(budget["deadline_at"])
                            - datetime.now(UTC)
                        ).total_seconds()
                        await asyncio.sleep(max(0, remaining + offset))
                        for _ in range(2):
                            # The platform normalizes the native 202 into its existing ACK.
                            await request("POST", path + "/runs/" + run_id + "/cancel")
                        assert await execution
                        run = await request("GET", path + "/runs/" + run_id)
                        assert run["status"] in {"timeout", "interrupted"}, run
                        await inspect(path, run_id, run["status"])
                    results.append(
                        {"scenario": "cancel-timeout-race", "status": "passed"}
                    )

                    path, run_id, payload = await submit("slow")
                    execution = asyncio.create_task(worker.run_once())
                    async with asyncio.timeout(10):
                        while not (before := await stored_budget(run_id)):
                            await asyncio.sleep(0.02)
                    queued = await request(
                        "POST",
                        path + "/runs",
                        json={
                            **payload,
                            "input": {
                                "messages": [{"role": "user", "content": "short"}]
                            },
                            "multitask_strategy": "enqueue",
                        },
                    )
                    assert not await stored_budget(queued["run_id"])
                    assert await execution
                    await inspect(path, run_id, "timeout")
                    pending = await request("GET", path + "/runs/" + queued["run_id"])
                    assert pending["status"] == "pending"
                    assert await stored_budget(run_id) == before
                    assert await worker.run_once()
                    _state, after = await inspect(path, queued["run_id"], "success")
                    assert after["started_at"] > before["deadline_at"]
                    results.append(
                        {
                            "scenario": "queued-message-does-not-renew-budget",
                            "status": "passed",
                        }
                    )

                    os.environ["AGENT_RUN_WRAPUP_RESERVE_SECONDS"] = "0"
                    path, run_id, payload = await submit("wrapup")
                    assert await ProductionWorker(
                        native.state.graph_registry, owner="disabled"
                    ).run_once()
                    state, _stored = await inspect(path, run_id, "success")
                    assert "wrapup=False" in str(state["values"]["messages"])
                    results.append({"scenario": "disable-reminder", "status": "passed"})

                    for envelope in (
                        {KEY: {}},
                        {"config": {"configurable": {KEY: {}}}},
                        {"input": {KEY: {}}},
                    ):
                        await request(
                            "POST",
                            path + "/runs",
                            expected=400,
                            json={**payload, **envelope},
                        )
                    results.append(
                        {
                            "scenario": "http-private-budget-rejection",
                            "status": "passed",
                        }
                    )
    print(json.dumps({"database": DB_NAME, "results": results}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
