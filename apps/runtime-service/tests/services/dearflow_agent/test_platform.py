"""Opt-in local Platform -> Agent Server smoke using an isolated test project."""
import os
import time
import hashlib
import json
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import pytest


def test_platform_creates_and_completes_dear_run():
    if os.environ.get("DEAR_PLATFORM_TEST") != "1":
        pytest.skip("DEAR_PLATFORM_TEST=1 enables local Platform writes and real model usage")
    with httpx.Client(base_url="http://127.0.0.1:2142", timeout=45, trust_env=False) as client:
        # Same development account as scripts/local_stack_l2_runtime_smoke.py.
        login = client.post("/api/identity/session", json={"username": "admin", "password": "admin123456"})
        assert login.status_code == 200, f"local login HTTP {login.status_code}"
        token = login.json()["tokens"]["access_token"]
        client.headers["Authorization"] = "Bearer " + token
        project = client.post("/api/projects", json={"name": "dear-p1-verification-" + uuid4().hex[:10]})
        assert project.status_code == 200, f"project create HTTP {project.status_code}"
        project_id = project.json()["id"]
        client.headers["X-Project-Id"] = project_id
        refresh = client.post("/api/runtime/graphs/refresh", json={})
        assert refresh.status_code == 200, f"catalog refresh HTTP {refresh.status_code}"
        registered = client.post(f"/api/projects/{project_id}/agents",
            json={"graph_id": "dearflow_agent", "name": "Dear P1 verification", "context": {}})
        assert registered.status_code in {200, 201}, f"register Dear HTTP {registered.status_code}: {registered.text[:200]}"
        response = client.post("/api/langgraph/threads", json={"graph_id": "dearflow_agent", "metadata": {"harness": "dear-p1-verification"}})
        assert response.status_code in {200, 201}, f"Dear thread HTTP {response.status_code}: {response.text[:200]}"
        thread_id = response.json().get("thread_id") or response.json()["id"]
        capabilities = client.get(f"/api/langgraph/threads/{thread_id}/capabilities")
        assert capabilities.status_code == 200, f"capabilities HTTP {capabilities.status_code}: {capabilities.text[:200]}"
        assert capabilities.json()["execution_modes"] == ["flash", "standard", "pro", "ultra"]
        from dotenv import dotenv_values
        settings = dotenv_values(".env")
        models_resp = client.get("/api/runtime/models")
        assert models_resp.status_code == 200
        existing_model = next(
            (
                m
                for m in models_resp.json().get("models", [])
                if m["model"] == "DeepSeek-V4-Flash"
                and m["provider"] == "deepseek"
                and m.get("base_url") == settings["DEEPSEEK_PROXY_URL"]
            ),
            None,
        )
        if existing_model:
            model_id = existing_model["id"]
        else:
            model = client.post("/api/runtime/models", json={
                "provider": "deepseek", "protocol": "deepseek",
                "display_name": "dear-p1-verification-" + uuid4().hex[:10],
                "model": "DeepSeek-V4-Flash",
                "base_url": settings["DEEPSEEK_PROXY_URL"],
                "api_key": settings["DEEPSEEK_PROXY_API_KEY"],
            })
            assert model.status_code == 201, f"test model HTTP {model.status_code}"
            model_id = model.json()["id"]
        research_mode = os.environ.get("DEAR_PLATFORM_RESEARCH_TEST") == "1"
        subagent_mode = os.environ.get("DEAR_PLATFORM_SUBAGENT_TEST") == "1"
        cancel_children = os.environ.get("DEAR_PLATFORM_CANCEL_CHILDREN") == "1"
        files_mode = os.environ.get("DEAR_PLATFORM_FILES_TEST") == "1" or research_mode
        if files_mode or subagent_mode:
            refreshed = client.post("/api/runtime/tools/refresh", json={})
            assert refreshed.status_code == 200
        tools = ["read_file", "execute", "request_information", "present_artifacts"] if files_mode else []
        if research_mode:
            tools += ["search_web", "fetch_page", "write_todos", "write_file"]
        context = {"model_id": model_id, "tools": tools}
        if research_mode:
            context["execution_mode"] = "pro"
        if subagent_mode:
            context.update(execution_mode="ultra", tools=["task", "read_file"])
        try:
            prompt = "Reply exactly: dear-platform-ok. Do not use tools."
            if subagent_mode:
                prompt = (
                    "验收普通子智能体：在同一次模型响应并行调用两次 task，subagent_type 均为 general-purpose。"
                    "第一个 description 为：这是委派验收，直接回答 ALPHA，不使用工具。"
                    "第二个 description 为：这是委派验收，直接回答 BETA，不使用工具。"
                    "必须分别委派两个任务，收到结果后简短汇总。不要请求澄清，不写文件，不再委派第三次。"
                )
            if files_mode:
                raw = b"dear platform file verified"
                digest = hashlib.sha256(raw).hexdigest()
                uploaded = client.put(f"/api/langgraph/threads/{thread_id}/files/uploads/{digest}",
                    content=raw, headers={"Content-Type": "text/plain"}, params={"file_name": "input.txt"})
                assert uploaded.status_code == 200, f"upload HTTP {uploaded.status_code}"
                input_path = uploaded.json()["path"]
                prompt = (
                    f"这是合成验收任务：先单独调用 request_information 问我是否转为大写，"
                    'fields=[{"name":"operation","label":"操作","type":"select","options":[{"value":"uppercase","label":"转大写"}]}]。'
                    f"收到回答后读取 /skills/runtime-smoke/SKILL.md 与 {input_path}，"
                    "调用 execute 用 Python 把文件内容转为大写写入 /workspace/work/result.txt，"
                    "再调用 present_artifacts 发布此文件。不要更改其他文件。"
                )
                if research_mode:
                    from .test_p2_contracts import FIELDS
                    prompt = (
                        "这是公开技术研究验收。先单独调用 request_information，question=研究范围确认，fields="
                        + json.dumps(FIELDS, ensure_ascii=False) + "。回答后必须调用 write_todos 规划，"
                        "搜索 Python asyncio TaskGroup 的取消与错误传播，再 fetch_page 阅读至少一个真实来源。"
                        "用 write_file 将简短中文报告写到 /workspace/work/result.txt，包含至少一个真实来源 URL，"
                        "然后 present_artifacts 发布。若收到补充消息，将要求落实到报告中。不要调用 execute。"
                    )
            response = client.post(f"/api/langgraph/threads/{thread_id}/runs",
                headers={"Idempotency-Key": uuid4().hex},
                json={"assistant_id": "dearflow_agent", "context": context, "input": {"messages": [{"role": "user", "content": prompt}]}})
            assert response.status_code in {200, 201}, f"run create HTTP {response.status_code}: {response.text[:200]}"
            run_id = response.json().get("run_id") or response.json()["id"]
            print(f"verification project={project_id} thread={thread_id} run={run_id}", flush=True)
            timeout_seconds = 1200 if research_mode else 600 if subagent_mode else 480 if files_mode else 120
            deadline = time.monotonic() + timeout_seconds
            seen = []
            restarted = False
            queued_id = None
            cancel_sent = False
            while time.monotonic() < deadline:
                response = client.get(f"/api/langgraph/threads/{thread_id}/runs/{run_id}")
                assert response.status_code == 200
                status = response.json().get("status")
                if subagent_mode and cancel_children and not cancel_sent and status == "running":
                    current = client.get(f"/api/langgraph/threads/{thread_id}/state").json()
                    calls = [call for message in current.get("values", {}).get("messages", [])
                             for call in message.get("tool_calls", []) if call.get("name") == "task"]
                    if len(calls) >= 2:
                        cancelled = client.post(f"/api/langgraph/threads/{thread_id}/runs/{run_id}/cancel",
                                                json={"action": "interrupt"})
                        assert cancelled.status_code in {200, 202}
                        cancel_sent = True
                if cancel_sent and status not in {"pending", "running"}:
                    assert status == "interrupted", f"cancel terminal was {status}"
                    print("parent cancel terminal verified", flush=True)
                    return
                if research_mode and status == "running" and queued_id is None:
                    message_id = str(uuid4())
                    payload = {"client_message_id": message_id, "target_run_id": run_id,
                               "content": "补充要求：报告末尾必须写入验收标记 DEAR-P2-QUEUE-VERIFIED。"}
                    receipt = client.post(f"/api/langgraph/threads/{thread_id}/messages", json=payload,
                                          headers={"Idempotency-Key": message_id})
                    if receipt.status_code == 202:
                        queued_id = message_id
                        duplicate = client.post(f"/api/langgraph/threads/{thread_id}/messages", json=payload,
                                                headers={"Idempotency-Key": message_id})
                        assert duplicate.status_code == 202
                    else:
                        assert receipt.status_code == 409, f"enqueue HTTP {receipt.status_code}"
                if status == "interrupted" and files_mode:
                    state_response = client.get(f"/api/langgraph/threads/{thread_id}/state")
                    assert state_response.status_code == 200
                    state = state_response.json()
                    interrupts = state.get("interrupts")
                    if not interrupts:
                        interrupts = [item for task in state.get("tasks", []) for item in task.get("interrupts", [])]
                    if isinstance(interrupts, dict):
                        interrupts = [{"id": key, "value": value.get("value", value)} for key, value in interrupts.items()]
                    assert interrupts, "interrupted Run without payload"
                    if os.environ.get("DEAR_PLATFORM_RESTART_TEST") == "1" and not restarted:
                        repo = Path(__file__).resolve().parents[5]
                        subprocess.run(["rtk", "proxy", "bash", str(repo / "scripts/local-stack.sh"),
                                        "restart-one", "runtime-worker"], cwd=repo,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       check=True, timeout=90)
                        after = client.get(f"/api/langgraph/threads/{thread_id}/state").json()
                        assert after["checkpoint"] == state["checkpoint"]
                        restarted = True
                    resumes = {}
                    for item in interrupts:
                        payload = item["value"]
                        if payload.get("kind") == "clarification":
                            seen.append("clarification")
                            resumes[item["id"]] = {"schema_version": 1, "status": "answered",
                                                   "values": {"operation": "uppercase"}}
                            if research_mode:
                                from .test_p2_contracts import VALUES
                                resumes[item["id"]]["values"] = VALUES
                        else:
                            actions = payload["action_requests"]
                            for action in actions:
                                assert action["name"] in {"execute", "write_file", "present_artifacts"}, action["name"]
                                seen.append(action["name"])
                            resumes[item["id"]] = {"decisions": [{"type": "approve"} for _ in actions]}
                    resumed = client.post(f"/api/langgraph/threads/{thread_id}/runs", json={"command": {"resume": resumes}})
                    assert resumed.status_code in {200, 201}, f"resume HTTP {resumed.status_code}: {resumed.text[:200]}"
                    run_id = resumed.json().get("run_id") or resumed.json()["id"]
                    continue
                if status not in {"pending", "running"}:
                    assert status in {"success", "completed"}, f"Run ended with {status}"
                    break
                time.sleep(1)
            else:
                pytest.fail(f"Dear deployment run did not finish within {timeout_seconds} seconds")
            state = client.get(f"/api/langgraph/threads/{thread_id}/state").json()
            messages = state.get("values", {}).get("messages", [])
            if files_mode:
                assert {"clarification", "write_file" if research_mode else "execute", "present_artifacts"} <= set(seen), seen
                publications = [m for m in messages if m.get("name") == "present_artifacts"]
                assert publications
                ref = json.loads(publications[-1]["content"])
                download = client.get(f"/api/langgraph/threads/{thread_id}/files/content", params={"path": ref["path"]})
                assert download.status_code == 200
                if research_mode:
                    assert b"DEAR-P2-QUEUE-VERIFIED" in download.content
                    source_messages = [m for m in messages if m.get("name") == "fetch_page" and m.get("artifact")]
                    assert source_messages
                    source = source_messages[-1]["artifact"]["sources"][0]
                    assert source["source_url"].encode() in download.content
                    assert source["thread_id"] == thread_id
                    assert any(m.get("name") == "write_todos" for m in messages)
                    assert queued_id is not None
                    receipts = client.get(f"/api/langgraph/threads/{thread_id}/messages")
                    assert receipts.status_code == 200
                    matching = [row for row in receipts.json()["messages"] if row["message_id"] == queued_id]
                    assert len(matching) == 1 and matching[0]["status"] == "consumed"
                    print("research-chain verified; queue consumed; mode=pro")
                else:
                    assert download.content.strip() == raw.upper()
                assert hashlib.sha256(download.content).hexdigest() == ref["sha256"]
                if os.environ.get("DEAR_PLATFORM_RESTART_TEST") == "1":
                    assert restarted
                print("file-chain verified; worker_restarted=" + str(restarted))
            elif subagent_mode:
                assert not cancel_children, "children finished before cancellation could be verified"
                calls = [call for message in messages for call in message.get("tool_calls", []) if call.get("name") == "task"]
                assert len(calls) == 2 and len({call["id"] for call in calls}) == 2
                results = {message["tool_call_id"]: message for message in messages if message.get("type") == "tool"
                           and message.get("tool_call_id") in {call["id"] for call in calls}}
                assert len(results) == 2
                assert all(message.get("status") != "error" for message in results.values())
                assert any("ALPHA" in str(message["content"]) for message in results.values())
                assert any("BETA" in str(message["content"]) for message in results.values())
                assert not any(message.get("name") == "read_file" for message in messages)
                refreshed = client.get(f"/api/langgraph/threads/{thread_id}/state").json()
                assert refreshed["checkpoint"] == state["checkpoint"]
                print("two child results and root isolation verified", flush=True)
            else:
                assert "dear-platform-ok" in str(messages[-1])
        finally:
            assert client.patch(f"/api/runtime/models/{model_id}", json={"enabled": False}).status_code == 200


