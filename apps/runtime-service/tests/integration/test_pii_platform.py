"""Opt-in real API/Worker/PostgreSQL/Redis privacy and rollback evidence."""

import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import psycopg
import pytest
from langchain_core.messages import HumanMessage
from services.dearflow_agent.test_tool_error_platform import (
    facts,
    protocol_replay,
    request,
    wait_for,
)

from runtime_service.messaging import MessageInbox
from runtime_service.runtime.pii import PiiRedactionConfig
from runtime_service.services.dearflow_agent.memory import MemoryCommand, MemoryStorage
from runtime_service.services.dearflow_agent.middleware.memory import (
    MemoryContextMiddleware,
)

SECRET = "synthetic-redaction-secret-32-bytes"
pytest_plugins = ["services.dearflow_agent.test_tool_error_platform"]
EMAIL = "alice@example.test"
PHONE = "13800138000"


@pytest.mark.parametrize(
    "stack",
    [
        {
            "fixture": "pii_redaction_platform.py",
            "provider": True,
            "http_app": True,
            "env": {
                "RUNTIME_BACKEND": "local",
                "RUNTIME_PII_REDACTION_ENABLED": "true",
                "RUNTIME_PII_TOKEN_SECRET": SECRET,
            },
        }
    ],
    indirect=True,
)
def test_real_worker_inputs_errors_approval_history_and_restart(stack, monkeypatch):
    client, spec, env, processes, start, stop, tmp_path = stack
    evidence = []

    def run(prompt, *, thread=None):
        if thread is None:
            thread = request(
                client,
                "POST",
                "/threads",
                json={"metadata": {"graph_id": "dearflow_agent"}},
            )["thread_id"]
        response = client.post(
            f"/threads/{thread}/runs/stream",
            json={
                "assistant_id": "dearflow_agent",
                "context": {"model_id": spec["model"], "execution_mode": "ultra"},
                "input": {"messages": [{"role": "user", "content": prompt}]},
                "version": "v3",
                "stream_mode": ["values", "tasks", "tools", "updates"],
                "stream_subgraphs": True,
            },
        )
        assert response.status_code == 200, response.text[:1000]
        return (
            thread,
            request(client, "GET", f"/threads/{thread}/runs")[0],
            response.text,
        )

    for prompt in ("main " + EMAIL + " " + PHONE, "child " + EMAIL):
        before = len(facts(env))
        thread, run_value, events = run(prompt)
        assert run_value["status"] == "success", events[-3000:]
        rows = facts(env)[before:]
        calls = [row["body"] for row in rows if row["event"] == "http-model"]
        assert len(calls) >= 2
        assert EMAIL not in json.dumps(calls) and PHONE not in json.dumps(calls)
        assert "[EMAIL_" in json.dumps(calls)
        state = request(client, "GET", f"/threads/{thread}/state")
        assert prompt in str(state) and EMAIL in str(state)
        assert SECRET not in str((state, events, run_value))
        with psycopg.connect(env["DATABASE_URI"]) as db:
            assert (
                db.execute(
                    "SELECT retry_count FROM runs WHERE run_id=%s",
                    (run_value["run_id"],),
                ).fetchone()[0]
                == 1
            )
        evidence.append(
            {
                "scenario": prompt.split()[0],
                "thread_id": thread,
                "run_id": run_value["run_id"],
                "status": run_value["status"],
                "provider_calls": len(calls),
            }
        )
    # Unknown outbound structure fails before the first provider call and survives durable replay.
    before = sum(row["event"] == "http-model" for row in facts(env))
    thread, failed, events = run([{"type": "unknown", "text": EMAIL}])
    assert failed["status"] == "error", events[-3000:]
    code = "runtime.privacy.redaction_failed"
    assert code in events
    assert sum(row["event"] == "http-model" for row in facts(env)) == before
    frames = protocol_replay(client, thread)
    assert code in str(frames) and SECRET not in str(frames)
    terminal = next(
        frame["params"]["data"]
        for frame in frames
        if frame.get("method") == "lifecycle"
        and frame["params"]["data"].get("status") == "error"
    )
    assert terminal["error"] in (
        code,
        {
            "type": "RuntimePrivacyError",
            "code": code,
            "message": "隐私保护处理失败，本次模型请求未发送。",
        },
    )
    assert '"type":"RuntimePrivacyError"' in events and "本次模型请求未发送" in events
    with psycopg.connect(env["DATABASE_URI"]) as db:
        assert (
            db.execute(
                "SELECT retry_count FROM runs WHERE run_id=%s", (failed["run_id"],)
            ).fetchone()[0]
            == 1
        )
    evidence.append(
        {
            "scenario": "blocked",
            "thread_id": thread,
            "run_id": failed["run_id"],
            "status": "error",
            "provider_calls": 0,
            "error": terminal["error"],
        }
    )
    # A real HITL resume retains its original tool arguments and file contents.
    thread, paused, events = run("approval " + EMAIL)
    assert paused["status"] == "interrupted", events[-3000:]
    state = request(client, "GET", f"/threads/{thread}/state")
    interrupts = [
        item for task in state["tasks"] for item in task.get("interrupts", [])
    ]
    assert len(interrupts) == 1
    response = client.post(
        f"/threads/{thread}/runs/stream",
        json={
            "assistant_id": "dearflow_agent",
            "command": {
                "resume": {interrupts[0]["id"]: {"decisions": [{"type": "approve"}]}}
            },
        },
    )
    assert response.status_code == 200, response.text[:1000]
    approved = request(client, "GET", f"/threads/{thread}/runs")[0]
    assert approved["status"] == "success", response.text[-3000:]
    saved = list((tmp_path / "workspaces").rglob("approved.txt"))
    assert len(saved) == 1 and saved[0].read_text() == EMAIL
    evidence.append(
        {
            "scenario": "approval_resume",
            "status": "success",
            "original_tool_argument_preserved": True,
        }
    )
    for decision in ("edit", "reject"):
        approval_thread, paused, events = run("approval " + EMAIL)
        assert paused["status"] == "interrupted"
        state = request(client, "GET", f"/threads/{approval_thread}/state")
        interrupts = [
            item for task in state["tasks"] for item in task.get("interrupts", [])
        ]
        decision_value = {"type": decision}
        if decision == "edit":
            decision_value["edited_action"] = {
                "name": "write_file",
                "args": {
                    "file_path": "/workspace/work/edited.txt",
                    "content": "edited " + EMAIL,
                },
            }
        else:
            decision_value["message"] = "synthetic rejection"
        response = client.post(
            f"/threads/{approval_thread}/runs/stream",
            json={
                "assistant_id": "dearflow_agent",
                "command": {
                    "resume": {interrupts[0]["id"]: {"decisions": [decision_value]}}
                },
            },
        )
        assert response.status_code == 200, response.text
        assert (
            request(client, "GET", f"/threads/{approval_thread}/runs")[0]["status"]
            == "success"
        ), response.text[-3000:]
        if decision == "edit":
            edited = list((tmp_path / "workspaces").rglob("edited.txt"))
            assert len(edited) == 1 and edited[0].read_text() == "edited " + EMAIL
        assert len(list((tmp_path / "workspaces").rglob("approved.txt"))) == 1
        evidence.append({"scenario": "hitl_" + decision, "status": "success"})
    # Automatic memory uses a real isolated PG store and verifies source quotes unchanged.
    from runtime_service.services.dearflow_agent.middleware import (
        memory as memory_module,
    )

    scope = (spec["tenant"], spec["project"], "synthetic-memory-user")
    store = MemoryStorage(env["DATABASE_URI"])
    settings = store.change(
        scope,
        MemoryCommand(
            action="settings", expected_revision=0, automatic_candidates=True
        ),
        thread_id="",
        source_id="explicit-management",
    )
    monkeypatch.setattr(
        memory_module, "memory_allowed", lambda _: asyncio.sleep(0, result=True)
    )
    monkeypatch.setattr(memory_module, "memory_scope", lambda _: scope)
    monkeypatch.setenv("DATABASE_URI", env["DATABASE_URI"])
    candidate = memory_module.Candidate(
        text="喜欢中文",
        quote="中文",
        scope="personal",
        durability="stable",
        authority="personal_fact",
    )
    model_call = AsyncMock(
        return_value={
            "parsed": memory_module.Candidates(candidates=[candidate]),
            "raw": SimpleNamespace(usage_metadata={}),
        }
    )
    model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: SimpleNamespace(ainvoke=model_call)
    )
    policy = PiiRedactionConfig(
        True, SECRET, scope=(spec["tenant"], spec["project"], thread)
    )
    middleware = MemoryContextMiddleware(model, policy)
    runtime = SimpleNamespace(
        execution_info=SimpleNamespace(thread_id=thread, run_id=approved["run_id"])
    )

    def memory_state(message_id, content):
        return {
            "messages": [HumanMessage(content, id=message_id)],
            "dear_memory_source": {
                "id": message_id,
                "text": content[:6000],
                "epoch": settings["epoch"],
                "enabled": True,
            },
        }

    asyncio.run(
        middleware.aafter_agent(
            memory_state("filtered", "x" * 5999 + " " + EMAIL), runtime
        )
    )
    assert model_call.await_count == 0 and store.read(scope)["candidates"] == []
    asyncio.run(middleware.aafter_agent(memory_state("safe", "我喜欢中文"), runtime))
    assert model_call.await_count == 1
    view = store.read(scope)
    assert view["candidates"] and view["candidates"][0]["quote"] in "我喜欢中文"
    candidate.quote = "非原文"
    asyncio.run(
        middleware.aafter_agent(memory_state("wrong-quote", "我喜欢中文"), runtime)
    )
    assert len(store.read(scope)["candidates"]) == 1
    evidence.append(
        {
            "scenario": "memory_pg",
            "filtered_model_calls": 0,
            "quote_match_preserved": True,
            "wrong_quote_rejected": True,
        }
    )
    # Delivered sources use durable sender identity and scan the complete inbox payload.
    inbox = MessageInbox(env["DATABASE_URI"])
    queued = []
    for sender, text in (
        (scope[2], "我喜欢中文"),
        (scope[2], "x" * 5999 + " " + EMAIL),
        ("other-sender", "我喜欢英文"),
    ):
        message_id = str(uuid4())
        inbox.enqueue(
            thread_id=thread,
            target_run_id=approved["run_id"],
            sender_id=sender,
            client_message_id=message_id,
            idempotency_key=message_id,
            content=text,
        )
        queued.append(message_id)
    inbox.claim(thread_id=thread, target_run_id=approved["run_id"], owner="fixture")
    candidate.quote = "中文"
    candidate.source_message_id = queued[0]
    model_call.reset_mock()
    asyncio.run(
        middleware.aafter_agent(
            {
                "messages": [],
                "runtime_message_claim": {
                    "run_id": approved["run_id"],
                    "message_ids": queued,
                },
            },
            runtime,
        )
    )
    assert model_call.await_count == 1
    assert EMAIL not in str(model_call.call_args)
    assert model_call.call_args.args[0][-1].content == "我喜欢中文"
    evidence.append({"scenario": "inbox_pg", "safe_sources_sent": 1})
    # Restore a valid old checkpoint after a same-key Worker restart.
    retained_thread = evidence[0]["thread_id"]
    stop("worker")
    start("worker")
    _, resumed, events = run("next " + EMAIL, thread=retained_thread)
    assert resumed["status"] == "success", events[-3000:]
    title = request(
        client,
        "POST",
        f"/threads/{retained_thread}/title/summarize",
        json={"messages": [{"role": "user", "content": "title " + EMAIL}]},
    )
    assert title["title"] == "safe answe"
    suggestions = request(
        client,
        "POST",
        f"/threads/{retained_thread}/suggestions",
        json={
            "messages": [{"role": "user", "content": "suggest " + EMAIL}],
            "model_id": spec["model"],
        },
    )
    assert suggestions == {"suggestions": ["继续研究"]}
    evidence.append({"scenario": "title_suggestions_http", "safe_responses": True})
    calls = [row["body"] for row in facts(env) if row["event"] == "http-model"]
    assert EMAIL not in json.dumps(calls) and PHONE not in json.dumps(calls)
    evidence.append({"scenario": "same_key_restart", "status": resumed["status"]})
    # Rotation changes new placeholders while preserving old checkpoint facts.
    old_token = re.search(r"\[EMAIL_[a-z]{27}\]", json.dumps(calls[0])).group()
    stop("worker")
    stop("runtime")
    env["RUNTIME_PII_TOKEN_SECRET"] = SECRET + "-rotated"
    start("runtime")
    import httpx

    wait_for(
        lambda: httpx.get(spec["runtime_url"] + "/ready", trust_env=False).is_success,
        process=processes["runtime"],
    )
    start("worker")
    before = len(calls)
    _, rotated, events = run("rotation " + EMAIL, thread=retained_thread)
    assert rotated["status"] == "success", events[-3000:]
    new_calls = [row["body"] for row in facts(env) if row["event"] == "http-model"][
        before:
    ]
    assert EMAIL not in json.dumps(new_calls)
    latest = next(
        m["content"] for m in reversed(new_calls[0]["messages"]) if m["role"] == "user"
    )
    new_token = re.search(r"\[EMAIL_[a-z]{27}\]", latest).group()
    assert new_token != old_token
    assert EMAIL in str(request(client, "GET", f"/threads/{retained_thread}/state"))
    evidence.append({"scenario": "rotated_key_restart", "new_token_differs": True})
    # Drain/stop our isolated API and Worker, then restore the disabled deployment behavior.
    stop("worker")
    stop("runtime")
    env["RUNTIME_PII_REDACTION_ENABLED"] = "false"
    start("runtime")

    wait_for(
        lambda: httpx.get(spec["runtime_url"] + "/ready", trust_env=False).is_success,
        process=processes["runtime"],
    )
    start("worker")
    before = sum(row["event"] == "http-model" for row in facts(env))
    _, restored, events = run("disabled " + EMAIL)
    assert restored["status"] == "success", events[-3000:]
    calls = [row["body"] for row in facts(env) if row["event"] == "http-model"][before:]
    assert EMAIL in json.dumps(calls)
    evidence.append(
        {
            "scenario": "disabled_after_restart",
            "status": "success",
            "original_text_sent": True,
        }
    )
    (tmp_path / "pii-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2)
    )
    print(json.dumps(evidence, ensure_ascii=False))


