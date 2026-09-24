"""Memory management and shared Thread authorization contracts."""
import unittest
from unittest.mock import AsyncMock
import hashlib
import hmac
import time
from types import SimpleNamespace
from unittest.mock import patch

from platform_api.modules.runtime_gateway.application.thread_access import personal_memory_allowed
from platform_api.modules.runtime_catalog.presentation.http import authorize_runtime_memory
from platform_api.modules.runtime_gateway.application.service import RuntimeGatewayService
from platform_api.core.errors import BadRequestError
from platform_api.core.context.models import ActorContext
from fastapi import FastAPI
from platform_api.modules.runtime_gateway.presentation.http import router as gateway_router


class MemoryAuthorizationTest(unittest.TestCase):
    def test_only_unshared_owner_thread_allows_memory(self):
        access = {"access_version": 1, "project_id": "p", "owner_user_id": "u",
                  "visibility": "private", "shared_actions": {}, "project_actions": []}
        self.assertTrue(personal_memory_allowed(access, project_id="p", user_id="u"))
        self.assertFalse(personal_memory_allowed(access, project_id="p", user_id="other"))
        self.assertFalse(personal_memory_allowed({**access, "shared_actions": {"other": ["read"]}},
                                                 project_id="p", user_id="u"))
        self.assertFalse(personal_memory_allowed({**access, "visibility": "project"},
                                                 project_id="p", user_id="u"))

    def test_internal_callback_requires_valid_signature(self):
        request = SimpleNamespace(headers={}, app=SimpleNamespace(state=SimpleNamespace(
            settings=SimpleNamespace(runtime_delegation_secret="test-secret"), db_session_factory=object())))
        with self.assertRaises(Exception):
            authorize_runtime_memory(request, project_id="p", thread_id="t", user_id="u")
        with patch("platform_api.modules.runtime_gateway.application.thread_access.get") as get:
            get.assert_not_called()

    def test_internal_callback_reads_current_acl(self):
        stamp = str(int(time.time()))
        message = f"{stamp}\np\nt\nu"
        signature = hmac.new(b"test-secret", message.encode(), hashlib.sha256).hexdigest()
        request = SimpleNamespace(headers={"x-runtime-memory-timestamp": stamp,
            "x-runtime-memory-signature": signature}, app=SimpleNamespace(state=SimpleNamespace(
            settings=SimpleNamespace(runtime_delegation_secret="test-secret"), db_session_factory=object())))
        access = {"access_version": 1, "project_id": "p", "owner_user_id": "u",
                  "visibility": "private", "shared_actions": {}, "project_actions": []}
        with patch("platform_api.modules.runtime_gateway.application.thread_access.get", return_value=access):
            self.assertEqual(authorize_runtime_memory(request, project_id="p", thread_id="t", user_id="u"),
                             {"allowed": True})
            access["shared_actions"] = {"peer": ["read"]}
            self.assertEqual(authorize_runtime_memory(request, project_id="p", thread_id="t", user_id="u"),
                             {"allowed": False})


class MemoryStateInputTest(unittest.IsolatedAsyncioTestCase):
    async def test_nested_payload_rejects_private_runtime_state(self):
        from platform_api.modules.runtime_gateway.application.service import _normalize_payload

        for key in ("dear_memory_source", "runtime_message_claim", "dear_skill_snapshot"):
            with self.assertRaises(BadRequestError):
                _normalize_payload({"input": {"nested": {key: {"forged": True}}}})

    async def test_thread_state_update_rejects_private_source(self):
        upstream = SimpleNamespace(update_thread_state=AsyncMock())
        service = SimpleNamespace(_load_thread=AsyncMock(), _upstream=upstream)
        with self.assertRaises(BadRequestError):
            await RuntimeGatewayService.update_thread_state(service, actor=ActorContext(),
                project_id="p", thread_id="t", payload={"values": {
                    "dear_memory_source": {"text": "forged"}}})
        upstream.update_thread_state.assert_not_called()


class MemoryOpenAPITest(unittest.TestCase):
    def test_public_memory_schema_is_available_to_frontend(self):
        app = FastAPI()
        app.include_router(gateway_router)
        operation = app.openapi()["paths"]["/api/langgraph/dear/memory"]
        self.assertEqual(operation["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"],
                         "#/components/schemas/MemoryView")
        body = operation["post"]["requestBody"]["content"]["application/json"]["schema"]
        self.assertIn("action", body["required"])
        self.assertIn("expected_revision", body["required"])
