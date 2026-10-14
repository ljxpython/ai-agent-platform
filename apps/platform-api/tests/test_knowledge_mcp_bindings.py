import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import ValidationError

from platform_api.adapters.langgraph.sdk_client import redact_runtime_private_fields
from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import BadRequestError
from platform_api.core.runtime_contract import (
    normalize_protocol_v2_command,
    normalize_runtime_payload,
)
from platform_api.modules.runtime_gateway.application.knowledge_bindings import (
    build_knowledge_binding,
)
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from tests.thread_acl_fixture import thread_acl_factory

PROJECT = str(uuid4())
TENANT = "__default"
MAPPING = {f"{TENANT}:{PROJECT}": "knowledge-v1"}


class KnowledgeBindingTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.actor = ActorContext(
            user_id="owner", project_roles={PROJECT: ("project_admin",)}
        )
        self.upstream = SimpleNamespace(
            create_thread=AsyncMock(side_effect=lambda p: copy.deepcopy(p)),
            get_thread_state=AsyncMock(return_value={"values": {"messages": []}}),
            update_thread_state=AsyncMock(),
        )
        self.service = RuntimeGatewayService(
            session_factory=thread_acl_factory(
                self, actor=self.actor, project_id=PROJECT
            ),
            upstream=self.upstream,
            knowledge_mcp_bindings=MAPPING,
            tenant_id=TENANT,
        )
        self.service._prepare_project_scope = Mock()
        self.service._mark_thread_provisioned = AsyncMock()

    async def test_authorized_new_thread_scope_and_unconfigured_project(self):
        thread = await self.service.create_thread(
            actor=self.actor, project_id=PROJECT, payload={"graph_id": "showcase_demo"}
        )
        binding = thread["metadata"]["runtime_resource_bindings"]
        self.assertEqual(binding["schema"], "runtime-resource-bindings/v1")
        self.assertEqual(binding["mcp"]["thread_id"], thread["thread_id"])
        self.assertEqual(binding["mcp"]["tenant_id"], TENANT)
        self.assertEqual(binding["mcp"]["project_id"], PROJECT)
        self.assertEqual(binding["mcp"]["resource_id"], "knowledge-v1")
        self.assertNotIn(
            "runtime_resource_bindings", repr(redact_runtime_private_fields(thread))
        )
        self.service._knowledge_mcp_bindings = {}
        plain = await self.service.create_thread(
            actor=self.actor, project_id=PROJECT, payload={"graph_id": "showcase_demo"}
        )
        self.assertNotIn("runtime_resource_bindings", plain["metadata"])

    async def test_dynamic_jwt_binding_when_unconfigured_in_static_mapping(self):
        import jwt

        secret = "test-secret-at-least-32-bytes-long-123456"
        self.service._knowledge_mcp_bindings = {}
        self.service._knowledge_secret = secret
        self.service._knowledge_gateway_url = "http://152.136.27.196:8000/mcp"

        thread = await self.service.create_thread(
            actor=self.actor, project_id=PROJECT, payload={"graph_id": "showcase_demo"}
        )
        binding = thread["metadata"]["runtime_resource_bindings"]
        self.assertEqual(binding["schema"], "runtime-resource-bindings/v1")
        mcp = binding["mcp"]
        self.assertEqual(mcp["tenant_id"], TENANT)
        self.assertEqual(mcp["project_id"], PROJECT)
        self.assertTrue(mcp["auth_token"])
        self.assertEqual(mcp["gateway_url"], "http://152.136.27.196:8000/mcp")

        # 验证签发的 Token 可以被正确解密
        payload = jwt.decode(
            mcp["auth_token"],
            secret,
            algorithms=["HS256"],
            audience="rag-service",
        )
        self.assertEqual(payload["tenant_id"], TENANT)
        self.assertEqual(payload["project_id"], PROJECT)
        self.assertTrue(payload["knowledge_base_id"].startswith("kb_"))

    async def test_forged_binding_is_rejected_before_acl_or_upstream(self):
        for payload in (
            {"metadata": {"runtime_resource_bindings": {}}},
            {
                "supersteps": [
                    {"updates": [{"values": {"__graphharbor_thread_metadata": {}}}]}
                ]
            },
            {"config": {"configurable": {"runtime_resource_bindings": {}}}},
        ):
            with self.subTest(payload=payload), self.assertRaises(BadRequestError):
                await self.service.create_thread(
                    actor=self.actor, project_id=PROJECT, payload=payload
                )
        self.upstream.create_thread.assert_not_awaited()
        self.service._prepare_project_scope.assert_not_called()

    async def test_fork_receives_new_thread_binding(self):
        source = {
            "thread_id": "old",
            "metadata": {
                "project_id": PROJECT,
                "graph_id": "showcase_demo",
                "owner_user_id": "owner",
                "runtime_resource_bindings": {"mcp": {"resource_id": "old"}},
            },
        }
        self.service._load_thread = AsyncMock(return_value=source)
        self.upstream.get_thread_state.return_value = {
            "values": {"messages": [{"type": "human", "content": "history"}]}
        }
        target = await self.service.fork_thread(
            actor=self.actor,
            project_id=PROJECT,
            thread_id="old",
            checkpoint_id="checkpoint",
            title=None,
        )
        binding = target["metadata"]["runtime_resource_bindings"]["mcp"]
        self.assertNotEqual(binding["thread_id"], "old")
        self.assertEqual(binding["thread_id"], target["thread_id"])
        self.assertEqual(binding["resource_id"], "knowledge-v1")

    def test_configuration_scopes_and_public_inputs(self):
        self.assertEqual(
            Settings(knowledge_mcp_bindings=MAPPING).knowledge_mcp_bindings, MAPPING
        )
        for mapping in (
            {"bad": "r"},
            {f"{TENANT}:{PROJECT}": "../bad"},
            {f"{TENANT}:{PROJECT}": "same", f"{TENANT}:{uuid4()}": "same"},
        ):
            with self.assertRaises(ValidationError):
                Settings(knowledge_mcp_bindings=mapping)
        self.assertEqual(
            build_knowledge_binding(MAPPING, str(uuid4()), PROJECT, "t"), {}
        )
        for field in ("metadata", "config", "context", "input"):
            payload = {field: {"nested": [{"runtime_resource_bindings": {}}]}}
            with self.assertRaises(ValueError):
                normalize_runtime_payload(payload=payload, project_id=PROJECT)
            with self.assertRaises(ValueError):
                normalize_protocol_v2_command(
                    payload={
                        "id": 1,
                        "method": "run.start",
                        "params": {"assistant_id": "showcase_demo", **payload},
                    }
                )

    def test_fresh_database_has_single_migration_head(self):
        scripts = ScriptDirectory.from_config(Config("alembic.ini"))
        self.assertEqual(len(scripts.get_heads()), 1)
        for revision in ("20261007_0006", "20261009_0007"):
            self.assertIsNotNone(scripts.get_revision(revision))
