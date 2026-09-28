"""Opt-in platform error fixture with an isolated database and controlled upstream."""

import json
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import token_urlsafe
from uuid import uuid4

import uvicorn

from platform_api.adapters.langgraph.sdk_client import create_runtime_upstream_error
from platform_api.bootstrap.lifespan import lifespan
from platform_api.core.db import session_scope
from platform_api.core.errors import ForbiddenError
from platform_api.core.security import hash_password
from platform_api.main import create_app
from platform_api.modules.iam.domain import ProjectRole
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_gateway.presentation.http import (
    get_runtime_gateway_service,
)

PASSWORD = "Error-contract-test-only-2026!"
STATE = Path("/tmp/platform-error-contract-e2e.json")


class ControlledGateway:
    def __init__(self):
        self.pending = {}
        self.create_calls = 0

    async def create_thread(self, *, actor, project_id, payload):
        self.create_calls += 1
        thread_id = str(uuid4())
        self.pending[thread_id] = {
            "owner": actor.user_id,
            "project_id": project_id,
            "checks": 0,
        }
        error = create_runtime_upstream_error(
            status_code=503,
            detail={"detail": "private-upstream-marker"},
            fallback_code="thread_create_failed",
        )
        error.extra.update(
            {
                "thread_id": thread_id,
                "reconcile_path": f"/api/langgraph/threads/{thread_id}/reconcile",
            }
        )
        raise error

    async def reconcile_pending_thread(self, *, actor, project_id, thread_id):
        item = self.pending.get(thread_id)
        if (
            not item
            or item["owner"] != actor.user_id
            or item["project_id"] != project_id
        ):
            raise ForbiddenError(
                code="thread_action_denied", message="Thread is unavailable"
            )
        item["checks"] += 1
        if item["checks"] == 1:
            return {"thread_id": thread_id, "status": "pending"}
        return {
            "thread_id": thread_id,
            "status": "ready",
            "thread": {"thread_id": thread_id},
        }

    async def get_thread(self, *, actor, project_id, thread_id):
        item = self.pending.get(thread_id)
        if (
            not item
            or item["owner"] != actor.user_id
            or item["project_id"] != project_id
        ):
            raise ForbiddenError(
                code="thread_action_denied", message="Thread is unavailable"
            )
        return {"thread_id": thread_id}

    async def thread_workspace(self, *, actor, project_id, thread_id, resource, path):
        self._check_owner(actor, project_id, thread_id)
        if path.endswith("forced-502"):
            raise create_runtime_upstream_error(
                status_code=503,
                detail={"detail": "private-upstream-marker"},
                fallback_code="workspace_read_failed",
            )
        raise create_runtime_upstream_error(
            status_code=404,
            detail={
                "code": "workspace_file_unavailable",
                "message": "private-upstream-marker",
            },
            fallback_code="workspace_read_failed",
        )

    def _check_owner(self, actor, project_id, thread_id):
        item = self.pending.get(thread_id)
        if (
            not item
            or item["owner"] != actor.user_id
            or item["project_id"] != project_id
        ):
            raise ForbiddenError(
                code="thread_action_denied", message="Thread is unavailable"
            )


def serve():
    if os.environ.get("RUN_ERROR_CONTRACT_E2E") != "1":
        raise SystemExit("Set RUN_ERROR_CONTRACT_E2E=1 to start the isolated fixture")
    with tempfile.TemporaryDirectory(prefix="platform-error-contract-") as directory:
        app = create_app()
        settings = app.state.settings
        settings.database_url = f"sqlite:///{Path(directory) / 'platform.db'}"
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = True
        settings.bootstrap_admin_enabled = False
        settings.oidc_enabled = False
        settings.jwt_access_secret = token_urlsafe(48)
        settings.jwt_refresh_secret = token_urlsafe(48)
        settings.jwt_access_verification_keys = {}
        settings.jwt_refresh_verification_keys = {}
        gateway = ControlledGateway()
        app.dependency_overrides[get_runtime_gateway_service] = lambda: gateway

        @asynccontextmanager
        async def fixture_lifespan(application):
            async with lifespan(application):
                with session_scope(application.state.db_session_factory) as session:
                    projects = SqlAlchemyProjectsRepository(session)
                    tenant = projects.get_or_create_default_tenant()
                    project = projects.create_project(
                        tenant_id=tenant.id,
                        name="Error Contract E2E",
                        description="Temporary browser fixture",
                    )
                    users = SqlAlchemyIdentityRepository(session)
                    identities = {}
                    for name in ("owner", "peer"):
                        user = users.create_user(
                            username=f"error-contract-{name}",
                            password_hash=hash_password(PASSWORD),
                            external_subject=f"error-contract-{name}",
                            email=None,
                            is_super_admin=False,
                        )
                        identities[name] = str(user.id)
                        projects.upsert_project_member(
                            project_id=project.id,
                            user_id=user.id,
                            role=ProjectRole.EXECUTOR,
                        )
                STATE.write_text(
                    json.dumps({"project_id": str(project.id), "users": identities})
                )
                try:
                    yield
                finally:
                    STATE.unlink(missing_ok=True)
                    if gateway.pending and any(
                        item["checks"] < 2 for item in gateway.pending.values()
                    ):
                        raise RuntimeError("Fixture left unresolved pending Threads")

        app.router.lifespan_context = fixture_lifespan
        uvicorn.run(app, host="127.0.0.1", port=12143, log_level="warning")


if __name__ == "__main__":
    serve()
