"""Opt-in real models on the registered Worktree stack; never starts shared services."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from workspace.test_office_documents import docx_bytes, pptx_bytes, replace_member

from runtime_service.workspace.document_reader import DOCX_MIME, PPTX_MIME


@pytest.mark.skipif(
    os.getenv("OFFICE_PLATFORM_LIVE") != "1",
    reason="requires this Worktree's local-stack",
)
@pytest.mark.parametrize(
    "graph_id,mime,builder",
    [
        ("showcase_demo", DOCX_MIME, docx_bytes),
        ("dearflow_agent", PPTX_MIME, pptx_bytes),
    ],
    ids=["showcase-docx", "dearflow-pptx"],
)
def test_office_api_worker_docker_real_model(graph_id, mime, builder):
    repo = Path(__file__).resolve().parents[4]
    environment = json.loads((repo / ".local-stack/environment.json").read_text())
    assert Path(environment["root"]).resolve() == repo and environment["id"].startswith(
        "wt_"
    )
    output = repo / ".local-stack/evidence/office" / graph_id
    output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "environment": environment["id"],
        "graph": graph_id,
        "model_kind": "real",
        "runs": [],
    }
    started = time.monotonic()
    with httpx.Client(
        base_url=f"http://127.0.0.1:{environment['ports']['PLATFORM_API_PORT']}",
        trust_env=False,
        timeout=60,
    ) as client:

        def request(method, path, *, expected=200, **kwargs):
            for attempt in range(3):
                try:
                    response = client.request(method, path, **kwargs)
                    if (
                        method == "GET"
                        and response.status_code in {502, 503, 504}
                        and attempt < 2
                    ):
                        time.sleep(1)
                        continue
                    break
                except httpx.ReadTimeout:
                    if method != "GET" or attempt == 2:
                        raise
            assert response.status_code == expected, {
                "path": path,
                "status": response.status_code,
                "body": response.text[:1000],
            }
            return response

        login = request(
            "POST",
            "/api/identity/session",
            json={"username": "admin", "password": "admin123"},
        ).json()
        client.headers["authorization"] = "Bearer " + login["tokens"]["access_token"]
        project = request(
            "POST", "/api/projects", json={"name": "f10-" + uuid4().hex[:12]}
        ).json()["id"]
        client.headers["x-project-id"] = project
        evidence["project_id"] = project
        request("POST", "/api/runtime/graphs/refresh")
        models = request("GET", "/api/runtime/models").json()["models"]
        model = next(
            m
            for m in models
            if m["enabled"]
            and m["model"] == os.getenv("OFFICE_PLATFORM_MODEL", "deepseek-v4-flash")
        )
        evidence["model"] = model["model"]
        context = {
            "model_id": model["id"],
            "max_tokens": 2048,
            "execution_mode": "standard",
        }
        agent = request(
            "POST",
            f"/api/projects/{project}/agents",
            json={"graph_id": graph_id, "name": "f10-office", "context": context},
        ).json()
        thread = request(
            "POST",
            "/api/langgraph/threads",
            json={"graph_id": graph_id, "metadata": {"agent_id": agent["id"]}},
        ).json()["thread_id"]
        base = f"/api/langgraph/threads/{thread}"
        evidence["thread_id"] = thread
        marker = "OFFICE_VERIFIED_" + uuid4().hex[:10]
        raw = builder(marker + " Revenue 125 中文")
        digest = hashlib.sha256(raw).hexdigest()
        (output / ("sample.docx" if mime == DOCX_MIME else "sample.pptx")).write_bytes(
            raw
        )
        upload_start = time.monotonic()
        ref = request(
            "PUT",
            base + "/files/uploads/" + digest,
            content=raw,
            headers={"content-type": mime},
            params={"file_name": "source.docx" if mime == DOCX_MIME else "source.pptx"},
        ).json()
        evidence["upload_ms"] = round((time.monotonic() - upload_start) * 1000)
        evidence["file"] = ref
        assert set(ref) == {
            "version",
            "path",
            "file_name",
            "mime_type",
            "size_bytes",
            "sha256",
        }
        downloaded = request(
            "GET", base + "/files/content", params={"path": ref["path"]}
        )
        assert downloaded.content == raw and downloaded.headers["content-type"] == mime
        assert "attachment" in downloaded.headers["content-disposition"]
        assert downloaded.headers["cache-control"] == "private, no-store"
        assert downloaded.headers["x-content-type-options"] == "nosniff"
        invalid = replace_member(
            raw,
            "word/document.xml" if mime == DOCX_MIME else "ppt/presentation.xml",
            b"broken",
        )
        request(
            "PUT",
            base + "/files/uploads/" + hashlib.sha256(invalid).hexdigest(),
            content=invalid,
            headers={"content-type": mime},
            expected=422,
        )
        request(
            "PUT",
            base + "/files/uploads/" + "a" * 64,
            content=raw,
            headers={"content-type": mime},
            expected=400,
        )
        other = request(
            "POST", "/api/projects", json={"name": "f10-other-" + uuid4().hex[:12]}
        ).json()["id"]
        request(
            "GET",
            base + "/files/content",
            params={"path": ref["path"]},
            headers={"x-project-id": other},
            expected=403,
        )

        def read(target, attachment=None):
            source = attachment or ref
            before = request("GET", target + "/state").json()
            previous_calls = {
                message.get("tool_call_id")
                for message in (before.get("values") or {}).get("messages", [])
                if message.get("type") == "tool"
            }
            prompt = (
                "务必在本轮实际重新调用一次 parse_document，历史结果不算本次读取。读取 "
                + source["path"]
                + "，不要 query。不要调用其他工具，成功读取后只返回文档中的 OFFICE_VERIFIED 标记和 Revenue 数值。验收序号 "
                + uuid4().hex[:10]
            )
            content = [{"type": "text", "text": prompt}]
            if attachment:
                content.append(
                    {
                        "type": "text",
                        "text": "[文档附件] "
                        + attachment["file_name"]
                        + "\n"
                        + attachment["path"],
                        "extras": {"runtime_file": attachment},
                    }
                )
            run = request(
                "POST",
                target + "/commands",
                headers={"Idempotency-Key": "f10-" + uuid4().hex},
                json={
                    "id": 1,
                    "method": "run.start",
                    "params": {
                        "assistant_id": graph_id,
                        "context": context,
                        "input": {"messages": [{"role": "user", "content": content}]},
                    },
                },
            ).json()["result"]["run_id"]
            print(
                json.dumps(
                    {"graph": graph_id, "thread": target.rsplit("/", 1)[-1], "run": run}
                ),
                flush=True,
            )
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                snapshot = request("GET", target + "/runs/" + run).json()
                if snapshot["status"] in {"success", "error", "interrupted", "timeout"}:
                    break
                time.sleep(0.5)
            else:
                request(
                    "POST", target + "/runs/" + run + "/cancel", json={"wait": True}
                )
                pytest.fail("real Office run exceeded 240s")
            assert snapshot["status"] == "success", {
                "run_id": run,
                "status": snapshot["status"],
                "reason": snapshot.get("reason"),
            }
            state = request("GET", target + "/state").json()
            messages = state["values"]["messages"]
            tool = next(
                m
                for m in reversed(messages)
                if m.get("type") == "tool"
                and m.get("name") == "parse_document"
                and m.get("tool_call_id") not in previous_calls
            )
            assert tool.get("status", "success") == "success", tool
            body = json.loads(tool["content"])
            assert marker in body["text"] and "125" in body["text"]
            assert (
                body["file"]["sha256"] == source["sha256"]
                and len(body["text"]) <= 12000
            )
            assert body["read_range"] == [1, 1] and body["next_read"] is None
            assert (
                body["chunks"][0].get("section" if mime == DOCX_MIME else "page") == 1
            )
            assert any(
                call["id"] == tool["tool_call_id"]
                for message in messages
                for call in message.get("tool_calls", [])
            )
            evidence["runs"].append(
                {
                    "run_id": run,
                    "status": snapshot["status"],
                    "result": body,
                    "tool_call_id": tool["tool_call_id"],
                }
            )
            return state

        state = read(base, ref)
        assert any(
            block.get("extras", {}).get("runtime_file") == ref
            for message in state["values"]["messages"]
            for block in message.get("content", [])
            if isinstance(block, dict)
        )
        history = request("POST", base + "/history", json={"limit": 20}).json()
        assert digest in json.dumps(history)
        if graph_id == "showcase_demo":
            restarted = subprocess.run(
                [
                    "bash",
                    str(repo / "scripts/local-stack.sh"),
                    "restart-one",
                    "runtime-worker",
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert restarted.returncode == 0, (
                "owned Worker restart failed; inspect local-stack logs"
            )
            assert (
                request(
                    "GET", base + "/files/content", params={"path": ref["path"]}
                ).content
                == raw
            )
            evidence["worker_restart"] = True
        second_raw = builder("Second upload " + marker + " Revenue 125 中文")
        second_digest = hashlib.sha256(second_raw).hexdigest()
        second_ref = request(
            "PUT",
            base + "/files/uploads/" + second_digest,
            content=second_raw,
            headers={"content-type": mime},
            params={"file_name": "second.docx" if mime == DOCX_MIME else "second.pptx"},
        ).json()
        assert second_ref["path"] != ref["path"]
        assert (
            request(
                "GET", base + "/files/content", params={"path": ref["path"]}
            ).content
            == raw
        )
        state = read(base, second_ref)
        checkpoint = state["checkpoint"]["checkpoint_id"]
        fork = request(
            "POST",
            base + "/fork",
            json={"checkpoint_id": checkpoint, "title": "f10-office-fork"},
        ).json()["thread_id"]
        fork_base = "/api/langgraph/threads/" + fork
        fork_download = request(
            "GET",
            fork_base + "/files/content",
            params={"path": ref["path"]},
        )
        assert fork_download.content == raw
        read(fork_base)
        evidence["fork_thread_id"] = fork
        evidence["checks"] = {
            "original_bytes": True,
            "malformed_rejected": True,
            "hash_rejected": True,
            "cross_project_denied": True,
            "history_restored": True,
            "fork_authorized_workspace_copy": True,
            "second_upload_preserves_first": True,
        }
    evidence["duration_ms"] = round((time.monotonic() - started) * 1000)
    (output / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: evidence[key]
                for key in (
                    "environment",
                    "graph",
                    "model",
                    "thread_id",
                    "duration_ms",
                    "checks",
                )
            },
            ensure_ascii=False,
        )
    )
