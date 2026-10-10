"""Plan approval through real API, Runtime, persistent Worker and native interrupts."""

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from services.dearflow_agent.test_tool_error_platform import (  # noqa: F401
    facts,
    request,
    stack,
    wait_for,
)


@pytest.mark.parametrize(
    "stack",
    [
        {
            "fixture": "plan_mode_platform.py",
            "graphs": {
                "reference_agent": "fixture.py:reference_graph",
                "workflow_demo": "fixture.py:workflow_graph",
            },
            "env": {
                "RUNTIME_BACKEND": "local",
                "RUNTIME_SHOWCASE_EXECUTION_MODE": "local",
            },
        }
    ],
    indirect=True,
)
def test_plan_http_worker_restarts_and_original_approval(stack):  # noqa: F811
    client, spec, env, processes, start, stop, tmp_path = stack

    def command(thread, method, params, key=None):
        return request(
            client,
            "POST",
            f"/threads/{thread}/commands",
            json={"id": 1, "method": method, "params": params},
            headers={"Idempotency-Key": key} if key else {},
        )

    def run_status(thread, status):
        return wait_for(
            lambda: next(
                (
                    r
                    for r in request(client, "GET", f"/threads/{thread}/runs")
                    if r["status"] == status
                ),
                None,
            )
        )

    def pending(thread):
        state = request(client, "GET", f"/threads/{thread}/state")
        records = state.get("interrupts") or [
            i for task in state.get("tasks", []) for i in task.get("interrupts", [])
        ]
        assert len(records) == 1
        return state, records[0]

    for graph_id in (
        "reference_agent",
        "workflow_demo",
        "dearflow_agent",
        "showcase_demo",
    ):
        thread = request(
            client, "POST", "/threads", json={"metadata": {"graph_id": graph_id}}
        )["thread_id"]
        context = {"plan_mode": True, "execution_mode": "standard"}
        if graph_id != "workflow_demo":
            context["model_id"] = spec["model"]
        command(
            thread,
            "run.start",
            {
                "assistant_id": graph_id,
                "input": {"messages": [{"role": "user", "content": "plan"}]},
                "context": context,
            },
            "start-" + graph_id,
        )
        run_status(thread, "interrupted")
        state, review = pending(thread)
        assert review["value"]["type"] == "agent_plan_review"
        assert state["values"]["agent_plan"]["status"] == "awaiting_review"
        assert "bound_execution_id" not in json.dumps(state)
        before = len(
            [f for f in facts(env) if f["event"] == "business_write_requested"]
        )
        if graph_id == "reference_agent":
            stop("worker")
            start("worker")
        answer = {
            "version": 1,
            "type": "agent_plan_response",
            "decision": "approve",
            **{
                key: review["value"][key]
                for key in ("plan_id", "revision", "content_hash")
            },
        }
        if graph_id == "reference_agent":
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(
                    pool.map(
                        lambda _, thread=thread, review=review, answer=answer: command(
                            thread, "input.respond", {"resume": {review["id"]: answer}}
                        ),
                        range(2),
                    )
                )
            assert results[0] == results[1]
            result = results[0]
        else:
            result = command(
                thread, "input.respond", {"resume": {review["id"]: answer}}
            )
        assert (
            command(thread, "input.respond", {"resume": {review["id"]: answer}})
            == result
        )
        if graph_id in {"dearflow_agent", "showcase_demo"}:
            wait_for(
                lambda before=before: (
                    len(
                        [
                            f
                            for f in facts(env)
                            if f["event"] == "business_write_requested"
                        ]
                    )
                    == before + 1
                )
            )
            state, tool_review = wait_for(
                lambda thread=thread: (
                    pending(thread)
                    if request(client, "GET", f"/threads/{thread}/state").get(
                        "interrupts"
                    )
                    else None
                )
            )
            assert state["values"]["agent_plan"]["status"] == "approved"
            assert tool_review["value"]["action_requests"][0]["name"] == "write_file"
            command(
                thread,
                "input.respond",
                {"resume": {tool_review["id"]: {"decisions": [{"type": "approve"}]}}},
            )
        run_status(thread, "success")
        state = request(client, "GET", f"/threads/{thread}/state")
        assert state["values"]["agent_plan"]["status"] == "approved"
        assert state["values"]["agent_plan"]["approved_by"]["user_id"]

    # Keep the current enforcement pair when an older runtime cannot protect plan state.
    graph_id = "reference_agent"
    thread = request(
        client, "POST", "/threads", json={"metadata": {"graph_id": graph_id}}
    )["thread_id"]
    command(
        thread,
        "run.start",
        {
            "assistant_id": graph_id,
            "input": {"messages": [{"role": "user", "content": "plan"}]},
            "context": {"model_id": spec["model"], "plan_mode": True},
        },
        "rollback-start",
    )
    run_status(thread, "interrupted")
    state, review = pending(thread)
    before = review["value"]
    with sqlite3.connect(spec["database"]) as db:
        db.execute(
            "UPDATE agents SET status = 'disabled' WHERE graph_id = ?", (graph_id,)
        )
    answer = {
        "version": 1,
        "type": "agent_plan_response",
        "decision": "approve",
        **{key: before[key] for key in ("plan_id", "revision", "content_hash")},
    }
    for method, params in (
        (
            "run.start",
            {
                "assistant_id": graph_id,
                "context": {"plan_mode": False},
                "input": {"messages": [{"role": "user", "content": "bypass"}]},
            },
        ),
        ("input.respond", {"resume": {review["id"]: answer}}),
    ):
        result = client.post(
            f"/threads/{thread}/commands",
            json={"id": 2, "method": method, "params": params},
            headers={"Idempotency-Key": "rollback-block"},
        )
        assert result.status_code == 403, result.text[:1000]
    stop("worker")
    start("worker")
    assert pending(thread)[1]["value"] == before
    with sqlite3.connect(spec["database"]) as db:
        db.execute(
            "UPDATE agents SET status = 'active' WHERE graph_id = ?", (graph_id,)
        )
    command(thread, "input.respond", {"resume": {review["id"]: answer}})
    run_status(thread, "success")
    assert (
        request(client, "GET", f"/threads/{thread}/state")["values"]["agent_plan"][
            "status"
        ]
        == "approved"
    )


