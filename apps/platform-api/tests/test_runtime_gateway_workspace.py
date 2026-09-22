"""Workspace gateway contracts, plus real loopback HTTP to Runtime."""

import asyncio
import base64
import hashlib
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import jwt
import uvicorn
from fastapi import FastAPI
from tests.thread_acl_fixture import thread_acl_factory
from platform_api.adapters.langgraph.runtime_gateway_upstream import (
    LangGraphRuntimeGatewayUpstream,
)
from platform_api.modules.runtime_gateway.application.ports import BinaryPayload
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import register_exception_handlers
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_actor_context,
    get_runtime_gateway_service,
    router,
)

SECRET = "workspace-test-secret-with-at-least-32-bytes"


class WorkspaceGatewayTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        register_exception_handlers(self.app)
        self.actor = ActorContext(user_id="user-a", project_roles={"project-a": ("project_admin",)})
        self.upstream = Mock()
        self.upstream.get_thread = AsyncMock(
            return_value={
                "metadata": {"project_id": "project-a", "graph_id": "showcase_demo"}
            }
        )
        self.upstream.workspace_json = AsyncMock(
            return_value={"items": [], "next_cursor": None}
        )
        async def fake_zip_stream():
            yield b"PK\x03\x04mock-zip"

        self.upstream.workspace_zip = AsyncMock(
            return_value=BinaryPayload(
                body=fake_zip_stream(),
                content_type="application/zip",
                content_disposition="attachment; filename*=UTF-8''workspace-thread-1.zip",
            )
        )
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service = RuntimeGatewayService(
            session_factory=thread_acl_factory(self, actor=self.actor, project_id="project-a"),
            upstream=self.upstream,
            delegation_headers_factory=self.delegation,
        )
        self.service._prepare_project_scope = Mock()
        self.service._assistant_belongs_project = Mock(return_value=True)
        self.app.dependency_overrides[get_actor_context] = lambda: self.actor
        self.app.dependency_overrides[get_runtime_gateway_service] = lambda: (
            self.service
        )

        @self.app.middleware("http")
        async def scope(request, call_next):
            request.state.platform_context = SimpleNamespace(
                project=SimpleNamespace(project_id=request.headers.get("x-project-id"))
            )
            return await call_next(request)

    def delegation(self, *, project_id, agent_key, thread_id, context_hash, operation):
        now = int(time.time())
        claims = {
            "type": "runtime_delegation", "delegation_version": 2,
            "sub": "user-a",
            "tenant_id": "tenant-a",
            "project_id": project_id,
            "role": "developer",
            "permissions": ["runtime.tool.read", "runtime.tool.execute"],
            "policy_version": "test-1",
            "allowed_model_ids": ["deepseek:deepseek-chat"],
            "tool_overrides": {}, "tool_policy_version": "test-tools-v2",
            "iat": now,
            "exp": now + 60,
            "iss": "runtime-test",
            "aud": "runtime-service",
            "scope": {
                "tenant_id": "tenant-a",
                "project_id": project_id,
                "thread_id": thread_id,
                "assistant_id": agent_key,
                "operation": operation,
            },
            "context_hash": context_hash,
        }
        return {
            "authorization": "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")
        }

    async def test_routes_scope_paths_and_capability(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            prefix = "/api/langgraph/threads/thread-1"
            for route in ("/workspace/tree", "/artifacts", "/workspace/zip"):
                response = await client.get(
                    prefix + route, headers={"x-project-id": "project-a"}
                )
                self.assertEqual(response.status_code, 200, response.text)
            for path in (
                "/etc/passwd",
                "/workspace/../file",
                "/workspace/work/./file",
                "/workspace/work/file\n",
            ):
                response = await client.get(
                    prefix + "/workspace/content",
                    params={"path": path},
                    headers={"x-project-id": "project-a"},
                )
                self.assertEqual(response.status_code, 400)
            response = await client.get(
                prefix + "/artifacts", headers={"x-project-id": "other"}
            )
            self.assertEqual(response.status_code, 403)
            self.service._assistant_belongs_project.return_value = False
            response = await client.get(
                prefix + "/artifacts", headers={"x-project-id": "project-a"}
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"]["code"], "runtime_target_denied")

    async def test_artifact_request_boundaries_and_pagination(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            prefix = "/api/langgraph/threads/thread-1"
            response = await client.get(prefix + "/artifacts")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["error"]["code"], "project_id_required")
            self.upstream.workspace_json.assert_not_awaited()
            client.headers["x-project-id"] = "project-a"
            for params in ({"limit": 0}, {"limit": 201}, {"cursor": "x" * 8193}):
                response = await client.get(prefix + "/artifacts", params=params)
                self.assertEqual(response.status_code, 422)
            response = await client.get(prefix + "/workspace/preview")
            self.assertEqual(response.status_code, 422)
            self.upstream.workspace_json.assert_not_awaited()
            self.upstream.workspace_json.return_value = {
                "items": [{"path": "/workspace/outputs/test.md", "_runtime_private": "hidden"}],
                "next_cursor": "opaque",
            }
            response = await client.get(prefix + "/artifacts", params={"limit": 17, "cursor": "opaque"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"items": [{"path": "/workspace/outputs/test.md"}], "next_cursor": "opaque"})
            self.assertEqual(response.headers["cache-control"], "private, no-store")
            self.upstream.workspace_json.assert_awaited_once_with("thread-1", "artifacts", {"limit": 17, "cursor": "opaque"})

    async def test_real_two_service_http(self):
        await self._check_two_service_http("showcase_demo", terminal=True)

    async def test_dear_artifacts_two_service_http(self):
        await self._check_two_service_http("dearflow_agent", terminal=False)

    async def _check_two_service_http(self, graph, *, terminal):
        self.upstream.get_thread.return_value["metadata"]["graph_id"] = graph
        runtime_dir = Path(__file__).resolve().parents[2] / "runtime-service"
        interpreter = runtime_dir / ".venv/bin/python"
        self.assertTrue(
            interpreter.exists(), "Runtime venv is required for this integration test"
        )
        with tempfile.TemporaryDirectory(prefix="workspace-contract-") as directory:
            runtime_socket = socket.socket()
            runtime_socket.bind(("127.0.0.1", 0))
            runtime_socket.listen()
            runtime_port = runtime_socket.getsockname()[1]
            env = {
                **os.environ,
                "RUNTIME_SHOWCASE_WORKSPACE_ROOT": directory,
                "RUNTIME_WORKSPACE_ROOT": directory,
                "ARTIFACT_TEST_GRAPH": graph,
                "RUNTIME_SHOWCASE_BACKEND": "local",
                "RUNTIME_TERMINAL_ENABLED": "1",
                "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
                "PLATFORM_RUNTIME_DELEGATION_ISSUER": "runtime-test",
                "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
            }
            script = """
import sys, os, uvicorn
from runtime_service.workspace.scoped import resolve_thread_workspace
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
if len(sys.argv) > 2:
    root = resolve_thread_workspace('tenant-a', 'project-a', 'thread-1', os.environ['ARTIFACT_TEST_GRAPH'])
    (root / 'work').mkdir(parents=True)
    (root / 'work/payment.yaml').write_text('openapi: 3.1.0')
    (root / 'work/view.html').write_text('<h1>Architecture</h1><script>fetch(\"https://evil.test\")</script>')
    ArtifactWorkspace(root).publish('/workspace/work/payment.yaml')
uvicorn.run('runtime_service.webapp:app', fd=int(sys.argv[1]), log_level='error', lifespan='off')
"""
            with tempfile.TemporaryFile() as log:
                process = await asyncio.to_thread(
                    subprocess.Popen,
                    [
                        str(interpreter),
                        "-c",
                        script,
                        str(runtime_socket.fileno()),
                        "seed",
                    ],
                    cwd=runtime_dir,
                    env=env,
                    pass_fds=(runtime_socket.fileno(),),
                    stdout=log,
                    stderr=log,
                )
                self.addCleanup(runtime_socket.close)
                api_socket = socket.socket()
                api_socket.bind(("127.0.0.1", 0))
                api_socket.listen()
                api_port = api_socket.getsockname()[1]
                upstream = LangGraphRuntimeGatewayUpstream(
                    base_url=f"http://127.0.0.1:{runtime_port}", timeout_seconds=10
                )
                # Identity/catalog fixtures are locked; all workspace IO and delegation validation are real.
                upstream.get_thread = self.upstream.get_thread
                self.service._upstream = upstream
                server = uvicorn.Server(
                    uvicorn.Config(self.app, log_level="error", lifespan="off")
                )
                thread = threading.Thread(
                    target=server.run, kwargs={"sockets": [api_socket]}, daemon=True
                )
                thread.start()

                async def wait_ready():
                    # Cold Runtime SDK imports can exceed 45s on a loaded dev host.
                    deadline = time.monotonic() + 120
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            log.seek(0)
                            self.fail(log.read().decode())
                        try:
                            response = await asyncio.to_thread(
                                httpx.get,
                                f"http://127.0.0.1:{runtime_port}/openapi.json",
                                timeout=0.2,
                            )
                            if response.status_code == 200 and server.started:
                                break
                        except httpx.HTTPError:
                            pass
                        await asyncio.sleep(0.1)
                    else:
                        log.seek(0)
                        self.fail("Local HTTP services did not start\n" + log.read().decode())

                try:
                    await wait_ready()
                    async with httpx.AsyncClient(
                        base_url=f"http://127.0.0.1:{api_port}",
                        headers={"x-project-id": "project-a"},
                        timeout=10,
                    ) as client:
                        prefix = "/api/langgraph/threads/thread-1"
                        listed = await client.get(prefix + "/artifacts")
                        self.assertEqual(listed.status_code, 200, listed.text)
                        ref = listed.json()["items"][0]
                        for route in ("/workspace/content", "/files/content"):
                            result = await client.get(
                                prefix + route, params={"path": ref["path"]}
                            )
                            self.assertEqual(result.status_code, 200, result.text)
                            self.assertEqual(
                                hashlib.sha256(result.content).hexdigest(),
                                ref["sha256"],
                            )
                            self.assertIn(
                                "attachment", result.headers["content-disposition"]
                            )
                        result = await client.get(
                            prefix + "/workspace/preview",
                            params={"path": "/workspace/work/payment.yaml"},
                        )
                        self.assertEqual(result.json()["text"], "openapi: 3.1.0")
                        result = await client.get(
                            prefix + "/workspace/preview",
                            params={"path": "/workspace/work/view.html"},
                        )
                        self.assertEqual(result.status_code, 200, result.text)
                        self.assertNotIn("<script", result.text)
                        self.assertIn("Content-Security-Policy", result.text)
                        self.assertIn(
                            "sandbox", result.headers["content-security-policy"]
                        )
                        result = await client.get(
                            prefix + "/workspace/tree",
                            params={"path": "/workspace/work"},
                        )
                        self.assertEqual(len(result.json()["items"]), 2)
                        result = await client.get(
                            prefix + "/workspace/content",
                            params={"path": "/workspace/work/missing.txt"},
                        )
                        self.assertEqual(result.status_code, 404, result.text)
                        self.assertEqual(result.json()["error"]["message"], "workspace_file_unavailable")
                        self.assertEqual(result.json()["error"]["code"], "workspace_file_unavailable")
                        if terminal:
                            body = {"request_id": "00000000-0000-4000-8000-000000000001", "acknowledge_execution": True}
                            created = await client.post(prefix + "/terminals", json=body)
                            self.assertEqual(created.status_code, 200, created.text)
                            terminal_id = created.json()["terminal_id"]
                            terminal_url = prefix + "/terminals/" + terminal_id
                            repeated = await client.post(prefix + "/terminals", json=body)
                            self.assertEqual(repeated.json()["terminal_id"], terminal_id)
                            entered = await client.post(terminal_url + "/input", json={"sequence": 0,
                                "data_base64": base64.b64encode(b"printf 'terminal-http-ok\\n'\n").decode()})
                            self.assertEqual(entered.status_code, 200, entered.text)
                            output = b""
                            offset = 0
                            for _ in range(100):
                                response = await client.get(terminal_url + "/output", params={"offset": offset})
                                self.assertEqual(response.status_code, 200, response.text)
                                output += base64.b64decode(response.json()["data_base64"])
                                offset = response.json()["next_offset"]
                                if b"\r\nterminal-http-ok\r\n" in output:
                                    break
                                await asyncio.sleep(0.05)
                            self.assertIn(b"\r\nterminal-http-ok\r\n", output)
                            replay = await client.get(terminal_url + "/output", params={"offset": 0})
                            self.assertIn(output, base64.b64decode(replay.json()["data_base64"]))
                            resized = await client.post(terminal_url + "/resize", json={"rows": 40, "cols": 120})
                            self.assertEqual(resized.json()["rows"], 40)
                            closed = await client.delete(terminal_url)
                            self.assertEqual(closed.json()["status"], "exited")
                        # Restart the real Runtime process without seeding or publishing again.
                        process.terminate()
                        await asyncio.to_thread(process.wait, timeout=5)
                        process = await asyncio.to_thread(
                            subprocess.Popen,
                            [
                                str(interpreter),
                                "-c",
                                script,
                                str(runtime_socket.fileno()),
                            ],
                            cwd=runtime_dir,
                            env=env,
                            pass_fds=(runtime_socket.fileno(),),
                            stdout=log,
                            stderr=log,
                        )
                        await wait_ready()
                        if terminal:
                            lost = await client.get(terminal_url + "/output")
                            self.assertEqual(lost.status_code, 409, lost.text)
                        restored = await client.get(prefix + "/artifacts")
                        self.assertEqual(restored.json()["items"][0], ref)
                        downloaded = await client.get(
                            prefix + "/workspace/content", params={"path": ref["path"]}
                        )
                        self.assertEqual(
                            hashlib.sha256(downloaded.content).hexdigest(),
                            ref["sha256"],
                        )
                        zip_resp = await client.get(prefix + "/workspace/zip")
                        self.assertEqual(zip_resp.status_code, 200, zip_resp.text)
                        self.assertEqual(zip_resp.headers["content-type"], "application/zip")
                        self.assertIn("attachment; filename*=", zip_resp.headers.get("content-disposition", ""))
                        import io, zipfile
                        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as archive:
                            names = archive.namelist()
                            self.assertIn("work/payment.yaml", names)
                            self.assertIn("work/view.html", names)
                finally:
                    server.should_exit = True
                    await asyncio.to_thread(thread.join, timeout=5)
                    api_socket.close()
                    process.terminate()
                    try:
                        await asyncio.to_thread(process.wait, timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        await asyncio.to_thread(process.wait, timeout=5)
