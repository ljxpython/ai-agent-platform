"""Tests for Platform API image gateway endpoints, permissions, validations and upstream proxy."""

import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import jwt
from fastapi import FastAPI
from tests.thread_acl_fixture import thread_acl_factory

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


class RuntimeGatewayImagesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        register_exception_handlers(self.app)

        self.actor = ActorContext(user_id="user-1", project_roles={"proj-1": ("project_executor",)})
        self.upstream = Mock()
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.session_factory = thread_acl_factory(self, actor=self.actor, project_id="proj-1")

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

    async def test_upload_image_success(self):
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        sha = hashlib.sha256(data).hexdigest()

        self.upstream.get_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "graph_id": "showcase_demo"}}
        )
        self.upstream.upload_thread_image = AsyncMock(
            return_value={
                "version": 1,
                "path": f"/workspace/uploads/{sha}.png",
                "sha256": sha,
                "mime_type": "image/png",
                "size_bytes": len(data),
            }
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            response = await client.put(
                f"/api/langgraph/threads/thread-1/images/uploads/{sha}",
                content=data,
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "image/png",
                    "content-length": str(len(data)),
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["version"], 1)
        self.assertEqual(body["sha256"], sha)
        self.assertEqual(body["mime_type"], "image/png")

        # Verify delegation token
        self.assertEqual(len(self.delegation_calls), 1)
        self.assertEqual(self.delegation_calls[0]["operation"], "image-upload")
        self.assertEqual(self.delegation_calls[0]["project_id"], "proj-1")
        self.assertEqual(self.delegation_calls[0]["agent_key"], "showcase_demo")
        self.assertEqual(self.delegation_calls[0]["thread_id"], "thread-1")

    async def test_upload_image_validations(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            # 1. Bad sha256
            resp = await client.put(
                "/api/langgraph/threads/thread-1/images/uploads/badsha",
                content=b"123",
                headers={"x-project-id": "proj-1", "content-type": "image/png"},
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()["error"]["code"], "image_hash_invalid")

            # 2. Unsupported MIME
            sha = "a" * 64
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/images/uploads/{sha}",
                content=b"123",
                headers={"x-project-id": "proj-1", "content-type": "text/plain"},
            )
            self.assertEqual(resp.status_code, 415)
            self.assertEqual(resp.json()["error"]["code"], "image_mime_unsupported")

            # 3. Exceeds 5MB limit
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/images/uploads/{sha}",
                content=b"123",
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "image/png",
                    "content-length": str(6 * 1024 * 1024),
                },
            )
            self.assertEqual(resp.status_code, 413)
            self.assertEqual(resp.json()["error"]["code"], "image_too_large")

            # 4. Missing graph_id in thread
            self.upstream.get_thread = AsyncMock(
                return_value={"metadata": {"project_id": "proj-1"}}
            )
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/images/uploads/{sha}",
                content=b"123",
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "image/png",
                    "content-length": "3",
                },
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()["error"]["code"], "graph_id_required")

            # 5. Thread from other project
            self.upstream.get_thread = AsyncMock(
                return_value={"metadata": {"project_id": "other-proj", "graph_id": "showcase_demo"}}
            )
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/images/uploads/{sha}",
                content=b"123",
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "image/png",
                    "content-length": "3",
                },
            )
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.json()["error"]["code"], "thread_project_denied")

    async def test_read_image_success(self):
        self.upstream.get_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "graph_id": "showcase_demo"}}
        )

        async def fake_body():
            yield b"image-data-chunk"

        self.upstream.read_thread_image = AsyncMock(
            return_value=BinaryPayload(
                body=fake_body(),
                content_type="image/png",
                content_length=16,
                etag='"123456"',
                cache_control="public, max-age=86400",
            )
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/langgraph/threads/thread-1/images/content",
                params={"path": "/workspace/uploads/test.png"},
                headers={"x-project-id": "proj-1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["content-length"], "16")
        self.assertEqual(response.headers["etag"], '"123456"')
        self.assertEqual(response.headers["cache-control"], "public, max-age=86400")
        self.assertEqual(response.content, b"image-data-chunk")

        # Verify delegation token
        self.assertEqual(len(self.delegation_calls), 1)
        self.assertEqual(self.delegation_calls[0]["operation"], "image-read")
        self.assertEqual(self.delegation_calls[0]["project_id"], "proj-1")
        self.assertEqual(self.delegation_calls[0]["agent_key"], "showcase_demo")
        self.assertEqual(self.delegation_calls[0]["thread_id"], "thread-1")

    async def test_read_image_validations(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            # 1. Path traversal
            resp = await client.get(
                "/api/langgraph/threads/thread-1/images/content",
                params={"path": "/workspace/uploads/../../etc/passwd"},
                headers={"x-project-id": "proj-1"},
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()["error"]["code"], "image_path_invalid")

            # 2. Outside workspace image dir
            resp = await client.get(
                "/api/langgraph/threads/thread-1/images/content",
                params={"path": "/etc/passwd"},
                headers={"x-project-id": "proj-1"},
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json()["error"]["code"], "image_path_invalid")

            # 3. Thread belongs to other project
            self.upstream.get_thread = AsyncMock(
                return_value={"metadata": {"project_id": "other-proj", "graph_id": "showcase_demo"}}
            )
            resp = await client.get(
                "/api/langgraph/threads/thread-1/images/content",
                params={"path": "/workspace/generated/test.png"},
                headers={"x-project-id": "proj-1"},
            )
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.json()["error"]["code"], "thread_project_denied")

    async def test_upstream_error_propagation(self):
        self.upstream.get_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "graph_id": "showcase_demo"}}
        )

        # 1. Upstream 404 image_not_found
        self.upstream.read_thread_image = AsyncMock(
            side_effect=PlatformApiError(
                code="image_not_found",
                status_code=404,
                message="Image not found",
            )
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/langgraph/threads/thread-1/images/content",
                params={"path": "/workspace/uploads/missing.png"},
                headers={"x-project-id": "proj-1"},
            )
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(resp.json()["error"]["code"], "image_not_found")

        # 2. Upstream invalid response structure
        self.upstream.upload_thread_image = AsyncMock(
            return_value={"invalid": "payload"}
        )
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        sha = hashlib.sha256(data).hexdigest()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        ) as client:
            resp = await client.put(
                f"/api/langgraph/threads/thread-1/images/uploads/{sha}",
                content=data,
                headers={
                    "x-project-id": "proj-1",
                    "content-type": "image/png",
                    "content-length": str(len(data)),
                },
            )
            self.assertEqual(resp.status_code, 502)
            self.assertEqual(resp.json()["error"]["code"], "runtime_invalid_image_response")


if __name__ == "__main__":
    unittest.main()
