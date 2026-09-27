import hashlib
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from platform_api.adapters.langgraph.sdk_client import create_runtime_upstream_error
from platform_api.config import Settings
from platform_api.main import create_app


class ErrorResponseContractTest(unittest.TestCase):
    def test_unexpected_error_keeps_json_cors_and_request_id(self):
        settings = Settings(
            platform_db_enabled=False,
            auth_required=False,
            cors_allow_origins=("http://127.0.0.1:3000",),
        )
        with patch("platform_api.main.load_settings", return_value=settings):
            app = create_app()

        @app.get("/__error_contract_failure")
        def failure():
            raise RuntimeError("private-token-marker")

        @app.get("/__error_contract_success")
        def success():
            return {"ok": True}

        @app.get("/__error_contract_upstream")
        def upstream():
            raise create_runtime_upstream_error(
                status_code=401,
                detail={
                    "error": {
                        "code": "invalid_token",
                        "message": "private-token-marker",
                    }
                },
                fallback_code="thread_get_failed",
            )

        client = TestClient(app, raise_server_exceptions=False)
        headers = {"Origin": "http://127.0.0.1:3000"}
        with self.assertLogs(
            "platform_api.core.errors.handlers", level="ERROR"
        ) as logs:
            failed = client.get("/__error_contract_failure", headers=headers)
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(
            failed.json()["error"],
            {
                "code": "internal_server_error",
                "message": "Internal server error",
                "details": [],
            },
        )
        self.assertEqual(failed.json()["request_id"], failed.headers["x-request-id"])
        self.assertEqual(
            failed.headers["access-control-allow-origin"], headers["Origin"]
        )
        self.assertNotIn("private-token-marker", failed.text + str(logs.output))
        healthy = client.get("/__error_contract_success", headers=headers)
        self.assertEqual(healthy.status_code, 200)
        self.assertNotEqual(
            healthy.headers["x-request-id"], failed.headers["x-request-id"]
        )
        rejected = client.get("/__error_contract_upstream", headers=headers)
        self.assertEqual(rejected.status_code, 502)
        self.assertEqual(
            rejected.json()["error"]["code"], "runtime_delegation_rejected"
        )
        self.assertEqual(rejected.json()["error"]["extra"]["upstream_status_code"], 401)
        self.assertEqual(
            rejected.json()["request_id"], rejected.headers["x-request-id"]
        )
        self.assertNotIn("private-token-marker", rejected.text)

    @unittest.skipUnless(
        os.getenv("PLATFORM_ERROR_CONTRACT_REAL") == "1",
        "requires the existing local stack and Langfuse export",
    )
    def test_real_submission_run_audit_and_observation(self):
        platform = dotenv_values("apps/platform-api/.env")
        runtime = dotenv_values("apps/runtime-service/.env")
        self.assertEqual(runtime.get("LANGFUSE_ENABLED"), "true")
        marker = f"error-contract-{uuid4().hex[:12]}"
        with httpx.Client(base_url="http://127.0.0.1:2142", timeout=60) as client:
            login = client.post(
                "/api/identity/session",
                json={
                    "username": platform["PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME"],
                    "password": platform["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"],
                },
            )
            self.assertEqual(login.status_code, 200)
            token = login.json()["tokens"]["access_token"]
            auth = {"authorization": f"Bearer {token}"}
            created = client.post("/api/projects", headers=auth, json={"name": marker})
            self.assertEqual(created.status_code, 200)
            project_id = created.json()["id"]
            headers = {**auth, "x-project-id": project_id}
            thread_id = None
            workspace_thread_id = None
            peer_user_id = None
            peer_member_added = False
            try:
                refreshed = client.post(
                    "/api/runtime/graphs/refresh", headers=headers, json={}
                )
                self.assertEqual(refreshed.status_code, 200)
                models = client.get("/api/runtime/models", headers=headers)
                self.assertEqual(models.status_code, 200)
                model = next(
                    item for item in models.json()["models"] if item.get("enabled")
                )
                agent = client.post(
                    f"/api/projects/{project_id}/agents",
                    headers=headers,
                    json={
                        "graph_id": "reference_agent",
                        "name": marker,
                        "context": {"model_id": model["id"]},
                    },
                )
                self.assertEqual(agent.status_code, 200)
                showcase_agent = client.post(
                    f"/api/projects/{project_id}/agents",
                    headers=headers,
                    json={
                        "graph_id": "showcase_demo",
                        "name": marker + "-showcase",
                        "context": {"model_id": model["id"]},
                    },
                )
                self.assertEqual(showcase_agent.status_code, 200)
                dear_agent = client.post(
                    f"/api/projects/{project_id}/agents",
                    headers=headers,
                    json={
                        "graph_id": "dearflow_agent",
                        "name": marker + "-dear",
                        "context": {"model_id": model["id"]},
                    },
                )
                self.assertEqual(dear_agent.status_code, 200)
                memory = client.get("/api/langgraph/dear/memory", headers=headers)
                self.assertEqual(memory.status_code, 200)
                memory_status = memory.json()["status"]
                if memory_status == "ready":
                    conflict = client.post(
                        "/api/langgraph/dear/memory",
                        headers=headers,
                        json={
                            "action": "clear",
                            "expected_revision": memory.json()["document"]["revision"]
                            + 1,
                        },
                    )
                    self.assertEqual(conflict.status_code, 409)
                    self.assertEqual(
                        conflict.json()["error"]["code"], "memory_revision_conflict"
                    )
                    self.assertEqual(
                        conflict.json()["request_id"], conflict.headers["x-request-id"]
                    )
                thread = client.post(
                    "/api/langgraph/threads",
                    headers=headers,
                    json={
                        "graph_id": "reference_agent",
                        "metadata": {"harness": marker},
                    },
                )
                self.assertEqual(thread.status_code, 200)
                thread_id = thread.json()["thread_id"]
                owned = client.get(
                    f"/api/langgraph/threads/{thread_id}", headers=headers
                )
                self.assertEqual(owned.status_code, 200)

                workspace_thread = client.post(
                    "/api/langgraph/threads",
                    headers=headers,
                    json={
                        "graph_id": "showcase_demo",
                        "metadata": {"harness": marker + "-workspace"},
                    },
                )
                self.assertEqual(workspace_thread.status_code, 200)
                workspace_thread_id = workspace_thread.json()["thread_id"]
                content = b"error-response-workspace-proof\n"
                digest = hashlib.sha256(content).hexdigest()
                uploaded = client.put(
                    f"/api/langgraph/threads/{workspace_thread_id}/files/uploads/{digest}",
                    headers={**headers, "content-type": "text/plain"},
                    content=content,
                )
                self.assertEqual(uploaded.status_code, 200)
                workspace_path = uploaded.json()["path"]
                downloaded = client.get(
                    f"/api/langgraph/threads/{workspace_thread_id}/files/content",
                    headers=headers,
                    params={"path": workspace_path},
                )
                self.assertEqual(downloaded.status_code, 200)
                self.assertEqual(downloaded.content, content)
                unavailable = client.get(
                    f"/api/langgraph/threads/{workspace_thread_id}/workspace/content",
                    headers=headers,
                    params={"path": "/workspace/work/not-found.txt"},
                )
                self.assertEqual(unavailable.status_code, 404)
                self.assertEqual(
                    unavailable.json()["error"]["code"], "workspace_file_unavailable"
                )
                self.assertEqual(
                    unavailable.json()["request_id"],
                    unavailable.headers["x-request-id"],
                )

                peer_password = "ErrorPeer123456"
                peer = client.post(
                    "/api/users",
                    headers=auth,
                    json={"username": marker + "-peer", "password": peer_password},
                )
                self.assertEqual(peer.status_code, 200)
                peer_user_id = peer.json()["id"]
                membership = client.put(
                    f"/api/projects/{project_id}/members/{peer_user_id}",
                    headers=headers,
                    json={"role": "project_executor"},
                )
                self.assertEqual(membership.status_code, 200)
                peer_member_added = True
                peer_login = client.post(
                    "/api/identity/session",
                    json={"username": marker + "-peer", "password": peer_password},
                )
                self.assertEqual(peer_login.status_code, 200)
                peer_headers = {
                    "authorization": "Bearer "
                    + peer_login.json()["tokens"]["access_token"],
                    "x-project-id": project_id,
                }
                peer_denied = client.get(
                    f"/api/langgraph/threads/{thread_id}",
                    headers=peer_headers,
                )
                self.assertEqual(peer_denied.status_code, 403)
                self.assertEqual(
                    peer_denied.json()["error"]["code"], "thread_action_denied"
                )
                self.assertEqual(
                    peer_denied.json()["request_id"],
                    peer_denied.headers["x-request-id"],
                )

                denied = client.get(
                    f"/api/langgraph/threads/{uuid4()}",
                    headers=headers,
                )
                self.assertEqual(denied.status_code, 403)
                self.assertEqual(
                    denied.json()["request_id"], denied.headers["x-request-id"]
                )
                stream_denied = client.post(
                    f"/api/langgraph/threads/{uuid4()}/stream/events",
                    headers=headers,
                    json={},
                )
                self.assertEqual(stream_denied.status_code, 403)
                self.assertNotIn(
                    "text/event-stream", stream_denied.headers["content-type"]
                )
                self.assertEqual(
                    stream_denied.json()["request_id"],
                    stream_denied.headers["x-request-id"],
                )

                payload = {
                    "assistant_id": "reference_agent",
                    "input": {
                        "messages": [
                            {"role": "user", "content": "Reply exactly: local-l2-ok"}
                        ]
                    },
                    "durability": "sync",
                    "stream_resumable": True,
                }
                key = marker + "-run"
                first = client.post(
                    f"/api/langgraph/threads/{thread_id}/runs",
                    headers={**headers, "Idempotency-Key": key},
                    json=payload,
                )
                self.assertEqual(first.status_code, 200)
                second = client.post(
                    f"/api/langgraph/threads/{thread_id}/runs",
                    headers={**headers, "Idempotency-Key": key},
                    json=payload,
                )
                self.assertEqual(second.status_code, 200)
                run_id = first.json()["run_id"]
                self.assertEqual(second.json()["run_id"], run_id)
                request_ids = [
                    first.headers["x-request-id"],
                    second.headers["x-request-id"],
                ]
                self.assertNotEqual(*request_ids)

                for _ in range(30):
                    run = client.get(
                        f"/api/langgraph/threads/{thread_id}/runs/{run_id}",
                        headers=headers,
                    )
                    self.assertEqual(run.status_code, 200)
                    if run.json()["status"] in {"success", "error", "cancelled"}:
                        break
                    time.sleep(2)
                self.assertEqual(run.json()["status"], "success")

                audit = []
                for _ in range(15):
                    audit = [
                        client.get(
                            "/api/audit",
                            headers=auth,
                            params={"project_id": project_id, "request_id": request_id},
                        ).json()
                        for request_id in request_ids
                    ]
                    if all(item["total"] == 1 for item in audit):
                        break
                    time.sleep(1)
                self.assertTrue(all(item["total"] == 1 for item in audit))
                metadata = [item["items"][0]["metadata"] for item in audit]
                self.assertEqual({item["run_id"] for item in metadata}, {run_id})
                self.assertEqual(len({item["submission_id"] for item in metadata}), 1)
                self.assertEqual({item["thread_id"] for item in metadata}, {thread_id})

                log_path = (
                    Path(os.environ.get("TMPDIR", "/tmp"))
                    / "aitestlab-local-stack/logs/platform-api.log"
                )
                log_offset = log_path.stat().st_size
                with client.stream(
                    "GET",
                    f"/api/langgraph/threads/{thread_id}/runs/{run_id}/stream",
                    headers=headers,
                    params={"stream_mode": "values"},
                ) as stream:
                    self.assertEqual(stream.status_code, 200)
                    stream_request_id = stream.headers["x-request-id"]
                    self.assertTrue(
                        any(line.startswith("data:") for line in stream.iter_lines())
                    )
                for _ in range(10):
                    stream_log = log_path.read_text()[log_offset:]
                    events = [
                        line
                        for line in stream_log.splitlines()
                        if f'"request_id": "{stream_request_id}"' in line
                        and f'"run_id": "{run_id}"' in line
                    ]
                    if all(
                        any(
                            f'"event": "runtime.stream.{event}"' in line
                            for line in events
                        )
                        for event in ("opened", "closed")
                    ):
                        break
                    time.sleep(1)
                self.assertTrue(
                    any('"event": "runtime.stream.opened"' in line for line in events)
                )
                self.assertTrue(
                    any('"event": "runtime.stream.closed"' in line for line in events)
                )

                with httpx.Client(
                    base_url=runtime["LANGFUSE_BASE_URL"],
                    auth=(
                        runtime["LANGFUSE_PUBLIC_KEY"],
                        runtime["LANGFUSE_SECRET_KEY"],
                    ),
                    timeout=20,
                ) as observation:
                    for _ in range(15):
                        traces = observation.get(
                            "/api/public/traces", params={"sessionId": thread_id}
                        )
                        self.assertEqual(traces.status_code, 200)
                        matched = [
                            item
                            for item in traces.json()["data"]
                            if item.get("metadata", {}).get("request_id") in request_ids
                        ]
                        if matched:
                            break
                        time.sleep(2)
                self.assertTrue(
                    matched, "no exported trace matches either submission request"
                )
                print(
                    {
                        "project_id": project_id,
                        "thread_id": thread_id,
                        "run_id": run_id,
                        "request_ids": request_ids,
                        "stream_request_id": stream_request_id,
                        "memory_status": memory_status,
                        "submission_id": metadata[0]["submission_id"],
                        "langfuse_trace_ids": [item["id"] for item in matched],
                    }
                )
            finally:
                deleted_thread = (
                    client.delete(
                        f"/api/langgraph/threads/{thread_id}", headers=headers
                    )
                    if thread_id
                    else None
                )
                deleted_workspace_thread = (
                    client.delete(
                        f"/api/langgraph/threads/{workspace_thread_id}", headers=headers
                    )
                    if workspace_thread_id
                    else None
                )
                if peer_member_added:
                    removed_member = client.delete(
                        f"/api/projects/{project_id}/members/{peer_user_id}",
                        headers=headers,
                    )
                    self.assertEqual(removed_member.status_code, 200)
                if peer_user_id:
                    disabled_peer = client.patch(
                        f"/api/users/{peer_user_id}",
                        headers=auth,
                        json={"status": "disabled"},
                    )
                    self.assertEqual(disabled_peer.status_code, 200)
                deleted = client.delete(f"/api/projects/{project_id}", headers=auth)
                if deleted_thread is not None:
                    self.assertEqual(deleted_thread.status_code, 200)
                if deleted_workspace_thread is not None:
                    self.assertEqual(deleted_workspace_thread.status_code, 200)
                self.assertEqual(deleted.status_code, 200)


if __name__ == "__main__":
    unittest.main()
