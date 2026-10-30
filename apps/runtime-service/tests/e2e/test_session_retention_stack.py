"""Opt-in verification against this Worktree's registered three-service stack."""

import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from dotenv import dotenv_values
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from runtime_service.workspace.scoped import get_thread_local_workspace_root


@pytest.mark.skipif(
    os.getenv("RUN_RETENTION_STACK_TEST") != "1", reason="requires registered stack"
)
def test_session_retention_stack(monkeypatch):
    root = Path(__file__).resolve().parents[4]
    entry = json.loads((root / ".local-stack/environment.json").read_text())
    assert entry["root"] == str(root) and entry["id"].startswith("wt_")
    runtime = dotenv_values(root / ".local-stack/runtime.env", interpolate=False)
    platform = dotenv_values(root / ".local-stack/platform.env", interpolate=False)
    dsn = runtime["DATABASE_URI"]
    platform_dsn = (
        make_url(platform["PLATFORM_API_DATABASE_URL"])
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )
    with psycopg.connect(dsn) as db:
        assert db.info.dbname == entry["databases"]["runtime"]
        assert db.info.user == db.info.dbname
    with psycopg.connect(platform_dsn) as db:
        assert db.info.dbname == entry["databases"]["platform"]
        assert db.info.user == db.info.dbname
    for key, value in runtime.items():
        if value is not None:
            monkeypatch.setenv(key, value)
    env = dict(os.environ)
    evidence = {"environment": entry["id"], "checks": [], "threads": []}

    def sql(query, *params):
        with psycopg.connect(dsn, row_factory=dict_row) as db:
            cursor = db.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    def platform_sql(query, *params):
        with psycopg.connect(platform_dsn, row_factory=dict_row) as db:
            cursor = db.execute(query, params)
            return cursor.fetchall() if cursor.description else []

    def register(apply=False):
        script = (
            "import json; from platform_api.config import load_settings; "
            "from platform_api.core.db import build_engine,build_session_factory; "
            "from platform_api.modules.runtime_gateway.application.retention import register_missing; "
            "s=load_settings(); e=build_engine(s.database_url); "
            f"print(json.dumps(register_missing(build_session_factory(e),s,apply={apply},limit=2))); "
            "e.dispose()"
        )
        result = subprocess.run(
            [str(root / "apps/platform-api/.venv/bin/python"), "-c", script],
            cwd=root / "apps/platform-api",
            env={**os.environ, **{k: v for k, v in platform.items() if v is not None}},
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        return json.loads(result.stdout.splitlines()[-1])

    def cli(apply=False):
        started = time.monotonic()
        result = subprocess.run(
            [
                str(root / "apps/runtime-service/.venv/bin/graphharbor"),
                "retention",
                "--config",
                str(root / "apps/runtime-service/langgraph.json"),
                "--limit",
                "20",
                *(["--apply"] if apply else []),
            ],
            cwd=root / "apps/runtime-service",
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr[-1000:]
        evidence.setdefault("maintenance_seconds", []).append(
            round(time.monotonic() - started, 3)
        )
        return next(
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.startswith("{")
        )

    def retry(thread):
        sql(
            "UPDATE thread_deletions SET next_attempt_at=now() WHERE thread_id=%s",
            thread,
        )
        cli(True)
        assert (
            sql("SELECT state FROM thread_deletions WHERE thread_id=%s", thread)[0][
                "state"
            ]
            == "completed"
        )

    with httpx.Client(
        base_url=f"http://127.0.0.1:{entry['ports']['PLATFORM_API_PORT']}",
        trust_env=False,
        timeout=30,
    ) as client:
        response = client.post(
            "/api/identity/session",
            json={
                "username": platform["PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME"],
                "password": platform["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"],
            },
        )
        assert response.status_code == 200
        client.headers["authorization"] = (
            "Bearer " + response.json()["tokens"]["access_token"]
        )
        project = client.get("/api/projects").json()["items"][0]
        client.headers["x-project-id"] = project["id"]
        agents = client.get(f"/api/projects/{project['id']}/agents").json()["items"]
        agent = next(item for item in agents if item["graph_id"] == "dearflow_agent")

        def call(path, method="GET", body=None):
            response = client.request(method, path, json=body)
            assert response.is_success, (response.status_code, response.text[:400])
            return response.json() if response.content else None

        def create():
            data = call(
                "/api/langgraph/threads",
                "POST",
                {
                    "graph_id": agent["graph_id"],
                    "metadata": {
                        "agent_id": agent["id"],
                        "graph_id": agent["graph_id"],
                        "title": "retention acceptance",
                    },
                    "retention": {"mode": "fixed", "ttl_minutes": 1},
                },
            )
            thread = data["thread_id"]
            evidence["threads"].append(thread)
            return thread

        def snapshot(thread):
            return call(f"/api/langgraph/threads/{thread}")["retention"]

        def workspace(thread):
            metadata = call(f"/api/langgraph/threads/{thread}")["metadata"]
            path = get_thread_local_workspace_root(
                metadata["tenant_id"], project["id"], thread, agent["graph_id"]
            )
            path.mkdir(parents=True)
            (path / "acceptance.txt").write_text("disposable acceptance fixture")
            return path

        def deleted(thread, path):
            assert not sql("SELECT 1 FROM threads WHERE thread_id=%s", thread)
            assert not path.parent.exists()
            assert client.get(f"/api/langgraph/threads/{thread}").status_code in (
                403,
                404,
            )
            job = sql(
                "SELECT state,metadata FROM thread_deletions WHERE thread_id=%s", thread
            )[0]
            assert job["state"] == "completed"
            assert set(job["metadata"]) == {"tenant_id", "project_id"}
            assert job["metadata"]["project_id"] == project["id"]
            assert not platform_sql(
                "SELECT 1 FROM thread_access WHERE thread_id=%s", thread
            )

        legacy, existing = create(), create()
        existing_policy = snapshot(existing)
        sql(
            "UPDATE threads SET retention=NULL,last_activity_at=NULL,expires_at=NULL WHERE thread_id=%s",
            legacy,
        )
        for fixture in (legacy, existing):
            platform_sql(
                "UPDATE thread_access SET retention_configured_at=NULL,retention_attempted_at=NULL WHERE thread_id=%s",
                fixture,
            )
        assert (
            platform_sql(
                "SELECT count(*) AS n FROM thread_access WHERE retention_configured_at IS NULL"
            )[0]["n"]
            == 2
        )
        assert register()["candidates"] == 2
        assert snapshot(legacy)["policy"] is None
        assert not platform_sql(
            "SELECT 1 FROM thread_access WHERE thread_id IN (%s,%s) AND retention_configured_at IS NOT NULL",
            legacy,
            existing,
        )
        registered_at = datetime.now(UTC)
        assert register(True)["configured"] == 2
        installed = snapshot(legacy)
        assert installed["policy"] == {"mode": "idle", "ttl_minutes": 43200}
        assert datetime.fromisoformat(
            installed["expires_at"]
        ) >= registered_at + timedelta(days=30)
        assert snapshot(existing) == existing_policy
        evidence["checks"] += [
            "legacy-registration-preview-is-read-only",
            "legacy-registration-grants-full-30-days",
            "registration-preserves-existing-policy-and-activity",
        ]
        for fixture in (legacy, existing):
            path = workspace(fixture)
            call(f"/api/langgraph/threads/{fixture}", "DELETE")
            retry(fixture)
            deleted(fixture, path)

        thread = create()
        initial = snapshot(thread)
        assert initial["policy"] == {"mode": "idle", "ttl_minutes": 43200}
        call("/api/langgraph/threads/search", "POST", {"limit": 10})
        call(f"/api/langgraph/threads/{thread}/state")
        call(f"/api/langgraph/threads/{thread}/history", "POST", {"limit": 1})
        assert snapshot(thread) == initial
        touched = call(f"/api/langgraph/threads/{thread}/activity", "POST")
        assert touched["last_activity_at"] > initial["last_activity_at"]
        denied = client.post(
            f"/api/langgraph/threads/{thread}/activity",
            headers={"x-project-id": str(uuid4())},
        )
        assert denied.status_code in (403, 404)
        assert snapshot(thread) == touched
        forged = client.post(
            "/api/runtime/internal/thread-deletion",
            json={
                "task_id": str(uuid4()),
                "thread_id": thread,
                "project_id": project["id"],
            },
        )
        assert forged.status_code == 403
        evidence["checks"] += [
            "platform-policy-overrides-client",
            "background-reads-do-not-touch",
            "explicit-view-touches",
            "wrong-project-and-unsigned-callback-denied",
        ]
        path = workspace(thread)
        call(f"/api/langgraph/threads/{thread}", "DELETE")
        retry(thread)
        deleted(thread, path)
        evidence["checks"].append("manual-delete-workspace-and-platform-acl")

        ttl = create()
        path = workspace(ttl)
        sql(
            "UPDATE threads SET expires_at=now()-interval '1 minute' WHERE thread_id=%s",
            ttl,
        )
        preview = cli()
        assert ttl in preview["due_threads"]
        assert (
            sql("SELECT deletion_requested_at FROM threads WHERE thread_id=%s", ttl)[0][
                "deletion_requested_at"
            ]
            is None
        )
        assert path.exists()
        cli(True)
        retry(ttl)
        deleted(ttl, path)
        evidence["checks"] += [
            "cli-preview-is-read-only",
            "engine-ttl-deletes-workspace-and-platform-acl",
        ]

        held = create()
        path = workspace(held)
        with (path / "acceptance.txt").open():
            call(f"/api/langgraph/threads/{held}", "DELETE")
            assert path.exists()
            job = sql(
                "SELECT state,last_error FROM thread_deletions WHERE thread_id=%s", held
            )[0]
            assert job["state"] == "after_delete" and job["last_error"]
            assert client.post(
                f"/api/langgraph/threads/{held}/activity"
            ).status_code in (404, 409)
        retry(held)
        deleted(held, path)
        evidence["checks"].append("open-file-blocks-and-retry-resumes")

        concurrent = create()
        path = workspace(concurrent)
        sql(
            "UPDATE threads SET expires_at=now()-interval '1 minute' WHERE thread_id=%s",
            concurrent,
        )
        with ThreadPoolExecutor(max_workers=2) as workers:
            list(workers.map(lambda _: cli(True), range(2)))
        retry(concurrent)
        deleted(concurrent, path)
        evidence["checks"].append("concurrent-maintainers-complete-one-durable-task")
        evidence["checks"].append("completed-tombstone-keeps-only-auth-metadata")
    output = root / ".local-stack/evidence"
    output.mkdir(exist_ok=True)
    (output / "retention-stack.json").write_text(json.dumps(evidence, indent=2))
