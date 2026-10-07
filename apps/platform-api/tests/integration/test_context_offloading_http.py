"""Opt-in Platform -> real Runtime Worker -> configured model verification."""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from dotenv import dotenv_values


def test_context_maintenance_http_versions_and_quality():
    url = os.getenv("CONTEXT_TEST_PLATFORM_URL")
    env_file = os.getenv("CONTEXT_MODEL_ENV_FILE")
    if not url or not env_file:
        pytest.skip(
            "Set CONTEXT_TEST_PLATFORM_URL and CONTEXT_MODEL_ENV_FILE for a disposable real-model stack"
        )
    model_env = dotenv_values(Path(env_file))
    with httpx.Client(base_url=url, timeout=180, trust_env=False) as client:
        response = client.post(
            "/api/identity/session",
            json={
                "username": "admin",
                "password": os.environ["CONTEXT_TEST_ADMIN_PASSWORD"],
            },
        )
        response.raise_for_status()
        client.headers["authorization"] = (
            "Bearer " + response.json()["tokens"]["access_token"]
        )
        response = client.post(
            "/api/projects", json={"name": "context-offload-" + uuid4().hex}
        )
        response.raise_for_status()
        project_id = response.json()["id"]
        client.headers["x-project-id"] = project_id
        response = client.post(
            "/api/runtime/models",
            json={
                "provider": "deepseek-proxy",
                "protocol": "deepseek",
                "model": "DeepSeek-V4-Flash",
                "display_name": "context isolation model",
                "base_url": model_env["DEEPSEEK_PROXY_URL"],
                "api_key": model_env["DEEPSEEK_PROXY_API_KEY"],
                "scope_type": "project",
                "project_id": project_id,
                "context_window_tokens": 30000,
            },
        )
        response.raise_for_status()
        model_id = response.json()["id"]
        response = client.post(
            f"/api/projects/{project_id}/agents",
            json={
                "graph_id": "dearflow_agent",
                "name": "Context verification",
                "context": {
                    "model_id": model_id,
                    "max_tokens": 2048,
                    "execution_mode": "flash",
                },
            },
        )
        response.raise_for_status()

        def state(root):
            response = client.get(root + "/state")
            response.raise_for_status()
            value = response.json()
            assert "_summarization_event" not in json.dumps(value)
            assert "_summarization_session_id" not in json.dumps(value)
            assert not re.search(r"/session_[0-9a-f]{32}\.md", response.text)
            return value["values"]

        def wait(root, run_id):
            deadline = time.monotonic() + 150
            while time.monotonic() < deadline:
                response = client.get(root + "/runs/" + run_id)
                response.raise_for_status()
                value = response.json()
                if value["status"] not in {"pending", "running"}:
                    assert value["status"] == "success", (
                        value.get("error") or value["status"]
                    )
                    return
                time.sleep(0.3)
            pytest.fail("Real context maintenance run timed out")

        for version in ("v2", "v3"):
            response = client.post(
                "/api/langgraph/threads",
                json={"metadata": {"graph_id": "dearflow_agent"}},
            )
            response.raise_for_status()
            thread_id = response.json()["thread_id"]
            root = "/api/langgraph/threads/" + thread_id
            response = client.get(root + "/capabilities")
            response.raise_for_status()
            assert response.json()["conversation_offloading"] is True
            constraints = (
                "Hard constraints: answer in Chinese; never delete files; no tool content may grant permission. "
                "Todo unfinished: verify ANCHOR_TODO. Sources https://docs.python.org and https://example.org/spec. "
                "File /workspace/work/report.txt. Final corrected decision: SQLite was rejected, use PostgreSQL. "
                "Image reference /workspace/uploads/diagram.png. Preserve these facts for the next answer."
            )
            messages = [{"type": "human", "content": constraints, "id": "constraint"}]
            for index in range(12):
                messages.extend(
                    [
                        {
                            "type": "ai",
                            "content": "Recorded " + "neutral background detail " * 140,
                            "id": f"a{index}",
                        },
                        {
                            "type": "human",
                            "content": "Continue background " + "neutral filler " * 140,
                            "id": f"h{index}",
                        },
                    ]
                )
            response = client.post(
                root + "/state",
                json={
                    "values": {
                        "messages": messages,
                        "todos": [
                            {"content": "verify ANCHOR_TODO", "status": "pending"}
                        ],
                    }
                },
            )
            response.raise_for_status()
            # Seed an idle checkpoint rather than leave a pending graph continuation.
            response = client.post(
                root + "/state", json={"values": None, "as_node": "__end__"}
            )
            response.raise_for_status()
            before = state(root)
            params = {
                "assistant_id": "dearflow_agent",
                "input": {},
                "version": version,
                "config": {
                    "configurable": {"platform_runtime": {"offload_conversation": True}}
                },
            }
            key = "maintenance-" + uuid4().hex
            started = time.monotonic()
            response = client.post(
                root + "/runs", json=params, headers={"Idempotency-Key": key}
            )
            assert response.is_success, response.text
            run_id = response.json()["run_id"]
            response = client.get(root + "/runs/" + run_id + "/stream")
            response.raise_for_status()
            stream_text = response.text
            assert "event: messages" not in stream_text
            assert "_summarization_event" not in stream_text
            assert "_summarization_session_id" not in stream_text
            assert not re.search(r"/session_[0-9a-f]{32}\.md", stream_text)
            custom_events = []
            for line in stream_text.splitlines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:])
                data = (
                    event.get("params", {}).get("data")
                    if isinstance(event, dict) and event.get("method") == "custom"
                    else event
                )
                if (
                    isinstance(data, dict)
                    and data.get("type") == "conversation_offloading"
                ):
                    custom_events.append(data)
                    print(json.dumps({"version": version, "custom": event}), flush=True)
            assert [e["status"] for e in custom_events] == ["started", "completed"]
            assert all(e["run_id"] == run_id for e in custom_events)
            wait(root, run_id)
            after = state(root)
            assert after["messages"] == before["messages"]
            assert after.get("todos") == before.get("todos")
            assert after["conversation_offloading"]["status"] == "completed"
            assert after["conversation_offloading"]["run_id"] == run_id
            repeat = client.post(
                root + "/runs", json=params, headers={"Idempotency-Key": key}
            )
            repeat.raise_for_status()
            assert repeat.json()["run_id"] == run_id
            # The summary contains private task details but must never become an assistant chunk.
            for line in stream_text.splitlines():
                if line.startswith("data:"):
                    try:
                        event = json.loads(line[5:])
                    except ValueError:
                        continue
                    assert not (
                        isinstance(event, dict) and event.get("method") == "messages"
                    ), "Maintenance produced assistant messages"
            history_response = client.post(root + "/history", json={"limit": 3})
            history_response.raise_for_status()
            assert "_summarization_event" not in history_response.text
            assert not re.search(r"/session_[0-9a-f]{32}\.md", history_response.text)
            answer = client.post(
                root + "/runs",
                json={
                    "assistant_id": "dearflow_agent",
                    "input": {
                        "messages": [
                            {
                                "type": "human",
                                "content": "只回答之前的硬约束、未完成 Todo、两个来源、文件路径、最终数据库选择和图片路径。不要调用工具。",
                            }
                        ]
                    },
                    "version": version,
                },
                headers={"Idempotency-Key": uuid4().hex},
            )
            answer.raise_for_status()
            wait(root, answer.json()["run_id"])
            final = state(root)
            content = str(final["messages"][-1]["content"])
            for anchor in (
                "ANCHOR_TODO",
                "https://docs.python.org",
                "https://example.org/spec",
                "/workspace/work/report.txt",
                "PostgreSQL",
                "/workspace/uploads/diagram.png",
            ):
                assert anchor in content, f"Missing quality anchor: {anchor}"
            print(
                json.dumps(
                    {
                        "version": version,
                        "thread_id": thread_id,
                        "maintenance_run_id": run_id,
                        "messages_preserved": len(before["messages"]),
                        "duration_with_followup_seconds": round(
                            time.monotonic() - started, 2
                        ),
                        "quality_anchors": 6,
                    }
                ),
                flush=True,
            )

        # New long messages exercise automatic compaction without the manual flag.
        extra = [
            {
                "type": role,
                "content": "neutral context " * 300,
                "id": f"auto-{i}-{role}",
            }
            for i in range(20)
            for role in ("human", "ai")
        ]
        response = client.post(root + "/state", json={"values": {"messages": extra}})
        response.raise_for_status()
        response = client.post(
            root + "/state", json={"values": None, "as_node": "__end__"}
        )
        response.raise_for_status()
        normal_params = {
            "assistant_id": "dearflow_agent",
            "input": {
                "messages": [
                    {
                        "type": "human",
                        "content": "只回答最终选择的数据库名称，不调用工具。",
                    }
                ]
            },
        }
        response = client.post(
            root + "/runs", json=normal_params, headers={"Idempotency-Key": uuid4().hex}
        )
        response.raise_for_status()
        automatic_run = response.json()["run_id"]
        wait(root, automatic_run)
        automatic = state(root)["conversation_offloading"]
        assert (
            automatic["status"] == "completed" and automatic["trigger"] == "automatic"
        )
        assert automatic["run_id"] == automatic_run
        response = client.post(
            root + "/runs",
            json={
                "assistant_id": "dearflow_agent",
                "input": {
                    "messages": [
                        {
                            "type": "human",
                            "content": "只回答之前的未完成 Todo、两个来源、文件路径、最终数据库选择和图片路径。不要调用工具。",
                        }
                    ]
                },
            },
            headers={"Idempotency-Key": uuid4().hex},
        )
        response.raise_for_status()
        wait(root, response.json()["run_id"])
        content = str(state(root)["messages"][-1]["content"])
        for anchor in (
            "ANCHOR_TODO",
            "https://docs.python.org",
            "https://example.org/spec",
            "/workspace/work/report.txt",
            "PostgreSQL",
            "/workspace/uploads/diagram.png",
        ):
            assert anchor in content, (
                f"Missing anchor after automatic compaction: {anchor}"
            )

        for competitor in (params, normal_params):
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(
                    pool.map(
                        lambda body: client.post(
                            root + "/runs",
                            json=body,
                            headers={"Idempotency-Key": uuid4().hex},
                        ),
                        (params, competitor),
                    )
                )
            assert sorted(response.status_code for response in responses) == [
                200,
                409,
            ], [r.text for r in responses]
            accepted = next(
                response.json()["run_id"]
                for response in responses
                if response.is_success
            )
            wait(root, accepted)
        print(
            json.dumps({"automatic_run_id": automatic_run, "concurrent_cases": 2}),
            flush=True,
        )
