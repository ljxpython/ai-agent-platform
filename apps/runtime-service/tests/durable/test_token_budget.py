"""Actual isolated PG/Redis/API/Worker verification, reusing the service fixture."""

import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from services.dearflow_agent.test_tool_error_platform import (
    facts,
    protocol_replay,
    request,
    stack,  # noqa: F401 - shared pytest fixture
    wait_for,
)

OPTIONS = {
    "fixture": "token_budget_platform.py",
    "provider": True,
    "startup_timeout": 600,
    "graphs": {
        "dearflow_agent": "fixture.py:graph",
        "showcase_demo": "fixture.py:showcase_graph",
        "reference_agent": "fixture.py:reference_graph",
        "workflow_demo": "fixture.py:workflow_graph",
    },
    "env": {
        "RUNTIME_BACKEND": "local",
        "RUNTIME_USAGE_ENABLED": "true",
        "RUNTIME_TOKEN_BUDGET_ENABLED": "true",
        "RUNTIME_TOKEN_BUDGET_MAX_TOKENS": "10",
        "TOKEN_PROVIDER_HTTP": "1",
        "GRAPHHARBOR_LEASE_SECONDS": "60",
        "GRAPHHARBOR_RUN_TIMEOUT_SECONDS": "300",
    },
}


@pytest.mark.parametrize("stack", [OPTIONS], indirect=True)
def test_real_worker_token_budget_and_platform_chain(stack, monkeypatch):  # noqa: F811 - fixture
    client, spec, env, processes, start, stop, tmp_path = stack
    from runtime_service.db import upgrade
    from runtime_service.db.repositories import usage as repo

    monkeypatch.setenv("DATABASE_URI", env["DATABASE_URI"])
    upgrade()
    upgrade()
    evidence = {
        "complete": False,
        "provider": "controlled_http_provider",
        "cases": {},
        "samples": {},
    }

    def create(prompt, graph="reference_agent", thread=None):
        before = len([f for f in facts(env) if f["event"] == "model"])
        thread = (
            thread
            or request(
                client, "POST", "/threads", json={"metadata": {"graph_id": graph}}
            )["thread_id"]
        )
        response = client.post(
            f"/threads/{thread}/runs/stream",
            json={
                "assistant_id": graph,
                "version": "v3",
                "stream_subgraphs": True,
                "stream_mode": ["custom", "values", "tasks", "tools"],
                "input": {"messages": [{"role": "user", "content": prompt}]},
                "context": {
                    "model_id": spec["model"],
                    **({"execution_mode": "ultra"} if prompt == "child" else {}),
                },
            },
        )
        assert response.status_code == 200, response.text[-1000:]
        run = request(client, "GET", f"/threads/{thread}/runs")[0]
        run_id = run.get("run_id") or run.get("id")
        usage = request(client, "GET", f"/threads/{thread}/runs/{run_id}/usage")
        assert usage["run_id"] == run_id
        with psycopg.connect(env["DATABASE_URI"]) as conn:
            row = conn.execute(
                "SELECT status,retry_count,reason FROM runs WHERE run_id=%s", (run_id,)
            ).fetchone()
        assert row[1] == 1, row
        after = len([f for f in facts(env) if f["event"] == "model"])
        if env["RUNTIME_TOKEN_BUDGET_ENABLED"] == "true" and prompt in {
            "normal",
            "cap-tool",
            "unknown-tool",
            "cap-final",
        }:
            assert after - before == 1, (prompt, after - before)
        return thread, run_id, run, usage, response.text

    for graph in OPTIONS["graphs"]:
        for prompt, status, stop_code in (
            ("normal", "success", None),
            ("cap-tool", "error", "token_budget_exhausted"),
            ("unknown-tool", "error", "token_budget_unverifiable"),
            ("cap-final", "success", None),
        ):
            _, _, run, usage, stream = create(prompt, graph)
            assert run["status"] == status, run
            assert usage["token_budget"]["stop_code"] == stop_code, usage
            assert usage["token_budget"]["max_tokens"] == 10
            if stop_code:
                assert "runtime_" + stop_code in stream, stream[-2000:]
            assert "SECRET_CANARY" not in stream
            key = graph + ":" + prompt
            evidence["cases"][key] = "passed"
            evidence["samples"][key] = usage
    _, _, run, usage, stream = create("warning")
    assert run["status"] == "success" and "token_budget_approaching" in stream
    evidence["cases"]["warning"] = "passed"
    evidence["samples"]["warning"] = usage
    for graph in ("dearflow_agent", "showcase_demo"):
        _, _, run, usage, stream = create("child", graph)
        assert (
            run["status"] == "error"
            and usage["token_budget"]["known_used_tokens"] == 14
        ), usage
        assert usage["token_budget"]["stop_code"] == "token_budget_exhausted", usage
        evidence["cases"]["shared_child_" + graph] = "passed"

    # A new native Run in the same Thread receives a new cap.
    old = evidence["samples"]["reference_agent:cap-final"]
    _, _, run, usage, _ = create("normal", thread=old["thread_id"])
    assert (
        run["status"] == "success" and usage["token_budget"]["known_used_tokens"] == 4
    )
    evidence["cases"]["new_run_same_thread"] = "passed"

    thread = request(
        client, "POST", "/threads", json={"metadata": {"graph_id": "workflow_demo"}}
    )["thread_id"]
    response = client.post(
        f"/threads/{thread}/runs/stream",
        json={
            "assistant_id": "workflow_demo",
            "input": {
                "messages": [{"role": "user", "content": "normal"}],
                "requires_confirmation": True,
            },
            "context": {"model_id": spec["model"]},
        },
    )
    assert response.status_code == 200
    assert (
        request(client, "GET", f"/threads/{thread}/runs")[0]["status"] == "interrupted"
    )
    state = request(client, "GET", f"/threads/{thread}/state")
    interrupts = state.get("interrupts") or [
        i for task in state.get("tasks", []) for i in task.get("interrupts", [])
    ]
    if isinstance(interrupts, dict):
        interrupts = [{"id": key} for key in interrupts]
    assert len(interrupts) == 1
    response = client.post(
        f"/threads/{thread}/runs/stream",
        json={
            "assistant_id": "workflow_demo",
            "command": {
                "resume": {interrupts[0]["id"]: {"decisions": [{"type": "approve"}]}}
            },
        },
    )
    assert response.status_code == 200, response.text
    assert request(client, "GET", f"/threads/{thread}/runs")[0]["status"] == "success"
    evidence["cases"]["hitl_interrupt_id_and_explicit_resume"] = "passed"

    target = evidence["samples"]["reference_agent:cap-tool"]
    frames = protocol_replay(client, target["thread_id"])
    assert "runtime_token_budget_exhausted" in json.dumps(frames)
    evidence["cases"]["protocol_replay_safe_error"] = "passed"
    path = f"/threads/{target['thread_id']}/runs/{target['run_id']}/usage"
    assert client.get(
        path, headers={"x-project-id": spec["other_project"]}
    ).status_code in (403, 404)
    ready = json.loads(Path(spec["ready"]).read_text())
    peer_auth = {"Authorization": "Bearer " + ready["peer_token"]}
    assert client.get(path, headers=peer_auth).status_code == 403
    assert (
        client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401
    )
    evidence["cases"]["cross_project_peer_and_invalid_auth"] = "passed"
    import sqlite3

    with sqlite3.connect(spec["database"]) as connection:
        removed = connection.execute(
            "DELETE FROM project_members WHERE user_id=? AND project_id=?",
            (ready["peer_id"].replace("-", ""), spec["project"].replace("-", "")),
        )
        assert removed.rowcount == 1
    assert (
        client.get(
            f"/threads/{target['thread_id']}/usage", headers=peer_auth
        ).status_code
        == 403
    )
    evidence["cases"]["revoked_membership_usage_read"] = "passed"

    identity = {
        "tenant_id": "token-tests",
        "project_id": str(uuid4()),
        "graph_id": "reference_agent",
        "thread_id": str(uuid4()),
        "run_id": str(uuid4()),
    }
    policy = {"version": 1, "max_tokens": 10, "warn_at_tokens": 8}
    repo.begin_collection(identity, policy)
    repo.begin_collection(identity, {**policy, "max_tokens": 100, "warn_at_tokens": 80})
    assert repo.read_budget(identity)["policy"] == policy
    repo.finish_collection(identity, False, "token_budget_exhausted")
    repo.finish_collection(identity, False)
    assert repo.read_budget(identity)["stop_code"] == "token_budget_exhausted"
    evidence["cases"]["frozen_policy_and_retained_stop"] = "passed"

    for shape in (
        {"input": {"token_budget": {"max_tokens": 10000}}},
        {"context": {"token_budget": {"max_tokens": 10000}}},
    ):
        thread = request(
            client,
            "POST",
            "/threads",
            json={"metadata": {"graph_id": "reference_agent"}},
        )["thread_id"]
        response = client.post(
            f"/threads/{thread}/runs", json={"assistant_id": "reference_agent", **shape}
        )
        assert response.status_code == 400, response.text
    evidence["cases"]["private_budget_injection"] = "passed"

    # Kill only the disposable Worker and let a new Worker claim the same native Run.
    for stale in (False, True):
        release = tmp_path / ("release-unknown" if stale else "release-known")
        stop("worker")
        env["TOKEN_RELEASE_FILE"] = str(release)
        env["RUNTIME_TOKEN_BUDGET_MAX_TOKENS"] = "10"
        start("worker")
        thread = request(
            client,
            "POST",
            "/threads",
            json={"metadata": {"graph_id": "reference_agent"}},
        )["thread_id"]
        created = request(
            client,
            "POST",
            f"/threads/{thread}/runs",
            json={
                "assistant_id": "reference_agent",
                "input": {"messages": [{"role": "user", "content": "resume-worker"}]},
                "context": {"model_id": spec["model"]},
            },
        )
        run_id = created.get("run_id") or created["id"]
        wait_for(
            lambda run_id=run_id: any(
                f["event"] == "pause" and f["run"] == run_id for f in facts(env)
            )
        )
        process = processes.pop("worker")
        process.kill()
        process.wait(timeout=20)
        with psycopg.connect(env["DATABASE_URI"]) as conn:
            conn.execute(
                "UPDATE runs SET lease_expires_at=now()-interval '1 second' WHERE run_id=%s",
                (run_id,),
            )
            if stale:
                conn.execute(
                    "UPDATE runtime_usage_calls SET outcome='started', quality='missing', total_tokens=NULL WHERE run_id=%s",
                    (run_id,),
                )
        release.touch()
        env["RUNTIME_TOKEN_BUDGET_MAX_TOKENS"] = "1000"
        start("worker")

        def finished(thread=thread, run_id=run_id):
            result = request(client, "GET", f"/threads/{thread}/runs/{run_id}")
            return result if result["status"] in {"success", "error"} else None

        run = wait_for(finished, timeout=120)
        usage = request(client, "GET", f"/threads/{thread}/runs/{run_id}/usage")
        budget = usage["token_budget"]
        assert budget["max_tokens"] == 10, usage
        assert run["status"] == ("error" if stale else "success"), run
        assert budget["stop_code"] == (
            "token_budget_unverifiable" if stale else None
        ), usage
        with psycopg.connect(env["DATABASE_URI"]) as conn:
            attempts = conn.execute(
                "SELECT retry_count FROM runs WHERE run_id=%s", (run_id,)
            ).fetchone()[0]
        assert attempts >= 2
        if not stale:
            assert budget["known_used_tokens"] == 8, usage
        evidence["cases"][
            "worker_recovery_unknown" if stale else "worker_recovery_known"
        ] = {"status": "passed", "attempts": attempts, "usage": usage}
    env["RUNTIME_TOKEN_BUDGET_MAX_TOKENS"] = "10"

    stop("worker")
    release = tmp_path / "cancel-release"
    env["TOKEN_RELEASE_FILE"] = str(release)
    start("worker")
    thread = request(
        client, "POST", "/threads", json={"metadata": {"graph_id": "reference_agent"}}
    )["thread_id"]
    created = request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json={
            "assistant_id": "reference_agent",
            "input": {"messages": [{"role": "user", "content": "resume-worker"}]},
            "context": {"model_id": spec["model"]},
        },
    )
    run_id = created.get("run_id") or created["id"]
    wait_for(
        lambda: any(f["event"] == "pause" and f["run"] == run_id for f in facts(env))
    )
    before = len([f for f in facts(env) if f["event"] == "model"])
    request(
        client,
        "POST",
        f"/threads/{thread}/runs/{run_id}/cancel",
        json={"action": "interrupt"},
    )
    release.touch()
    wait_for(
        lambda: (
            request(client, "GET", f"/threads/{thread}/runs/{run_id}")["status"]
            == "interrupted"
        )
    )
    assert len([f for f in facts(env) if f["event"] == "model"]) == before
    usage = request(client, "GET", f"/threads/{thread}/runs/{run_id}/usage")
    assert usage["token_budget"]["stop_code"] is None
    evidence["cases"]["cancel_preserves_native_status_no_new_dispatch"] = "passed"

    stop("worker")
    env["RUNTIME_TOKEN_BUDGET_ENABLED"] = "false"
    start("worker")
    _, _, run, usage, _ = create("cap-tool")
    assert run["status"] == "success" and usage["token_budget"] is None
    first = evidence["samples"]["reference_agent:cap-tool"]
    history = request(
        client, "GET", f"/threads/{first['thread_id']}/runs/{first['run_id']}/usage"
    )
    assert history["token_budget"]["stop_code"] == "token_budget_exhausted"
    evidence["cases"]["rollback_history_retained"] = "passed"
    evidence["complete"] = True
    target = Path(
        os.environ.get("TOKEN_BUDGET_EVIDENCE_PATH", str(tmp_path / "evidence.json"))
    )
    target.write_text(json.dumps(evidence, indent=2) + "\n")
    export = os.getenv("TOKEN_BUDGET_FIXTURE_PATH")
    if export:
        from fixtures.token_budget_platform import export_contract

        export_contract(evidence, export)
