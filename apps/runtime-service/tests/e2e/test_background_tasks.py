"""Disposable native API/Worker gates for managed background completion."""

import io
import json
import sqlite3
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest
from e2e.test_run_reliability import (
    STACK,
    counts,
    new_thread,
    run_body,
    terminal,
)
from e2e.test_run_reliability import stack as disposable_stack
from services.dearflow_agent.test_tool_error_platform import (
    facts,
    request,
    wait_for,
)

stack = disposable_stack


def background_thread(client):
    return request(
        client,
        "POST",
        "/threads",
        json={
            "metadata": {
                "graph_id": "dearflow_agent",
                "access_policy": "workspace_write",
            }
        },
    )["thread_id"]


def first_task(client, thread):
    def read():
        values = request(client, "GET", f"/threads/{thread}/background-tasks")["items"]
        return values[0] if values else None

    return wait_for(read)


def task_when(client, thread, task_id, check):
    def read():
        value = request(client, "GET", f"/threads/{thread}/background-tasks/{task_id}")
        return value if check(value) else None

    return wait_for(read)


def interrupts(client, thread):
    state = request(client, "GET", f"/threads/{thread}/state")
    values = state.get("interrupts") or [
        value for task in state.get("tasks", []) for value in task.get("interrupts", [])
    ]
    if isinstance(values, dict):
        values = [
            {"id": key, "value": value.get("value", value)}
            for key, value in values.items()
        ]
    return values


def resume(client, thread, decision):
    pending = interrupts(client, thread)
    assert len(pending) == 1
    return request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json={
            "assistant_id": "dearflow_agent",
            "command": {
                "resume": {
                    pending[0]["id"]: {
                        "decisions": [
                            decision
                            if isinstance(decision, dict)
                            else {"type": decision}
                        ]
                    }
                }
            },
        },
    )


BACKGROUND_STACK = {
    **STACK,
    "graphs": {"dearflow_agent": "fixture.py:graph"},
    "env": {
        **STACK["env"],
        "AGENT_MODEL_CALL_TIMEOUT_SECONDS": "30",
        "GRAPHHARBOR_LEASE_SECONDS": "60",
        "RUNTIME_BACKEND": "docker",
        "RUNTIME_BACKGROUND_TASKS_ENABLED": "1",
        "RUNTIME_EXECUTION_HOST_ID": "background-e2e",
    },
}


@pytest.mark.parametrize(
    "stack",
    [
        {
            **STACK,
            "graphs": {"dearflow_agent": "fixture.py:graph"},
            "env": {
                **STACK["env"],
                "AGENT_MODEL_CALL_TIMEOUT_SECONDS": "30",
                "GRAPHHARBOR_LEASE_SECONDS": "60",
            },
        }
    ],
    indirect=True,
)
def test_native_enqueue_idempotency_and_fixed_stop_boundary(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    thread = new_thread(client)
    source = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-gate-block"),
    )
    wait_for(lambda: counts(env, "background-gate-block") == 1)
    queued = {**run_body(spec, "queued-completion"), "multitask_strategy": "enqueue"}
    headers = {"Idempotency-Key": "background-gate-event"}
    first = request(
        client, "POST", f"/threads/{thread}/runs", json=queued, headers=headers
    )
    second = request(
        client, "POST", f"/threads/{thread}/runs", json=queued, headers=headers
    )
    assert first["run_id"] == second["run_id"]
    assert first["status"] == "pending"
    assert counts(env, "queued-completion") == 0
    receipt = request(
        client,
        "POST",
        f"/threads/{thread}/cancel",
        json={},
        headers={"Idempotency-Key": "background-gate-stop"},
    )
    stop_id = receipt["stop_id"]
    stopped = wait_for(
        lambda: (
            value
            if (
                value := request(
                    client, "GET", f"/threads/{thread}/stop-requests/{stop_id}"
                )
            )["phase"]
            in {"stopped", "no_active_run"}
            else None
        )
    )
    assert stopped["execution_stopped"]
    assert terminal(client, thread, source["run_id"])["status"] == "interrupted"
    assert terminal(client, thread, first["run_id"])["status"] == "interrupted"
    assert counts(env, "queued-completion") == 0
    later = request(
        client, "POST", f"/threads/{thread}/runs", json=run_body(spec, "after-stop")
    )
    assert terminal(client, thread, later["run_id"])["status"] == "success"


