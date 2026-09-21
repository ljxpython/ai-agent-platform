"""Opt-in real artifact delivery; retain synthetic projects for frontend handoff."""
import hashlib
import json
import os
import secrets
import time
from uuid import uuid4

import httpx
import pytest


def test_real_artifact_delivery():
    if os.environ.get("DEAR_ARTIFACT_PLATFORM_TEST") != "1":
        pytest.skip("Opt in to local test projects/user creation and real model usage")
    with httpx.Client(base_url="http://127.0.0.1:2142", timeout=45, trust_env=False) as client:
        def request(method, path, *, expected=200, **kwargs):
            response = client.request(method, path, **kwargs)
            assert response.status_code == expected, (method, path, response.status_code)
            return response

        login = request("POST", "/api/identity/session", json={
            "username": "admin", "password": "admin123456",
        })
        client.headers["Authorization"] = "Bearer " + login.json()["tokens"]["access_token"]
        suffix = uuid4().hex[:10]
        projects = [request("POST", "/api/projects", json={
            "name": f"artifact-handoff-{suffix}-{name}",
        }).json()["id"] for name in ("a", "b")]
        client.headers["X-Project-Id"] = projects[0]
        request("POST", f"/api/projects/{projects[0]}/agents", json={
            "graph_id": "dearflow_agent", "name": "Artifact handoff", "context": {},
        })
        thread = request("POST", "/api/langgraph/threads", json={
            "graph_id": "dearflow_agent", "metadata": {"harness": "artifact-handoff"},
        }).json()["thread_id"]
        root = f"/api/langgraph/threads/{thread}"
        assert request("GET", root + "/capabilities").json()["workspace"] is True
        assert request("GET", root + "/artifacts").json()["items"] == []
        models = request("GET", "/api/runtime/models").json()["models"]
        model = next(m for m in models if m["enabled"] and m["model"] == "DeepSeek-V4-Flash")
        prompt = (
            "这是合成成果验收。仅用 write_file 分别写两个文件："
            "/workspace/work/report.md 内容为 '# report\\n'（实际换行），"
            "/workspace/work/data.csv 内容为 'name,value\\nsample,1\\n'（实际换行）。"
            "再分别调用 present_artifacts 发布这两个文件，然后结束。"
            "不要搜索、执行命令、委派、读取技能、询问用户或改其他文件。"
        )
        run = request("POST", root + "/runs", json={
            "assistant_id": "dearflow_agent", "context": {"model_id": model["id"]},
            "input": {"messages": [{"role": "user", "content": prompt}]},
        }).json()["run_id"]
        print(json.dumps({"projects": projects, "thread": thread, "initial_run": run}), flush=True)
        runs = [run]
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            status = request("GET", root + "/runs/" + run).json()["status"]
            if status == "interrupted":
                state = request("GET", root + "/state").json()
                interrupts = state.get("interrupts") or [
                    i for task in state.get("tasks", []) for i in task.get("interrupts", [])
                ]
                if isinstance(interrupts, dict):
                    interrupts = [{"id": key, "value": value.get("value", value)}
                                  for key, value in interrupts.items()]
                assert interrupts
                resumes = {}
                for item in interrupts:
                    actions = item["value"]["action_requests"]
                    for action in actions:
                        assert action["name"] in {"write_file", "present_artifacts"}
                        assert action["args"]["file_path"] in {
                            "/workspace/work/report.md", "/workspace/work/data.csv",
                        }
                    resumes[item["id"]] = {"decisions": [{"type": "approve"} for _ in actions]}
                run = request("POST", root + "/runs", json={"command": {"resume": resumes}}).json()["run_id"]
                runs.append(run)
            elif status in {"success", "completed"}:
                break
            else:
                assert status in {"pending", "running"}, status
            time.sleep(1)
        else:
            pytest.fail("Real Dear artifact run exceeded 300 seconds")
        messages = request("GET", root + "/state").json()["values"]["messages"]
        refs = [json.loads(m["content"]) for m in messages if m.get("name") == "present_artifacts"]
        page = request("GET", root + "/artifacts").json()
        assert len(refs) == len(page["items"]) == 2
        assert {r["path"] for r in refs} == {r["path"] for r in page["items"]}
        for ref in refs:
            preview = request("GET", root + "/workspace/preview", params={"path": ref["path"]})
            assert preview.json()["sha256"] == ref["sha256"]
            download = request("GET", root + "/workspace/content", params={"path": ref["path"]})
            assert hashlib.sha256(download.content).hexdigest() == ref["sha256"]
            assert download.headers["content-disposition"].startswith("attachment")
            assert download.headers["x-content-type-options"] == "nosniff"
            assert download.headers["cache-control"] == "private, no-store"
        del client.headers["X-Project-Id"]
        missing = request("GET", root + "/artifacts", expected=400).json()
        assert missing["error"]["code"] == "project_id_required"
        client.headers["X-Project-Id"] = projects[1]
        # The deployed Agent Server hides threads outside the forwarded project
        # before Platform's own thread_project_denied guard can see metadata.
        cross = request("GET", root + "/artifacts", expected=404).json()
        assert cross["error"]["code"] == "langgraph_thread_get_failed"
        password = secrets.token_urlsafe(24)
        username = "artifact-nonmember-" + suffix
        request("POST", "/api/users", json={"username": username, "password": password})
        restricted = request("POST", "/api/identity/session", json={"username": username, "password": password})
        client.headers.update({"Authorization": "Bearer " + restricted.json()["tokens"]["access_token"],
                               "X-Project-Id": projects[0]})
        denied = request("GET", root + "/artifacts", expected=403).json()
        print(json.dumps({"projects": projects, "thread": thread, "runs": runs,
                          "artifacts": page, "missing_project": missing,
                          "cross_project": cross, "nonmember": denied,
                          "retained_nonmember": username}, ensure_ascii=False), flush=True)
