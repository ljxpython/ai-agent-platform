"""Tests for Platform API document/file gateway endpoints, permissions, validations and upstream proxy."""

import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import jwt
from fastapi import FastAPI

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import (
    BadRequestError,
    ForbiddenError,
    PlatformApiError,
    register_exception_handlers,
)
from platform_api.modules.runtime_gateway.application.ports import BinaryPayload
from platform_api.modules.runtime_gateway.application.service import RuntimeGatewayService
from platform_api.modules.runtime_gateway.presentation.http import (
    get_actor_context,
    get_runtime_gateway_service,
    router,
)


class RuntimeGatewayFilesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        register_exception_handlers(self.app)

        self.actor = ActorContext(user_id="user-1")
        self.upstream = Mock()
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.session_factory = Mock()

        self.delegation_calls = []

        def delegation_factory(*, project_id, agent_key, thread_id, context_hash, operation):
            token = jwt.encode(
                {
                    "sub": "user-1",
                    "project_id": project_id,
                    "agent_key": agent_key,
                    "thread_id": thread_id,
                    "operation": operation,
                },
                "secret-key-at-least-32-bytes-long-123456",
                algorithm="HS256",
            )
            self.delegation_calls.append(
                {
                    "project_id": project_id,
                    "agent_key": agent_key,
                    "thread_id": thread_id,
                    "operation": operation,
                    "token": token,
                }
            )
            return {"authorization": f"Bearer {token}"}

        self.service = RuntimeGatewayService(
            session_factory=self.session_factory,
            upstream=self.upstream,
            delegation_headers_factory=delegation_factory,
        )
        self.service._prepare_project_scope = Mock()

        self.app.dependency_overrides[get_actor_context] = lambda: self.actor
        self.app.dependency_overrides[get_runtime_gateway_service] = lambda: self.service

        @self.app.middleware("http")
        async def scope(request, call_next):
            request.state.platform_context = SimpleNamespace(
                project=SimpleNamespace(project_id=request.headers.get("x-project-id"))
            )
            return await call_next(request)

    async def test_upload_file_success(self):
        data = b"%PDF-1.4\n" + b"x" * 100
        sha = hashlib.sha256(data).hexdigest()

        self.upstream.get_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "graph_id": "showcase_demo"}}
        )
        self.upstream.upload_thread_file = AsyncMock(
            return_value={
                "version": 1,
                "path": f"/workspace/uploads/{sha}.pdf",
                "sha256": sha,
                "file_name": "采购合同.pdf",
                "mime_type": "application/pdf",
                "size_bytes": len(data),
            }
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            response = await client.put(
                f"/api/langgraph/threads/thread-1/files/uploads/{sha}?file_name=%E9%87%87%E8%B4%AD%E5%90%88%E5%90%8C.pdf",
                content=data,
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "application/pdf",
                    "content-length": str(len(data)),
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["version"], 1)
        self.assertEqual(body["sha256"], sha)
        self.assertEqual(body["mime_type"], "application/pdf")
        self.assertEqual(body["file_name"], "采购合同.pdf")
        self.assertEqual(body["path"], f"/workspace/uploads/{sha}.pdf")

        # 验证 delegation token 为 workspace-file-upload
        self.assertEqual(len(self.delegation_calls), 1)
        self.assertEqual(self.delegation_calls[0]["operation"], "workspace-file-upload")
        self.assertEqual(self.delegation_calls[0]["project_id"], "proj-1")
        self.assertEqual(self.delegation_calls[0]["agent_key"], "showcase_demo")
        self.assertEqual(self.delegation_calls[0]["thread_id"], "thread-1")

    async def test_upload_file_validations(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            # 1. 非法 sha256
            resp = await client.put(
                "/api/langgraph/threads/thread-1/files/uploads/badsha",
                content=b"123",
                headers={"x-project-id": "proj-1", "content-type": "application/pdf"},
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()["error"]["code"], "invalid_file_ref")

            # 2. 不支持的 MIME（如图片）
            sha = "a" * 64
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/files/uploads/{sha}",
                content=b"123",
                headers={"x-project-id": "proj-1", "content-type": "image/png"},
            )
            self.assertEqual(resp.status_code, 415)
            self.assertEqual(resp.json()["error"]["code"], "unsupported_file_type")

            # 3. 超过 20MB 限制
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/files/uploads/{sha}",
                content=b"123",
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "application/pdf",
                    "content-length": str(21 * 1024 * 1024),
                },
            )
            self.assertEqual(resp.status_code, 413)
            self.assertEqual(resp.json()["error"]["code"], "file_too_large")

            # 4. 线程缺失 graph_id
            self.upstream.get_thread = AsyncMock(
                return_value={"metadata": {"project_id": "proj-1"}}
            )
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/files/uploads/{sha}",
                content=b"123",
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "application/pdf",
                    "content-length": "3",
                },
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()["error"]["code"], "graph_id_required")

            # 5. 跨项目线程访问
            self.upstream.get_thread = AsyncMock(
                return_value={"metadata": {"project_id": "other-proj", "graph_id": "showcase_demo"}}
            )
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/files/uploads/{sha}",
                content=b"123",
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "application/pdf",
                    "content-length": "3",
                },
            )
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.json()["error"]["code"], "thread_project_denied")

    async def test_read_file_success(self):
        self.upstream.get_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "graph_id": "showcase_demo"}}
        )

        async def fake_body():
            yield b"%PDF-1.4 file content"

        self.upstream.read_thread_file = AsyncMock(
            return_value=BinaryPayload(
                body=fake_body(),
                content_type="application/pdf",
                content_length=22,
                etag='"abcdef"',
                cache_control="private, no-store",
            )
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/langgraph/threads/thread-1/files/content",
                params={"path": "/workspace/uploads/test.pdf"},
                headers={"x-project-id": "proj-1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.headers["content-length"], "22")
        self.assertEqual(response.headers["etag"], '"abcdef"')
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertIn("inline", response.headers["content-disposition"])
        self.assertEqual(response.content, b"%PDF-1.4 file content")

        # 验证 delegation token 为 workspace-file-read
        self.assertEqual(len(self.delegation_calls), 1)
        self.assertEqual(self.delegation_calls[0]["operation"], "workspace-file-read")
        self.assertEqual(self.delegation_calls[0]["project_id"], "proj-1")
        self.assertEqual(self.delegation_calls[0]["agent_key"], "showcase_demo")
        self.assertEqual(self.delegation_calls[0]["thread_id"], "thread-1")

    async def test_read_file_validations(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            # 1. 路径穿越
            resp = await client.get(
                "/api/langgraph/threads/thread-1/files/content",
                params={"path": "/workspace/uploads/../../etc/passwd"},
                headers={"x-project-id": "proj-1"},
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()["error"]["code"], "invalid_file_ref")

            # 2. 非 uploads 路径
            resp = await client.get(
                "/api/langgraph/threads/thread-1/files/content",
                params={"path": "/etc/passwd"},
                headers={"x-project-id": "proj-1"},
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()["error"]["code"], "invalid_file_ref")