def test_completed_research_delivery():
    """Read-only recheck of a retained deployment after the polling client stopped."""
    identifiers = os.environ.get("DEAR_COMPLETED_RESEARCH")
    if not identifiers:
        pytest.skip("DEAR_COMPLETED_RESEARCH=project_id,thread_id,final_run_id enables read-only verification")
    project_id, thread_id, run_id = identifiers.split(",")
    with httpx.Client(base_url="http://127.0.0.1:2142", timeout=45, trust_env=False) as client:
        login = client.post("/api/identity/session", json={"username": "admin", "password": "admin123456"})
        assert login.status_code == 200
        client.headers.update({"Authorization": "Bearer " + login.json()["tokens"]["access_token"],
                               "X-Project-Id": project_id})
        root = f"/api/langgraph/threads/{thread_id}"
        assert client.get(root + "/runs/" + run_id).json()["status"] == "success"
        state = client.get(root + "/state").json()
        assert not state.get("next")
        messages = state["values"]["messages"]
        names = {message.get("name") for message in messages}
        assert {"request_information", "write_todos", "search_web", "fetch_page", "write_file", "present_artifacts"} <= names
        publication = next(message for message in reversed(messages) if message.get("name") == "present_artifacts")
        ref = json.loads(publication["content"])
        download = client.get(root + "/files/content", params={"path": ref["path"]})
        assert download.status_code == 200
        assert hashlib.sha256(download.content).hexdigest() == ref["sha256"]
        assert b"DEAR-P2-QUEUE-VERIFIED" in download.content
        source = next(message for message in reversed(messages)
                      if message.get("name") == "fetch_page" and message.get("artifact"))["artifact"]["sources"][0]
        assert source["thread_id"] == thread_id
        assert source["source_url"].encode() in download.content
        receipts = client.get(root + "/messages").json()["messages"]
        assert len(receipts) == 1 and receipts[0]["status"] == "consumed"
        assert sum(message.get("id") == receipts[0]["message_id"] for message in messages) == 1
