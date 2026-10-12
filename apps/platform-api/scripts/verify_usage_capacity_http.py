"""Owned native PG capacity fixture: real public auth/ACL/audit, HMAC and projector."""

import argparse
import asyncio
import json
import math
import os
import socket
import statistics
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
from dotenv import dotenv_values
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import make_url


def timings(values):
    ordered = sorted(values)
    return dict(
        n=len(values),
        p50_ms=round(statistics.median(values) * 1000, 2),
        p95_ms=round(ordered[math.ceil(len(values) * 0.95) - 1] * 1000, 2),
        p99_ms=round(ordered[math.ceil(len(values) * 0.99) - 1] * 1000, 2),
    )


def launch(root, python, code, environment, log):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    sock.set_inheritable(True)
    process = subprocess.Popen(
        ["rtk", "proxy", str(python), "-c", code],
        cwd=root,
        env={**os.environ, **environment, "USAGE_CAPACITY_FD": str(sock.fileno())},
        pass_fds=(sock.fileno(),),
        stdout=log,
        stderr=log,
    )
    port = sock.getsockname()[1]
    sock.close()
    return process, port


def writer(root, environment, samples):
    code = """import json,os,runpy
module=runpy.run_path('apps/runtime-service/scripts/verify_usage_capacity.py')
identity=json.loads(os.environ['USAGE_CAPACITY_IDENTITY'])
print('READY',flush=True)
assert input()=='START'
samples,errors=module['write_pair'](os.environ['DATABASE_URI'],identity,int(os.environ['USAGE_CAPACITY_SAMPLES']),at=os.environ['USAGE_CAPACITY_WRITE_AT'])
print(json.dumps({'samples':samples,'errors':errors}))
"""
    process = subprocess.Popen(
        [
            "rtk",
            "proxy",
            str(root / "apps/runtime-service/.venv/bin/python"),
            "-c",
            code,
        ],
        cwd=root,
        env={**os.environ, **environment, "USAGE_CAPACITY_SAMPLES": str(samples)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
    )
    assert process.stdout.readline().strip() == "READY", "writer failed readiness"
    process.stdin.write("START\n")
    process.stdin.flush()
    return process


def write_result(process):
    stdout, _ = process.communicate(timeout=60)
    if process.returncode:
        raise AssertionError("capacity writer failed")
    result = json.loads(stdout)
    assert not result["errors"], result["errors"]
    return timings(result["samples"])


def run(database, output):
    root = Path(__file__).resolve().parents[3]
    identity = json.loads((root / ".local-stack/environment.json").read_text())
    runtime = dict(dotenv_values(root / ".local-stack/runtime.env"))
    settings = dict(dotenv_values(root / ".local-stack/platform.env"))
    params = conninfo_to_dict(runtime["DATABASE_URI"])
    assert database.startswith(identity["id"] + "_usage_capacity_")
    platform_name = identity["id"] + "_usage_http_" + uuid4().hex[:8]
    platform_url = make_url(settings["PLATFORM_API_DATABASE_URL"])
    with psycopg.connect(
        os.getenv("LOCAL_STACK_PG_ADMIN_DSN", "dbname=postgres"), autocommit=True
    ) as admin:
        assert admin.execute(
            "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",
            (database,),
        ).fetchone() == ("local-stack:" + identity["id"],)
        admin.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(platform_name), sql.Identifier(platform_url.username)
            )
        )
        admin.execute(
            sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                sql.Identifier(platform_name),
                sql.Literal("local-stack:" + identity["id"]),
            )
        )
    params["dbname"] = database
    runtime["DATABASE_URI"] = make_conninfo(**params)
    settings["PLATFORM_API_DATABASE_URL"] = platform_url.set(
        database=platform_name
    ).render_as_string(hide_password=False)
    settings["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"] = "admin123456"
    with psycopg.connect(runtime["DATABASE_URI"]) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM runtime_usage_calls WHERE tenant_id='__default'"
            ).fetchone()[0]
            >= 1000000
        )
        projects = [
            r[0]
            for r in conn.execute(
                "SELECT project_id FROM runtime_usage_runs WHERE tenant_id='__default' GROUP BY 1 ORDER BY 1"
            )
        ]
        threads = list(
            conn.execute(
                "SELECT DISTINCT project_id,thread_id FROM runtime_usage_runs WHERE tenant_id='__default'"
            )
        )
    migration = subprocess.run(
        [
            "rtk",
            "proxy",
            str(root / "apps/platform-api/.venv/bin/python"),
            "scripts/database.py",
            "upgrade",
        ],
        cwd=root / "apps/platform-api",
        env={**os.environ, **settings},
        capture_output=True,
    )
    assert migration.returncode == 0, "isolated Platform migration failed"
    runtime_code = """import os,uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from runtime_service.http.usage_analytics import router
from runtime_service.observability.usage_projection import usage_projection_lifespan
@asynccontextmanager
async def lifespan(app):
    async with usage_projection_lifespan(): yield
app=FastAPI(lifespan=lifespan);app.include_router(router)
uvicorn.run(app,fd=int(os.environ['USAGE_CAPACITY_FD']),log_level='warning')
"""
    platform_code = """import os,uvicorn
from platform_api.main import create_app
uvicorn.run(create_app(),fd=int(os.environ['USAGE_CAPACITY_FD']),log_level='warning')
"""
    processes = []
    log_path = root / ".local-stack/usage-capacity-http.log"
    report = dict(
        runtime_database=database,
        platform_database=platform_name,
        processes="Platform API + Runtime query/projector + independent Worker with two writer threads",
        queries={},
        cases={},
    )
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    with log_path.open("a") as log:
        try:
            process, runtime_port = launch(
                root,
                root / "apps/runtime-service/.venv/bin/python",
                runtime_code,
                runtime,
                log,
            )
            processes.append(process)
            settings["PLATFORM_API_LANGGRAPH_UPSTREAM_URL"] = (
                f"http://127.0.0.1:{runtime_port}"
            )
            process, api_port = launch(
                root,
                root / "apps/platform-api/.venv/bin/python",
                platform_code,
                settings,
                log,
            )
            processes.append(process)
            base = f"http://127.0.0.1:{api_port}"
            with httpx.Client(base_url=base, timeout=10, trust_env=False) as client:
                deadline = time.monotonic() + 60
                while True:
                    try:
                        if client.get("/_system/health").status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    assert time.monotonic() < deadline and all(
                        p.poll() is None for p in processes
                    ), "capacity servers failed to start"
                    time.sleep(0.2)
                session = client.post(
                    "/api/identity/session",
                    json=dict(username="admin", password="admin123456"),
                )
                assert session.status_code == 200
                auth = {
                    "authorization": "Bearer "
                    + session.json()["tokens"]["access_token"]
                }
                seed = client.post(
                    "/api/projects",
                    headers=auth,
                    json={"name": "Capacity fixture seed"},
                )
                assert seed.status_code in (200, 201), seed.status_code
                # Seed only the freshly created Platform fixture with the ledger's project IDs and real ACL rows.
                connection_url = make_url(settings["PLATFORM_API_DATABASE_URL"])
                dsn = make_conninfo(
                    host=connection_url.host,
                    port=connection_url.port,
                    dbname=platform_name,
                    user=connection_url.username,
                    password=connection_url.password,
                )
                with psycopg.connect(dsn) as conn:
                    tenant = conn.execute(
                        "SELECT id FROM tenants WHERE slug='__default'"
                    ).fetchone()[0]
                    all_projects = projects + [
                        str(uuid4()) for _ in range(200 - len(projects))
                    ]
                    conn.cursor().executemany(
                        "INSERT INTO projects(id,tenant_id,name,description,status) VALUES (%s,%s,%s,'','active')",
                        [
                            (project, tenant, "Capacity " + str(i))
                            for i, project in enumerate(all_projects)
                        ],
                    )
                    conn.cursor().executemany(
                        "INSERT INTO project_members(id,project_id,user_id,role) VALUES (%s,%s,%s,'project_admin')",
                        [
                            (uuid4(), project, session.json()["user"]["id"])
                            for project in all_projects
                        ],
                    )
                    conn.cursor().executemany(
                        "INSERT INTO thread_access(thread_id,project_id,owner_user_id,visibility,shared_actions,project_actions,takeovers,provisioning_status) VALUES (%s,%s,%s,'private','{}','[]','{}','ready')",
                        [
                            (str(thread), project, session.json()["user"]["id"])
                            for project, thread in threads
                        ],
                    )
                params = dict(
                    **{"from": "2026-09-01T00:00:00Z", "to": "2026-10-01T00:00:00Z"},
                    project_ids=projects,
                )
                for group in ("model", "project", "agent", "purpose", "scope"):
                    samples = []
                    for _ in range(3):
                        started = time.perf_counter()
                        response = client.get(
                            "/api/usage/dashboard",
                            headers=auth,
                            params={**params, "group_by": group},
                        )
                        samples.append(time.perf_counter() - started)
                        assert (
                            response.status_code == 200
                            and response.json()["availability"] == "available"
                        ), (group, response.status_code)
                        assert (
                            response.json()["summary"]["tokens"]["total_tokens"]
                            == 120000000
                        )
                    report["queries"][group] = timings(samples)
                writer_env = {
                    **runtime,
                    "USAGE_CAPACITY_WRITE_AT": "2026-10-11T00:00:00Z",
                    "USAGE_CAPACITY_IDENTITY": json.dumps(
                        dict(
                            tenant_id="__default",
                            project_id=projects[0],
                            run_id=str(uuid4()),
                            thread_id=str(uuid4()),
                            graph_id="writer",
                        )
                    ),
                }
                worker = writer(root, writer_env, 50)
                processes.append(worker)
                report["writes_idle"] = write_result(worker)
                report["write_scope"] = (
                    "same tenant/project, two distinct Runs, current-date start/end facts outside the historical query window"
                )

                async def reads():
                    elapsed = []
                    available = []
                    async with httpx.AsyncClient(
                        base_url=base, headers=auth, timeout=6, trust_env=False
                    ) as async_client:

                        async def one(index):
                            started = time.perf_counter()
                            r = await async_client.get(
                                "/api/usage/dashboard",
                                params={
                                    **params,
                                    "group_by": (
                                        "model",
                                        "project",
                                        "agent",
                                        "purpose",
                                        "scope",
                                    )[index % 5],
                                },
                            )
                            elapsed.append(time.perf_counter() - started)
                            assert r.status_code == 200, r.status_code
                            available.append(r.json()["availability"])
                            assert (
                                r.json()["summary"]["tokens"]["total_tokens"]
                                == 120000000
                            ), (
                                r.json()["availability"],
                                r.json()["unavailable_reason"],
                            )

                        for _ in range(3):
                            await asyncio.gather(*(one(i) for i in range(10)))
                    return timings(elapsed), {
                        v: available.count(v) for v in set(available)
                    }

                worker = writer(root, writer_env, 50)
                processes.append(worker)
                report["reads_concurrent"], report["availability_concurrent"] = (
                    asyncio.run(reads())
                )
                report["writes_under_reads"] = write_result(worker)
                report["write_p95_change_ratio"] = round(
                    report["writes_under_reads"]["p95_ms"]
                    / report["writes_idle"]["p95_ms"]
                    - 1,
                    4,
                )
                started = time.perf_counter()
                boundary = client.get(
                    "/api/usage/dashboard",
                    headers=auth,
                    params={
                        **params,
                        "from": "2026-07-03T00:00:00Z",
                        "project_ids": all_projects,
                    },
                )
                assert (
                    boundary.status_code == 200
                    and boundary.json()["availability"] == "available"
                )
                report["boundary_200_projects_90_days"] = dict(
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                    projects=boundary.json()["scope"]["covered_project_count"],
                )
                samples = []
                cursor = None
                seen = set()
                for _ in range(4):
                    started = time.perf_counter()
                    r = client.get(
                        f"/api/projects/{projects[0]}/usage/runs",
                        headers={**auth, "x-project-id": projects[0]},
                        params={
                            k: v
                            for k, v in {**params, "cursor": cursor}.items()
                            if k != "project_ids" and v is not None
                        },
                    )
                    samples.append(time.perf_counter() - started)
                    assert r.status_code == 200, (
                        r.status_code,
                        r.json().get("error", {}).get("code"),
                    )
                    page = r.json()
                    assert len(page["items"]) == 50
                    identifiers = {row["run_id"] for row in page["items"]}
                    assert not seen & identifiers
                    seen |= identifiers
                    cursor = page["next_cursor"]
                report["public_runs"] = dict(**timings(samples), unique_runs=len(seen))
                report["cases"]["real_jwt_current_scope_hmac_dto_audit_acl_cursor"] = (
                    "passed"
                )
                report["gates"] = dict(
                    queries_complete=report["availability_concurrent"]
                    == {"available": 30},
                    query_latency=report["reads_concurrent"]["p95_ms"] <= 1500
                    and report["reads_concurrent"]["p99_ms"] <= 3000,
                    write_impact=report["write_p95_change_ratio"] <= 0.2,
                    runs_latency=report["public_runs"]["p95_ms"] <= 1500,
                    boundary=report["boundary_200_projects_90_days"]["projects"] == 200,
                )
        finally:
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            for process in reversed(processes):
                if process.poll() is not None:
                    continue
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if all(report["gates"].values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.database, args.output))
