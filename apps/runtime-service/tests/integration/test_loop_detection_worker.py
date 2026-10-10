"""Real isolated PostgreSQL/Redis, HTTP provider and production Worker contracts."""

import io
import json
import os
import subprocess
import tarfile
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest
from e2e.test_run_reliability import db_attempts, run_body, terminal
from scripts.verify_execution_budget import notices, transport_samples
from services.dearflow_agent.test_tool_error_platform import facts, request, wait_for
from services.dearflow_agent.test_tool_error_platform import stack as disposable_stack

stack = disposable_stack
STACK = {
    "fixture": "loop_detection.py",
    "provider": True,
    "http_app": True,
    "graphs": {
        "reference_agent": "fixture.py:reference_graph",
        "workflow_demo": "fixture.py:workflow_graph",
    },
    "env": {
        "RUNTIME_BACKEND": "local",
        "AGENT_LOOP_DETECTION_ENABLED": "1",
        "AGENT_MODEL_CALL_LIMIT_PER_RUN": "30",
        "AGENT_MODEL_CALL_LIMIT_PER_THREAD": "300",
        "AGENT_TOOL_CALL_LIMIT_PER_RUN": "50",
        "AGENT_TOOL_CALL_LIMIT_PER_THREAD": "500",
        "GRAPHHARBOR_LEASE_SECONDS": "30",
        "GRAPHHARBOR_REAPER_INTERVAL_SECONDS": "0.5",
        "AGENT_MODEL_CALL_TIMEOUT_SECONDS": "60",
    },
}
pytestmark = pytest.mark.integration


def models(env, prompt):
    return [
        item
        for item in facts(env)
        if item["event"] == "f02-model" and item.get("prompt") == prompt
    ]


def body(spec, prompt, graph="dearflow_agent", **changes):
    value = {
        **run_body(spec, prompt),
        "assistant_id": graph,
        "stream_mode": [
            "messages",
            "updates",
            "tools",
            "values",
            "custom",
            "tasks",
            "debug",
        ],
        **changes,
    }
    if graph in {"reference_agent", "workflow_demo"}:
        value["context"].pop("execution_mode")
        value["context"].pop("access_policy")
    return value


def thread_for(client, graph="dearflow_agent"):
    return request(client, "POST", "/threads", json={"metadata": {"graph_id": graph}})[
        "thread_id"
    ]


def save_evidence(rows, tmp_path):
    target = Path(os.getenv("LOOP_EVIDENCE_PATH", str(tmp_path / "f02-evidence.json")))
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")


