import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from cryptography.fernet import Fernet
from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import ConflictError
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.models import ProjectMemberRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.application.service import RuntimeCatalogService
from platform_api.modules.runtime_catalog.domain.models import RuntimeModelCreate, RuntimeModelUpdate
from platform_api.modules.runtime_policies.infra.sqlalchemy.repository import (
    SqlAlchemyRuntimePolicyRepository,
)


class ModelCatalogAndPolicyUniquenessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = build_engine(f"sqlite:///{Path(self.temp.name) / "test.db"}")
        self.addCleanup(self.engine.dispose)
        self.factory = build_session_factory(self.engine)
        create_core_tables(self.engine)
        self.settings = Settings(
            runtime_delegation_secret="x" * 32,
            model_config_master_key=Fernet.generate_key().decode(),
        )
        with self.factory.begin() as session:
            projects = SqlAlchemyProjectsRepository(session)
            tenant = projects.get_or_create_default_tenant()
            self.project = projects.create_project(
                tenant_id=tenant.id, name="Test Project", description=""
            ).id
            self.user = SqlAlchemyIdentityRepository(session).create_user(
                username="admin_user",
                external_subject="admin",
                password_hash="unused",
                email=None,
                is_super_admin=True,
            ).id
            session.add(
                ProjectMemberRecord(
                    project_id=self.project, user_id=self.user, role="admin"
                )
            )
        self.service = RuntimeCatalogService(
            session_factory=self.factory,
            upstream=None,
            runtime_base_url="http://runtime",
            settings=self.settings,
        )
        self.actor = ActorContext(
            user_id=str(self.user),
            platform_roles=("platform_super_admin",),
            project_roles={str(self.project): ("project_admin",)},
        )

    def test_duplicate_model_creation_fails_with_conflict(self):
        payload = RuntimeModelCreate(
            provider="deepseek",
            base_url="https://api.deepseek.com/v1",
            protocol="deepseek",
            model="DeepSeek-V4-Flash",
            display_name="DeepSeek V4 Flash",
            api_key="sk-test-key",
            enabled=True,
        )
        item = self.service.create_model(
            actor=self.actor,
            project_id=str(self.project),
            payload=payload,
        )
        self.assertEqual(item.model, "DeepSeek-V4-Flash")

        updated = self.service.update_model(
            actor=self.actor,
            project_id=str(self.project),
            model_id=item.id,
            payload=RuntimeModelUpdate(enabled=False),
        )
        self.assertFalse(updated.enabled)
        self.assertEqual(updated.model, item.model)

        duplicate_payload = RuntimeModelCreate(
            provider="deepseek",
            base_url="https://api.deepseek.com/v1",
            protocol="deepseek",
            model="DeepSeek-V4-Flash",
            display_name="Another DeepSeek Name",
            api_key="sk-another-key",
            enabled=True,
        )
        with self.assertRaises(ConflictError) as ctx:
            self.service.create_model(
                actor=self.actor,
                project_id=str(self.project),
                payload=duplicate_payload,
            )
        self.assertEqual(ctx.exception.code, "duplicate_model")

    def test_default_model_policy_is_mutually_exclusive(self):
        model1 = self.service.create_model(
            actor=self.actor,
            project_id=str(self.project),
            payload=RuntimeModelCreate(
                provider="deepseek",
                base_url="https://api.deepseek.com/v1",
                protocol="deepseek",
                model="deepseek-chat",
                display_name="DeepSeek Chat",
                api_key="sk-key1",
                enabled=True,
            ),
        )
        model2 = self.service.create_model(
            actor=self.actor,
            project_id=str(self.project),
            payload=RuntimeModelCreate(
                provider="deepseek",
                base_url="https://api.deepseek.com/v1",
                protocol="deepseek",
                model="deepseek-reasoner",
                display_name="DeepSeek Reasoner",
                api_key="sk-key2",
                enabled=True,
            ),
        )

        m1_id = UUID(model1.id)
        m2_id = UUID(model2.id)

        with self.factory.begin() as session:
            repo = SqlAlchemyRuntimePolicyRepository(session)
            repo.upsert_model_policy(
                project_id=self.project,
                model_catalog_id=m1_id,
                is_enabled=True,
                is_default_for_project=True,
                temperature_default=None,
                note=None,
                updated_by="admin",
            )

        with self.factory.begin() as session:
            repo = SqlAlchemyRuntimePolicyRepository(session)
            self.assertEqual(
                repo.get_default_model_id(project_id=self.project),
                str(m1_id),
            )

        with self.factory.begin() as session:
            repo = SqlAlchemyRuntimePolicyRepository(session)
            repo.upsert_model_policy(
                project_id=self.project,
                model_catalog_id=m2_id,
                is_enabled=True,
                is_default_for_project=True,
                temperature_default=None,
                note=None,
                updated_by="admin",
            )

        with self.factory.begin() as session:
            repo = SqlAlchemyRuntimePolicyRepository(session)
            policies = repo.list_model_policies(project_id=self.project)
            policy_map = {p.model_catalog_id: p.is_default_for_project for p in policies}
            self.assertFalse(policy_map[m1_id])
            self.assertTrue(policy_map[m2_id])
            default_count = sum(1 for p in policies if p.is_default_for_project)
            self.assertEqual(default_count, 1)
            self.assertEqual(
                repo.get_default_model_id(project_id=self.project),
                str(m2_id),
            )

if __name__ == "__main__":
    unittest.main()
