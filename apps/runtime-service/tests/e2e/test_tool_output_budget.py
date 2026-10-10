"""F04 non-browser verification with real HTTP, PG, Redis and Worker."""

import json
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path

import psycopg
import pytest
from fixtures.tool_output_budget import evidence, result_path
from services.dearflow_agent.test_tool_error_platform import (
    facts,
    request,
    wait_for,
)
from services.dearflow_agent.test_tool_error_platform import (
    stack as disposable_stack,
)

stack = disposable_stack

STACK = {
    "fixture": "tool_output_budget.py",
    "env": {
        "RUNTIME_BACKEND": "local",
        "AGENT_CONTEXT_MANAGEMENT_ENABLED": "1",
        "WORKSPACE_TEST_PROBE_FAILURE_FILE": "",
    },
}


def body(spec, graph_id, prompt, *, version="v3"):
    return {
        "assistant_id": graph_id,
        "input": {"messages": [{"role": "user", "content": prompt}]},
        "context": {
            "model_id": spec["model"],
            "max_tokens": 256,
            "execution_mode": "ultra",
        },
        "stream_mode": ["messages", "updates", "values"],
        "stream_subgraphs": True,
        "version": version,
    }


def terminal(client, thread, run):
    def read():
        result = request(client, "GET", f"/threads/{thread}/runs/{run}")
        return result if result["status"] not in {"pending", "running"} else None

    return wait_for(read)


