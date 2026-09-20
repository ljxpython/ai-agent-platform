"""Compare two-worker Platform CRUD/audit load on isolated SQLite and PostgreSQL copies."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/platform-api"
sys.path.insert(0, str(APP / "scripts"))
from database import migration_config
from migrate_sqlite_to_postgres import copy_data


async def run_case(url, label, args, output):
    env = {
        **os.environ,
        **{k: v for k, v in dotenv_values(APP / ".env").items() if v is not None},
        "PLATFORM_API_DATABASE_URL": url,
        "PLATFORM_API_PLATFORM_DB_AUTO_CREATE": "false",
        "PLATFORM_API_BOOTSTRAP_ADMIN_ENABLED": "false",
        "PLATFORM_API_PLATFORM_DB_ENABLED": "true",
    }
    timings, errors, created, connection_peaks = [], [], [], []
    engine = create_engine(url)
    with engine.connect() as conn:
        audit_before = conn.execute(
            text("SELECT count(*) FROM audit_logs")
        ).scalar_one()
    with (output / f"{label}.log").open("wb") as log:
        process = await asyncio.create_subprocess_exec(
            str(APP / ".venv/bin/python"),
            "-m",
            "uvicorn",
            "platform_api.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--workers",
            "2",
            cwd=APP,
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        try:
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{args.port}", trust_env=False, timeout=30
            ) as client:
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    assert process.returncode is None, "Probe process exited"
                    try:
                        ready = await client.get("/_system/probes/ready")
                        if ready.status_code == 200 and ready.json().get(
                            "database_ready"
                        ):
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(0.5)
                else:
                    raise TimeoutError("Probe startup")
                credentials = {
                    "username": env["PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME"],
                    "password": env["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"],
                }
                login = await client.post("/api/identity/session", json=credentials)
                login.raise_for_status()
                headers = {
                    "authorization": "Bearer " + login.json()["tokens"]["access_token"]
                }
                started = time.monotonic()

                async def user(index):
                    iteration = 0
                    while time.monotonic() - started < args.seconds:
                        operations = [
                            (
                                "POST",
                                "/api/projects",
                                {"name": f"pg-load-{index}-{iteration}"},
                            ),
                            ("GET", "/api/projects?limit=10", None),
                        ]
                        if iteration % 20 == 0:
                            operations.append(
                                ("POST", "/api/identity/session", credentials)
                            )
                        for method, path, payload in operations:
                            begin = time.monotonic()
                            try:
                                response = await client.request(
                                    method, path, json=payload, headers=headers
                                )
                                if response.status_code >= 400:
                                    errors.append(
                                        {"path": path, "status": response.status_code}
                                    )
                                elif method == "POST" and path == "/api/projects":
                                    created.append(response.json()["id"])
                            except httpx.HTTPError as exc:
                                errors.append(
                                    {"path": path, "type": type(exc).__name__}
                                )
                            timings.append((time.monotonic() - begin) * 1000)
                        iteration += 1
                        await asyncio.sleep(0.25)

                async def monitor():
                    if engine.dialect.name != "postgresql":
                        return
                    while time.monotonic() - started < args.seconds:

                        def sample():
                            with engine.connect() as conn:
                                return conn.execute(
                                    text(
                                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()"
                                    )
                                ).scalar_one()

                        connection_peaks.append(await asyncio.to_thread(sample))
                        await asyncio.sleep(1)

                await asyncio.gather(*(user(i) for i in range(10)), monitor())
                elapsed = time.monotonic() - started
        finally:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), 30)
            except TimeoutError:
                os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
    with engine.connect() as conn:
        # Each successful HTTP-created project must exist after all workers stopped.
        rows = conn.execute(
            text("SELECT id FROM projects WHERE name LIKE 'pg-load-%'")
        ).scalars()
        persisted = {str(value).replace("-", "") for value in rows}
        assert {value.replace("-", "") for value in created} == persisted
        audit_after = conn.execute(text("SELECT count(*) FROM audit_logs")).scalar_one()
    engine.dispose()
    ordered = sorted(timings)
    result = {
        "workers": 2,
        "clients": 10,
        "seconds": elapsed,
        "requests": len(timings),
        "p95_ms": ordered[int(len(ordered) * 0.95)],
        "requests_per_second": len(timings) / elapsed,
        "errors": errors,
        "created_and_persisted": len(created),
        "audit_rows_written": audit_after - audit_before,
        "database_connection_peak": max(connection_peaks, default=None),
    }
    assert result["audit_rows_written"] >= len(created), "Missing write audits"
    (output / f"{label}.json").write_text(json.dumps(result, indent=2))
    print(
        label,
        json.dumps({k: v for k, v in result.items() if k != "errors"}),
        flush=True,
    )
    return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--port", type=int, default=18429)
    args = parser.parse_args()
    url = os.environ["PLATFORM_LOAD_DATABASE_URL"]
    parsed = make_url(url)
    assert parsed.host in {"127.0.0.1", "localhost"} and parsed.database.startswith(
        "platform_migration_test_"
    )
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    sqlite_file = args.output / "baseline.db"
    shutil.copyfile(args.source, sqlite_file)
    sqlite_file.chmod(0o600)
    sqlite_url = f"sqlite:///{sqlite_file.resolve()}"
    source, target = create_engine(sqlite_url), create_engine(url)
    # Target must already be Alembic-initialized and empty; the copier enforces that.
    copy_data(source, target, migration_config(url), assume_naive_utc=True)
    source.dispose()
    target.dispose()
    sqlite_result = await run_case(sqlite_url, "sqlite", args, args.output)
    pg_result = await run_case(url, "postgresql", args, args.output)
    summary = {
        "sqlite_p95_ms": sqlite_result["p95_ms"],
        "postgresql_p95_ms": pg_result["p95_ms"],
        "p95_ratio": pg_result["p95_ms"] / sqlite_result["p95_ms"],
        "postgresql_errors": len(pg_result["errors"]),
        "sqlite_errors": len(sqlite_result["errors"]),
        "scope": "Real HTTP login/list/create and audit; gateway idempotency verified separately.",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)
    assert not pg_result["errors"] and summary["p95_ratio"] <= 1.2, (
        "Performance gate failed"
    )


if __name__ == "__main__":
    asyncio.run(main())