@pytest.mark.parametrize(
    "stack",
    [
        {
            "fixture": "plan_mode_platform.py",
            "graphs": {"reference_agent": "fixture.py:reference_graph"},
            "env": {
                "RUNTIME_BACKEND": "local",
                "RUNTIME_SHOWCASE_EXECUTION_MODE": "local",
            },
        }
    ],
    indirect=True,
)
@pytest.mark.skipif(
    os.getenv("PLAN_MODE_LIVE_TEST") != "1",
    reason="PLAN_MODE_LIVE_TEST=1 enables synthetic real model verification",
)
@pytest.mark.parametrize("graph_id", ["reference_agent", "dearflow_agent"])
def test_plan_real_model_http_approval_and_revision(stack, graph_id):  # noqa: F811
    client, spec, env, processes, start, stop, tmp_path = stack
    evidence = {"graph": graph_id, "snapshots": []}

    def command(thread, method, params, key=None):
        return request(
            client,
            "POST",
            f"/threads/{thread}/commands",
            json={"id": 1, "method": method, "params": params},
            headers={"Idempotency-Key": key} if key else {},
        )

    def terminal(thread, run_id):
        run = request(client, "GET", f"/threads/{thread}/runs/{run_id}")
        if run["status"] == "error":
            state = request(client, "GET", f"/threads/{thread}/state")
            print({"failed_run": run_id, "error": state.get("error")})
        assert run["status"] != "error", (
            "Real model run failed; inspect isolated service logs"
        )
        return run if run["status"] in {"success", "interrupted"} else None

    def review(thread, run_id):
        run = wait_for(lambda: terminal(thread, run_id), timeout=240)
        state = request(client, "GET", f"/threads/{thread}/state")
        messages = state.get("values", {}).get("messages", [])
        print(
            {
                "phase": "review",
                "graph_run": run_id,
                "status": run["status"],
                "agent_plan": {
                    key: state.get("values", {}).get("agent_plan", {}).get(key)
                    for key in ("status", "active", "revision", "decision")
                },
                "tool_names": [
                    call.get("name")
                    for message in messages
                    for call in message.get("tool_calls", [])
                ],
                "budget_notices": [
                    message.get("additional_kwargs", {}).get("runtime_budget_notice")
                    for message in messages
                    if message.get("additional_kwargs", {}).get("runtime_budget_notice")
                ],
            }
        )
        assert run["status"] == "interrupted"
        records = state.get("interrupts") or [
            i for task in state.get("tasks", []) for i in task.get("interrupts", [])
        ]
        assert len(records) == 1 and records[0]["value"]["type"] == "agent_plan_review"
        assert state["values"]["agent_plan"]["status"] == "awaiting_review"
        evidence["snapshots"].append(
            {
                "run_id": run_id,
                "interrupt": records[0],
                "agent_plan": state["values"]["agent_plan"],
            }
        )
        (tmp_path / "plan-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2)
        )
        return records[0]

    thread = request(
        client, "POST", "/threads", json={"metadata": {"graph_id": graph_id}}
    )["thread_id"]
    output = None
    research = "请先调用 read_reference，topic=runtime，做一次只读调研。"
    if graph_id == "dearflow_agent":
        from runtime_service.workspace.scoped import hashed_thread_root

        workspace = (
            hashed_thread_root(
                Path(env["RUNTIME_WORKSPACE_ROOT"]) / graph_id,
                "__default",
                spec["project"],
                thread,
            )
            / "workspace"
        )
        (workspace / "work").mkdir(parents=True)
        (workspace / "work/plan-input.txt").write_text(
            "Create plan-live.txt after human approval."
        )
        output = workspace / "work/plan-live.txt"
        research = (
            "请先用 read_file 读取 /workspace/work/plan-input.txt 做一次只读调研。"
        )
    prompt = (
        "这是隔离测试。"
        + research
        + "然后调用 save_plan 保存计划，下一轮单独调用 submit_plan 等待人工审批。每轮只能调用一个计划工具。"
        "计划标题为验收计划，正文包含目标和验证。如果被要求修改，先修改正文并 save_plan，再单独 submit_plan。"
        + (
            "批准后只用 write_file 写入 /workspace/work/plan-live.txt，内容为 plan-live-ok，工具审批后回答 plan-live-ok 并结束。不要发布成果，不要执行脚本，不要搜索网络，不要请求澄清。"
            if graph_id == "dearflow_agent"
            else "批准后只回答 plan-live-ok，不再调用计划工具。"
        )
    )
    run = command(
        thread,
        "run.start",
        {
            "assistant_id": graph_id,
            "context": {
                "model_id": spec["model"],
                "plan_mode": True,
                "execution_mode": "standard",
                "max_tokens": 4096,
            },
            "input": {"messages": [{"role": "user", "content": prompt}]},
        },
        "live-" + graph_id,
    )
    pending = review(thread, run["result"]["run_id"])
    revisions = [pending["value"]["revision"]]
    if graph_id == "reference_agent":
        answer = {
            "version": 1,
            "type": "agent_plan_response",
            "decision": "request_changes",
            "feedback": "请在正文新增回退章节，批准后只回复 plan-live-ok。",
            **{
                key: pending["value"][key]
                for key in ("plan_id", "revision", "content_hash")
            },
        }
        run = command(thread, "input.respond", {"resume": {pending["id"]: answer}})
        changed = review(thread, run["result"]["run_id"])
        assert changed["value"]["plan_id"] == pending["value"]["plan_id"]
        assert changed["value"]["revision"] > pending["value"]["revision"]
        pending = changed
        revisions.append(pending["value"]["revision"])
    if output is not None:
        assert not output.exists()
    answer = {
        "version": 1,
        "type": "agent_plan_response",
        "decision": "approve",
        **{
            key: pending["value"][key]
            for key in ("plan_id", "revision", "content_hash")
        },
    }
    run = command(thread, "input.respond", {"resume": {pending["id"]: answer}})
    run_id = run["result"]["run_id"]
    result = wait_for(lambda: terminal(thread, run_id), timeout=240)
    if output is not None:
        assert result["status"] == "interrupted"
        state = request(client, "GET", f"/threads/{thread}/state")
        tool_review = state["interrupts"][0]
        actions = tool_review["value"]["action_requests"]
        assert len(actions) == 1 and actions[0]["name"] == "write_file"
        assert actions[0]["args"]["file_path"] == "/workspace/work/plan-live.txt"
        assert not output.exists()
        run = command(
            thread,
            "input.respond",
            {"resume": {tool_review["id"]: {"decisions": [{"type": "approve"}]}}},
        )
        run_id = run["result"]["run_id"]
        result = wait_for(lambda: terminal(thread, run_id), timeout=240)
        state = request(client, "GET", f"/threads/{thread}/state")
        print(
            {
                "phase": "tool_approval_resumed",
                "run_id": run_id,
                "status": result["status"],
                "tool_results": [
                    {"name": message.get("name"), "content": message.get("content")}
                    for message in state.get("values", {}).get("messages", [])
                    if message.get("type") == "tool"
                    and message.get("name") in {"read_file", "write_file"}
                ],
            }
        )
        assert result["status"] == "success"
        assert output.read_text().strip() == "plan-live-ok"
    assert result["status"] == "success"
    state = request(client, "GET", f"/threads/{thread}/state")
    assert state["values"]["agent_plan"]["status"] == "approved"
    assert "plan-live-ok" in json.dumps(state["values"]["messages"])
    evidence.update(
        thread_id=thread,
        run_id=result["run_id"],
        status=result["status"],
        agent_plan=state["values"]["agent_plan"],
    )
    (tmp_path / "plan-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2)
    )
    print(
        {
            "graph": graph_id,
            "thread_id": thread,
            "run_id": result["run_id"],
            "revisions": revisions,
            "status": result["status"],
            "approved": True,
        }
    )