@pytest.mark.parametrize("stack", [BACKGROUND_STACK], indirect=True)
def test_real_background_command_completion_cancel_and_repository(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    thread = background_thread(client)
    run = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-short"),
    )
    assert terminal(client, thread, run["run_id"])["status"] == "success"

    def task_page():
        return request(client, "GET", f"/threads/{thread}/background-tasks")

    row = wait_for(lambda: task_page()["items"][0] if task_page()["items"] else None)
    assert row["origin_run_id"] == run["run_id"]
    task_id = row["task_id"]
    completed = wait_for(
        lambda: (
            value
            if (
                value := request(
                    client, "GET", f"/threads/{thread}/background-tasks/{task_id}"
                )
            )["delivery"]["state"]
            == "accepted"
            else None
        )
    )
    completion_run = completed["delivery"]["run_id"]
    assert terminal(client, thread, completion_run)["status"] == "success"
    assert (
        completed["status"] == "succeeded" and completed["cleanup_state"] == "confirmed"
    )
    log = request(client, "GET", f"/threads/{thread}/background-tasks/{task_id}/output")
    assert log["available"] and log["text"] == "BACKGROUND_DONE"
    assert (
        len([value for value in facts(env) if value["event"] == "completion-model"])
        == 1
    )
    assert task_page()["latest_delivery_run_id"] == completion_run

    thread = background_thread(client)
    run = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-long"),
    )
    assert terminal(client, thread, run["run_id"])["status"] == "success"
    row = request(client, "GET", f"/threads/{thread}/background-tasks")["items"][0]
    path = f"/threads/{thread}/background-tasks/{row['task_id']}"
    assert row["status"] == "running"
    for _ in range(2):
        response = client.post(
            path + "/cancel", json={}, headers={"Idempotency-Key": "cancel-once"}
        )
        assert (
            response.status_code == 202
            and response.headers["cache-control"] == "no-store"
        ), response.text
    cancelled = wait_for(
        lambda: (
            value
            if (value := request(client, "GET", path))["cleanup_state"] == "confirmed"
            else None
        )
    )
    assert (
        cancelled["status"] == "cancelled"
        and cancelled["delivery"]["state"] == "suppressed"
    )
    assert len(request(client, "GET", f"/threads/{thread}/runs")) == 1

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/background/test_repository.py",
            "tests/services/test_run_control.py",
            "-q",
            "--basetemp=" + str(tmp_path / "repository-tests"),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **env,
            "BACKGROUND_TEST_DSN": env["DATABASE_URI"],
            "RUNTIME_MESSAGE_TEST_DSN": env["DATABASE_URI"],
        },
        capture_output=True,
        timeout=300,
    )
    (tmp_path / "background-repository-regression.log").write_bytes(
        result.stdout + result.stderr
    )
    assert result.returncode == 0, (result.stdout + result.stderr).decode(
        errors="replace"
    )[-10000:]
    print(result.stdout.decode(errors="replace"), flush=True)
    (tmp_path / "background-evidence.json").write_text(
        json.dumps({"completed": completed, "cancelled": cancelled}, indent=2)
    )


