"""Opt-in production factory/API/Worker verification against an HTTP provider."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from services.dearflow_agent.test_tool_error_platform import (
    facts,
    protocol_replay,
    request,
    wait_for,
)
from services.dearflow_agent.test_tool_error_platform import (
    stack as disposable_stack,
)

stack = disposable_stack

STACK = {
    "fixture": "run_reliability.py",
    "provider": True,
    "http_app": True,
    "env": {
        "GRAPHHARBOR_LEASE_SECONDS": "5",
        "GRAPHHARBOR_REAPER_INTERVAL_SECONDS": "0.5",
        "AGENT_MODEL_CALL_TIMEOUT_SECONDS": "3",
    },
}


def run_body(spec, prompt):
    return {
        "assistant_id": "dearflow_agent",
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "context": {
            "model_id": spec["model"],
            "execution_mode": "ultra",
            "access_policy": "workspace_write",
        },
        "stream_mode": ["messages", "updates", "tools", "values"],
        "stream_subgraphs": True,
        "version": "v3",
    }


def new_thread(client):
    return request(
        client, "POST", "/threads", json={"metadata": {"graph_id": "dearflow_agent"}}
    )["thread_id"]


def counts(env, key):
    return sum(
        item["event"] == "http-model" and item.get("key") == key for item in facts(env)
    )


def terminal(client, thread, run_id):
    def read():
        value = request(client, "GET", f"/threads/{thread}/runs/{run_id}")
        return value if value["status"] not in {"pending", "running"} else None

    return wait_for(read)


def db_attempts(env, run_id):
    import psycopg

    with psycopg.connect(env["DATABASE_URI"]) as conn:
        return conn.execute(
            "select retry_count from runs where run_id = %s", (run_id,)
        ).fetchone()[0]


@pytest.mark.parametrize("stack", [STACK], indirect=True)
def test_http_retry_task_partial_security_and_diagnostics(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    summaries = []
    for prompt, status, expected in (
        ("retry", "success", 2),
        ("exhausted", "error", 2),
        ("denied", "error", 1),
        ("partial", "error", 1),
        ("timeout", "error", 2),
        ("child", "success", 1),
        ("parallel", "success", 1),
        ("write-retry", "success", 1),
    ):
        thread = new_thread(client)
        response = client.post(
            f"/threads/{thread}/runs/stream", json=run_body(spec, prompt)
        )
        assert response.status_code == 200, response.text[:1000]
        runs = request(client, "GET", f"/threads/{thread}/runs")
        run_id = runs[0].get("run_id", runs[0].get("id"))
        if prompt == "write-retry":
            assert terminal(client, thread, run_id)["status"] == "interrupted"
            pending = request(client, "GET", f"/threads/{thread}/state")
            interrupts = pending.get("interrupts") or [
                item
                for task in pending.get("tasks", [])
                for item in task.get("interrupts", [])
            ]
            if isinstance(interrupts, dict):
                interrupts = [
                    {"id": key, "value": value.get("value", value)}
                    for key, value in interrupts.items()
                ]
            assert len(interrupts) == 1
            assert interrupts[0]["value"]["action_requests"][0]["name"] == "write_file"
            assert not list(Path(env["RUNTIME_WORKSPACE_ROOT"]).rglob("once.txt"))
            response = client.post(
                f"/threads/{thread}/runs/stream",
                json={
                    "assistant_id": "dearflow_agent",
                    "command": {
                        "resume": {
                            interrupts[0]["id"]: {"decisions": [{"type": "approve"}]}
                        }
                    },
                },
            )
            assert response.is_success, response.text[:1000]
            resumed = request(client, "GET", f"/threads/{thread}/runs")[0]
            resumed_id = resumed.get("run_id", resumed.get("id"))
            assert resumed_id != run_id
            run_id = resumed_id
        assert terminal(client, thread, run_id)["status"] == status, (prompt, runs[0])
        assert counts(env, prompt) == expected, (prompt, counts(env, prompt))
        assert db_attempts(env, run_id) == 1
        state = request(
            client, "GET", f"/threads/{thread}/state", params={"subgraphs": "true"}
        )
        history = request(
            client, "POST", f"/threads/{thread}/history", json={"limit": 100}
        )
        diag_response = client.get(f"/threads/{thread}/runs/{run_id}/diagnostics")
        assert diag_response.is_success, diag_response.text
        diag = diag_response.json()
        assert diag_response.headers["cache-control"] == "no-store"
        assert diag["run_status"] == status and diag["retries"], diag
        if prompt != "write-retry":
            assert diag["preparations"], diag
        assert all(1 <= item["attempts"] <= 2 for item in diag["retries"])
        assert "runtime_prepare" not in json.dumps([state, history, diag])
        assert "PROVIDER_CANARY" not in json.dumps(
            [response.text, state, history, diag]
        )
        if prompt == "child":
            assert counts(env, "child-exhausted") == 2
            assert any(
                item["unit"] == "task"
                and item["attempts"] == 2
                and item["outcome"] == "exhausted"
                for item in diag["retries"]
            )
            assert "choose_alternative" in json.dumps(state)
        if prompt == "parallel":
            assert counts(env, "child-partial") == 1 and counts(env, "child-retry") == 2
            assert "VISIBLE_ONCE" in response.text
        if prompt == "write-retry":
            assert counts(env, "write-retry-after-tool") == 2
            assert len(list(Path(env["RUNTIME_WORKSPACE_ROOT"]).rglob("once.txt"))) == 1
            assert json.dumps(state).count('"tool_call_id": "write-once"') == 1
        if prompt in {"retry", "child"}:
            assert "PROVIDER_CANARY" not in json.dumps(protocol_replay(client, thread))
        summary = {
            "prompt": prompt,
            "run_id": run_id,
            "thread_id": thread,
            "status": status,
            "attempts": counts(env, prompt),
            "diagnostics": diag,
        }
        summaries.append(summary)
        print(
            json.dumps({k: v for k, v in summary.items() if k != "diagnostics"}),
            flush=True,
        )

    thread = new_thread(client)
    for payload in (
        {"input": {"runtime_prepare": {"workspace": "CANARY"}}},
        {"input": {"messages": [], "nested": {"runtime_prepare": {}}}},
        {"command": {"update": {"runtime_prepare": {}}}},
    ):
        response = client.post(
            f"/threads/{thread}/runs", json={**run_body(spec, "retry"), **payload}
        )
        assert response.status_code == 400
    response = client.post(
        f"/threads/{thread}/state", json={"values": {"runtime_prepare": {}}}
    )
    assert response.status_code == 400
    assert not request(client, "GET", f"/threads/{thread}/runs")
    (tmp_path / "reliability-evidence.json").write_text(json.dumps(summaries, indent=2))
    openapi = client.get(f"http://127.0.0.1:{spec['platform_port']}/openapi.json")
    assert openapi.is_success
    schemas = openapi.json()["components"]["schemas"]
    assert "preparations" in schemas["RunDiagnostics"]["properties"]
    (tmp_path / "diagnostics-openapi.json").write_text(
        json.dumps(
            {
                name: schema
                for name, schema in schemas.items()
                if name in {"RunDiagnostics", "PreparationSummary", "RetrySummary"}
            },
            indent=2,
        )
    )


@pytest.mark.parametrize("stack", [STACK], indirect=True)
def test_worker_crash_windows_checkpoint_cancel_and_rollback(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    retained = []
    for prompt, expected_prepares in (
        ("prepare-before", 2),
        ("prepare-after", 1),
        ("infra-pg", 2),
    ):
        thread = new_thread(client)
        run = request(
            client, "POST", f"/threads/{thread}/runs", json=run_body(spec, prompt)
        )
        run_id = run.get("run_id", run.get("id"))
        if prompt != "infra-pg":
            wait_for(
                lambda prompt=prompt: any(
                    item["event"] == "crash-window" and item["prompt"] == prompt
                    for item in facts(env)
                )
            )
            processes["worker"].kill()
            processes["worker"].wait(timeout=15)
            stop("worker")
            start("worker")
        assert terminal(client, thread, run_id)["status"] == "success"
        assert (
            sum(
                item["event"] == "prepare" and item["run_id"] == run_id
                for item in facts(env)
            )
            == expected_prepares
        )
        assert db_attempts(env, run_id) == 2
        assert all(
            path.read_text() == "user version"
            for path in Path(env["RUNTIME_WORKSPACE_ROOT"]).rglob("retained.txt")
        )
        state = request(client, "GET", f"/threads/{thread}/state")
        assert "runtime_prepare" not in json.dumps(state)
        retained.append((thread, state["values"]["messages"]))
        print(
            json.dumps(
                {
                    "crash": prompt,
                    "run_id": run_id,
                    "worker_attempts": 2,
                    "prepares": expected_prepares,
                }
            ),
            flush=True,
        )

    thread = new_thread(client)
    run = request(
        client, "POST", f"/threads/{thread}/runs", json=run_body(spec, "cancel")
    )
    run_id = run.get("run_id", run.get("id"))
    wait_for(lambda: counts(env, "cancel") == 1)
    request(
        client,
        "POST",
        f"/threads/{thread}/runs/{run_id}/cancel",
        json={"action": "interrupt"},
    )
    assert terminal(client, thread, run_id)["status"] == "interrupted"
    assert counts(env, "cancel") == 1

    stop("worker")
    repo = Path(__file__).resolve().parents[4]
    archive = subprocess.run(
        ["git", "archive", "HEAD", "apps/runtime-service/src"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    import io
    import tarfile

    old = tmp_path / "old"
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(old, filter="data")
    start("worker", old / "apps/runtime-service/src")
    for thread, messages in retained:
        assert (
            request(client, "GET", f"/threads/{thread}/state")["values"]["messages"]
            == messages
        )
        run = request(
            client, "POST", f"/threads/{thread}/runs", json=run_body(spec, "old-normal")
        )
        assert (
            terminal(client, thread, run.get("run_id", run.get("id")))["status"]
            == "success"
        )
    stop("worker")
    start("worker")
    for thread, _ in retained:
        run = request(
            client, "POST", f"/threads/{thread}/runs", json=run_body(spec, "new-normal")
        )
        assert (
            terminal(client, thread, run.get("run_id", run.get("id")))["status"]
            == "success"
        )
    print(
        json.dumps(
            {"cancel": "passed", "rollback": "old/new retained checkpoints passed"}
        ),
        flush=True,
    )

    stop("worker")
    env["GRAPHHARBOR_RUN_TIMEOUT_SECONDS"] = "2.5"
    start("worker")
    thread = new_thread(client)
    run = request(
        client, "POST", f"/threads/{thread}/runs", json=run_body(spec, "run-deadline")
    )
    run_id = run.get("run_id", run.get("id"))
    assert terminal(client, thread, run_id)["status"] == "timeout"
    assert counts(env, "run-deadline") == 1 and db_attempts(env, run_id) == 1
    print(json.dumps({"run_deadline": "passed", "attempts": 1}), flush=True)


@pytest.mark.parametrize("stack", [STACK], indirect=True)
def test_local_pg_skills_memory_and_message_queue_regression(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    stop("worker")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/services/dearflow_agent/test_restart.py",
            "tests/services/dearflow_agent/test_skill_restart.py",
            "tests/services/dearflow_agent/test_p6_governance.py",
            "tests/services/test_message_inbox_postgres.py",
            "-k",
            "not live",
            "-q",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **env,
            "DEAR_TEST_DATABASE_URI": env["DATABASE_URI"],
            "RUNTIME_MESSAGE_TEST_DSN": env["DATABASE_URI"],
        },
        capture_output=True,
        timeout=900,
    )
    output = result.stdout + result.stderr
    (tmp_path / "persistence-regression.log").write_bytes(output)
    assert result.returncode == 0, output.decode(errors="replace")[-8000:]
    assert b" skipped" not in result.stdout, result.stdout.decode(errors="replace")
    print(result.stdout.decode(errors="replace")[-2000:], flush=True)
