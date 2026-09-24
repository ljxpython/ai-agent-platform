"""Real loopback Platform-to-Runtime personal-memory contract."""
import asyncio
import os
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import httpx
import psycopg
import test_runtime_gateway_workspace as workspace_tests
from psycopg import sql
from psycopg.conninfo import make_conninfo

from platform_api.adapters.langgraph.runtime_gateway_upstream import LangGraphRuntimeGatewayUpstream
from platform_api.core.context.models import ActorContext


class MemoryGatewayTest(unittest.IsolatedAsyncioTestCase):
    delegation = workspace_tests.WorkspaceGatewayTest.delegation

    def setUp(self):
        workspace_tests.WorkspaceGatewayTest.setUp(self)

        @self.app.middleware("http")
        async def request_id(request, call_next):
            request.state.request_id = "memory-test-request"
            return await call_next(request)

    async def test_anonymous_and_outsider_are_rejected_before_runtime(self):
        del self.service._prepare_project_scope
        for actor, status in ((ActorContext(), 403), (ActorContext(user_id="outsider"), 403)):
            self.actor = actor
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                    base_url="http://platform", headers={"x-project-id": "project-a"}) as client:
                self.assertEqual((await client.get("/api/langgraph/dear/memory")).status_code, status)
                self.assertEqual((await client.post("/api/langgraph/dear/memory", json={
                    "action": "clear", "expected_revision": 0})).status_code, status)
        self.upstream.with_forwarded_headers.assert_not_called()

    async def test_real_http_crud_restart_and_safe_validation(self):
        source = os.environ.get("RUNTIME_MESSAGE_TEST_DSN")
        if not source:
            self.skipTest("Explicit RUNTIME_MESSAGE_TEST_DSN required")
        schema = "memory_http_" + uuid4().hex
        with psycopg.connect(source) as db:
            db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        dsn = make_conninfo(source, options=f"-c search_path={schema}")
        runtime_dir = Path(__file__).resolve().parents[2] / "runtime-service"
        env = {**os.environ, "DATABASE_URI": dsn, "RUNTIME_DEAR_GOVERNANCE_ENABLED": "1",
               "PLATFORM_RUNTIME_DELEGATION_SECRET": workspace_tests.SECRET,
               "PLATFORM_RUNTIME_DELEGATION_ISSUER": "runtime-test",
               "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service"}
        self.service._authorize = Mock()
        runtime_socket = socket.socket()
        runtime_socket.bind(("127.0.0.1", 0))
        runtime_socket.listen()
        self.service._upstream = LangGraphRuntimeGatewayUpstream(
            base_url=f"http://127.0.0.1:{runtime_socket.getsockname()[1]}", timeout_seconds=10)
        script = "import sys,uvicorn; from runtime_service.db import upgrade; upgrade(); uvicorn.run('runtime_service.webapp:app', fd=int(sys.argv[1]), log_level='error', lifespan='off')"
        process = None
        with tempfile.TemporaryFile() as log:
            def start():
                return subprocess.Popen([str(runtime_dir / ".venv/bin/python"), "-c", script,
                    str(runtime_socket.fileno())], cwd=runtime_dir, env=env,
                    pass_fds=(runtime_socket.fileno(),), stdout=log, stderr=log)

            async def ready():
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        self.fail(log.read().decode())
                    try:
                        async with httpx.AsyncClient(timeout=0.2) as client:
                            response = await client.get(f"http://127.0.0.1:{runtime_socket.getsockname()[1]}/openapi.json")
                            if response.status_code == 200:
                                return
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(0.1)
                self.fail("Runtime HTTP did not become ready")

            try:
                process = start()
                await ready()
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                        base_url="http://platform", headers={"x-project-id": "project-a"}) as client:
                    url = "/api/langgraph/dear/memory"
                    empty = await client.get(url)
                    self.assertEqual(empty.status_code, 200, empty.text)
                    self.assertEqual(empty.json()["document"]["revision"], 0)
                    self.assertTrue(empty.json()["capabilities"]["can_write"])
                    saved = await client.post(url, json={"action": "save", "expected_revision": 0,
                        "fact": {"text": "synthetic memory marker", "category": "fact"}})
                    self.assertEqual(saved.status_code, 200, saved.text)
                    self.assertEqual(saved.json()["mutation"]["added"], 1)
                    self.assertEqual(saved.json()["document"]["facts"][0]["source_kind"], "management")
                    self.assertNotIn("sources", saved.json()["document"])
                    conflict = await client.post(url, json={"action": "clear", "expected_revision": 0})
                    self.assertEqual(conflict.status_code, 409, conflict.text)
                    self.assertEqual(conflict.json()["error"]["code"], "memory_revision_conflict")
                    self.assertTrue(conflict.json()["request_id"])
                    marker = "SENSITIVE_TEST_BODY_DO_NOT_ECHO"
                    invalid = await client.post(url, json={"action": "clear", "expected_revision": 1,
                        "fact": {"text": marker}})
                    self.assertEqual(invalid.status_code, 422, invalid.text)
                    self.assertNotIn(marker, invalid.text)
                    self.assertIn("loc", invalid.json()["error"]["details"][0])
                    non_object = await client.post(url, json=[{"action": "clear"}])
                    self.assertEqual(non_object.status_code, 422, non_object.text)
                    oversized = await client.post(url, content=b"x" * 1500001,
                        headers={"content-type": "application/json"})
                    self.assertEqual(oversized.status_code, 413, oversized.text)
                    self.assertEqual(oversized.json()["error"]["code"], "memory_payload_too_large")
                    process.terminate()
                    await asyncio.to_thread(process.wait, timeout=10)
                    process = start()
                    await ready()
                    restored = await client.get(url)
                    self.assertEqual(restored.status_code, 200, restored.text)
                    self.assertEqual(restored.json()["document"]["facts"][0]["text"], "synthetic memory marker")
            finally:
                if process and process.poll() is None:
                    process.terminate()
                    await asyncio.to_thread(process.wait, timeout=10)
                runtime_socket.close()
                with psycopg.connect(source) as db:
                    db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