@pytest.mark.parametrize("stack", [BACKGROUND_STACK], indirect=True)
def test_source_lifecycle_hitl_stop_and_independent_process_recovery(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    evidence = []
    body = run_body(spec, "background-long")
    body["context"]["access_policy"] = "review"
    thread = background_thread(client)
    request(
        client,
        "PATCH",
        f"/threads/{thread}/access-policy",
        json={"access_policy": "review"},
    )
    source = request(client, "POST", f"/threads/{thread}/runs", json=body)
    assert terminal(client, thread, source["run_id"])["status"] == "interrupted"
    assert request(client, "GET", f"/threads/{thread}/background-tasks")["items"] == []
    rejected = resume(client, thread, "reject")
    assert terminal(client, thread, rejected["run_id"])["status"] == "success"
    assert request(client, "GET", f"/threads/{thread}/background-tasks")["items"] == []

    thread = background_thread(client)
    request(
        client,
        "PATCH",
        f"/threads/{thread}/access-policy",
        json={"access_policy": "review"},
    )
    source = request(client, "POST", f"/threads/{thread}/runs", json=body)
    assert terminal(client, thread, source["run_id"])["status"] == "interrupted"
    approved = resume(client, thread, "approve")
    assert terminal(client, thread, approved["run_id"])["status"] == "success"
    row = first_task(client, thread)
    assert row["origin_run_id"] == approved["run_id"]
    stop("runtime")
    stop("worker")
    start("runtime")
    wait_for(
        lambda: (
            client.get(f"http://127.0.0.1:{spec['runtime_port']}/ready").status_code
            == 200
        )
    )
    start("worker")
    row = task_when(
        client, thread, row["task_id"], lambda value: value["status"] == "running"
    )
    receipt = request(
        client,
        "POST",
        f"/threads/{thread}/cancel",
        json={},
        headers={"Idempotency-Key": "background-idle-stop"},
    )

    def read_stop():
        value = request(
            client, "GET", f"/threads/{thread}/stop-requests/{receipt['stop_id']}"
        )
        return (
            value
            if value["phase"] in {"stopped", "no_active_run"}
            and value["resource_cleanup"] == "confirmed"
            else None
        )

    stopped = wait_for(read_stop)
    assert stopped["report"]["background_tasks"]["target_count"] == 1
    assert stopped["report"]["background_tasks"]["cleanup_confirmed_count"] == 1
    evidence.append(
        task_when(
            client,
            thread,
            row["task_id"],
            lambda value: value["cleanup_state"] == "confirmed",
        )
    )
    assert evidence[-1]["delivery"]["state"] == "suppressed"

    for prompt, status in (
        ("background-source-error", "error"),
        ("background-timeout", "success"),
        ("background-exit124", "success"),
    ):
        thread = background_thread(client)
        source = request(
            client, "POST", f"/threads/{thread}/runs", json=run_body(spec, prompt)
        )
        assert terminal(client, thread, source["run_id"])["status"] == status
        row = first_task(client, thread)
        row = task_when(
            client,
            thread,
            row["task_id"],
            lambda value: value["cleanup_state"] == "confirmed",
        )
        if prompt == "background-source-error":
            assert (
                row["status"] == "cancelled"
                and row["delivery"]["state"] == "suppressed"
            )
        elif prompt == "background-timeout":
            assert row["status"] == "timed_out"
        else:
            assert row["status"] == "failed" and row["exit_code"] == 124
        evidence.append(row)
    (tmp_path / "background-lifecycle-evidence.json").write_text(
        json.dumps(evidence, indent=2)
    )


@pytest.mark.parametrize(
    "stack",
    [
        {
            **BACKGROUND_STACK,
            "startup_timeout": 360,
            "env": {
                **BACKGROUND_STACK["env"],
                "PLATFORM_ACL_TIMEOUT_SECONDS": "60",
            },
        }
    ],
    indirect=True,
)
def test_completion_waits_for_hitl_and_new_tasks_survive_old_stop(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    thread = background_thread(client)
    request(
        client,
        "PATCH",
        f"/threads/{thread}/access-policy",
        json={"access_policy": "review"},
    )
    source = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-long"),
    )
    assert terminal(client, thread, source["run_id"])["status"] == "interrupted"
    edited = resume(
        client,
        thread,
        {
            "type": "edit",
            "edited_action": {
                "name": "background_execute",
                "args": {
                    "command": "while [ ! -f background-approval-ready ]; do sleep 0.1; done; printf EDITED",
                    "timeout": 180,
                },
            },
        },
    )
    assert terminal(client, thread, edited["run_id"])["status"] == "success"
    row = first_task(client, thread)
    assert row["origin_run_id"] == edited["run_id"] and row["status"] == "running"
    approval = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "write-retry"),
    )
    assert terminal(client, thread, approval["run_id"])["status"] == "interrupted"
    interrupt_id = interrupts(client, thread)[0]["id"]
    workspaces = list(
        Path(env["RUNTIME_WORKSPACE_ROOT"]).glob("dearflow_agent/*/workspace")
    )
    assert workspaces
    (workspaces[0] / "work/background-approval-ready").write_text("ready")
    pending = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["delivery"]["state"] == "pending"
        and value["delivery"]["reason_code"] == "background_task_approval_pending",
    )
    assert pending["status"] == "succeeded" and pending["cleanup_state"] == "confirmed"
    assert interrupts(client, thread)[0]["id"] == interrupt_id
    assert not [value for value in facts(env) if value["event"] == "completion-model"]
    rejected = resume(client, thread, "reject")
    assert terminal(client, thread, rejected["run_id"])["status"] == "success"
    accepted = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["delivery"]["state"] == "accepted",
    )
    assert (
        terminal(client, thread, accepted["delivery"]["run_id"])["status"] == "success"
    )
    assert (
        request(
            client, "GET", f"/threads/{thread}/background-tasks/{row['task_id']}/output"
        )["text"]
        == "EDITED"
    )

    request(
        client,
        "PATCH",
        f"/threads/{thread}/access-policy",
        json={"access_policy": "workspace_write"},
    )
    source = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-stop-target"),
    )
    assert terminal(client, thread, source["run_id"])["status"] == "success"
    target = first_task(client, thread)
    receipt = request(
        client,
        "POST",
        f"/threads/{thread}/cancel",
        json={},
        headers={"Idempotency-Key": "fixed-background-stop"},
    )

    def confirmed_stop():
        value = request(
            client, "GET", f"/threads/{thread}/stop-requests/{receipt['stop_id']}"
        )
        return value if value["resource_cleanup"] == "confirmed" else None

    stopped = wait_for(confirmed_stop)
    assert stopped["report"]["background_tasks"]["target_count"] == 2
    assert stopped["report"]["background_tasks"]["cleanup_confirmed_count"] == 2
    previous = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["delivery"]["state"] == "suppressed",
    )
    assert previous["status"] == "succeeded"
    assert previous["delivery"]["run_id"] == accepted["delivery"]["run_id"]
    assert (
        task_when(
            client,
            thread,
            target["task_id"],
            lambda value: value["cleanup_state"] == "confirmed",
        )["delivery"]["state"]
        == "suppressed"
    )
    followup = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-after-stop"),
    )
    assert terminal(client, thread, followup["run_id"])["status"] == "success"
    new_task = first_task(client, thread)
    assert new_task["task_id"] != target["task_id"] and new_task["status"] == "running"
    assert (
        confirmed_stop()["report"]["background_tasks"]
        == stopped["report"]["background_tasks"]
    )
    request(
        client,
        "POST",
        f"/threads/{thread}/background-tasks/{new_task['task_id']}/cancel",
        json={},
        headers={"Idempotency-Key": "new-task-cleanup"},
    )
    task_when(
        client,
        thread,
        new_task["task_id"],
        lambda value: value["cleanup_state"] == "confirmed",
    )
    assert sum(value["event"] == "completion-model" for value in facts(env)) == 1
    (tmp_path / "background-approval-stop-evidence.json").write_text(
        json.dumps(
            {"edited": accepted, "stop": stopped, "new_task": new_task}, indent=2
        )
    )


