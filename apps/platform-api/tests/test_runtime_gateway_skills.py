"""Real HTTP gateway/Runtime/PostgreSQL chain with isolated identity/catalog fixtures."""
import asyncio
import base64
import io
import os
import socket
import subprocess
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock

import httpx
import psycopg
import uvicorn
from psycopg import sql
from psycopg.conninfo import make_conninfo

import test_runtime_gateway_workspace as workspace_tests

SECRET = workspace_tests.SECRET
from platform_api.adapters.langgraph.runtime_gateway_upstream import LangGraphRuntimeGatewayUpstream
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ForbiddenError


def package(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("SKILL.md", "---\nname: http-skill\ndescription: HTTP fixture\n---\n" + text)
    return {"package_base64": base64.b64encode(buffer.getvalue()).decode()}


class SkillsGatewayTest(unittest.IsolatedAsyncioTestCase):
    setUp = workspace_tests.WorkspaceGatewayTest.setUp
    delegation = workspace_tests.WorkspaceGatewayTest.delegation

    async def test_anonymous_and_outsider_all_routes(self):
        routes = [("GET", "", None), ("POST", "/custom", package("A")),
                  ("PUT", "/custom/http-skill", {**package("B"), "expected_revision": "old"}),
                  ("PATCH", "/custom/http-skill", {"enabled": False, "expected_revision": "old"}),
                  ("DELETE", "/custom/http-skill", None), ("GET", "/public/runtime-smoke", None),
                  ("GET", "/public/runtime-smoke/content", None)]
        # Restore real authorization: no upstream request or DB lookup may happen.
        del self.service._prepare_project_scope
        for actor, expected in [(ActorContext(), 401), (ActorContext(user_id="outsider"), 403)]:
            self.actor = actor
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
                for method, path, body in routes:
                    response = await client.request(method, "/api/langgraph/dear/skills" + path,
                        json=body, params={"expected_revision": "old", "path": "SKILL.md", "revision": "old"},
                        headers={"x-project-id": "project-a"})
                    self.assertEqual(response.status_code, expected, response.text)
        self.upstream.with_forwarded_headers.assert_not_called()

    async def test_real_http_crud_restart_and_permissions(self):
        source = os.environ.get("RUNTIME_MESSAGE_TEST_DSN")
        if not source:
            self.skipTest("Explicit RUNTIME_MESSAGE_TEST_DSN required")
        schema = "skills_http_" + uuid4().hex
        with psycopg.connect(source) as db:
            db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        dsn = make_conninfo(source, options=f"-c search_path={schema}")
        runtime_dir = Path(__file__).resolve().parents[2] / "runtime-service"
        env = {**os.environ, "DATABASE_URI": dsn, "RUNTIME_DEAR_GOVERNANCE_ENABLED": "1",
               "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
               "PLATFORM_RUNTIME_DELEGATION_ISSUER": "runtime-test",
               "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service"}
        self.service._authorize = Mock()
        runtime_socket = socket.socket()
        runtime_socket.bind(("127.0.0.1", 0))
        runtime_socket.listen()
        api_socket = socket.socket()
        api_socket.bind(("127.0.0.1", 0))
        api_socket.listen()
        self.service._upstream = LangGraphRuntimeGatewayUpstream(base_url=f"http://127.0.0.1:{runtime_socket.getsockname()[1]}", timeout_seconds=10)
        server = uvicorn.Server(uvicorn.Config(self.app, log_level="error", lifespan="off"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [api_socket]}, daemon=True)
        process = None
        script = "import sys,uvicorn; from runtime_service.db import upgrade; upgrade(); uvicorn.run('runtime_service.webapp:app', fd=int(sys.argv[1]), log_level='error', lifespan='off')"
        with tempfile.TemporaryFile() as log:
            def start():
                return subprocess.Popen([str(runtime_dir / ".venv/bin/python"), "-c", script, str(runtime_socket.fileno())],
                    cwd=runtime_dir, env=env, pass_fds=(runtime_socket.fileno(),), stdout=log, stderr=log)
            async def ready():
                for _ in range(150):
                    if process.poll() is not None:
                        log.seek(0)
                        self.fail(log.read().decode())
                    try:
                        async with httpx.AsyncClient(timeout=0.2) as client:
                            r = await client.get(f"http://127.0.0.1:{runtime_socket.getsockname()[1]}/openapi.json")
                            if r.status_code == 200 and server.started:
                                return
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(0.1)
                self.fail("HTTP services did not become ready")
            try:
                process = start()
                thread.start()
                await ready()
                async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{api_socket.getsockname()[1]}", headers={"x-project-id": "project-a"}, timeout=10) as client:
                    prefix = "/api/langgraph/dear/skills"
                    r = await client.post(prefix + "/custom", json=package("VALUE_A"))
                    self.assertEqual(r.status_code, 201, r.text)
                    a = r.json()
                    url = prefix + "/custom/http-skill"
                    listed = await client.get(prefix)
                    self.assertEqual(listed.status_code, 200, listed.text)
                    self.assertTrue(listed.json()["capabilities"]["can_write"])
                    self.upstream.get_thread.assert_not_called()
                    text = await client.get(url + "/content", params={"path": "SKILL.md", "revision": a["revision"]})
                    self.assertIn("VALUE_A", text.json()["content"])
                    r = await client.put(url, json={**package("VALUE_B"), "expected_revision": a["revision"]})
                    self.assertEqual(r.status_code, 200, r.text)
                    b = r.json()
                    conflict = await client.put(url, json={**package("C"), "expected_revision": a["revision"]})
                    self.assertEqual(conflict.status_code, 409, conflict.text)
                    self.assertEqual(conflict.json()["error"]["code"], "skill_revision_conflict")
                    other = await client.get(url, headers={"x-project-id": "project-b"})
                    self.assertEqual(other.status_code, 404, other.text)
                    self.service._authorize.side_effect = ForbiddenError(code="denied", message="read-only")
                    read_only = await client.get(prefix)
                    self.assertFalse(read_only.json()["capabilities"]["can_write"])
                    self.service._authorize.side_effect = None
                    self.service._assistant_belongs_project.return_value = False
                    denied = await client.get(prefix)
                    self.assertEqual(denied.status_code, 403)
                    self.service._assistant_belongs_project.return_value = True
                    process.terminate()
                    await asyncio.to_thread(process.wait, timeout=10)
                    process = start()
                    await ready()
                    restored = await client.get(url)
                    self.assertEqual(restored.json()["revision"], b["revision"])
                    r = await client.patch(url, json={"enabled": False, "expected_revision": b["revision"]})
                    self.assertEqual(r.status_code, 200, r.text)
                    r = await client.delete(url, params={"expected_revision": r.json()["revision"]})
                    self.assertEqual(r.status_code, 204, r.text)
                    self.assertEqual((await client.get(url)).status_code, 404)
            finally:
                server.should_exit = True
                if thread.is_alive():
                    await asyncio.to_thread(thread.join, timeout=10)
                if process and process.poll() is None:
                    process.terminate()
                    await asyncio.to_thread(process.wait, timeout=10)
                runtime_socket.close()
                api_socket.close()
                with psycopg.connect(source) as db:
                    db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