@pytest.mark.parametrize("stack", [STACK], indirect=True)
def test_large_result_http_restart_acl_and_rollback(stack):
    client, spec, env, processes, start, stop, tmp_path = stack
    retained = []
    for graph_id, version in (("dearflow_agent", "v3"), ("showcase_demo", "v2")):
        thread = request(
            client, "POST", "/threads", json={"metadata": {"graph_id": graph_id}}
        )["thread_id"]
        policy = request(
            client,
            "PATCH",
            f"/threads/{thread}/access-policy",
            json={"access_policy": "workspace_write"},
        )
        assert policy["access_policy"] == "workspace_write"
        started = time.monotonic()
        response = client.post(
            f"/threads/{thread}/runs/stream",
            json=body(spec, graph_id, "budget", version=version),
        )
        assert response.is_success, response.text[:1000]
        run = request(client, "GET", f"/threads/{thread}/runs")[0]
        run_id = run.get("run_id", run.get("id"))
        assert terminal(client, thread, run_id)["status"] == "success", (
            run,
            response.text[-3000:],
            facts(env),
        )
        state_response = client.get(f"/threads/{thread}/state")
        assert state_response.is_success, (state_response.text, facts(env))
        state = state_response.json()
        key = result_path("main").removeprefix("/large_tool_results")
        raw = state["values"]["files"][key]["content"]
        assert (
            sha256(raw.encode()).hexdigest()
            == sha256(evidence("main").encode()).hexdigest()
        )
        assert "F04_MIDDLE_main" in str(state["values"]["messages"][-1]["content"])
        history = request(
            client, "POST", f"/threads/{thread}/history", json={"limit": 20}
        )
        assert result_path("main") in json.dumps(history)
        assert result_path("main") in response.text
        assert "F04_MIDDLE_main" in response.text
        ready = json.loads(Path(spec["ready"]).read_text())
        denied = client.get(
            f"/threads/{thread}/state",
            headers={"Authorization": "Bearer " + ready["peer_token"]},
        )
        assert denied.status_code == 403
        with psycopg.connect(env["DATABASE_URI"]) as connection:
            checkpoint_bytes, write_bytes, json_bytes = connection.execute(
                """select
                (select coalesce(sum(octet_length(blob)),0)
                 from checkpoint_blobs where thread_id=%s),
                (select coalesce(sum(octet_length(blob)),0)
                 from checkpoint_writes where thread_id=%s),
                (select coalesce(sum(octet_length(checkpoint::text)
                                    +octet_length(metadata::text)),0)
                 from checkpoints where thread_id=%s)""",
                (thread, thread, thread),
            ).fetchone()
        retained.append(
            {
                "graph_id": graph_id,
                "thread_id": thread,
                "run_id": run_id,
                "version": version,
                "sha256": sha256(raw.encode()).hexdigest(),
                "raw_bytes": len(raw.encode()),
                "state_http_bytes": len(state_response.content),
                "stream_bytes": len(response.content),
                "checkpoint_blob_bytes": checkpoint_bytes,
                "checkpoint_write_bytes": write_bytes,
                "checkpoint_json_bytes": json_bytes,
                "duration_seconds": round(time.monotonic() - started, 2),
            }
        )
        (tmp_path / f"f04-{graph_id}-samples.json").write_text(
            json.dumps(
                {
                    "state": state,
                    "history": history,
                    "stream": response.text,
                },
                indent=2,
            )
        )
        delegated = client.post(
            f"/threads/{thread}/runs/stream",
            json=body(spec, graph_id, "delegate", version=version),
        )
        assert delegated.is_success, delegated.text[:1000]
        child_run = request(client, "GET", f"/threads/{thread}/runs")[0]
        child_run_id = child_run.get("run_id", child_run.get("id"))
        assert terminal(client, thread, child_run_id)["status"] == "success", (
            child_run,
            delegated.text[-3000:],
            facts(env),
        )
        after_child = request(
            client, "GET", f"/threads/{thread}/state", params={"subgraphs": "true"}
        )
        assert after_child["values"]["files"][key]["content"] == raw
        child_key = result_path(
            "child", executed=graph_id == "showcase_demo"
        ).removeprefix("/large_tool_results")
        child_raw = evidence("child") + (
            "\n[Command succeeded with exit code 0]"
            if graph_id == "showcase_demo"
            else ""
        )
        assert after_child["values"]["files"][child_key]["content"] == child_raw
        assert "F04_MIDDLE_child" in delegated.text
        retained[-1]["child_run_id"] = child_run_id
        retained[-1]["child_sha256"] = sha256(child_raw.encode()).hexdigest()
        retained[-1]["child_raw_bytes"] = len(child_raw.encode())
        (tmp_path / f"f04-{graph_id}-child-samples.json").write_text(
            json.dumps({"state": after_child, "stream": delegated.text}, indent=2)
        )

    pending_approvals = []
    for decision in ("approve", "reject"):
        thread = request(
            client,
            "POST",
            "/threads",
            json={"metadata": {"graph_id": "dearflow_agent"}},
        )["thread_id"]
        pending_body = body(spec, "dearflow_agent", "approval")
        response = client.post(f"/threads/{thread}/runs/stream", json=pending_body)
        assert response.is_success
        run = request(client, "GET", f"/threads/{thread}/runs")[0]
        run_id = run.get("run_id", run.get("id"))
        assert terminal(client, thread, run_id)["status"] == "interrupted"
        pending = request(client, "GET", f"/threads/{thread}/state")
        interrupts = pending.get("interrupts") or [
            interrupt
            for task in pending.get("tasks", [])
            for interrupt in task.get("interrupts", [])
        ]
        if isinstance(interrupts, dict):
            interrupts = [
                {"id": key, "value": value.get("value", value)}
                for key, value in interrupts.items()
            ]
        assert len(interrupts) == 1
        pending_approvals.append((decision, thread, interrupts[0]["id"]))

    stop("worker")
    start("worker")
    approvals = []
    for decision, thread, interrupt_id in pending_approvals:
        response = client.post(
            f"/threads/{thread}/runs/stream",
            json={
                "assistant_id": "dearflow_agent",
                "command": {
                    "resume": {interrupt_id: {"decisions": [{"type": decision}]}}
                },
            },
        )
        assert response.is_success
        resumed = request(client, "GET", f"/threads/{thread}/runs")[0]
        resumed_id = resumed.get("run_id", resumed.get("id"))
        assert terminal(client, thread, resumed_id)["status"] == "success", (
            response.text[-3000:],
            facts(env),
        )
        state = request(client, "GET", f"/threads/{thread}/state")
        calls = [m for m in state["values"]["messages"] if m.get("tool_calls")]
        assert calls[0]["tool_calls"][0]["args"]["content"] == evidence("approval")
        workspace = client.get(
            f"/threads/{thread}/workspace/content",
            params={"path": "/workspace/work/approved.txt"},
        )
        if decision == "approve":
            assert workspace.is_success and workspace.content.decode() == evidence(
                "approval"
            )
        else:
            assert not workspace.is_success
        approvals.append(
            {
                "decision": decision,
                "thread_id": thread,
                "run_id": resumed_id,
                "worker_restart": True,
            }
        )

    for item in retained:
        response = client.post(
            f"/threads/{item['thread_id']}/runs/stream",
            json=body(spec, item["graph_id"], "recover"),
        )
        assert response.is_success
        recovered = request(client, "GET", f"/threads/{item['thread_id']}/runs")[0]
        recovered_id = recovered.get("run_id", recovered.get("id"))
        assert terminal(client, item["thread_id"], recovered_id)["status"] == "success"
        assert "F04_RESTORED_main" in response.text
        item["restart_recovery_run_id"] = recovered_id

    env["AGENT_CONTEXT_MANAGEMENT_ENABLED"] = "0"
    stop("worker")
    start("worker")
    for item in retained:
        response = client.post(
            f"/threads/{item['thread_id']}/runs/stream",
            json=body(spec, item["graph_id"], "recover"),
        )
        assert response.is_success
        recovered = request(client, "GET", f"/threads/{item['thread_id']}/runs")[0]
        recovered_id = recovered.get("run_id", recovered.get("id"))
        assert terminal(client, item["thread_id"], recovered_id)["status"] == "success"
        assert "F04_RESTORED_main" in response.text
        item["switch_off_recovery_run_id"] = recovered_id
    assert (
        sum(
            item["event"] == "large-tool" and item.get("label") == "main"
            for item in facts(env)
        )
        == 2
    )
    assert not any(
        item.get("summary") for item in facts(env) if item["event"] == "model-input"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/integration/test_context_offloading_postgres.py",
            "-q",
            "-s",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={**env, "CONTEXT_TEST_CHECKPOINT_DSN": env["DATABASE_URI"]},
        capture_output=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()
    print(result.stdout.decode(), flush=True)
    model_env = env.get("CONTEXT_MODEL_ENV_FILE")
    if model_env:
        live = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/integration/test_context_offloading_model.py",
                "-q",
                "-s",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env={
                **env,
                "CONTEXT_TEST_CHECKPOINT_DSN": env["DATABASE_URI"],
                "CONTEXT_MODEL_ENV_FILE": model_env,
            },
            capture_output=True,
            timeout=600,
        )
        print(live.stdout.decode(), flush=True)
        assert live.returncode == 0, live.stdout.decode() + live.stderr.decode()
    (tmp_path / "f04-http-evidence.json").write_text(
        json.dumps(
            {
                "runs": retained,
                "approvals": approvals,
                "model_inputs": [
                    item for item in facts(env) if item["event"] == "model-input"
                ],
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "evidence_file": str(tmp_path / "f04-http-evidence.json"),
                "runs": retained,
                "worker_restart": True,
                "switch_off_read": True,
            }
        ),
        flush=True,
    )