@pytest.mark.parametrize(
    "stack",
    [
        {
            "fixture": "pii_redaction_platform.py",
            "provider": True,
            "http_app": True,
            "env": {
                "RUNTIME_BACKEND": "local",
                "RUNTIME_PII_REDACTION_ENABLED": "true",
                "RUNTIME_PII_TOKEN_SECRET": SECRET,
            },
        }
    ],
    indirect=True,
)
def test_real_worker_child_cancellation_with_privacy_enabled(stack):
    _, _, env, _, _, stop, tmp_path = stack
    # Existing cancellation contracts require their own disposable database and Redis namespace.
    stop("worker")
    cancel_database = "graphharbor_pii_cancel"
    with psycopg.connect(env["DATABASE_URI"], autocommit=True) as db:
        db.execute("CREATE DATABASE " + cancel_database)
    cancel_uri = env["DATABASE_URI"].rsplit("/", 1)[0] + "/" + cancel_database
    cancel_env = {
        **env,
        "DATABASE_URI": cancel_uri,
        "POSTGRES_URI": cancel_uri,
        "RUNTIME_PII_REDACTION_ENABLED": "true",
        "GRAPHHARBOR_REDIS_PREFIX": "graphharbor:cancel:pii:",
        "RUN_MODEL_RESILIENCE_GRAPH_WORKER": "1",
    }
    migration = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os; from langgraph_runtime_pg.migrate import upgrade_head; upgrade_head(os.environ['DATABASE_URI'])",
        ],
        env=cancel_env,
        capture_output=True,
        timeout=60,
    )
    assert migration.returncode == 0, migration.stderr.decode(errors="replace")
    cancellation = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "tests/services/test_model_resilience_composition.py::test_worker_cancel_stops_actual_child_and_candidate_waits",
            "-q",
            "--tb=short",
            "--junitxml=" + str(tmp_path / "cancellation.xml"),
            "--basetemp=" + str(tmp_path / "cancellation"),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=cancel_env,
        capture_output=True,
        timeout=360,
    )
    (tmp_path / "cancellation.log").write_bytes(
        cancellation.stdout + cancellation.stderr
    )
    assert cancellation.returncode == 0, cancellation.stdout.decode(errors="replace")[
        -6000:
    ]
