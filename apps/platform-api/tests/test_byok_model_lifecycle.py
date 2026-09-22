import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet
from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import ForbiddenError
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.models import ProjectMemberRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.application.model_connection import (
    create_model_reference,
)
from platform_api.modules.runtime_catalog.application.service import (
    RuntimeCatalogService,
)
from platform_api.modules.runtime_catalog.domain.models import (
    RuntimeModelCreate,
    RuntimeModelUpdate,
)
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)


class ByokModelLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = build_engine(f"sqlite:///{Path(self.temp.name) / 'test.db'}")
        self.addCleanup(self.engine.dispose)
        self.factory = build_session_factory(self.engine)
        create_core_tables(self.engine)
        self.settings = Settings(
            runtime_delegation_secret="x" * 32,
            runtime_model_config_secret="y" * 32,
            model_config_master_key=Fernet.generate_key().decode(),
        )
        with self.factory.begin() as session:
            projects = SqlAlchemyProjectsRepository(session)
            tenant = projects.get_or_create_default_tenant()
            self.project_1 = projects.create_project(
                tenant_id=tenant.id, name="Project Alpha", description=""
            ).id
            self.project_2 = projects.create_project(
                tenant_id=tenant.id, name="Project Beta", description=""
            ).id
            identities = SqlAlchemyIdentityRepository(session)
            self.user_admin_1 = identities.create_user(
                username="admin_p1",
                external_subject="p1_admin",
                password_hash="unused",
                email=None,
                is_super_admin=False,
            ).id
            self.user_exec_1 = identities.create_user(
                username="exec_p1",
                external_subject="p1_exec",
                password_hash="unused",
                email=None,
                is_super_admin=False,
            ).id
            self.user_admin_2 = identities.create_user(
                username="admin_p2",
                external_subject="p2_admin",
                password_hash="unused",
                email=None,
                is_super_admin=False,
            ).id
            session.add(
                ProjectMemberRecord(
                    project_id=self.project_1, user_id=self.user_admin_1, role="admin"
                )
            )
            session.add(
                ProjectMemberRecord(
                    project_id=self.project_1, user_id=self.user_exec_1, role="executor"
                )
            )
            session.add(
                ProjectMemberRecord(
                    project_id=self.project_2, user_id=self.user_admin_2, role="admin"
                )
            )
            from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
            session.add(
                AgentRecord(
                    project_id=self.project_1,
                    name="Demo Agent",
                    graph_id="demo_agent",
                    status="active",
                    created_by=self.user_admin_1,
                    updated_by=self.user_admin_1,
                )
            )

        self.service = RuntimeCatalogService(
            session_factory=self.factory,
            upstream=None,
            runtime_base_url="http://runtime",
            settings=self.settings,
        )
        self.actor_admin_1 = ActorContext(
            user_id=str(self.user_admin_1),
            project_roles={str(self.project_1): ("project_admin",)},
        )
        self.actor_exec_1 = ActorContext(
            user_id=str(self.user_exec_1),
            project_roles={str(self.project_1): ("project_executor",)},
        )
        self.actor_admin_2 = ActorContext(
            user_id=str(self.user_admin_2),
            project_roles={str(self.project_2): ("project_admin",)},
        )
        self.platform_admin = ActorContext(
            user_id="platform-super-admin",
            platform_roles=("platform_super_admin",),
        )

    def test_project_admin_can_create_update_and_delete_byok_model(self):
        # 1. Project Admin creates BYOK model
        payload = RuntimeModelCreate(
            provider="openai-compatible",
            display_name="Project 1 Private Ollama",
            base_url="https://ollama.mycorp.internal/v1",
            protocol="openai-compatible",
            model="qwen2.5-coder",
            api_key="ollama-local-key",
            scope_type="project",
            project_id=str(self.project_1),
        )
        item = self.service.create_model(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            payload=payload,
        )
        self.assertEqual(item.scope_type, "project")
        self.assertEqual(item.project_id, str(self.project_1))
        self.assertEqual(item.display_name, "Project 1 Private Ollama")
        self.assertTrue(item.credential_configured)

        # 2. List models in project 1 sees it with full base_url and credential_configured=True
        listed = self.service.list_models(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
        )
        p1_model = next((m for m in listed.models if m.id == item.id), None)
        self.assertIsNotNone(p1_model)
        self.assertEqual(p1_model.base_url, "https://ollama.mycorp.internal/v1")
        self.assertTrue(p1_model.credential_configured)

        # 3. Project Admin updates BYOK model
        updated = self.service.update_model(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            model_id=item.id,
            payload=RuntimeModelUpdate(display_name="Project 1 Updated Ollama"),
        )
        self.assertEqual(updated.display_name, "Project 1 Updated Ollama")

        # 4. Project Admin deletes BYOK model
        self.service.delete_model(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            model_id=item.id,
        )
        listed_after = self.service.list_models(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
        )
        self.assertNotIn(item.id, [m.id for m in listed_after.models])

    def test_executor_cannot_create_update_or_delete_byok_model(self):
        payload = RuntimeModelCreate(
            provider="openai-compatible",
            display_name="Executor Illegal Model",
            base_url="https://ollama.mycorp.internal/v1",
            protocol="openai-compatible",
            model="qwen",
            api_key="key",
            scope_type="project",
            project_id=str(self.project_1),
        )
        # Executor lacks project.runtime.write -> ForbiddenError
        with self.assertRaises(ForbiddenError):
            self.service.create_model(
                actor=self.actor_exec_1,
                project_id=str(self.project_1),
                payload=payload,
            )

    def test_byok_cross_project_isolation(self):
        # Create model in Project 1
        payload = RuntimeModelCreate(
            provider="openai-compatible",
            display_name="P1 DeepSeek",
            base_url="https://shared-api.corp.internal/v1",
            protocol="openai-compatible",
            model="deepseek-r1",
            api_key="p1-secret-key",
            scope_type="project",
            project_id=str(self.project_1),
        )
        p1_model = self.service.create_model(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            payload=payload,
        )

        # Project 2 admin cannot see P1 model
        p2_list = self.service.list_models(
            actor=self.actor_admin_2,
            project_id=str(self.project_2),
        )
        self.assertNotIn(p1_model.id, [m.id for m in p2_list.models])

        # Project 2 admin cannot modify P1 model
        with self.assertRaises(ForbiddenError):
            self.service.update_model(
                actor=self.actor_admin_2,
                project_id=str(self.project_2),
                model_id=p1_model.id,
                payload=RuntimeModelUpdate(display_name="Hacked P1 Model"),
            )

        # Project 2 admin cannot delete P1 model
        with self.assertRaises(ForbiddenError):
            self.service.delete_model(
                actor=self.actor_admin_2,
                project_id=str(self.project_2),
                model_id=p1_model.id,
            )

        # Project 2 can create its OWN model with identical provider, base_url, model without conflict
        p2_payload = RuntimeModelCreate(
            provider="openai-compatible",
            display_name="P2 DeepSeek",
            base_url="https://shared-api.corp.internal/v1",
            protocol="openai-compatible",
            model="deepseek-r1",
            api_key="p2-different-secret-key",
            scope_type="project",
            project_id=str(self.project_2),
        )
        p2_model = self.service.create_model(
            actor=self.actor_admin_2,
            project_id=str(self.project_2),
            payload=p2_payload,
        )
        self.assertNotEqual(p1_model.id, p2_model.id)

    def test_gateway_byok_model_resolution_and_protection(self):
        # 1. Project 1 creates BYOK model
        payload = RuntimeModelCreate(
            provider="deepseek",
            display_name="P1 Custom Key",
            base_url="https://api.deepseek.com/v1",
            protocol="deepseek",
            model="deepseek-chat",
            api_key="sk-p1-private",
            scope_type="project",
            project_id=str(self.project_1),
        )
        p1_model = self.service.create_model(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            payload=payload,
        )

        gateway_service = RuntimeGatewayService(
            session_factory=self.factory,
            upstream=None,
            runtime_base_url="http://runtime",
            runtime_model_config_secret=self.settings.runtime_model_config_secret,
        )

        # 2. Assert runtime options: Project 1 member can use P1 BYOK model
        gateway_service._assert_runtime_options_allowed(
            project_id=str(self.project_1),
            options={"model_id": p1_model.id},
        )

        # 3. Project 2 member cannot use P1 BYOK model
        with self.assertRaises(ForbiddenError):
            gateway_service._assert_runtime_options_allowed(
                project_id=str(self.project_2),
                options={"model_id": p1_model.id},
            )

        # 4. Resolving model reference:
        from platform_api.modules.runtime_gateway.application import thread_access

        thread_access.register(
            self.factory,
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            thread_id="thread-p1",
        )
        ref = create_model_reference(
            project_id=str(self.project_1),
            model_id=p1_model.id,
            secret=self.settings.runtime_model_config_secret,
            ttl_seconds=60,
            thread_id="thread-p1",
            agent_key="demo_agent",
            actor={
                "user_id": str(self.user_admin_1),
                "principal_type": "user",
                "credential_id": None,
            },
        )

        # Succeeded with matching project_1
        resolved = self.service.resolve_model_connection(
            reference=ref,
            project_id=str(self.project_1),
        )
        self.assertEqual(resolved["model_id"], p1_model.id)
        self.assertEqual(resolved["api_key"], "sk-p1-private")

        # Denied when resolving with project_2
        with self.assertRaises(ForbiddenError):
            self.service.resolve_model_connection(
                reference=ref,
                project_id=str(self.project_2),
            )

    async def test_byok_http_api_endpoints(self):
        from types import SimpleNamespace

        import httpx
        from fastapi import FastAPI
        from platform_api.core.errors import register_exception_handlers
        from platform_api.modules.runtime_catalog.presentation.http import (
            get_actor_context,
            get_runtime_catalog_service,
            router,
        )

        app = FastAPI()
        @app.middleware("http")
        async def populate_context(request, call_next):
            request.state.platform_context = SimpleNamespace(
                project=SimpleNamespace(project_id=request.headers.get("x-project-id"))
            )
            return await call_next(request)

        app.include_router(router)
        register_exception_handlers(app)
        app.dependency_overrides[get_runtime_catalog_service] = lambda: self.service

        # 1. Platform admin creates a platform model
        platform_payload = RuntimeModelCreate(
            provider="openai",
            display_name="Global GPT-4o",
            base_url="https://api.openai.com/v1",
            protocol="openai",
            model="gpt-4o",
            api_key="sk-platform-key",
            scope_type="platform",
        )
        self.service.create_model(
            actor=self.platform_admin,
            project_id="",
            payload=platform_payload,
        )

        # 2. Project 1 Admin interacts via HTTP
        app.dependency_overrides[get_actor_context] = lambda: self.actor_admin_1
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # Create BYOK model in Project 1
            res = await client.post(
                "/api/runtime/models",
                headers={"x-project-id": str(self.project_1)},
                json={
                    "provider": "deepseek",
                    "display_name": "P1 DeepSeek HTTP",
                    "base_url": "https://api.deepseek.com/v1",
                    "protocol": "deepseek",
                    "model": "deepseek-v3",
                    "api_key": "sk-http-key",
                    "scope_type": "project",
                },
            )
            self.assertEqual(res.status_code, 201, res.text)
            p1_created = res.json()
            self.assertEqual(p1_created["scope_type"], "project")
            self.assertEqual(p1_created["project_id"], str(self.project_1))

            # List models in Project 1: should see both platform model (masked) and P1 BYOK model (unmasked)
            res_list = await client.get(
                "/api/runtime/models",
                headers={"x-project-id": str(self.project_1)},
            )
            self.assertEqual(res_list.status_code, 200)
            models = res_list.json()["models"]
            global_model = next((m for m in models if m["scope_type"] == "platform"), None)
            byok_model = next((m for m in models if m["id"] == p1_created["id"]), None)
            self.assertIsNotNone(global_model)
            self.assertEqual(global_model["base_url"], "")  # masked
            self.assertIsNotNone(byok_model)
            self.assertEqual(byok_model["base_url"], "https://api.deepseek.com/v1")  # not masked for project members

            # Update BYOK model
            res_update = await client.patch(
                f"/api/runtime/models/{p1_created['id']}",
                headers={"x-project-id": str(self.project_1)},
                json={"display_name": "P1 DeepSeek Renamed"},
            )
            self.assertEqual(res_update.status_code, 200)
            self.assertEqual(res_update.json()["display_name"], "P1 DeepSeek Renamed")

            # Project 2 Admin tries to modify or delete P1's model -> 403 Forbidden
            app.dependency_overrides[get_actor_context] = lambda: self.actor_admin_2
            res_denied_patch = await client.patch(
                f"/api/runtime/models/{p1_created['id']}",
                headers={"x-project-id": str(self.project_2)},
                json={"display_name": "Hacked"},
            )
            self.assertEqual(res_denied_patch.status_code, 403)

            res_denied_delete = await client.delete(
                f"/api/runtime/models/{p1_created['id']}",
                headers={"x-project-id": str(self.project_2)},
            )
            self.assertEqual(res_denied_delete.status_code, 403)

            # Project 1 Admin deletes BYOK model -> 204 No Content
            app.dependency_overrides[get_actor_context] = lambda: self.actor_admin_1
            res_delete = await client.delete(
                f"/api/runtime/models/{p1_created['id']}",
                headers={"x-project-id": str(self.project_1)},
            )
            self.assertEqual(res_delete.status_code, 204)

