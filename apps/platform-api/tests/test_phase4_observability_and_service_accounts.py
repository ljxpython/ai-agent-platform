from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from platform_api.main import create_app
from platform_api.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from platform_api.core.security import create_access_token, hash_password
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository


class Phase4ObservabilityAndServiceAccountsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "phase4-observability.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)
        self.user_id = self._create_admin_user()

        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.database_url = str(self._engine.url)
        settings.bootstrap_admin_enabled = False
        settings.api_docs_enabled = False
        settings.service_accounts_enabled = True
        settings.auth_required = True

        self.access_token = create_access_token(
            user_id=self.user_id,
            username="phase4-admin",
            settings=settings,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _create_admin_user(self) -> str:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyIdentityRepository(session)
            user = repository.create_user(
                username="phase4-admin",
                password_hash=hash_password("admin123456"),
                external_subject="phase4-admin",
                email="phase4@example.com",
                is_super_admin=True,
            )
            return str(user.id)

    def _create_operator_user(self) -> tuple[str, str]:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyIdentityRepository(session)
            user = repository.create_user(
                username="phase4-operator",
                password_hash=hash_password("operator123456"),
                external_subject="phase4-operator",
                email="operator@example.com",
                platform_roles=("platform_operator",),
                is_super_admin=False,
            )
        token = create_access_token(
            user_id=str(user.id),
            username=user.username,
            settings=self.app.state.settings,
        )
        return str(user.id), token

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def test_service_account_api_key_can_read_metrics_but_cannot_write_platform_config(self) -> None:
        create_response = self.client.post(
            "/api/service-accounts",
            headers=self._auth_headers(),
            json={
                "name": "phase4-viewer",
                "description": "phase-4 viewer key",
                "platform_roles": ["platform_viewer"],
            },
        )
        self.assertEqual(create_response.status_code, 200, create_response.text)
        service_account_id = create_response.json()["id"]

        token_response = self.client.post(
            f"/api/service-accounts/{service_account_id}/tokens",
            headers=self._auth_headers(),
            json={"name": "default"},
        )
        self.assertEqual(token_response.status_code, 200, token_response.text)
        api_key = token_response.json()["plain_text_token"]

        metrics_response = self.client.get(
            "/_system/metrics",
            headers={"x-platform-api-key": api_key},
        )
        self.assertEqual(metrics_response.status_code, 200, metrics_response.text)
        payload = metrics_response.json()
        self.assertIn("requests", payload)
        self.assertNotIn("operations", payload)
        self.assertNotIn("workers", payload)

        users_response = self.client.get(
            "/api/users",
            headers={"x-platform-api-key": api_key},
        )
        self.assertEqual(users_response.status_code, 200, users_response.text)

        forbidden_response = self.client.patch(
            "/_system/platform-config/feature-flags",
            headers={"x-platform-api-key": api_key},
            json={"feature_flags": {"platform_config_enabled": False}},
        )
        self.assertEqual(forbidden_response.status_code, 403, forbidden_response.text)


    def test_operator_cannot_manage_super_admin_service_account_credentials(self) -> None:
        _, operator_token = self._create_operator_user()
        operator_headers = {
            "Authorization": f"Bearer {operator_token}",
            "Content-Type": "application/json",
        }
        create_response = self.client.post(
            "/api/service-accounts",
            headers=operator_headers,
            json={
                "name": "forged-super-admin",
                "platform_roles": ["platform_super_admin"],
            },
        )
        self.assertEqual(create_response.status_code, 403, create_response.text)

        admin_create_response = self.client.post(
            "/api/service-accounts",
            headers=self._auth_headers(),
            json={
                "name": "protected-super-admin",
                "platform_roles": ["platform_super_admin"],
            },
        )
        self.assertEqual(admin_create_response.status_code, 200, admin_create_response.text)
        account_id = admin_create_response.json()["id"]

        admin_token_response = self.client.post(
            f"/api/service-accounts/{account_id}/tokens",
            headers=self._auth_headers(),
            json={"name": "protected-token"},
        )
        self.assertEqual(admin_token_response.status_code, 200, admin_token_response.text)
        token_id = admin_token_response.json()["token"]["id"]

        token_response = self.client.post(
            f"/api/service-accounts/{account_id}/tokens",
            headers=operator_headers,
            json={"name": "forged-token"},
        )
        self.assertEqual(token_response.status_code, 403, token_response.text)

        demote_response = self.client.patch(
            f"/api/service-accounts/{account_id}",
            headers=operator_headers,
            json={"platform_roles": ["platform_viewer"]},
        )
        self.assertEqual(demote_response.status_code, 403, demote_response.text)

        disable_response = self.client.patch(
            f"/api/service-accounts/{account_id}",
            headers=operator_headers,
            json={"status": "disabled"},
        )
        self.assertEqual(disable_response.status_code, 403, disable_response.text)

        revoke_response = self.client.delete(
            f"/api/service-accounts/{account_id}/tokens/{token_id}",
            headers=operator_headers,
        )
        self.assertEqual(revoke_response.status_code, 403, revoke_response.text)

    def test_platform_audit_filters_projects_without_exposing_private_metadata(self) -> None:
        from uuid import uuid4
        from platform_api.modules.audit.models import AuditLogRecord

        project_id = str(uuid4())
        with session_scope(self._session_factory) as session:
            session.add(AuditLogRecord(
                request_id="audit-privacy-test", plane="runtime_gateway", action="thread.read",
                project_id=project_id, result="success", method="GET", path="/api/langgraph/threads/thread",
                status_code=200, duration_ms=1,
                metadata_json={"query": "memory=private", "body": "private text", "api_key": "secret",
                               "reason": "support", "graph_id": "demo"},
            ))
        _, token = self._create_operator_user()
        response = self.client.get("/api/audit", params={"project_id": project_id},
                                   headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        item = next(item for item in response.json()["items"] if item["request_id"] == "audit-privacy-test")
        self.assertEqual(item["metadata"], {"reason": "support", "graph_id": "demo"})

    def test_identity_profile_exposes_authoritative_platform_permissions(self) -> None:
        _, token = self._create_operator_user()
        response = self.client.get("/api/identity/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200, response.text)
        permissions = response.json()["permissions"]
        self.assertIn("platform.model.write", permissions)
        self.assertIn("platform.user.create", permissions)
        self.assertNotIn("platform.user.role.write", permissions)
        self.assertTrue(all(value.startswith("platform.") for value in permissions))


    @staticmethod
    def _run_async(coro):
        import asyncio

        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
