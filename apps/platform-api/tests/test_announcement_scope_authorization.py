from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from platform_api.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from platform_api.core.security import create_access_token, hash_password
from platform_api.main import create_app
from platform_api.modules.iam.domain import ProjectRole
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository


class AnnouncementScopeAuthorizationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "announcement-scope.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)
        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.database_url = str(self._engine.url)
        settings.bootstrap_admin_enabled = False
        settings.auth_required = True

        with session_scope(self._session_factory) as session:
            identities = SqlAlchemyIdentityRepository(session)
            admin = identities.create_user(
                username="announcement-admin",
                password_hash=hash_password("password123"),
                external_subject="announcement-admin",
                email=None,
                platform_roles=("platform_super_admin",),
                is_super_admin=True,
            )
            editor = identities.create_user(
                username="announcement-editor",
                password_hash=hash_password("password123"),
                external_subject="announcement-editor",
                email=None,
                platform_roles=(),
                is_super_admin=False,
            )
            projects = SqlAlchemyProjectsRepository(session)
            tenant = projects.get_or_create_default_tenant()
            source = projects.create_project(tenant_id=tenant.id, name="Source", description="")
            target = projects.create_project(tenant_id=tenant.id, name="Target", description="")
            projects.upsert_project_member(
                project_id=source.id,
                user_id=admin.id,
                role=ProjectRole.ADMIN,
            )
            projects.upsert_project_member(
                project_id=target.id,
                user_id=editor.id,
                role=ProjectRole.EDITOR,
            )
            self.admin_id = str(admin.id)
            self.editor_id = str(editor.id)
            self.source_id = str(source.id)
            self.target_id = str(target.id)

        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _headers(
        self, user_id: str, username: str, project_id: str | None = None
    ) -> dict[str, str]:
        token = create_access_token(user_id=user_id, username=username, settings=self.app.state.settings)
        headers = {"Authorization": f"Bearer {token}"}
        if project_id:
            headers["x-project-id"] = project_id
        return headers

    def test_scope_migration_requires_source_and_target_permissions(self) -> None:
        created = self.client.post(
            "/api/announcements",
            headers=self._headers(
                self.admin_id, "announcement-admin", self.source_id
            ),
            json={
                "title": "Source announcement",
                "scope_type": "project",
                "scope_project_id": self.source_id,
            },
        )
        self.assertEqual(created.status_code, 200, created.text)

        moved = self.client.patch(
            f"/api/announcements/{created.json()['id']}",
            headers=self._headers(
                self.editor_id, "announcement-editor", self.target_id
            ),
            json={
                "scope_type": "project",
                "scope_project_id": self.target_id,
            },
        )

        self.assertEqual(moved.status_code, 403, moved.text)
        self.assertEqual(moved.json()["error"]["code"], "project_role_missing")

    def test_global_list_does_not_reveal_project_announcements(self) -> None:
        headers = self._headers(self.admin_id, "announcement-admin", self.source_id)
        project = self.client.post("/api/announcements", headers=headers, json={
            "title": "Private project notice", "scope_type": "project", "scope_project_id": self.source_id,
        })
        self.assertEqual(project.status_code, 200, project.text)
        global_notice = self.client.post("/api/announcements", headers=headers, json={
            "title": "Platform notice", "scope_type": "global",
        })
        self.assertEqual(global_notice.status_code, 200, global_notice.text)
        global_list = self.client.get("/api/announcements", headers=headers)
        self.assertEqual(global_list.status_code, 200, global_list.text)
        self.assertEqual([item["id"] for item in global_list.json()["items"]], [global_notice.json()["id"]])
        immutable = self.client.patch(f"/api/announcements/{project.json()['id']}", headers=headers,
                                     json={"scope_type": "global"})
        self.assertEqual(immutable.status_code, 400, immutable.text)
        self.assertEqual(immutable.json()["error"]["code"], "announcement_scope_immutable")


if __name__ == "__main__":
    unittest.main()
