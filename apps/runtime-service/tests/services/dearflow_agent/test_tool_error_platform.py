"""Opt-in HTTP/API/Worker chain on isolated local PostgreSQL/Redis and SQLite."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from runtime_service.workspace.scoped import hashed_thread_root


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(check, timeout=180, *, process=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise AssertionError(f"Disposable service exited: {process.returncode}")
        try:
            value = check()
            if value:
                return value
        except (OSError, httpx.HTTPError):
            pass
        time.sleep(0.1)
    raise AssertionError("Disposable service did not become ready")


@pytest.fixture
def stack(tmp_path, request):
    if os.getenv("TOOL_ERROR_PLATFORM_TEST") != "1":
        pytest.skip(
            "TOOL_ERROR_PLATFORM_TEST=1 enables isolated local API/Worker verification"
        )
    repo = Path(__file__).resolve().parents[5]
    options = getattr(request, "param", {})
    source = (
        repo
        / "apps/runtime-service/tests/fixtures"
        / options.get("fixture", "tool_error_platform.py")
    )
    fixture = tmp_path / "fixture.py"
    shutil.copyfile(source, fixture)
    prefix = "tool-errors-" + uuid4().hex[:12]
    processes, logs = {}, []
    runtime_port, platform_port = port(), port()
    spec = {
        "runtime_port": runtime_port,
        "platform_port": platform_port,
        "runtime_url": f"http://127.0.0.1:{runtime_port}",
        "database": str(tmp_path / "platform.db"),
        "ready": str(tmp_path / "ready.json"),
        "secret": "disposable-tool-error-verification-secret",
        **{k: str(uuid4()) for k in ("tenant", "project", "model")},
    }
    if options.get("provider"):
        spec["provider_port"] = port()
        spec["provider_url"] = f"http://127.0.0.1:{spec['provider_port']}/v1"
    spec["config"] = {
        "graphs": {"dearflow_agent": "fixture.py:graph"},
        "auth": {"path": "fixture.py:auth"},
        "http": {"disable_mcp": True},
    }
    if options.get("http_app"):
        spec["config"]["http"]["app"] = "fixture.py:app"
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec))
    (tmp_path / "langgraph.json").write_text(json.dumps(spec["config"]))
    env = {
        **os.environ,
        "NO_PROXY": "127.0.0.1,localhost",
        "PYTHONPATH": os.pathsep.join(
            str(repo / p)
            for p in (
                "apps/runtime-service/src",
                "apps/runtime-service/tests",
                "apps/platform-api/src",
            )
        ),
        "RUNTIME_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
        "RUNTIME_DEAR_GOVERNANCE_ENABLED": "0",
        "TAVILY_API_KEY": "synthetic",
        "TOOL_ERROR_TEST_FACTS": str(tmp_path / "facts.jsonl"),
        "GRAPHHARBOR_ENV": "production",
        "LG_RUNTIME_PG_AUTO_MIGRATE": "false",
        "GRAPHHARBOR_REDIS_PREFIX": prefix,
        "PLATFORM_RUNTIME_DELEGATION_SECRET": spec["secret"],
        "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
        "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
        "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": spec["secret"],
        "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER": "graphharbor",
        "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE": "graphharbor-worker",
        "PLATFORM_THREAD_AUTHORIZATION_URL": f"http://127.0.0.1:{platform_port}/api/runtime/internal/thread-authorization",
        "PLATFORM_RUNTIME_MODEL_CONFIG_URL": f"http://127.0.0.1:{platform_port}/api/runtime/internal/model-config",
        **options.get("env", {}),
    }
    for key in tuple(env):
        if key.startswith(("LANGFUSE_", "OTEL_EXPORTER_")):
            env.pop(key)
    if options.get("provider"):
        env["RELIABILITY_OBSERVATIONS_URL"] = (
            f"http://127.0.0.1:{spec['provider_port']}"
        )

    def start(role, source=None, command=None):
        output = (tmp_path / f"{role}-{len(logs)}.log").open("w")
        logs.append(output)
        processes[role] = subprocess.Popen(
            command
            or [
                os.getenv("PLATFORM_API_TEST_PYTHON", sys.executable)
                if role == "platform"
                else sys.executable,
                str(fixture),
                role,
                str(spec_path),
            ],
            env=env
            if source is None
            else {**env, "PYTHONPATH": str(source) + os.pathsep + env["PYTHONPATH"]},
            stdout=output,
            stderr=output,
        )
        return processes[role]

    def stop(role):
        process = processes.pop(role, None)
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    try:
        initdb = shutil.which("initdb") or "/Library/PostgreSQL/17/bin/initdb"
        postgres = str(Path(initdb).with_name("postgres"))
        redis_server = shutil.which("redis-server")
        assert Path(initdb).is_file() and Path(postgres).is_file(), (
            "Local PostgreSQL initdb/postgres binaries are required"
        )
        assert redis_server, "Local redis-server is required"
        pg_port, redis_port = port(), port()
        pg_data = tmp_path / "postgres"
        initialization = subprocess.run(
            [
                initdb,
                "-D",
                str(pg_data),
                "-U",
                "postgres",
                "-A",
                "trust",
                "--encoding=UTF8",
                "--locale=C",
            ],
            capture_output=True,
            timeout=45,
        )
        (tmp_path / "initdb.log").write_bytes(
            initialization.stdout + initialization.stderr
        )
        assert initialization.returncode == 0, initialization.stderr.decode(
            errors="replace"
        )
        env["DATABASE_URI"] = f"postgresql://postgres@127.0.0.1:{pg_port}/postgres"
        env["REDIS_URI"] = f"redis://127.0.0.1:{redis_port}/0"
        pg_process = start(
            "postgres",
            command=[
                postgres,
                "-D",
                str(pg_data),
                "-h",
                "127.0.0.1",
                "-p",
                str(pg_port),
                "-c",
                "unix_socket_directories=",
            ],
        )
        wait_for(
            lambda: (
                subprocess.run(
                    [
                        str(Path(initdb).with_name("pg_isready")),
                        "-h",
                        "127.0.0.1",
                        "-p",
                        str(pg_port),
                        "-U",
                        "postgres",
                    ],
                    capture_output=True,
                ).returncode
                == 0
            ),
            process=pg_process,
        )
        redis_process = start(
            "redis",
            command=[
                redis_server,
                "--bind",
                "127.0.0.1",
                "--port",
                str(redis_port),
                "--dir",
                str(tmp_path),
                "--save",
                "",
                "--appendonly",
                "no",
            ],
        )
        from redis import Redis

        wait_for(lambda: Redis.from_url(env["REDIS_URI"]).ping(), process=redis_process)
        migration = subprocess.run(
            [
                sys.executable,
                "-c",
                "import os; from langgraph_runtime_pg.migrate import upgrade_head; upgrade_head(os.environ['DATABASE_URI']); from runtime_service.db import upgrade; upgrade()",
            ],
            env=env,
            capture_output=True,
            timeout=90,
        )
        (tmp_path / "migration.log").write_bytes(migration.stdout + migration.stderr)
        assert migration.returncode == 0, migration.stderr.decode(errors="replace")
        if options.get("provider"):
            provider_process = start("provider")
            wait_for(
                lambda: (
                    httpx.get(
                        spec["provider_url"] + "/ready", trust_env=False
                    ).is_success
                ),
                process=provider_process,
            )
        runtime_process = start("runtime")
        wait_for(
            lambda: (
                httpx.get(
                    spec["runtime_url"] + "/ready", trust_env=False, timeout=2
                ).status_code
                == 200
            ),
            process=runtime_process,
        )
        platform_process = start("platform")
        wait_for(lambda: Path(spec["ready"]).is_file(), process=platform_process)
        start("worker")
        headers = {
            "x-project-id": spec["project"],
            "Authorization": "Bearer "
            + json.loads(Path(spec["ready"]).read_text())["token"],
            "x-request-id": prefix,
        }
        with httpx.Client(
            base_url=f"http://127.0.0.1:{platform_port}/api/langgraph",
            headers=headers,
            timeout=240,
            trust_env=False,
        ) as client:
            yield client, spec, env, processes, start, stop, tmp_path
    finally:
        for role in reversed(tuple(processes)):
            stop(role)
        for output in logs:
            output.close()


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    assert response.is_success, (response.status_code, response.text[:1000])
    return response.json()


def facts(env):
    path = Path(env["TOOL_ERROR_TEST_FACTS"])
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def protocol_replay(client, thread):
    frames = []
    with client.stream(
        "POST",
        f"/threads/{thread}/stream/events",
        json={"channels": ["tools", "messages", "tasks", "lifecycle"], "since": 0},
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            frame = json.loads(line[5:])
            frames.append(frame)
            if frame.get("method") == "lifecycle" and frame["params"]["data"].get(
                "status"
            ) in ("success", "error"):
                break
    return frames


def verify_controls(client, spec, env, body):
    workspace_root = Path(env["RUNTIME_WORKSPACE_ROOT"]) / "dearflow_agent"
    for decision in ("approve", "edit", "reject", "clarification"):
        thread = request(
            client,
            "POST",
            "/threads",
            json={"metadata": {"graph_id": "dearflow_agent"}},
        )["thread_id"]
        # Platform request context uses DEFAULT_TENANT_ID, not the catalog tenant.
        target = (
            hashed_thread_root(workspace_root, "__default", spec["project"], thread)
            / "workspace/work/approved.txt"
        )
        assert not target.exists()
        response = client.post(
            f"/threads/{thread}/runs/stream",
            json={
                **body,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": "clarification"
                            if decision == "clarification"
                            else "approval",
                        }
                    ]
                },
            },
        )
        assert (
            response.status_code == 200 and "tool.execution_failed" not in response.text
        )
        assert (
            request(client, "GET", f"/threads/{thread}/runs")[0]["status"]
            == "interrupted"
        )
        state = request(client, "GET", f"/threads/{thread}/state")
        interrupts = state.get("interrupts") or [
            i for task in state.get("tasks", []) for i in task.get("interrupts", [])
        ]
        if isinstance(interrupts, dict):
            interrupts = [
                {"id": k, "value": v.get("value", v)} for k, v in interrupts.items()
            ]
        assert len(interrupts) == 1
        before_files = set(workspace_root.glob("*/workspace/work/approved.txt"))
        if decision == "clarification":
            assert interrupts[0]["value"]["kind"] == "clarification"
            answer = {
                "schema_version": 1,
                "status": "answered",
                "values": {"title": "fixture"},
            }
        else:
            assert interrupts[0]["value"]["action_requests"][0]["name"] == "write_file"
            action = {"type": decision}
            if decision == "edit":
                action["edited_action"] = {
                    "name": "write_file",
                    "args": {
                        "file_path": "/workspace/work/approved.txt",
                        "content": "reviewed",
                    },
                }
            answer = {"decisions": [action]}
        response = client.post(
            f"/threads/{thread}/runs/stream",
            json={
                "assistant_id": body["assistant_id"],
                "command": {"resume": {interrupts[0]["id"]: answer}},
            },
        )
        assert response.status_code == 200, response.text[:1000]
        assert "recovered" in response.text
        assert (
            request(client, "GET", f"/threads/{thread}/runs")[0]["status"] == "success"
        )
        after_files = set(workspace_root.glob("*/workspace/work/approved.txt"))
        created = after_files - before_files
        if decision in ("approve", "edit"):
            assert created == {target}
            assert target.read_text() == ("reviewed" if decision == "edit" else "once")
        else:
            assert not created and not target.exists()
    thread = request(
        client,
        "POST",
        "/threads",
        json={"metadata": {"graph_id": "dearflow_agent"}},
    )["thread_id"]
    before = sum(f["event"] == "provider" for f in facts(env))
    run = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json={**body, "input": {"messages": [{"role": "user", "content": "slow"}]}},
    )
    run_id = run.get("run_id") or run["id"]
    wait_for(lambda: sum(f["event"] == "provider" for f in facts(env)) == before + 1)
    request(
        client,
        "POST",
        f"/threads/{thread}/runs/{run_id}/cancel",
        json={"action": "interrupt"},
    )

    def cancelled():
        current = request(client, "GET", f"/threads/{thread}/runs/{run_id}")
        return current if current["status"] not in ("pending", "running") else None

    assert wait_for(cancelled)["status"] == "interrupted"
    assert sum(f["event"] == "provider" for f in facts(env)) == before + 1
    print(
        json.dumps(
            {
                "controls": ["approve", "edit", "reject", "clarification", "cancel"],
                "all_passed": True,
            }
        ),
        flush=True,
    )


def test_http_main_child_errors_and_restart_replay(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    retained = []
    for prompt in ("main", "child"):
        created = request(
            client,
            "POST",
            "/threads",
            json={"metadata": {"graph_id": "dearflow_agent"}},
        )
        assert created["metadata"]["graph_id"] == "dearflow_agent"
        thread = created["thread_id"]
        body = {
            "assistant_id": "dearflow_agent",
            "input": {"messages": [{"role": "user", "content": prompt}]},
            "context": {"model_id": spec["model"], "execution_mode": "ultra"},
            "stream_mode": ["updates", "tools", "values"],
            "stream_subgraphs": True,
            "version": "v3",
        }
        response = client.post(f"/threads/{thread}/runs/stream", json=body)
        assert response.status_code == 200, response.text[:1000]
        assert "tool.invalid_input" in response.text and "recovered" in response.text
        state = request(
            client, "GET", f"/threads/{thread}/state", params={"subgraphs": "true"}
        )
        history = request(
            client, "POST", f"/threads/{thread}/history", json={"limit": 100}
        )
        runs = request(client, "GET", f"/threads/{thread}/runs")
        assert runs[0]["status"] == "success", runs[0]
        assert "recovered" in json.dumps(state)
        if prompt == "main":
            errors = [
                m for m in state["values"]["messages"] if m.get("status") == "error"
            ]
            assert errors[0]["tool_call_id"] == "fixture-search_web"
            assert json.loads(errors[0]["content"])["code"] == "tool.invalid_input"
            assert "tool.invalid_input" in json.dumps(history)
        else:
            assert "tools:" in response.text and "fixture-search_web" in response.text
        retained.append((thread, state["values"]["messages"]))
        replay = protocol_replay(client, thread)
        assert "tool.invalid_input" in json.dumps(replay)
        print(
            json.dumps(
                {
                    "run": prompt,
                    "thread_id": thread,
                    "run_id": runs[0].get("run_id", runs[0].get("id")),
                    "status": "success",
                    "tool_call_id": "fixture-search_web",
                    "protocol_replay": True,
                }
            ),
            flush=True,
        )
    facts = [
        json.loads(line)
        for line in Path(env["TOOL_ERROR_TEST_FACTS"]).read_text().splitlines()
    ]
    assert any(
        f["event"] == "model" and f["errors"] == ["fixture-search_web"] for f in facts
    )
    assert all(f["pid"] == processes["worker"].pid for f in facts)
    assert not any(f["event"] == "provider" for f in facts)
    fatal_thread = request(
        client,
        "POST",
        "/threads",
        json={"metadata": {"graph_id": "dearflow_agent"}},
    )["thread_id"]
    response = client.post(
        f"/threads/{fatal_thread}/runs/stream",
        json={**body, "input": {"messages": [{"role": "user", "content": "fatal"}]}},
    )
    assert response.status_code == 200 and "runtime.execution_failed" in response.text
    assert "EXCEPTION_CANARY" not in response.text
    fatal_runs = request(client, "GET", f"/threads/{fatal_thread}/runs")
    assert fatal_runs[0]["status"] == "error"
    thread_detail = request(client, "GET", f"/threads/{fatal_thread}")
    assert "EXCEPTION_CANARY" not in json.dumps(thread_detail)
    fatal_state = request(client, "GET", f"/threads/{fatal_thread}/state")
    fatal_history = request(
        client, "POST", f"/threads/{fatal_thread}/history", json={"limit": 100}
    )
    assert "EXCEPTION_CANARY" not in json.dumps([fatal_state, fatal_history])
    assert "EXCEPTION_CANARY" not in json.dumps(protocol_replay(client, fatal_thread))
    denied = client.post(
        f"/threads/{fatal_thread}/runs",
        json={**body, "context": {"model_id": str(uuid4())}},
    )
    assert denied.status_code in (400, 403)
    facts = [
        json.loads(line)
        for line in Path(env["TOOL_ERROR_TEST_FACTS"]).read_text().splitlines()
    ]
    assert sum(f["event"] == "provider" for f in facts) == 1
    verify_controls(client, spec, env, body)
    (tmp_path / "workspaces/keep.txt").write_text("keep")
    for role in ("worker", "runtime", "platform"):
        stop(role)
    Path(spec["ready"]).unlink()
    runtime_process = start("runtime")
    wait_for(
        lambda: (
            httpx.get(
                spec["runtime_url"] + "/ready", trust_env=False, timeout=2
            ).status_code
            == 200
        ),
        process=runtime_process,
    )
    platform_process = start("platform")
    wait_for(lambda: Path(spec["ready"]).is_file(), process=platform_process)
    start("worker")
    for thread, expected in retained:
        state = request(client, "GET", f"/threads/{thread}/state")
        assert state["values"]["messages"] == expected
    assert (tmp_path / "workspaces/keep.txt").read_text() == "keep"
    assert (
        Path(env["TOOL_ERROR_TEST_FACTS"]).read_text().count('"event": "provider"') == 2
    )
    import io
    import tarfile

    baseline = tmp_path / "baseline"
    baseline.mkdir()
    archive = subprocess.check_output(
        [
            "git",
            "archive",
            "HEAD",
            "apps/runtime-service/src",
            "apps/runtime-service/pyproject.toml",
            "apps/runtime-service/README.md",
        ],
        cwd=Path(__file__).resolve().parents[5],
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(baseline, filter="data")
    for role in ("worker", "runtime"):
        stop(role)
    baseline_source = baseline / "apps/runtime-service/src"
    runtime_process = start("runtime", baseline_source)
    wait_for(
        lambda: (
            httpx.get(
                spec["runtime_url"] + "/ready", trust_env=False, timeout=2
            ).status_code
            == 200
        ),
        process=runtime_process,
    )
    start("worker", baseline_source)
    for thread, expected in retained:
        assert (
            request(client, "GET", f"/threads/{thread}/state")["values"]["messages"]
            == expected
        )
    for prompt in ("main", "child"):
        thread = request(
            client,
            "POST",
            "/threads",
            json={"metadata": {"graph_id": "dearflow_agent"}},
        )["thread_id"]
        response = client.post(
            f"/threads/{thread}/runs/stream",
            json={**body, "input": {"messages": [{"role": "user", "content": prompt}]}},
        )
        assert (
            "recovered" in response.text and "invalid_research_query" in response.text
        )
        assert "tool.invalid_input" not in response.text
        assert (
            request(client, "GET", f"/threads/{thread}/runs")[0]["status"] == "success"
        )
    assert (tmp_path / "workspaces/keep.txt").read_text() == "keep"
    verify_controls(client, spec, env, body)
    print(
        json.dumps(
            {
                "main_child_run": "success",
                "restarted_roles": 3,
                "provider_calls_before_fatal": 0,
                "fatal_error_safe": True,
                "rollback_main_child": True,
                "model_error_consumed": True,
                "checkpoint_replay": True,
            }
        )
    )
