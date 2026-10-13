"""Real HTTP authentication/SQL membership with a controlled provider boundary."""

import asyncio
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event

from platform_api.config import KnowledgeConnection, Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.security import create_access_token
from platform_api.main import create_app
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.identity.models import UserRecord
from platform_api.modules.knowledge.service import KnowledgeService
from platform_api.modules.projects.models import (
    ProjectMemberRecord,
    ProjectRecord,
    TenantRecord,
)

JOB = "kj_" + "1" * 32
DOC = "kd_" + "2" * 32


def job_receipt(**changes):
    return {
        "version": 1,
        "job_id": JOB,
        "document_id": DOC,
        "file_name": "项目规范.md",
        "status": "queued",
        "searchable": False,
        "error_code": None,
        "created_at": "2026-10-12T00:00:00Z",
        "updated_at": "2026-10-12T00:00:00Z",
        **changes,
    }


class KnowledgeMembersTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = build_engine(f"sqlite:///{Path(self.temp.name) / 'knowledge.db'}")
        self.addCleanup(self.engine.dispose)
        create_core_tables(self.engine)
        self.factory = build_session_factory(self.engine)
        with self.factory.begin() as session:
            tenant = TenantRecord(name="knowledge", slug="knowledge")
            session.add(tenant)
            session.flush()
            project = ProjectRecord(name="knowledge", tenant_id=tenant.id)
            session.add(project)
            session.flush()
            self.project, self.tenant = str(project.id), str(tenant.id)
            self.users = {}
            for role in ("admin", "editor", "executor", "outsider"):
                user = UserRecord(username=role, external_subject=role)
                session.add(user)
                session.flush()
                self.users[role] = str(user.id)
                if role != "outsider":
                    session.add(
                        ProjectMemberRecord(
                            project_id=project.id, user_id=user.id, role=role
                        )
                    )
        self.app = create_app()
        self.settings = self.app.state.settings
        self.settings.platform_db_enabled = True
        self.settings.platform_db_auto_create = False
        self.settings.database_url = str(self.engine.url)
        self.settings.bootstrap_admin_enabled = False
        self.settings.auth_required = True
        self.settings.knowledge_mcp_bindings = {
            f"__default:{self.project}": "knowledge"
        }
        self.settings.knowledge_connections = {
            "knowledge": KnowledgeConnection(
                base_url="http://provider.invalid",
                token="synthetic-provider-token-" * 2,
                scope={"tenant_id": "__default", "project_id": self.project},
                knowledge_base_id="kb_" + "3" * 32,
            )
        }
        self.settings.knowledge_secret = "synthetic-knowledge-secret-" * 2
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.calls = []
        self.payload = {
            "version": 1,
            "read": True,
            "upload_enabled": True,
            "supported_mime_types": ["text/markdown", "text/plain"],
            "max_file_bytes": 20 * 1024**2,
            "disabled_reason": None,
        }

        def provider(request):
            self.calls.append(request)
            return httpx.Response(200, json=self.payload)

        self.app.state.knowledge_http = httpx.AsyncClient(
            transport=httpx.MockTransport(provider)
        )

    def headers(self, role="executor"):
        token = create_access_token(
            user_id=self.users[role], username=role, settings=self.settings
        )
        return {"Authorization": "Bearer " + token}

    def get(self, suffix="capabilities", **kwargs):
        return self.client.get(
            f"/api/projects/{self.project}/knowledge/{suffix}",
            headers=self.headers(),
            **kwargs,
        )

    def test_all_member_roles_have_distinct_read_and_upload_permissions(self):
        for role in ("admin", "editor", "executor"):
            response = self.client.get(
                f"/api/projects/{self.project}/knowledge/capabilities",
                headers=self.headers(role),
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse(response.json()["upload_enabled"])
            actor = ActorContext(
                user_id=self.users[role],
                project_roles={self.project: ("project_" + role,)},
            )
            for permission in (
                PermissionCode.PROJECT_KNOWLEDGE_READ,
                PermissionCode.PROJECT_KNOWLEDGE_UPLOAD,
            ):
                self.assertTrue(
                    IamPolicyEngine()
                    .evaluate(
                        actor=actor,
                        authorization=AuthorizationRequest(permission, self.project),
                    )
                    .allowed
                )
        self.assertFalse(
            IamPolicyEngine()
            .evaluate(
                actor=actor,
                authorization=AuthorizationRequest(
                    PermissionCode.PROJECT_RUNTIME_WRITE, self.project
                ),
            )
            .allowed
        )

    def test_nonmember_revoked_and_wrong_project_never_contact_provider(self):
        for project, headers in (
            (self.project, self.headers("outsider")),
            (str(uuid4()), self.headers()),
        ):
            self.assertEqual(
                self.client.get(
                    f"/api/projects/{project}/knowledge/jobs", headers=headers
                ).status_code,
                403,
            )
        old_headers = self.headers()
        with self.factory.begin() as session:
            session.query(ProjectMemberRecord).filter_by(
                project_id=UUID(self.project), user_id=UUID(self.users["executor"])
            ).delete()
        self.assertEqual(
            self.client.get(
                f"/api/projects/{self.project}/knowledge/jobs", headers=old_headers
            ).status_code,
            403,
        )
        self.assertEqual(self.calls, [])

    def test_project_disabled_or_provider_scope_mismatch_is_rejected(self):
        self.settings.knowledge_connections["knowledge"].scope["project_id"] = str(
            uuid4()
        )
        self.assertEqual(self.get().status_code, 404)
        self.settings.knowledge_connections["knowledge"].scope["project_id"] = (
            self.project
        )
        with self.factory.begin() as session:
            session.get(ProjectRecord, UUID(self.project)).status = "disabled"
        self.assertEqual(self.get().status_code, 404)
        self.assertEqual(self.calls, [])

    def test_public_projection_and_strict_queries(self):
        self.payload = {
            "items": [job_receipt(raw_data="SECRET", upload_id="PRIVATE")],
            "total": 1,
            "token": "SECRET",
        }
        response = self.get("jobs?limit=1&offset=0")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("SECRET", response.text)
        self.assertNotIn("PRIVATE", response.text)
        for suffix in (
            "jobs?limit=1&limit=2",
            "jobs?scope=other",
            "jobs?limit=101",
            "jobs/bad",
        ):
            self.assertIn(self.get(suffix).status_code, (400, 422))
        self.payload = job_receipt(job_id="kj_" + "4" * 32)
        self.assertEqual(self.get("jobs/" + JOB).status_code, 502)
        self.payload = {"items": [job_receipt(file_name="/PRIVATE")], "total": 1}
        self.assertEqual(self.get("jobs").status_code, 502)

    def test_no_configuration_returns_disabled_and_provider_failure_is_safe(self):
        self.settings.knowledge_connections = {}
        self.assertEqual(
            self.get().json()["disabled_reason"], "knowledge_not_configured"
        )
        self.assertEqual(self.get("documents").status_code, 404)
        self.assertEqual(self.calls, [])

    def test_configuration_rejects_reused_secret_and_unmanaged_connection(self):
        self.assertFalse(Settings(_env_file=None).knowledge_upload_enabled)
        for kwargs in (
            {"knowledge_upload_enabled": True},
            {"knowledge_secret": Settings(_env_file=None).jwt_access_secret},
        ):
            with self.assertRaises(ValidationError):
                Settings(_env_file=None, **kwargs)
        for url in (
            "file:///tmp/private",
            "https://user:pass@provider.invalid",
            "https://provider.invalid/path",
        ):
            with self.assertRaises(ValidationError):
                KnowledgeConnection(
                    base_url=url,
                    token="x" * 32,
                    scope={"tenant_id": "__default", "project_id": self.project},
                )

    def test_sessions_close_before_network_await_and_authorization_is_refreshed_after(
        self,
    ):
        threads = []
        event.listen(
            self.engine,
            "before_cursor_execute",
            lambda *a: threads.append(threading.get_ident()),
        )

        async def provider(*args):
            self.assertEqual(self.engine.pool.checkedout(), 0)
            with self.factory.begin() as session:
                session.query(ProjectMemberRecord).filter_by(
                    project_id=UUID(self.project), user_id=UUID(self.users["executor"])
                ).delete()
            return self.payload

        async def run():
            service = KnowledgeService(
                self.factory, self.settings, AsyncMock(get=provider)
            )
            actor = ActorContext(user_id=self.users["executor"])
            from platform_api.core.errors import ForbiddenError

            with self.assertRaises(ForbiddenError):
                await service.read(actor, self.project, "capabilities")

        asyncio.run(run())
        self.assertTrue(any(t != threading.get_ident() for t in threads))

    def test_provider_errors_and_oversized_response_are_bounded(self):
        from platform_api.adapters.knowledge.client import KnowledgeClient
        from platform_api.core.errors import PlatformApiError

        async def run():
            for status, content in (
                (500, b"SECRET /PRIVATE"),
                (200, b"x" * (1024**2 + 1)),
            ):
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(
                        lambda req, status=status, content=content: httpx.Response(
                            status, content=content
                        )
                    )
                ) as client:
                    with self.assertRaises(PlatformApiError) as caught:
                        await KnowledgeClient(client).get(
                            self.settings.knowledge_connections["knowledge"], "jobs"
                        )
                    self.assertEqual(caught.exception.code, "knowledge_unavailable")

        asyncio.run(run())
