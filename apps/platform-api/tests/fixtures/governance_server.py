"""Opt-in local browser fixture: isolated Platform DB, existing local Runtime."""
import json
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import urlparse

import uvicorn
from sqlalchemy import select

from platform_api.bootstrap.lifespan import lifespan
from platform_api.core.db import session_scope
from platform_api.core.security import hash_password, create_runtime_delegation_token, empty_runtime_context_hash
from platform_api.main import create_app
from platform_api.modules.iam.domain import ProjectRole
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import ThreadAccessRecord
from platform_api.adapters.langgraph.runtime_gateway_upstream import LangGraphRuntimeGatewayUpstream

PASSWORD = "Governance-test-only-2026!"


def serve():
    if os.environ.get("RUN_LOCAL_GOVERNANCE_E2E") != "1":
        raise SystemExit("Set RUN_LOCAL_GOVERNANCE_E2E=1 to start the isolated fixture")
    with tempfile.TemporaryDirectory(prefix="platform-governance-e2e-") as directory:
        app = create_app()
        settings = app.state.settings
        assert urlparse(settings.langgraph_upstream_url).hostname in {"localhost", "127.0.0.1", "::1"}
        settings.database_url = f"sqlite:///{Path(directory) / 'platform.db'}"
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = True
        settings.bootstrap_admin_enabled = False
        settings.oidc_enabled = False
        settings.jwt_access_secret = token_urlsafe(48)
        settings.jwt_refresh_secret = token_urlsafe(48)
        settings.jwt_access_verification_keys = {}
        settings.jwt_refresh_verification_keys = {}

        @asynccontextmanager
        async def fixture_lifespan(application):
            async with lifespan(application):
                factory = application.state.db_session_factory
                with session_scope(factory) as session:
                    projects = SqlAlchemyProjectsRepository(session)
                    tenant = projects.get_or_create_default_tenant()
                    project = projects.create_project(tenant_id=tenant.id, name="Governance E2E", description="Temporary browser fixture")
                    project_id = str(project.id)
                    users = SqlAlchemyIdentityRepository(session)
                    identities = {}
                    for name, platform_roles, role in (
                        ("owner", (), ProjectRole.EXECUTOR), ("peer", (), ProjectRole.EXECUTOR),
                        ("manager", (), ProjectRole.ADMIN), ("superadmin", ("platform_super_admin",), None),
                        ("operator", ("platform_operator",), None), ("viewer", ("platform_viewer",), None),
                        ("provisioner", ("platform_super_admin",), ProjectRole.ADMIN),
                    ):
                        user = users.create_user(username=f"governance-{name}", password_hash=hash_password(PASSWORD),
                            external_subject=f"governance-{name}", email=None, platform_roles=platform_roles,
                            is_super_admin=name == "superadmin")
                        identities[name] = str(user.id)
                        if role:
                            projects.upsert_project_member(project_id=project.id, user_id=user.id, role=role)
                Path("/tmp/platform-governance-e2e.json").write_text(json.dumps({"project_id": project_id, "users": identities}))
                try:
                    yield
                finally:
                    with session_scope(factory) as session:
                        ids = list(session.scalars(select(ThreadAccessRecord.thread_id).where(ThreadAccessRecord.project_id == project_id)))
                    if ids:
                        token = create_runtime_delegation_token(subject="governance-fixture-cleanup", tenant_id="__default",
                            project_id=project_id, role="project_admin", permissions=[], policy_version="test",
                            allowed_model_ids=["platform:no-enabled-model"], tool_overrides={}, tool_policy_version="unscoped-read-v2",
                            scope={"tenant_id": "__default", "project_id": project_id, "operation": "read"},
                            context_hash=empty_runtime_context_hash(), settings=settings)
                        upstream = LangGraphRuntimeGatewayUpstream(base_url=settings.langgraph_upstream_url,
                            timeout_seconds=10, forwarded_headers={"authorization": f"Bearer {token}"})
                        failures = []
                        for thread_id in ids:
                            try:
                                row = await upstream.get_thread(thread_id)
                                assert row["metadata"]["project_id"] == project_id
                                await upstream.delete_thread(thread_id)
                            except Exception as exc:
                                failures.append(RuntimeError(f"Fixture cleanup failed: project={project_id}, thread={thread_id}: {exc}"))
                        if failures:
                            raise ExceptionGroup("Fixture Thread cleanup failed", failures)

        app.router.lifespan_context = fixture_lifespan
        uvicorn.run(app, host="127.0.0.1", port=12142, log_level="warning")


if __name__ == "__main__":
    serve()
