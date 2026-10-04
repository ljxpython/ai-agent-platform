from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from platform_api.core.db import (
    build_engine,
    build_session_factory,
    create_core_tables,
    session_scope,
)
from platform_api.core.security import create_access_token, hash_password
from platform_api.main import create_app
from platform_api.modules.identity.models import RefreshTokenRecord, UserRecord
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.models import ProjectMemberRecord


class UserSoftDeleteApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "user-soft-delete.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.admin_username = "admin-user"
        self.admin_password = "admin123456"
        self.admin_user_id = self._create_admin_user()

        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.database_url = str(self._engine.url)
        settings.bootstrap_admin_enabled = False
        settings.api_docs_enabled = False
        settings.auth_required = True

        self.admin_access_token = create_access_token(
            user_id=self.admin_user_id,
            username=self.admin_username,
            settings=settings,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _headers(self, token: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token or self.admin_access_token}"}

    def _create_admin_user(self) -> str:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyIdentityRepository(session)
            user = repository.create_user(
                username=self.admin_username,
                password_hash=hash_password(self.admin_password),
                external_subject=self.admin_username,
                email="admin@example.com",
                is_super_admin=True,
                platform_roles=("platform_super_admin",),
            )
            return str(user.id)

    def _create_user(
        self,
        username: str,
        *,
        is_super_admin: bool = False,
        roles: tuple[str, ...] = (),
    ) -> str:
        res = self.client.post(
            "/api/users",
            json={
                "username": username,
                "password": "Password123!",
                "is_super_admin": is_super_admin,
                "platform_roles": list(roles),
            },
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["id"]

    def _create_project(self, name: str, user_id: str, username: str) -> str:
        user_token = create_access_token(
            user_id=user_id,
            username=username,
            settings=self.app.state.settings,
        )
        res = self.client.post(
            "/api/projects",
            json={"name": name},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["id"]

    def test_soft_delete_cannot_delete_self(self) -> None:
        res = self.client.delete(
            f"/api/users/{self.admin_user_id}",
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["error"]["code"], "cannot_delete_self")

    def test_soft_delete_last_super_admin_protected(self) -> None:
        admin2_id = self._create_user(
            "admin-2", is_super_admin=True, roles=("platform_super_admin",)
        )
        res = self.client.delete(f"/api/users/{admin2_id}", headers=self._headers())
        self.assertEqual(res.status_code, 200)

    def test_soft_delete_user_sole_project_admin_protected(self) -> None:
        user_id = self._create_user(
            "project-owner", is_super_admin=True, roles=("platform_super_admin",)
        )
        # 用该用户创建一个项目，该用户成为唯一 admin
        self._create_project("Sole Project", user_id, "project-owner")

        # 尝试删除该用户，应拦截并报错 user_is_sole_project_admin
        res = self.client.delete(f"/api/users/{user_id}", headers=self._headers())
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()["error"]["code"], "user_is_sole_project_admin")
        self.assertIn("Sole Project", res.json()["error"]["message"])

    def test_soft_delete_success_and_list_filter(self) -> None:
        user_id = self._create_user("bob")
        user_uuid = UUID(user_id)

        # admin 创建一个项目，将 bob 添加为普通成员 (executor)
        project_id = self._create_project(
            "Team Project", self.admin_user_id, self.admin_username
        )
        add_member_res = self.client.put(
            f"/api/projects/{project_id}/members/{user_id}",
            json={"role": "project_executor"},
            headers=self._headers(),
        )
        self.assertEqual(add_member_res.status_code, 200, add_member_res.text)

        # 添加一条 refresh token
        with session_scope(self._session_factory) as session:
            record = session.get(UserRecord, user_uuid)
            token = RefreshTokenRecord(
                user_id=user_uuid,
                token_id="token-bob",
                family_id="family-bob",
                expires_at=record.created_at,
            )
            session.add(token)

        # 软删除 bob
        del_res = self.client.delete(f"/api/users/{user_id}", headers=self._headers())
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["ok"])

        # 验证数据库状态
        with session_scope(self._session_factory) as session:
            record = session.get(UserRecord, user_uuid)
            self.assertIsNotNone(record)
            self.assertEqual(record.status, "deleted")
            self.assertTrue(record.username.startswith("bob#deleted#"))
            # 验证 token 被吊销
            token_record = (
                session.query(RefreshTokenRecord).filter_by(token_id="token-bob").one()
            )
            self.assertIsNotNone(token_record.revoked_at)
            # 验证项目成员记录被清除
            member_count = (
                session.query(ProjectMemberRecord).filter_by(user_id=user_uuid).count()
            )
            self.assertEqual(member_count, 0)

        # 验证原始 username "bob" 已被释放，可以重新注册！
        new_bob_id = self._create_user("bob")
        self.assertNotEqual(new_bob_id, user_id)

        # 验证 list_users 默认过滤已删除用户
        list_res = self.client.get("/api/users", headers=self._headers())
        self.assertEqual(list_res.status_code, 200)
        usernames = [u["username"] for u in list_res.json()["items"]]
        self.assertIn("bob", usernames)
        self.assertFalse(any("#deleted#" in u for u in usernames))

        # 验证显式指定 status=deleted 可查出
        deleted_list_res = self.client.get(
            "/api/users", params={"status": "deleted"}, headers=self._headers()
        )
        self.assertEqual(deleted_list_res.status_code, 200)
        del_items = deleted_list_res.json()["items"]
        self.assertTrue(any(u["id"] == user_id for u in del_items))