@pytest.mark.parametrize("stack", [BACKGROUND_STACK], indirect=True)
def test_lost_native_ack_is_not_resubmitted_and_late_guard_binds_receipt(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    thread = background_thread(client)
    source = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-short"),
    )
    assert terminal(client, thread, source["run_id"])["status"] == "success"
    stop("worker")
    Path(env["BACKGROUND_FAULT_MODE_PATH"]).write_text("lost-ack")
    row = first_task(client, thread)
    unknown = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["delivery"]["state"] == "unknown",
    )
    wait_for(
        lambda: any(value["event"] == "completion-ack-lost" for value in facts(env))
    )
    completion = [
        value
        for value in request(client, "GET", f"/threads/{thread}/runs")
        if value["run_id"] != source["run_id"]
    ]
    assert len(completion) == 1 and completion[0]["status"] == "pending"
    import psycopg

    with psycopg.connect(env["DATABASE_URI"]) as connection:
        connection.execute(
            "UPDATE runtime_background_tasks SET next_check_at=now() WHERE task_id=%s",
            (row["task_id"],),
        )
    time.sleep(2)
    assert len(request(client, "GET", f"/threads/{thread}/runs")) == 2
    start("worker")
    assert terminal(client, thread, completion[0]["run_id"])["status"] == "success"
    with psycopg.connect(env["DATABASE_URI"]) as connection:
        connection.execute(
            "UPDATE runtime_background_tasks SET next_check_at=now() WHERE task_id=%s",
            (row["task_id"],),
        )
    accepted = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["delivery"]["state"] == "accepted",
    )
    assert accepted["delivery"]["run_id"] == completion[0]["run_id"]
    assert (
        len([value for value in facts(env) if value["event"] == "completion-model"])
        == 1
    )
    (tmp_path / "background-lost-ack-evidence.json").write_text(
        json.dumps({"unknown": unknown, "accepted": accepted}, indent=2)
    )