@pytest.mark.parametrize(
    "stack",
    [
        {
            "fixture": "plan_mode_platform.py",
            "graphs": {"reference_agent": "fixture.py:reference_graph"},
            "env": {"RUNTIME_BACKEND": "local"},
        }
    ],
    indirect=True,
)
def test_plan_http_review_decisions_and_public_handoff(stack):  # noqa: F811
    client, spec, env, processes, start, stop, tmp_path = stack
    evidence = {"graph": "reference_agent", "commands": [], "snapshots": []}

    def command(thread, method, params):
        payload = {"id": 1, "method": method, "params": params}
        headers = {"Idempotency-Key": f"handoff-{len(evidence['commands'])}"}
        result = request(
            client, "POST", f"/threads/{thread}/commands", json=payload, headers=headers
        )
        evidence["commands"].append(
            {
                "thread_id": thread,
                "headers": headers,
                "request": payload,
                "response": result,
            }
        )
        return result["result"]["run_id"]

    def snapshot(thread, run_id, expected):
        def terminal():
            run = request(client, "GET", f"/threads/{thread}/runs/{run_id}")
            assert run["status"] != "error", run
            return run if run["status"] in {"interrupted", "success"} else None

        run = wait_for(terminal)
        state = request(client, "GET", f"/threads/{thread}/state")
        if run["status"] != expected:
            print(
                json.dumps(
                    {
                        "handoff_run": run_id,
                        "status": run["status"],
                        "plan": state.get("values", {}).get("agent_plan"),
                        "messages": state.get("values", {}).get("messages"),
                    }
                )
            )
        assert run["status"] == expected, {
            "status": run["status"],
            "agent_plan": state.get("values", {}).get("agent_plan"),
            "messages": state.get("values", {}).get("messages"),
        }
        history = request(
            client, "POST", f"/threads/{thread}/history", json={"limit": 20}
        )
        assert not any(
            private in json.dumps([state, history])
            for private in ("runtime_plan", "plan_execution_id", "bound_execution_id")
        )
        evidence["snapshots"].append(
            {
                "thread_id": thread,
                "run_id": run_id,
                "status": expected,
                "state": state,
                "history": history,
            }
        )
        return state

    def reply(thread, state, decision):
        pending = state["interrupts"][0]
        value = pending["value"]
        response = {
            "version": 1,
            "type": "agent_plan_response",
            "decision": decision,
            **{key: value[key] for key in ("plan_id", "revision", "content_hash")},
        }
        if decision == "request_changes":
            response["feedback"] = "Add validation and rollback."
        return command(thread, "input.respond", {"resume": {pending["id"]: response}})

    for abandon in (False, True):
        thread = request(
            client,
            "POST",
            "/threads",
            json={"metadata": {"graph_id": "reference_agent"}},
        )["thread_id"]
        run_id = command(
            thread,
            "run.start",
            {
                "assistant_id": "reference_agent",
                "context": {"model_id": spec["model"], "plan_mode": True},
                "input": {"messages": [{"role": "user", "content": "plan"}]},
            },
        )
        state = snapshot(thread, run_id, "interrupted")
        assert state["values"]["agent_plan"]["status"] == "awaiting_review"
        if not abandon:
            before = state["interrupts"][0]["value"]
            run_id = reply(thread, state, "request_changes")
            state = snapshot(thread, run_id, "interrupted")
            revised = state["interrupts"][0]["value"]
            assert revised["plan_id"] == before["plan_id"]
            assert revised["revision"] == before["revision"] + 1
            assert revised["content_hash"] != before["content_hash"]
        decision = "abandon" if abandon else "approve"
        run_id = reply(thread, state, decision)
        state = snapshot(thread, run_id, "success")
        plan = state["values"]["agent_plan"]
        assert plan["active"] is abandon
        assert plan["status"] == ("abandoned" if abandon else "approved")
        assert plan["decision"] == decision
        frames = []
        with client.stream(
            "POST",
            f"/threads/{thread}/stream/events",
            json={
                "channels": ["values", "checkpoints", "input", "lifecycle"],
                "since": 0,
            },
        ) as stream:
            assert stream.status_code == 200
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    frame = json.loads(line[5:])
                    frames.append(frame)
                    if (
                        frame.get("method") == "lifecycle"
                        and frame["params"]["data"].get("status") == "success"
                    ):
                        break
        serialized = json.dumps(frames)
        assert "agent_plan" in serialized
        assert not any(
            private in serialized
            for private in ("runtime_plan", "plan_execution_id", "bound_execution_id")
        )
        evidence.setdefault("sse", []).append({"thread_id": thread, "frames": frames})
    (tmp_path / "plan-handoff.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2)
    )
    print(
        {
            "handoff": "plan-handoff.json",
            "decisions": ["request_changes", "approve", "abandon"],
        }
    )
