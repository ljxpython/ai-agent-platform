import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
from fastapi import FastAPI

from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import register_exception_handlers
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.models import ProjectMemberRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.presentation.http import get_runtime_catalog_service
from platform_api.modules.runtime_policies.application.service import RuntimePolicyOverlayService
from platform_api.modules.runtime_policies.presentation.http import router, get_runtime_policy_overlay_service


class ToolRestrictionsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = build_engine(f"sqlite:///{Path(self.temp.name) / 'test.db'}")
        self.addCleanup(self.engine.dispose)
        create_core_tables(self.engine)
        self.factory = build_session_factory(self.engine)
        with self.factory.begin() as session:
            projects = SqlAlchemyProjectsRepository(session)
            tenant = projects.get_or_create_default_tenant()
            self.project = projects.create_project(tenant_id=tenant.id, name="Tools", description="").id
            self.other_project = projects.create_project(tenant_id=tenant.id, name="Other", description="").id
            self.user = SqlAlchemyIdentityRepository(session).create_user(
                username="tools_admin", external_subject="admin", password_hash="unused", email=None, is_super_admin=False).id
            session.add(ProjectMemberRecord(project_id=self.project, user_id=self.user, role="admin"))
        self.actor = ActorContext(user_id=str(self.user), project_roles={str(self.project): ("project_admin",), str(self.other_project): ("project_admin",)})
        self.service = RuntimePolicyOverlayService(session_factory=self.factory, runtime_base_url="http://unused")
        self.catalog = SimpleNamespace(read_tool_declarations=AsyncMock(return_value=[
            {"tool_key": "read_reference", "graph_ids": ["reference_agent"]}]))
        app = FastAPI()
        app.include_router(router)
        register_exception_handlers(app)
        app.dependency_overrides[get_actor_context] = lambda: self.actor
        app.dependency_overrides[get_runtime_policy_overlay_service] = lambda: self.service
        app.dependency_overrides[get_runtime_catalog_service] = lambda: self.catalog
        self.app = app
        self.url = f"/api/projects/{self.project}/runtime-policies/tool-restrictions"

    def policy(self, user=None, graph="reference_agent"):
        return self.service.resolve_tool_overrides(project_id=str(self.project), user_id=str(user or self.user), graph_id=graph)

    async def test_crud_union_isolation_and_live_validation(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            empty = self.policy()
            self.assertEqual((await client.get(self.url.replace("tool-restrictions", "tools"))).status_code, 404)
            self.assertEqual(empty["tool_overrides"], {})
            payload = {"graph_id": "reference_agent", "subject_type": "project", "subject_id": str(self.project), "tool_name": "read_reference", "reason": "test restriction"}
            response = await client.post(self.url, json=payload)
            self.assertEqual(response.status_code, 201, response.text)
            project_row = response.json()["id"]
            self.assertEqual((await client.post(self.url, json=payload)).status_code, 409)
            payload.update(subject_type="user", subject_id=str(self.user))
            response = await client.post(self.url, json=payload)
            self.assertEqual(response.status_code, 201, response.text)
            user_row = response.json()["id"]
            self.assertEqual((await client.get(self.url)).json()["total"], 2)
            self.assertEqual(self.policy()["tool_overrides"], {"read_reference": False})
            self.assertEqual(self.policy(uuid4())["tool_overrides"], {"read_reference": False})
            self.assertEqual(self.service.resolve_tool_overrides(project_id=str(self.project), user_id=None, graph_id="reference_agent")["tool_overrides"], {"read_reference": False})
            self.assertEqual(self.policy(graph="workflow_demo")["tool_overrides"], {})
            other_url = self.url.replace(str(self.project), str(self.other_project))
            self.assertEqual((await client.delete(f"{other_url}/{user_row}")).status_code, 404)
            self.assertEqual((await client.delete(f"{self.url}/{user_row}")).status_code, 204)
            self.assertEqual(self.policy()["tool_overrides"], {"read_reference": False})
            self.engine.dispose()
            self.assertEqual(self.policy()["tool_overrides"], {"read_reference": False})
            self.assertEqual((await client.delete(f"{self.url}/{project_row}")).status_code, 204)
            self.assertEqual(self.policy(), empty)
            for changes in ({"subject_id": str(uuid4())}, {"tool_name": "unknown"}, {"graph_id": "workflow_demo"}):
                response = await client.post(self.url, json={**payload, **changes})
                self.assertEqual(response.status_code, 400, response.text)
            self.assertEqual((await client.post(self.url, json={**payload, "is_enabled": True})).status_code, 422)

    async def test_executor_cannot_manage_or_read_restrictions(self):
        self.actor = ActorContext(user_id=str(self.user), project_roles={str(self.project): ("project_viewer",)})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            self.assertEqual((await client.get(self.url)).status_code, 403)
            response = await client.post(self.url, json={"graph_id": "reference_agent", "subject_type": "project", "subject_id": str(self.project), "tool_name": "read_reference", "reason": "denied"})
            self.assertEqual(response.status_code, 403)
            self.catalog.read_tool_declarations.assert_not_awaited()

    def test_database_failure_does_not_allow_tools(self):
        broken = RuntimePolicyOverlayService(session_factory=Mock(side_effect=RuntimeError("database unavailable")), runtime_base_url="http://unused")
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            broken.resolve_tool_overrides(project_id=str(self.project), user_id=str(self.user), graph_id="reference_agent")

    def test_signing_policy_never_reads_tool_catalog(self):
        from unittest.mock import patch
        with patch("platform_api.modules.runtime_catalog.infra.sqlalchemy.repository.SqlAlchemyRuntimeCatalogRepository.list_tools", side_effect=AssertionError("Catalog is display only")):
            self.assertEqual(self.policy()["tool_overrides"], {})
            self.assertNotIn("allowed_tool_names", self.service.build_delegation_policy(project_id=str(self.project)))