@pytest.mark.parametrize("stack", [BACKGROUND_STACK], indirect=True)
def test_source_native_timeout_cancel_and_disabled_drain(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    evidence = []
    stop("worker")
    env["GRAPHHARBOR_RUN_TIMEOUT_SECONDS"] = "60"
    env["AGENT_RUN_WRAPUP_RESERVE_SECONDS"] = "0"
    env["AGENT_MODEL_CALL_TIMEOUT_SECONDS"] = "120"
    start("worker")
    for prompt in ("background-source-timeout", "background-source-cancel"):
        thread = background_thread(client)
        run = request(
            client, "POST", f"/threads/{thread}/runs", json=run_body(spec, prompt)
        )
        row = first_task(client, thread)
        wait_for(lambda prompt=prompt: counts(env, prompt + "-after-tool") >= 1)
        if prompt.endswith("cancel"):
            request(client, "POST", f"/threads/{thread}/runs/{run['run_id']}/cancel")
        assert terminal(client, thread, run["run_id"])["status"] == (
            "timeout" if prompt.endswith("timeout") else "interrupted"
        )
        cleaned = task_when(
            client,
            thread,
            row["task_id"],
            lambda value: value["cleanup_state"] == "confirmed",
        )
        assert (
            cleaned["status"] == "cancelled"
            and cleaned["delivery"]["state"] == "suppressed"
        )
        evidence.append(cleaned)

    thread = background_thread(client)
    run = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-drain-short"),
    )
    assert terminal(client, thread, run["run_id"])["status"] == "success"
    row = first_task(client, thread)
    stop("runtime")
    stop("worker")
    env["RUNTIME_BACKGROUND_TASKS_ENABLED"] = "0"
    start("runtime")
    wait_for(
        lambda: client.get(f"http://127.0.0.1:{spec['runtime_port']}/ready").status_code
        == 200
    )
    start("worker")
    capabilities = request(client, "GET", f"/threads/{thread}/capabilities")
    assert (
        capabilities["background_tasks"]
        and not capabilities["background_tasks_start_enabled"]
    )
    blocked = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["cleanup_state"] == "confirmed"
        and value["delivery"]["state"] == "blocked",
    )
    assert (
        blocked["status"] == "succeeded"
        and blocked["delivery"]["reason_code"] == "background_task_disabled"
    )
    request(
        client,
        "POST",
        f"/threads/{thread}/background-tasks/{row['task_id']}/cancel",
        json={},
        headers={"Idempotency-Key": "disabled-drain"},
    )
    drained = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["delivery"]["state"] == "suppressed",
    )
    assert not request(client, "GET", f"/threads/{thread}/background-tasks")[
        "has_unresolved"
    ]
    assert not [value for value in facts(env) if value["event"] == "completion-model"]
    evidence.append(drained)
    import psycopg

    stop("runtime")
    stop("worker")
    downgrade = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; from pathlib import Path; from alembic import command; from alembic.config import Config; from sqlalchemy import create_engine; from sqlalchemy.pool import NullPool; import psycopg; from runtime_service import db; config=Config(); config.set_main_option('script_location',str(Path(db.__file__).with_name('migrations'))); engine=create_engine('postgresql+psycopg://',creator=lambda:psycopg.connect(os.environ['DATABASE_URI']),poolclass=NullPool)\nwith engine.begin() as connection:\n connection.exec_driver_sql('SELECT pg_advisory_xact_lock(746183209)'); config.attributes['connection']=connection; command.downgrade(config,'0002_run_control')\nengine.dispose()",
        ],
        env=env,
        capture_output=True,
        timeout=90,
    )
    assert downgrade.returncode == 0, downgrade.stderr.decode(errors="replace")
    archive = subprocess.run(
        ["git", "archive", "HEAD", "apps/runtime-service/src"],
        capture_output=True,
        check=True,
    )
    previous = tmp_path / "previous-source"
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as source:
        source.extractall(previous, filter="data")
    previous = previous / "apps/runtime-service/src"
    assert (
        "background_completion_execution"
        not in (previous / "runtime_service/graphs/dearflow_agent.py").read_text()
    )
    spec["config"]["graphs"] = {"dearflow_agent": "fixture.py:production_dear_graph"}
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    (tmp_path / "langgraph.json").write_text(json.dumps(spec["config"]))
    start("runtime", source=previous)
    wait_for(
        lambda: client.get(f"http://127.0.0.1:{spec['runtime_port']}/ready").status_code
        == 200
    )
    start("worker", source=previous)
    thread = new_thread(client)
    old_run = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "old-source-normal"),
    )
    assert terminal(client, thread, old_run["run_id"])["status"] == "success"
    with psycopg.connect(env["DATABASE_URI"]) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM runtime_background_tasks"
            ).fetchone()[0]
            == 3
        )
    evidence.append(
        {
            "previous_source": "HEAD",
            "normal_run": old_run["run_id"],
            "receipts_retained": 3,
        }
    )
    (tmp_path / "background-source-drain-evidence.json").write_text(
        json.dumps(evidence, indent=2)
    )