@pytest.mark.parametrize("stack", [STACK], indirect=True)
@pytest.mark.parametrize(
    "phase",
    [
        "boundaries",
        "recovery",
        pytest.param(
            "real-model",
            marks=pytest.mark.skipif(
                not os.getenv("LOOP_MODEL_ENV_FILE"),
                reason="LOOP_MODEL_ENV_FILE enables paid read-only model smoke tests",
            ),
        ),
    ],
)
def test_http_loop_boundaries_takeover_security_and_rollback(stack, phase):
    client, spec, env, processes, start, stop, tmp_path = stack
    rows = []

    def inspect(thread, run_id, response, expected, label):
        status = terminal(client, thread, run_id)["status"]
        assert status == expected, (label, status)
        state = request(
            client, "GET", f"/threads/{thread}/state", params={"subgraphs": "true"}
        )
        history = request(
            client, "POST", f"/threads/{thread}/history", json={"limit": 100}
        )
        diag = request(client, "GET", f"/threads/{thread}/runs/{run_id}/diagnostics")
        assert "runtime_loop_state" not in json.dumps(
            [response.text, state, history, diag]
        )
        row = {
            "case": label,
            "thread_id": thread,
            "run_id": run_id,
            "status": status,
            "worker_claims": db_attempts(env, run_id),
            "diagnostics": diag,
            "notices": notices(response.text),
            "transport": transport_samples(response.text),
        }
        rows.append(row)
        save_evidence(rows, tmp_path)
        print(
            json.dumps({key: row[key] for key in ("case", "status", "worker_claims")}),
            flush=True,
        )
        return state, diag, row

    def launch(thread, prompt, graph="dearflow_agent", **changes):
        response = client.post(
            f"/threads/{thread}/runs/stream", json=body(spec, prompt, graph, **changes)
        )
        assert response.is_success, response.text[:1000]
        run_id = request(client, "GET", f"/threads/{thread}/runs")[0]["run_id"]
        return run_id, response

    if phase == "real-model":
        from platform_api.core.context.runtime import DEFAULT_TENANT_ID

        from runtime_service.workspace.scoped import hashed_thread_root

        for scenario, prompt in (
            (
                "research",
                "读取已有 /workspace/work/retained.txt，并给出内容的简短分析。只允许读取。",
            ),
            (
                "pagination",
                "分别调用 read_file 读取 /workspace/work/retained.txt 的 offset=0、1、2，limit=1，汇总看到的内容；不要写入。",
            ),
            (
                "verification",
                "依次读取 /workspace/work/retained.txt 两次以核对内容，汇报两次是否一致；只允许读取，不创建文件。",
            ),
        ):
            thread = thread_for(client)
            workspace = (
                hashed_thread_root(
                    Path(env["RUNTIME_WORKSPACE_ROOT"]) / "dearflow_agent",
                    DEFAULT_TENANT_ID,
                    spec["project"],
                    thread,
                )
                / "workspace/work"
            )
            workspace.mkdir(parents=True)
            original = "\n".join(f"source line {i}" for i in range(8)) + "\n"
            source = workspace / "retained.txt"
            source.write_text(original)
            context = {
                **body(spec, prompt)["context"],
                "model_id": str(uuid5(UUID(spec["model"]), "real")),
                "execution_mode": "flash",
                "access_policy": "review",
                "max_tokens": 2048,
            }
            run_id, response = launch(thread, prompt, context=context)
            state, diag, row = inspect(
                thread, run_id, response, "success", "real-model-" + scenario
            )
            messages = state["values"]["messages"]
            calls = [call for m in messages for call in m.get("tool_calls", [])]
            results = [m for m in messages if m["type"] == "tool"]
            assert not diag["loop_detections"] and messages[-1]["content"]
            assert calls and all(call["name"] == "read_file" for call in calls)
            assert all(
                call["args"]["file_path"] == "/workspace/work/retained.txt"
                for call in calls
            )
            assert len(results) == len(calls) and all(
                m.get("status", "success") == "success" for m in results
            )
            reads = [
                (call["args"].get("offset", 0), call["args"].get("limit", 100))
                for call in calls
            ]
            if scenario == "pagination":
                assert sorted(reads) == [(0, 1), (1, 1), (2, 1)]
            elif scenario == "verification":
                assert len(reads) == 2 and reads[0] == reads[1]
                assert results[0]["content"] == results[1]["content"]
            assert source.read_text() == original
            assert {path.name for path in workspace.iterdir()} == {"retained.txt"}
            row["read_calls"] = [
                {"offset": offset, "limit": limit} for offset, limit in reads
            ]
            row["tool_results"] = ["success"] * len(results)
            row["source_unchanged"] = True
            save_evidence(rows, tmp_path)
        return

    if phase == "boundaries":
        for graph in ("dearflow_agent", "showcase_demo", "reference_agent"):
            thread = thread_for(client, graph)
            before = len(models(env, "f02-loop"))
            response = client.post(
                f"/threads/{thread}/runs/stream", json=body(spec, "f02-loop", graph)
            )
            assert response.is_success, response.text[:1000]
            run_id = request(client, "GET", f"/threads/{thread}/runs")[0]["run_id"]
            state, diag, row = inspect(thread, run_id, response, "error", graph)
            assert len(models(env, "f02-loop")) - before == 5
            assert (
                len([m for m in state["values"]["messages"] if m["type"] == "tool"])
                == 5
            )
            assert [
                n["code"] for n in row["notices"] if n["code"].startswith("tool_loop_")
            ] == ["tool_loop_approaching", "tool_loop_reached"]
            assert [d["repetitions"] for d in diag["loop_detections"]] == [3, 5]
            assert any(
                d["error_code"] == "runtime.loop.detected"
                for d in diag["graph_executions"]
            )
            assert not diag["model_errors"] and row["worker_claims"] == 1
            assert "runtime.loop.detected" in response.text

        thread = thread_for(client)
        run_id, response = launch(thread, "f02-loop-v2", version="v2")
        _, diag, row = inspect(thread, run_id, response, "error", "loop-v2")
        assert len(models(env, "f02-loop-v2")) == 5 and row["worker_claims"] == 1
        assert [d["repetitions"] for d in diag["loop_detections"]] == [3, 5]
        assert len([n for n in row["notices"] if n["unit"] == "tool_rounds"]) == 2

        for prompt in (
            "f02-pages",
            "f02-alternating",
            "f02-changing",
            "f02-warn-finish",
        ):
            thread = thread_for(client)
            response = client.post(
                f"/threads/{thread}/runs/stream", json=body(spec, prompt)
            )
            run_id = request(client, "GET", f"/threads/{thread}/runs")[0]["run_id"]
            _, diag, row = inspect(thread, run_id, response, "success", prompt)
            assert len(models(env, prompt)) == (4 if prompt == "f02-warn-finish" else 7)
            assert len(diag["loop_detections"]) == (
                1 if prompt == "f02-warn-finish" else 0
            )

        for graph in ("dearflow_agent", "showcase_demo"):
            thread = thread_for(client, graph)
            response = client.post(
                f"/threads/{thread}/runs/stream", json=body(spec, "f02-parent", graph)
            )
            run_id = request(client, "GET", f"/threads/{thread}/runs")[0]["run_id"]
            _, diag, row = inspect(thread, run_id, response, "error", graph + "-child")
            assert row["worker_claims"] == 1
            assert any(
                d["scope"] == "subagent" and d["namespace"]
                for d in diag["loop_detections"]
            )

        thread = thread_for(client)
        run_id, response = launch(thread, "f02-parallel")
        _, diag, row = inspect(
            thread, run_id, response, "success", "same-role-parallel"
        )
        assert len(diag["loop_detections"]) == 2
        assert len({tuple(d["namespace"]) for d in diag["loop_detections"]}) == 2
        assert (
            len({n["notice_id"] for n in row["notices"] if n["unit"] == "tool_rounds"})
            == 2
        )

        for decision in ("approve", "edit", "reject"):
            thread = thread_for(client)
            paths_before = set(
                Path(env["RUNTIME_WORKSPACE_ROOT"]).rglob("approved.txt")
            )
            run_id, response = launch(thread, "f02-approval")
            pending, _, _ = inspect(
                thread, run_id, response, "interrupted", "approval-" + decision
            )
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
            assert (
                set(Path(env["RUNTIME_WORKSPACE_ROOT"]).rglob("approved.txt"))
                == paths_before
            )
            edited = {
                "name": "write_file",
                "args": {
                    "file_path": "/workspace/work/approved.txt",
                    "content": "edited",
                },
            }
            choice = {
                "type": decision,
                **({"edited_action": edited} if decision == "edit" else {}),
            }
            response = client.post(
                f"/threads/{thread}/runs/stream",
                json={
                    "assistant_id": "dearflow_agent",
                    "command": {
                        "resume": {interrupts[0]["id"]: {"decisions": [choice]}}
                    },
                },
            )
            assert response.is_success, response.text[:1000]
            resumed_id = request(client, "GET", f"/threads/{thread}/runs")[0]["run_id"]
            assert resumed_id != run_id
            _, diag, _ = inspect(
                thread, resumed_id, response, "success", "resume-" + decision
            )
            assert not diag["loop_detections"]
            paths_after = set(Path(env["RUNTIME_WORKSPACE_ROOT"]).rglob("approved.txt"))
            assert len(paths_after - paths_before) == (0 if decision == "reject" else 1)
            assert all(
                path.read_text() == ("edited" if decision == "edit" else "once")
                for path in paths_after - paths_before
            )

        return

    retained = thread_for(client, "reference_agent")
    run_id, response = launch(retained, "f02-retained-loop", "reference_agent")
    inspect(retained, run_id, response, "error", "rollback-checkpoint")

    for prompt in ("f02-cancel", "f02-inbox"):
        thread = thread_for(client)
        run = request(
            client, "POST", f"/threads/{thread}/runs", json=body(spec, prompt)
        )
        run_id = run["run_id"]
        wait_for(
            lambda prompt=prompt: any(
                item["event"] == "f02-waiting" and item.get("prompt") == prompt
                for item in facts(env)
            )
        )
        if prompt == "f02-cancel":
            request(
                client,
                "POST",
                f"/threads/{thread}/runs/{run_id}/cancel",
                json={"action": "interrupt"},
            )
            expected = "interrupted"
        else:
            message_id = str(uuid4())
            receipt = request(
                client,
                "POST",
                f"/threads/{thread}/messages",
                headers={"Idempotency-Key": message_id},
                json={
                    "client_message_id": message_id,
                    "target_run_id": run_id,
                    "content": "f02-continue",
                },
            )
            assert receipt["status"] in {"queued", "claimed", "consumed"}
            expected = "success"
        Path(env["TOOL_ERROR_TEST_FACTS"] + "." + prompt).write_text("continue")
        terminal(client, thread, run_id)
        response = client.get(
            f"/threads/{thread}/runs/{run_id}/stream", params={"last_event_id": "0"}
        )
        state, diag, row = inspect(thread, run_id, response, expected, prompt)
        assert row["worker_claims"] == 1 and not any(
            d["code"] == "tool_loop_reached" for d in diag["loop_detections"]
        )
        if prompt == "f02-inbox":
            assert len(models(env, "f02-continue")) == 1
            assert any(
                m["content"] == "f02-continue"
                for m in state["values"]["messages"]
                if m["type"] == "human"
            )
            receipts = request(client, "GET", f"/threads/{thread}/messages")
            assert "consumed" in json.dumps(receipts)

    thread = thread_for(client)
    run = request(
        client, "POST", f"/threads/{thread}/runs", json=body(spec, "f02-crash")
    )
    run_id = run["run_id"]
    wait_for(lambda: any(item["event"] == "f02-crash-window" for item in facts(env)))
    processes["worker"].kill()
    processes["worker"].wait(timeout=15)
    stop("worker")
    start("worker")
    assert terminal(client, thread, run_id)["status"] == "error"
    response = client.get(
        f"/threads/{thread}/runs/{run_id}/stream", params={"last_event_id": "0"}
    )
    state, diag, row = inspect(thread, run_id, response, "error", "worker-takeover")
    assert row["worker_claims"] == 2 and len(models(env, "f02-crash")) == 6
    assert len([m for m in state["values"]["messages"] if m["type"] == "tool"]) == 5
    assert [d["repetitions"] for d in diag["loop_detections"]] == [3, 5]

    for payload in (
        {"input": {"runtime_loop_state": {}}},
        {"command": {"update": {"runtime_loop_state": {}}}},
        {"command": {"resume": {"id": {"runtime_loop_state": {}}}}},
    ):
        assert (
            client.post(
                f"/threads/{thread}/runs", json={**body(spec, "normal"), **payload}
            ).status_code
            == 400
        )
    assert (
        client.post(
            f"/threads/{thread}/state", json={"values": {"runtime_loop_state": {}}}
        ).status_code
        == 400
    )
    ready = json.loads(Path(spec["ready"]).read_text())
    for headers in (
        {"Authorization": "Bearer " + ready["peer_token"]},
        {"x-project-id": spec["other_project"]},
    ):
        assert (
            client.get(
                f"/threads/{thread}/runs/{run_id}/diagnostics", headers=headers
            ).status_code
            == 403
        )

    diagnostic_path = f"/threads/{thread}/runs/{run_id}/diagnostics"
    peer = {"Authorization": "Bearer " + ready["peer_token"]}
    request(
        client,
        "PUT",
        f"/threads/{thread}/shares",
        json={"user_id": ready["peer_id"], "actions": ["read"]},
    )
    assert client.get(diagnostic_path, headers=peer).status_code == 200
    request(
        client,
        "PUT",
        f"/threads/{thread}/shares",
        json={"user_id": ready["peer_id"], "actions": []},
    )
    assert client.get(diagnostic_path, headers=peer).status_code == 403

    import psycopg

    with psycopg.connect(env["DATABASE_URI"]) as connection:
        connection.execute(
            "update threads set event_pruned_through=2 where thread_id=%s", (thread,)
        )
    expired = client.post(
        f"/threads/{thread}/stream/events", json={"channels": ["custom"], "since": 1}
    )
    assert (
        expired.status_code == 410
        and expired.json()["error"]["code"] == "cursor_expired"
    )
    assert request(client, "GET", diagnostic_path)["run_id"] == run_id
    assert (
        request(client, "GET", f"/threads/{thread}/runs/{run_id}")["status"] == "error"
    )
    rows.append(
        {
            "case": "security-and-410",
            "private_writes": "denied",
            "shared_read": "passed",
            "revoke": "denied",
            "expired": expired.json(),
        }
    )
    save_evidence(rows, tmp_path)

    openapi = client.get(f"http://127.0.0.1:{spec['platform_port']}/openapi.json")
    assert openapi.is_success
    schemas = openapi.json()["components"]["schemas"]
    assert "loop_detections" in schemas["RunDiagnostics"]["properties"]
    rows.append(
        {
            "case": "openapi",
            "schemas": {
                name: schema
                for name, schema in schemas.items()
                if name in {"RunDiagnostics", "LoopDetectionSummary"}
            },
        }
    )
    save_evidence(rows, tmp_path)

    checkpoints = subprocess.run(
        [
            os.sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "apps/runtime-service/tests/integration/test_loop_detection_checkpoint.py",
        ],
        cwd=Path(__file__).resolve().parents[4],
        env={**env, "LOOP_TEST_CHECKPOINT_DSN": env["DATABASE_URI"]},
        capture_output=True,
        timeout=240,
    )
    (tmp_path / "compaction.log").write_bytes(checkpoints.stdout + checkpoints.stderr)
    assert checkpoints.returncode == 0, checkpoints.stdout.decode(errors="replace")[
        -7000:
    ]
    assert b"1 passed" in checkpoints.stdout and b"skipped" not in checkpoints.stdout
    rows.append({"case": "automatic-and-manual-compaction", "result": "passed"})
    save_evidence(rows, tmp_path)

    stop("worker")
    env["AGENT_LOOP_DETECTION_ENABLED"] = "0"
    start("worker")
    response = client.post(
        f"/threads/{retained}/runs/stream",
        json=body(spec, "f02-disabled", "reference_agent"),
    )
    run_id = request(client, "GET", f"/threads/{retained}/runs")[0]["run_id"]
    state, diag, row = inspect(
        retained, run_id, response, "success", "disabled-new-run"
    )
    assert not diag["loop_detections"]
    assert len(models(env, "f02-disabled")) == 7
    assert len([m for m in state["values"]["messages"] if m["type"] == "tool"]) == 11
    messages = state["values"]["messages"]
    stop("worker")
    repo = Path(__file__).resolve().parents[4]
    archive = subprocess.run(
        ["git", "archive", "HEAD", "apps/runtime-service/src"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    old = tmp_path / "old"
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(old, filter="data")
    start("worker", old / "apps/runtime-service/src")
    assert (
        request(client, "GET", f"/threads/{retained}/state")["values"]["messages"]
        == messages
    )
    run_id, response = launch(retained, "old-normal", "reference_agent")
    inspect(retained, run_id, response, "success", "old-code-checkpoint")
    stop("worker")
    env["AGENT_LOOP_DETECTION_ENABLED"] = "1"
    start("worker")
    run_id, response = launch(retained, "f02-loop-new-run", "reference_agent")
    _, diag, _ = inspect(retained, run_id, response, "error", "reenabled-new-run")
    assert (
        len(models(env, "f02-loop-new-run")) == 5 and len(diag["loop_detections"]) == 2
    )
