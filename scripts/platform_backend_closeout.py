"""Restore isolated acceptance databases, read real history, and measure mixed load.

Run with platform-api's Python; --source is a completed Showcase output directory.
Backups contain secrets: output is private and must never be committed.
Only evidence.json and metrics.json are safe to copy into project documentation.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager, suppress
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import signal
import subprocess
import time

import httpx
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def summary(values):
    ordered = sorted(values)
    assert ordered
    return {
        "count": len(ordered),
        "p50_ms": ordered[math.ceil(len(ordered) * 0.5) - 1],
        "p95_ms": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "max_ms": ordered[-1],
    }


def create_probe_app():
    """Measure the actual Platform event loop and pool, without adding an endpoint."""
    from platform_api.main import create_app

    app = create_app()
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        delays, connections = [], []
        async with original(application):

            async def sample():
                while True:
                    start = time.monotonic()
                    await asyncio.sleep(0.05)
                    delays.append(max(0, time.monotonic() - start - 0.05) * 1000)
                    connections.append(application.state.db_engine.pool.checkedout())

            task = asyncio.create_task(sample())
            try:
                yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                Path(os.environ["CLOSEOUT_METRICS_FILE"]).write_text(
                    json.dumps(
                        {
                            "event_loop_delay": summary(delays),
                            "checked_out_connections_max": max(connections),
                            "checked_out_connections_final": connections[-1],
                            "pool_size": application.state.db_engine.pool.size(),
                        },
                        indent=2,
                    )
                )

    app.router.lifespan_context = lifespan
    return app


def pg_params(uri):
    url = make_url(uri)
    assert url.host in {"localhost", "127.0.0.1"}, "Only local acceptance databases"
    return {
        "host": url.host,
        "port": url.port or 5432,
        "user": url.username,
        "dbname": url.database,
        **({"password": url.password} if url.password else {}),
    }


def fingerprint(params):
    result = {}
    with psycopg.connect(**params) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        tables = conn.execute(
            "SELECT schemaname, tablename FROM pg_tables WHERE "
            "schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1,2"
        ).fetchall()
        for schema, table in tables:
            rows = conn.execute(
                sql.SQL(
                    'SELECT to_jsonb(t)::text FROM {}.{} t ORDER BY to_jsonb(t)::text COLLATE "C"'
                ).format(sql.Identifier(schema), sql.Identifier(table))
            )
            digest, count = hashlib.sha256(), 0
            for (row,) in rows:
                digest.update(row.encode() + b"\n")
                count += 1
            result[f"{schema}.{table}"] = {"rows": count, "sha256": digest.hexdigest()}
    return result


def restore(source_env, output, pg_bin):
    restored, evidence = dict(source_env), {}
    for key, label in (
        ("PLATFORM_API_DATABASE_URL", "platform"),
        ("DATABASE_URI", "runtime"),
    ):
        params = pg_params(source_env[key])
        before = fingerprint(params)
        name = f"closeout_{label}_{secrets.token_hex(5)}"
        pg_env = dict(
            os.environ,
            PGHOST=params["host"],
            PGPORT=str(params["port"]),
            PGUSER=params["user"],
            PGDATABASE=params["dbname"],
            PGPASSWORD=params.get("password", ""),
        )
        backup = output / f"{label}.dump"
        subprocess.run(
            [
                str(pg_bin / "pg_dump"),
                "-Fc",
                "--no-owner",
                "--no-acl",
                "-f",
                str(backup),
            ],
            env=pg_env,
            check=True,
            capture_output=True,
        )
        backup.chmod(0o600)
        with psycopg.connect(
            **{**params, "dbname": "postgres"}, autocommit=True
        ) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        subprocess.run(
            [
                str(pg_bin / "pg_restore"),
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
                "-d",
                name,
                str(backup),
            ],
            env=pg_env,
            check=True,
            capture_output=True,
        )
        after = fingerprint({**params, "dbname": name})
        assert before == after == fingerprint(params), f"{label} snapshot mismatch"
        restored[key] = (
            make_url(source_env[key])
            .set(database=name)
            .render_as_string(hide_password=False)
        )
        evidence[label] = {
            "restored_database": name,
            "tables": after,
            "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
            "all_rows_match": True,
        }
    return restored, evidence


async def ready(client, path, process):
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        assert process.returncode is None, "Owned service exited; inspect private logs"
        try:
            response = await client.get(path)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.5)
    raise TimeoutError(path)


async def run(args):
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = args.source.resolve()
    env, backup_evidence = await asyncio.to_thread(
        restore,
        json.loads((source / "process-env.json").read_text()),
        output,
        args.pg_bin,
    )
    previous = json.loads((source / "evidence.json").read_text())
    env.update(
        GRAPHHARBOR_REDIS_PREFIX="closeout:" + secrets.token_hex(8),
        PLATFORM_API_LANGGRAPH_UPSTREAM_URL=f"http://127.0.0.1:{args.runtime_port}",
        PLATFORM_RUNTIME_MODEL_CONFIG_URL=f"http://127.0.0.1:{args.platform_port}/api/runtime/internal/model-config",
        CLOSEOUT_METRICS_FILE=str(output / "metrics.json"),
        PYTHONPATH=str(ROOT / "scripts"),
    )
    private = output / "process-env.json"
    private.touch(mode=0o600)
    private.write_text(json.dumps(env))
    (output / "evidence.json").write_text(
        json.dumps({"restore": backup_evidence, "status": "partial"}, indent=2)
    )
    processes, logs = [], []

    async def start(command, label, cwd):
        log = (output / f"{label}.log").open("wb")
        logs.append(log)
        process = await asyncio.create_subprocess_exec(
            *command, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True
        )
        processes.append(process)
        return process

    try:
        runtime = await start(
            [
                str(ROOT / "apps/runtime-service/.venv/bin/python"),
                "-m",
                "langhost.cli",
                "serve",
                "--config",
                str(source / "langgraph.json"),
                "--env-file",
                str(source / "empty.env"),
                "--n-jobs-per-worker",
                "0",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.runtime_port),
            ],
            "runtime",
            ROOT / "apps/runtime-service",
        )
        platform = await start(
            [
                str(ROOT / "apps/platform-api/.venv/bin/python"),
                "-m",
                "uvicorn",
                "platform_backend_closeout:create_probe_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.platform_port),
            ],
            "platform",
            ROOT / "apps/platform-api",
        )
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{args.runtime_port}",
            timeout=10,
            trust_env=False,
        ) as client:
            await ready(client, "/ready", runtime)
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{args.platform_port}",
            timeout=60,
            trust_env=False,
        ) as client:
            await ready(client, "/_system/probes/ready", platform)
            credentials = {
                "username": "acceptance-admin",
                "password": env["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"],
            }
            login = await client.post("/api/identity/session", json=credentials)
            login.raise_for_status()
            client.headers.update(
                {
                    "authorization": "Bearer " + login.json()["tokens"]["access_token"],
                    "x-project-id": previous["project_id"],
                }
            )

            async def request(method, path, payload=None, **kwargs):
                response = await client.request(
                    method, "/api/langgraph" + path, json=payload, **kwargs
                )
                response.raise_for_status()
                assert "runtime_model_ref" not in response.text
                return response.json()

            path = "/threads/" + previous["thread_id"]
            thread = await request("GET", path)
            state = await request("GET", path + "/state")
            history = await request("POST", path + "/history", {"limit": 100})
            assert (
                thread["thread_id"] == previous["thread_id"]
                and state["values"]["messages"]
                and history
            )
            for run in previous["runs"]:
                observed = await request("GET", path + "/runs/" + run["run_id"])
                assert observed["status"] == run["status"]
            params = pg_params(env["PLATFORM_API_DATABASE_URL"])
            with psycopg.connect(**params) as conn:
                records = conn.execute(
                    "SELECT run_id,parent_run_id FROM run_requests WHERE thread_id=%s",
                    (previous["thread_id"],),
                ).fetchall()
            ids = {row[0] for row in records}
            assert all(run["run_id"] in ids for run in previous["runs"])
            assert all(parent in ids for _, parent in records if parent)
            restore_http = {
                "thread_id": previous["thread_id"],
                "runs": previous["runs"],
                "messages": len(state["values"]["messages"]),
                "history": len(history),
                "request_parent_links_verified": True,
                "no_worker_started": True,
            }

            pending_thread = await request(
                "POST", "/threads", {"graph_id": "showcase_demo"}
            )
            pending_path = "/threads/" + pending_thread["thread_id"]
            pending = await request(
                "POST",
                pending_path + "/runs",
                {
                    "assistant_id": "showcase_demo",
                    "input": {"messages": [{"role": "user", "content": "load probe"}]},
                },
            )
            stream_ready = [asyncio.Event() for _ in range(2)]
            stream_results = []

            async def subscriber(index):
                begin = time.monotonic()
                async with client.stream(
                    "GET",
                    "/api/langgraph"
                    + pending_path
                    + "/runs/"
                    + pending["run_id"]
                    + "/stream",
                ) as response:
                    response.raise_for_status()
                    assert "text/event-stream" in response.headers["content-type"]
                    stream_ready[index].set()
                    size = 0
                    try:
                        async with asyncio.timeout(args.seconds + 15):
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                    except TimeoutError:
                        pass
                stream_results.append(
                    {"duration_seconds": time.monotonic() - begin, "bytes": size}
                )

            streams = [asyncio.create_task(subscriber(i)) for i in range(2)]
            await asyncio.wait_for(
                asyncio.gather(*(e.wait() for e in stream_ready)), 60
            )
            timings, errors, pg_connections = {"login": [], "list": []}, [], []
            begin = time.monotonic()

            async def user():
                while time.monotonic() - begin < args.seconds:
                    for label, method, url, payload in (
                        ("login", "POST", "/api/identity/session", credentials),
                        ("list", "GET", "/api/projects", None),
                    ):
                        started = time.monotonic()
                        try:
                            response = await client.request(method, url, json=payload)
                            response.raise_for_status()
                        except httpx.HTTPError as exc:
                            errors.append(
                                {
                                    "request": label,
                                    "type": type(exc).__name__,
                                    "status": getattr(
                                        getattr(exc, "response", None),
                                        "status_code",
                                        None,
                                    ),
                                }
                            )
                        timings[label].append((time.monotonic() - started) * 1000)

            def connection_count():
                with psycopg.connect(**params) as conn:
                    return conn.execute(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
                        (params["dbname"],),
                    ).fetchone()[0]

            async def monitor():
                while time.monotonic() - begin < args.seconds:
                    pg_connections.append(await asyncio.to_thread(connection_count))
                    await asyncio.sleep(0.5)

            await asyncio.gather(*(user() for _ in range(4)), monitor())
            elapsed = time.monotonic() - begin
            await request(
                "POST",
                pending_path + "/runs/" + pending["run_id"] + "/cancel",
                {"action": "interrupt"},
            )
            await asyncio.gather(*streams)
            assert len(stream_results) == 2 and all(
                x["duration_seconds"] >= args.seconds for x in stream_results
            )
            assert not errors, errors
            total = sum(len(v) for v in timings.values())
            evidence = {
                "status": "passed",
                "restore": backup_evidence,
                "restored_http": restore_http,
                "load": {
                    "concurrent_users": 4,
                    "concurrent_sse": 2,
                    "duration_seconds": elapsed,
                    "requests": total,
                    "requests_per_second": total / elapsed,
                    "error_rate": len(errors) / total,
                    "errors": errors,
                    "latency": {k: summary(v) for k, v in timings.items()},
                    "pg_connections_max": max(pg_connections),
                    "streams": stream_results,
                },
            }
            (output / "evidence.json").write_text(json.dumps(evidence, indent=2))
    finally:
        for process in reversed(processes):
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    await asyncio.wait_for(process.wait(), 30)
                except TimeoutError:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
        for log in logs:
            log.close()
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument(
        "--pg-bin",
        type=Path,
        required=True,
        help="Directory of PostgreSQL client tools matching the server major version",
    )
    parser.add_argument("--runtime-port", type=int, default=18325)
    parser.add_argument("--platform-port", type=int, default=18425)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), indent=2))