@pytest.mark.parametrize(
    "stack", [{**BACKGROUND_STACK, "runtime_image": True}], indirect=True
)
def test_release_linux_api_worker_completion_and_shared_storage(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    thread = background_thread(client)
    source = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-short"),
    )
    assert terminal(client, thread, source["run_id"])["status"] == "success"
    row = first_task(client, thread)
    row = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["delivery"]["state"] == "accepted",
    )
    assert terminal(client, thread, row["delivery"]["run_id"])["status"] == "success"
    log = request(
        client, "GET", f"/threads/{thread}/background-tasks/{row['task_id']}/output"
    )
    assert log["text"] == "BACKGROUND_DONE" and row["cleanup_state"] == "confirmed"
    assert list(Path(env["RUNTIME_BACKGROUND_LOG_ROOT"]).rglob("*.log"))
    assert sum(value["event"] == "completion-model" for value in facts(env)) == 1
    (tmp_path / "background-linux-release-evidence.json").write_text(
        json.dumps({"task": row, "output": log}, indent=2)
    )


@pytest.mark.parametrize("stack", [BACKGROUND_STACK], indirect=True)
def test_accepted_completion_revoked_model_is_rejected_before_model_and_acl_is_current(
    stack,
):
    client, spec, env, processes, start, stop, tmp_path = stack
    thread = background_thread(client)
    source = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-drain-short"),
    )
    assert terminal(client, thread, source["run_id"])["status"] == "success"
    stop("worker")
    row = first_task(client, thread)
    accepted = task_when(
        client,
        thread,
        row["task_id"],
        lambda value: value["delivery"]["state"] == "accepted",
    )
    run_id = accepted["delivery"]["run_id"]
    assert (
        request(client, "GET", f"/threads/{thread}/runs/{run_id}")["status"]
        == "pending"
    )
    with sqlite3.connect(spec["database"]) as connection:
        connection.execute(
            "UPDATE runtime_catalog_models SET enabled=0 WHERE id=?",
            (spec["model"].replace("-", ""),),
        )
    start("worker")
    assert terminal(client, thread, run_id)["status"] == "error"
    assert not [value for value in facts(env) if value["event"] == "completion-model"]
    ready = json.loads(Path(spec["ready"]).read_text())
    path = f"/threads/{thread}/background-tasks/{row['task_id']}"
    peer = {"Authorization": "Bearer " + ready["peer_token"]}
    assert client.get(path, headers=peer).status_code == 403
    request(
        client,
        "PUT",
        f"/threads/{thread}/shares",
        json={"user_id": ready["peer_id"], "actions": ["read"]},
    )
    shared = request(client, "GET", path, headers=peer)
    assert shared["allowed_actions"] == ["read", "logs"]
    assert (
        client.post(
            path + "/cancel",
            json={},
            headers={**peer, "Idempotency-Key": "peer-denied"},
        ).status_code
        == 403
    )
    assert (
        client.get(path, headers={"x-project-id": spec["other_project"]}).status_code
        == 403
    )
    request(
        client,
        "PUT",
        f"/threads/{thread}/shares",
        json={"user_id": ready["peer_id"], "actions": []},
    )
    assert client.get(path, headers=peer).status_code == 403
    (tmp_path / "background-revocation-evidence.json").write_text(
        json.dumps(
            {
                "task": accepted,
                "completion_run_id": run_id,
                "model_calls": 0,
                "acl": [
                    "owner",
                    "shared-read",
                    "cancel-denied",
                    "cross-project",
                    "revoked",
                ],
            },
            indent=2,
        )
    )


