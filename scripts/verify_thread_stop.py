"""Real HTTP/API/Runtime/Worker stop acceptance using disposable native PG/Redis.

Run inside GraphHarbor's run_isolated_tests.py with Runtime Python and both
service src paths in PYTHONPATH. Uses no active database or model credentials.
"""

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[1]
SECRET = "disposable-stop-verification-secret-at-least-32-bytes"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(check, *, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (httpx.HTTPError, OSError, ValueError):
            pass
        time.sleep(0.1)
    raise AssertionError("Stop acceptance condition timed out")


def main():
    assert os.environ.get("DATABASE_URI", "").endswith(
        "/graphharbor_event_retention_verify"
    )
    from langgraph_runtime_pg.migrate import upgrade_head
    from runtime_service.db import upgrade as runtime_upgrade
    from runtime_service.workspace.scoped import hashed_thread_root

    upgrade_head()
    runtime_upgrade()
    evidence = {"version": 2, "cases": {}, "samples": {}, "docker": {}}
    docker_ready = False
    if shutil.which("docker"):
        try:
            docker_ready = (
                subprocess.run(
                    ["docker", "info"], capture_output=True, timeout=10, check=False
                ).returncode
                == 0
            )
        except subprocess.TimeoutExpired:
            pass
    if not docker_ready:
        evidence["cases"]["docker_execute"] = "blocked: Docker daemon unavailable"
    with tempfile.TemporaryDirectory(prefix="stop-acceptance-") as directory:
        base = Path(directory)
        spec = {
            "runtime_port": free_port(),
            "platform_port": free_port(),
            "secret": SECRET,
            "database": str(base / "platform.db"),
            "ready": str(base / "ready.json"),
            **{key: str(uuid4()) for key in ("tenant", "project", "model")},
        }
        spec["runtime_url"] = f"http://127.0.0.1:{spec['runtime_port']}"
        fixture = ROOT / "apps/runtime-service/tests/fixtures/run_control_platform.py"
        graph_source = base / fixture.name
        shutil.copy2(fixture, graph_source)
        spec["config"] = {
            "graphs": {
                name: str(graph_source) + ":" + name
                for name in (
                    "reference_agent",
                    "workflow_demo",
                    "showcase_demo",
                    "dearflow_agent",
                )
            },
            "auth": {"path": str(graph_source) + ":auth"},
            "http": {
                "app": str(graph_source) + ":app",
                "disable_mcp": True,
            },
        }
        spec_path = base / "spec.json"
        spec_path.write_text(json.dumps(spec))
        (base / "langgraph.json").write_text(json.dumps(spec["config"]))
        platform_url = f"http://127.0.0.1:{spec['platform_port']}"
        env = {
            **os.environ,
            "LANGFUSE_ENABLED": "false",
            "OTEL_SDK_DISABLED": "true",
            "GRAPHHARBOR_ENV": "production",
            "LG_RUNTIME_PG_AUTO_MIGRATE": "false",
            "RUNTIME_SELF_URL": spec["runtime_url"],
            "PLATFORM_THREAD_AUTHORIZATION_URL": platform_url
            + "/api/runtime/internal/thread-authorization",
            "PLATFORM_RUNTIME_MODEL_CONFIG_URL": platform_url
            + "/api/runtime/internal/model-config",
            "PLATFORM_RUNTIME_MESSAGE_AUTH_URL": platform_url
            + "/api/runtime/internal/message-authorization",
            "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
            "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
            "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
            "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": SECRET,
            "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER": "graphharbor",
            "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE": "graphharbor-worker",
            "RUNTIME_WORKSPACE_ROOT": str(base / "workspaces"),
            "RUNTIME_SHOWCASE_WORKSPACE_ROOT": str(base / "showcase"),
            "RUNTIME_DEAR_GOVERNANCE_ENABLED": "0",
            "RUNTIME_BACKEND": "docker" if docker_ready else "local",
            "RUNTIME_SHOWCASE_IMAGE": "runtime-agent-workspace:p5",
            "RUNTIME_WORKSPACE_IMAGE": "runtime-agent-workspace:p5",
            "TAVILY_API_KEY": "synthetic",
            "STOP_PROBE_FACTS": str(base / "facts.jsonl"),
        }
        env["PYTHONPATH"] = os.pathsep.join(
            [
                str(fixture.parent),
                str(ROOT / "apps/runtime-service/tests"),
                env.get("PYTHONPATH", ""),
            ]
        )
        processes, logs = {}, []
        owned_containers = set()

        def container_for(workspace):
            identifiers = subprocess.check_output(
                ["docker", "ps", "-q", "--filter", "name=runtime-"], text=True
            ).split()
            if not identifiers:
                return None
            containers = json.loads(
                subprocess.check_output(["docker", "inspect", *identifiers], text=True)
            )
            return next(
                (
                    c
                    for c in containers
                    if c["State"]["Running"]
                    and any(
                        Path(m["Source"]).resolve() == workspace
                        for m in c["Mounts"]
                        if m["Type"] == "bind"
                    )
                ),
                None,
            )

        def start(role):
            log = (base / (role + "-" + str(len(logs)) + ".log")).open("w")
            logs.append(log)
            interpreter = (
                os.getenv("PLATFORM_API_TEST_PYTHON", sys.executable)
                if role == "platform"
                else sys.executable
            )
            processes[role] = subprocess.Popen(
                [interpreter, str(fixture), role, str(spec_path)],
                env=env,
                stdout=log,
                stderr=log,
            )

        def stop(role):
            process = processes.pop(role, None)
            if process:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)

        def facts():
            path = Path(env["STOP_PROBE_FACTS"])
            return (
                [json.loads(line) for line in path.read_text().splitlines()]
                if path.exists()
                else []
            )

        try:
            start("runtime")
            start("platform")
            wait_for(lambda: (base / "ready.json").exists())
            wait_for(
                lambda: (
                    httpx.get(platform_url + "/_system/health", timeout=1).is_success
                )
            )
            wait_for(
                lambda: httpx.get(spec["runtime_url"] + "/ok", timeout=1).is_success
            )
            ready = json.loads((base / "ready.json").read_text())
            headers = {
                "x-project-id": spec["project"],
                "Authorization": "Bearer " + ready["token"],
            }
            with httpx.Client(
                base_url=platform_url + "/api/langgraph",
                headers=headers,
                timeout=20,
                trust_env=False,
            ) as client:

                def request(method, path, status=200, **kwargs):
                    response = client.request(method, path, **kwargs)
                    assert response.status_code == status, (
                        response.status_code,
                        response.text[:500],
                    )
                    return response.json()

                def create(
                    graph="reference_agent",
                    prompt="slow",
                    *,
                    thread=None,
                    policy="full_access",
                ):
                    if thread is None:
                        thread = request(
                            "POST",
                            "/threads",
                            json={
                                "metadata": {"graph_id": graph, "access_policy": policy}
                            },
                        )["thread_id"]
                    run = request(
                        "POST",
                        f"/threads/{thread}/runs",
                        json={
                            "assistant_id": graph,
                            "context": {
                                "model_id": spec["model"],
                                "execution_mode": "ultra"
                                if prompt == "parallel"
                                else "standard",
                            },
                            "multitask_strategy": "enqueue",
                            "input": {
                                "messages": [{"role": "user", "content": prompt}]
                            },
                        },
                    )["run_id"]
                    return thread, run

                def cancel(thread, key=None):
                    return request(
                        "POST",
                        f"/threads/{thread}/cancel",
                        202,
                        json={},
                        headers={"Idempotency-Key": key or uuid4().hex},
                    )

                def confirmed(thread, stop_id):
                    item = request("GET", f"/threads/{thread}/stop-requests/{stop_id}")
                    return (
                        item
                        if item["phase"] in {"stopped", "no_active_run", "rejected"}
                        else None
                    )

                def case(name, result=None):
                    evidence["cases"][name] = "passed"
                    if result is not None:
                        evidence["samples"][name] = result
                    print("passed: " + name, flush=True)

                # Pending cancellation survives a Runtime restart and never creates a Run.
                thread, run = create()
                accepted = cancel(thread, "restart")
                stop("runtime")
                start("runtime")
                wait_for(
                    lambda: httpx.get(spec["runtime_url"] + "/ok", timeout=1).is_success
                )
                result = wait_for(lambda: confirmed(thread, accepted["stop_id"]))
                assert (
                    result["execution_stopped"] is True and result["target_count"] == 1
                )
                assert cancel(thread, "restart")["stop_id"] == accepted["stop_id"]
                evidence["cases"]["pending_restart_and_retry"] = "passed"
                print("passed: pending_restart_and_retry", flush=True)
                evidence["samples"]["pending"] = result
                # Exercise the real reconciler past its single HTTP wait budget.
                thread, run = create("workflow_demo", "complete")
                with psycopg.connect(os.environ["POSTGRES_URI"]) as connection:
                    connection.execute(
                        """INSERT INTO runs(run_id,thread_id,assistant_id,status,metadata,kwargs,multitask_strategy,queue_position)
                        SELECT gen_random_uuid(),thread_id,assistant_id,'pending',metadata,kwargs,'enqueue',queue_position+n
                        FROM runs CROSS JOIN generate_series(1,499) AS n WHERE run_id=%s""",
                        (run,),
                    )
                item = cancel(thread, "capacity-500")
                result = wait_for(
                    lambda: confirmed(thread, item["stop_id"]), timeout=180
                )
                assert (
                    result["target_count"] == 500
                    and result["queue"]["pending_cancelled_count"] == 500
                ), result
                assert (
                    result["execution_stopped"] is True
                    and result["report"]["truncated"] is True
                )
                case("capacity_500_background_recovery", result)
                # Actual Worker cancellation for async tools, model awaits and parallel agents.
                start("worker")
                for graph, prompt, event in (
                    ("reference_agent", "slow", "tool_started"),
                    ("reference_agent", "slow-model", "model_started"),
                    ("workflow_demo", "slow", "tool_started"),
                    ("dearflow_agent", "slow", "tool_started"),
                    ("showcase_demo", "parallel", "child_started"),
                    ("dearflow_agent", "parallel", "child_started"),
                    ("showcase_demo", "execute", None),
                    ("dearflow_agent", "execute", None),
                ):
                    before = len(facts())
                    thread, run = create(graph, prompt)
                    if event:

                        def started(
                            thread=thread,
                            run=run,
                            event=event,
                            graph=graph,
                            before=before,
                            prompt=prompt,
                        ):
                            current = request("GET", f"/threads/{thread}/runs/{run}")
                            assert current["status"] not in {
                                "error",
                                "success",
                                "timeout",
                            }, current
                            return sum(
                                f["event"] == event and f.get("graph_id") == graph
                                for f in facts()[before:]
                            ) >= (2 if prompt == "parallel" else 1)

                        wait_for(started)
                    else:
                        workspace = (
                            hashed_thread_root(
                                base / "showcase"
                                if graph == "showcase_demo"
                                else base / "workspaces" / graph,
                                ready["runtime_tenant"],
                                spec["project"],
                                thread,
                            )
                            / "workspace"
                        )
                        command_root = (
                            workspace
                            if graph == "showcase_demo"
                            else workspace / "work"
                        )

                        def resource_started(
                            run=run, thread=thread, command_root=command_root
                        ):
                            current = request("GET", f"/threads/{thread}/runs/{run}")
                            assert current["status"] not in {
                                "error",
                                "success",
                                "timeout",
                            }, current
                            with psycopg.connect(
                                os.environ["POSTGRES_URI"]
                            ) as connection:
                                row = connection.execute(
                                    "SELECT status FROM runtime_run_resources WHERE run_id=%s",
                                    (run,),
                                ).fetchone()
                            return (
                                row == ("active",)
                                and (command_root / "stop-probe-started.txt").is_file()
                            )

                        wait_for(resource_started)
                        if docker_ready:
                            container = wait_for(
                                lambda workspace=workspace: container_for(workspace)
                            )
                            owned_containers.add(container["Id"])
                            assert not (
                                command_root / "stop-probe-delayed.txt"
                            ).exists()
                    queued = []
                    if graph == "reference_agent" and prompt == "slow":
                        queued = [
                            create(graph, "complete", thread=thread)[1]
                            for _ in range(2)
                        ]
                        for i in range(2):
                            request(
                                "POST",
                                f"/threads/{thread}/messages",
                                202,
                                json={
                                    "target_run_id": run,
                                    "client_message_id": str(uuid4()),
                                    "content": "queued-stop-probe-" + str(i),
                                },
                                headers={"Idempotency-Key": uuid4().hex},
                            )
                    key = graph + "-" + prompt
                    item = cancel(thread, key)
                    result = wait_for(
                        lambda thread=thread, item=item: confirmed(
                            thread, item["stop_id"]
                        )
                    )
                    assert (
                        result["phase"] == "stopped"
                        and result["execution_stopped"] is True
                    ), result
                    assert result["resource_cleanup"] in {"confirmed", "not_required"}
                    if prompt == "execute" and docker_ready:
                        assert result["resource_cleanup"] == "confirmed", result
                        with psycopg.connect(os.environ["POSTGRES_URI"]) as connection:
                            resources = connection.execute(
                                "SELECT kind,status FROM runtime_run_resources WHERE run_id=%s",
                                (run,),
                            ).fetchall()
                        assert resources == [("docker_execute", "cleanup_confirmed")]
                        inspection = subprocess.run(
                            ["docker", "inspect", container["Id"]],
                            capture_output=True,
                            text=True,
                            timeout=10,
                            check=False,
                        )
                        assert (
                            inspection.returncode != 0
                            and "No such" in inspection.stderr
                        )
                        time.sleep(8)
                        assert not (command_root / "stop-probe-delayed.txt").exists()
                        evidence["docker"][graph] = {
                            "container_id": container["Id"],
                            "image_id": container["Image"],
                            "running_before_cancel": container["State"]["Running"],
                            "command_started": True,
                            "removed_after_cancel": True,
                            "cleanup_receipt": resources[0][1],
                            "delayed_write_absent_after_seconds": 8,
                        }
                    with psycopg.connect(os.environ["POSTGRES_URI"]) as connection:
                        assert connection.execute(
                            "SELECT lease_owner FROM runs WHERE run_id=%s", (run,)
                        ).fetchone() == (None,)
                    evidence["cases"][graph + "_" + prompt] = "passed"
                    print("passed: " + graph + "_" + prompt, flush=True)
                    evidence["samples"][graph + "_" + prompt] = result
                    if queued:
                        assert (
                            result["target_count"] == 3
                            and result["queue"]["pending_cancelled_count"] == 2
                        ), result
                        assert result["queue"]["inbox_not_consumed_count"] == 2, result
                        with psycopg.connect(os.environ["POSTGRES_URI"]) as connection:
                            rows = connection.execute(
                                "SELECT status,reason FROM runtime_message_inbox WHERE thread_id=%s",
                                (thread,),
                            ).fetchall()
                            assert rows == [("not_consumed", "user_stopped")] * 2, rows
                        case("fifo_and_inbox", result)
                    if event:
                        expected = {
                            "tool_started": "tool_exited",
                            "model_started": "model_exited",
                            "child_started": "child_exited",
                        }[event]
                        assert sum(
                            f["event"] == expected and f.get("graph_id") == graph
                            for f in facts()
                        ) >= (2 if prompt == "parallel" else 1)

                # No active Run, stale response and pagination recover through public reads.
                old_id = item["stop_id"]
                _, new_run = create("showcase_demo", "complete", thread=thread)
                assert cancel(thread, key)["stop_id"] == old_id
                wait_for(
                    lambda: (
                        request("GET", f"/threads/{thread}/runs/{new_run}")["status"]
                        == "success"
                    )
                )
                case("later_run_survives_old_stop")
                empty_thread = request(
                    "POST",
                    "/threads",
                    json={"metadata": {"graph_id": "reference_agent"}},
                )["thread_id"]
                first = cancel(empty_thread, "lost-response")
                second = cancel(empty_thread, "lost-response")
                assert first["stop_id"] == second["stop_id"]
                result = wait_for(lambda: confirmed(empty_thread, first["stop_id"]))
                assert (
                    result["phase"] == "no_active_run" and result["target_count"] == 0
                ), result
                cancel(empty_thread, "another-action")
                page = request("GET", f"/threads/{empty_thread}/stop-requests?limit=1")
                assert len(page["items"]) == 1 and page["next_cursor"]
                tail = request(
                    "GET",
                    f"/threads/{empty_thread}/stop-requests",
                    params={"limit": 1, "cursor": page["next_cursor"]},
                )
                assert tail["items"][0]["stop_id"] == first["stop_id"]
                request(
                    "GET", f"/threads/{empty_thread}/stop-requests?cursor=invalid", 422
                )
                request(
                    "POST",
                    f"/threads/{empty_thread}/cancel",
                    422,
                    json={"run_ids": [new_run]},
                    headers={"Idempotency-Key": "invalid"},
                )
                request("GET", f"/threads/{empty_thread}/stop-requests/{uuid4()}", 404)
                case("unknown_submission_pagination_and_input", result)

                thread, run = create("dearflow_agent", "approval", policy="review")
                wait_for(
                    lambda: (
                        request("GET", f"/threads/{thread}/runs/{run}")["status"]
                        == "interrupted"
                    )
                )
                item = cancel(thread)
                result = wait_for(lambda: confirmed(thread, item["stop_id"]))
                assert (
                    result["phase"] == "no_active_run"
                    and result["has_pending_interrupts"] is True
                ), result
                state = request("GET", f"/threads/{thread}/state")
                assert state["interrupts"], state
                case("hitl_preserved", result)
                interrupt_id = (
                    next(iter(state["interrupts"]))
                    if isinstance(state["interrupts"], dict)
                    else state["interrupts"][0]["id"]
                )
                resumed = request(
                    "POST",
                    f"/threads/{thread}/runs",
                    json={
                        "assistant_id": "dearflow_agent",
                        "command": {
                            "resume": {
                                interrupt_id: {"decisions": [{"type": "approve"}]}
                            }
                        },
                    },
                )
                wait_for(
                    lambda: (
                        request("GET", f"/threads/{thread}/runs/{resumed['run_id']}")[
                            "status"
                        ]
                        == "success"
                    )
                )
                assert request("GET", f"/threads/{thread}/state")["interrupts"] == []
                case("explicit_hitl_resume")

                # Revoke edit after the engine accepted the intent; cleanup still settles.
                before = len(facts())
                thread, run = create("dearflow_agent", "slow")
                wait_for(
                    lambda: any(f["event"] == "tool_started" for f in facts()[before:])
                )
                item = cancel(thread, "accepted-before-revoke")

                def stored():
                    with psycopg.connect(
                        os.environ["POSTGRES_URI"], row_factory=psycopg.rows.dict_row
                    ) as connection:
                        return connection.execute(
                            "SELECT * FROM runtime_stop_requests WHERE stop_id=%s",
                            (item["stop_id"],),
                        ).fetchone()

                wait_for(lambda: stored()["engine_receipt"])
                with sqlite3.connect(spec["database"]) as connection:
                    owner = connection.execute(
                        "SELECT owner_user_id FROM thread_access WHERE thread_id=?",
                        (thread,),
                    ).fetchone()[0]
                    connection.execute(
                        "UPDATE thread_access SET owner_user_id=NULL, shared_actions=? WHERE thread_id=?",
                        (json.dumps({owner: ["read"]}), thread),
                    )
                request(
                    "POST",
                    f"/threads/{thread}/cancel",
                    403,
                    json={},
                    headers={"Idempotency-Key": "revoked-new-action"},
                )
                # Remove read as well; a public query cannot reuse the prior delegation.
                with sqlite3.connect(spec["database"]) as connection:
                    member = connection.execute(
                        "SELECT * FROM project_members"
                    ).fetchone()
                    columns = [
                        r[1]
                        for r in connection.execute(
                            "PRAGMA table_info(project_members)"
                        )
                    ]
                    connection.execute("DELETE FROM project_members")
                request(
                    "GET", f"/threads/{thread}/stop-requests/{item['stop_id']}", 403
                )

                def audited_stop():
                    item = stored()
                    return (
                        item
                        if item["phase"] == "stopped" and not item["audit_pending"]
                        else None
                    )

                settled = wait_for(audited_stop)
                assert (
                    settled["engine_receipt"]["execution_stopped"] is True
                    and settled["audit_pending"] == []
                )
                with sqlite3.connect(spec["database"]) as connection:
                    connection.execute(
                        "INSERT INTO project_members ("
                        + ",".join(columns)
                        + ") VALUES ("
                        + ",".join("?" for _ in columns)
                        + ")",
                        member,
                    )
                    connection.execute(
                        "UPDATE thread_access SET owner_user_id=?, shared_actions='{}' WHERE thread_id=?",
                        (owner, thread),
                    )
                    phases = connection.execute(
                        "SELECT action,metadata_json FROM audit_logs WHERE target_id=?",
                        (item["stop_id"],),
                    ).fetchall()
                assert any(
                    action == "runtime.thread.stop.confirmed" for action, _ in phases
                ), phases
                case(
                    "accepted_cleanup_survives_acl_revocation",
                    request(
                        "GET", f"/threads/{thread}/stop-requests/{item['stop_id']}"
                    ),
                )
                evidence["complete"] = True
                output = os.environ.get("STOP_PROBE_OUTPUT")
                if output:
                    Path(output).write_text(json.dumps(evidence, indent=2))
                print(json.dumps({k: v for k, v in evidence.items() if k != "samples"}))
        except BaseException:
            for log in logs:
                log.flush()
                print(Path(log.name).read_text()[-3000:], file=sys.stderr)
            print(json.dumps(facts()[-20:]), file=sys.stderr)
            raise
        finally:
            if os.getenv("STOP_PROBE_OUTPUT"):
                Path(os.environ["STOP_PROBE_OUTPUT"]).write_text(
                    json.dumps(evidence, indent=2)
                )
            for role in list(processes):
                stop(role)
            for identifier in owned_containers:
                subprocess.run(
                    ["docker", "rm", "-f", identifier],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    check=False,
                )
            for log in logs:
                log.close()


if __name__ == "__main__":
    main()
