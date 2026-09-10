import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet
from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import ForbiddenError, NotFoundError
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.models import ProjectMemberRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.application.credentials import encrypt_api_key
from platform_api.modules.runtime_catalog.application.model_connection import (
    create_model_reference,
)
from platform_api.modules.runtime_catalog.application.service import (
    RuntimeCatalogService,
)
from platform_api.modules.runtime_catalog.infra.sqlalchemy.repository import (
    SqlAlchemyRuntimeCatalogRepository,
)
from platform_api.modules.runtime_policies.infra.sqlalchemy.models import (
    ProjectModelPolicyRecord,
)


class ModelConnectionLifecycleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = build_engine(f"sqlite:///{Path(self.temp.name) / 'models.db'}")
        self.addCleanup(self.engine.dispose)
        self.factory = build_session_factory(self.engine)
        create_core_tables(self.engine)
        self.settings = Settings(runtime_delegation_secret="x" * 32,
                                 model_config_master_key=Fernet.generate_key().decode())
        self.values = dict(provider="openai", display_name="A", base_url="https://example.com",
                           protocol="openai", model="same-model", enabled=True,
                           api_key_ciphertext=encrypt_api_key("old", master_key=self.settings.model_config_master_key))
        with self.factory.begin() as session:
            projects = SqlAlchemyProjectsRepository(session)
            tenant = projects.get_or_create_default_tenant()
            self.project = projects.create_project(tenant_id=tenant.id, name="Test", description="").id
            self.user = SqlAlchemyIdentityRepository(session).create_user(
                username="test", external_subject="test", password_hash="unused",
                email=None, is_super_admin=False).id
            session.add(ProjectMemberRecord(project_id=self.project, user_id=self.user, role="admin"))
            session.add(AgentRecord(project_id=self.project, name="Demo", graph_id="demo",
                                    created_by=self.user, updated_by=self.user))
            repo = SqlAlchemyRuntimeCatalogRepository(session)
            self.model = repo.create_configured_model(values=self.values).id
        self.service = RuntimeCatalogService(session_factory=self.factory, upstream=None,
                                             runtime_base_url="http://runtime", settings=self.settings)
        self.reference = create_model_reference(project_id=str(self.project), model_id=str(self.model),
            secret=self.settings.runtime_delegation_secret, agent_key="demo",
            actor={"user_id": str(self.user), "principal_type": "user", "credential_id": None})

    async def resolve(self):
        return self.service.resolve_model_connection(reference=self.reference, project_id=str(self.project))

    async def test_same_model_connections_are_distinct_and_rotation_keeps_identity(self):
        with self.factory.begin() as session:
            repo = SqlAlchemyRuntimeCatalogRepository(session)
            second = repo.create_configured_model(values={**self.values, "display_name": "B"})
            self.assertNotEqual(self.model, second.id)
            repo.update_configured_model(self.model, values={"api_key_ciphertext": encrypt_api_key(
                "rotated", master_key=self.settings.model_config_master_key)})
        result = await self.resolve()
        self.assertEqual(result["model_id"], str(self.model))
        self.assertEqual(result["api_key"], "rotated")
        public = self.service.list_models(actor=ActorContext(
                user_id=str(self.user), project_roles={str(self.project): ("project_admin",)}),
            project_id=str(self.project))
        from platform_api.modules.runtime_policies.application.service import (
            RuntimePolicyOverlayService,
        )
        policy = RuntimePolicyOverlayService(session_factory=self.factory, runtime_base_url="http://runtime").build_delegation_policy(project_id=str(self.project))
        self.assertIn(str(self.model), policy["allowed_model_ids"])
        self.assertEqual(public.count, 2)
        self.assertNotIn("sync_status", public.models[0].model_dump())
        self.assertNotIn("api_key", public.models[0].model_dump())

    async def test_current_model_policy_and_membership_revoke_redemption(self):
        await self.resolve()
        with self.factory.begin() as session:
            policy = ProjectModelPolicyRecord(project_id=self.project, model_catalog_id=self.model,
                                               is_enabled=False, is_default_for_project=False)
            session.add(policy)
        with self.assertRaises(ForbiddenError):
            await self.resolve()
        with self.factory.begin() as session:
            from sqlalchemy import delete
            session.execute(delete(ProjectModelPolicyRecord))
            session.execute(delete(ProjectMemberRecord))
        with self.assertRaises(ForbiddenError):
            await self.resolve()

    async def test_globally_disabled_model_cannot_be_redeemed(self):
        with self.factory.begin() as session:
            SqlAlchemyRuntimeCatalogRepository(session).update_configured_model(self.model, values={"enabled": False})
        with self.assertRaises(NotFoundError):
            await self.resolve()

    async def test_service_account_revoked_token_is_not_reusable(self):
        from platform_api.modules.service_accounts.models import ServiceAccountRecord, ServiceAccountTokenRecord, ServiceAccountProjectGrantRecord
        with self.factory.begin() as session:
            account = ServiceAccountRecord(name="worker", status="active")
            session.add(account)
            session.flush()
            token = ServiceAccountTokenRecord(service_account_id=account.id, name="test",
                token_prefix="unused", token_secret_hash="unused", status="active")
            session.add(token)
            session.flush()
            credential_id = token.id
            session.add(ServiceAccountProjectGrantRecord(service_account_id=account.id,
                project_id=self.project, role="executor"))
        self.reference = create_model_reference(project_id=str(self.project), model_id=str(self.model),
            secret=self.settings.runtime_delegation_secret, agent_key="demo",
            actor={"principal_type": "service_account", "credential_id": str(credential_id)})
        await self.resolve()
        with self.factory.begin() as session:
            session.get(ServiceAccountTokenRecord, credential_id).status = "revoked"
        with self.assertRaises(ForbiddenError):
            await self.resolve()

    async def test_agent_disable_blocks_reference_redemption(self):
        from sqlalchemy import select
        with self.factory.begin() as session:
            session.scalar(select(AgentRecord)).status = "disabled"
        with self.assertRaises(ForbiddenError):
            await self.resolve()