@pytest.mark.parametrize(
    "stack",
    [
        {
            **BACKGROUND_STACK,
            "real_model": True,
            "graphs": {
                "dearflow_agent": "fixture.py:production_dear_graph",
                "showcase_demo": "fixture.py:production_showcase_graph",
            },
            "env": {
                **BACKGROUND_STACK["env"],
                "RUNTIME_USAGE_ENABLED": "true",
                "AGENT_MODEL_CALL_TIMEOUT_SECONDS": "90",
            },
        }
    ],
    indirect=True,
)
def test_managed_real_models_both_compositions_and_completion_usage(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    pending = []
    prompt = "Use background_execute exactly once with command 'sleep 90; printf REAL_BACKGROUND_DONE' and timeout 120. Immediately after receiving its task_id, give a brief final answer containing that ID. Do not wait, poll, call background_task, or run the command through execute."
    for graph in ("dearflow_agent", "showcase_demo"):
        thread = request(
            client,
            "POST",
            "/threads",
            json={"metadata": {"graph_id": graph, "access_policy": "workspace_write"}},
        )["thread_id"]
        body = run_body(spec, prompt)
        body["assistant_id"] = graph
        body["context"].pop("execution_mode")
        source = request(client, "POST", f"/threads/{thread}/runs", json=body)
        assert terminal(client, thread, source["run_id"])["status"] == "success"
        row = first_task(client, thread)
        assert row["status"] == "running"
        assert (
            len(request(client, "GET", f"/threads/{thread}/background-tasks")["items"])
            == 1
        )
        pending.append((thread, source["run_id"], row["task_id"]))
    evidence = []
    for thread, source_id, task_id in pending:
        row = task_when(
            client,
            thread,
            task_id,
            lambda value: value["delivery"]["state"] == "accepted",
        )
        run_id = row["delivery"]["run_id"]
        assert terminal(client, thread, run_id)["status"] == "success"
        log = request(
            client, "GET", f"/threads/{thread}/background-tasks/{task_id}/output"
        )
        assert log["available"] and log["text"] == "REAL_BACKGROUND_DONE"
        source_usage = request(
            client, "GET", f"/threads/{thread}/runs/{source_id}/usage"
        )
        completion_usage = request(
            client, "GET", f"/threads/{thread}/runs/{run_id}/usage"
        )
        assert source_usage["coverage"]["observed_call_count"] >= 1
        assert completion_usage["coverage"]["observed_call_count"] >= 1
        assert completion_usage["run_id"] == run_id and source_id != run_id
        evidence.append(
            {
                "task": row,
                "source_usage": source_usage,
                "completion_usage": completion_usage,
            }
        )
    (tmp_path / "background-real-model-evidence.json").write_text(
        json.dumps(evidence, indent=2)
    )
