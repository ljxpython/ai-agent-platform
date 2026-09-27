"""Opt-in SSE contract fixture: real API/auth/router, controlled upstream only."""

import asyncio
import json
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from uuid import uuid4

import uvicorn
from fastapi import Body
from platform_api.adapters.langgraph.sdk_client import create_runtime_upstream_error
from platform_api.bootstrap.lifespan import lifespan
from platform_api.core.db import session_scope
from platform_api.core.security import hash_password
from platform_api.main import create_app
from platform_api.modules.iam.domain import ProjectRole
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.agents.infra.sqlalchemy.repository import (
    SqlAlchemyAssistantsRepository,
)
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogGraphRecord,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_runtime_gateway_service,
)

PASSWORD = "Sse-contract-test-only-2026!"
STATE = Path("/tmp/platform-sse-contract-e2e.json")


class ControlledGateway:
    def __init__(self):
        self.threads: dict[str, dict] = {}
        self.counters = {
            "subscriptions": 0,
            "commands": 0,
            "cancels": 0,
            "state": 0,
            "closed": 0,
        }
        self.scenario = "initial"
        self.queues: dict[str, list[asyncio.Queue[bytes | None]]] = {}
        self.revoked: set[str] = set()
        self.expired_once: set[str] = set()
        self.run_status: dict[str, str] = {}
        self.generation = 0

    def reset(self):
        self.generation += 1
        for queues in self.queues.values():
            for queue in queues:
                queue.put_nowait(None)
        self.queues.clear()
        self.threads.clear()
        self.counters = {
            "subscriptions": 0,
            "commands": 0,
            "cancels": 0,
            "state": 0,
            "closed": 0,
        }
        self.scenario = "initial"
        self.revoked.clear()
        self.expired_once.clear()
        self.run_status.clear()

    def advance(
        self, thread_id: str, event: dict | None, chunks: list[str] | None = None
    ):
        if thread_id not in self.threads:
            raise ValueError("Unknown fixture thread")
        frames = (
            [chunk.encode() for chunk in chunks]
            if chunks is not None
            else [
                None
                if event is None
                else f"event: event\ndata: {json.dumps(event)}\n\n".encode()
            ]
        )
        for queue in self.queues.get(thread_id, []):
            for frame in frames:
                queue.put_nowait(frame)

    async def create_thread(self, *, actor, project_id, payload):
        thread_id = str(uuid4())
        metadata = {
            **payload.get("metadata", {}),
            "allowed_actions": [
                "read",
                "comment",
                "edit",
                "approve",
                "share",
                "delete",
            ],
        }
        created_at = datetime.now(UTC).isoformat()
        self.threads[thread_id] = {
            "owner": actor.user_id,
            "project_id": project_id,
            "metadata": metadata,
            "created_at": created_at,
        }
        return {
            "thread_id": thread_id,
            "metadata": metadata,
            "status": "idle",
            "created_at": created_at,
            "updated_at": created_at,
        }

    async def get_thread(self, *, actor, project_id, thread_id):
        item = self.threads.get(thread_id)
        if (
            not item
            or thread_id in self.revoked
            or item["owner"] != actor.user_id
            or item["project_id"] != project_id
        ):
            from platform_api.core.errors import ForbiddenError

            raise ForbiddenError(
                code="thread_action_denied", message="Thread is unavailable"
            )
        return {
            "thread_id": thread_id,
            "metadata": item["metadata"],
            "status": "idle",
            "created_at": item["created_at"],
            "updated_at": item["created_at"],
        }

    async def search_threads(self, *, actor, project_id, payload):
        rows = [
            await self.get_thread(actor=actor, project_id=project_id, thread_id=key)
            for key, item in self.threads.items()
            if item["owner"] == actor.user_id and item["project_id"] == project_id
        ]
        metadata = payload.get("metadata") or {}
        rows = [
            row
            for row in rows
            if all(row["metadata"].get(key) == value for key, value in metadata.items())
        ]
        return rows[payload.get("offset", 0) :][: payload.get("limit", 20)]

    async def count_threads(self, *, actor, project_id, payload):
        return {
            "count": len(
                await self.search_threads(
                    actor=actor,
                    project_id=project_id,
                    payload={**payload, "limit": 10000},
                )
            )
        }

    async def stream_thread_events(self, *, actor, project_id, thread_id, payload):
        await self.get_thread(actor=actor, project_id=project_id, thread_id=thread_id)
        self.counters["subscriptions"] += 1
        if self.scenario.startswith("V12-"):
            status = int(self.scenario.removeprefix("V12-"))
            raise create_runtime_upstream_error(
                status_code=status,
                detail={
                    "code": "fixture_stream_status",
                    "message": "Stream unavailable",
                },
                fallback_code="stream_failed",
            )
        expired = self.scenario == "V13" and payload.get("since") is not None
        if self.scenario == "V13UI" and thread_id not in self.expired_once:
            self.expired_once.add(thread_id)
            expired = True
        if expired:
            raise create_runtime_upstream_error(
                status_code=410,
                detail={
                    "code": "cursor_expired",
                    "message": "Event cursor expired",
                    "watermark": 10,
                },
                fallback_code="stream_failed",
            )
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.queues.setdefault(thread_id, []).append(queue)
        generation = self.generation

        async def stream():
            try:
                yield b": heartbeat\n\n"
                if self.scenario == "initial":
                    event = {
                        "type": "event",
                        "seq": 1,
                        "event_id": "fixture-1",
                        "method": "values",
                        "params": {
                            "thread_id": thread_id,
                            "run_id": "run-1",
                            "namespace": [],
                            "data": {
                                "messages": [
                                    {
                                        "id": "fixture-message",
                                        "type": "ai",
                                        "content": "SSE fixture",
                                    }
                                ]
                            },
                        },
                    }
                    yield f"event: event\ndata: {json.dumps(event)}\n\n".encode()
                while True:
                    frame = await queue.get()
                    if frame is None:
                        return
                    yield frame
            finally:
                if generation == self.generation:
                    self.queues[thread_id].remove(queue)
                    self.counters["closed"] += 1

        return stream()

    async def get_thread_state(self, *, actor, project_id, thread_id, params):
        await self.get_thread(actor=actor, project_id=project_id, thread_id=thread_id)
        self.counters["state"] += 1
        return {
            "values": {"messages": []},
            "next": [],
            "tasks": [],
            "metadata": {"thread_id": thread_id},
        }

    async def get_thread_history(self, *, actor, project_id, thread_id, payload):
        await self.get_thread(actor=actor, project_id=project_id, thread_id=thread_id)
        return []

    async def list_thread_messages(self, *, actor, project_id, thread_id):
        await self.get_thread(actor=actor, project_id=project_id, thread_id=thread_id)
        return []

    async def list_thread_runs(self, *, actor, project_id, thread_id, params):
        await self.get_thread(actor=actor, project_id=project_id, thread_id=thread_id)
        status = self.run_status.get(thread_id)
        return (
            [{"run_id": "fixture-run", "thread_id": thread_id, "status": status}]
            if status
            else []
        )

    async def get_thread_run(self, *, actor, project_id, thread_id, run_id):
        await self.get_thread(actor=actor, project_id=project_id, thread_id=thread_id)
        return {
            "run_id": run_id,
            "thread_id": thread_id,
            "status": self.run_status.get(thread_id, "success"),
        }

    async def cancel_thread_run(self, *, actor, project_id, thread_id, run_id, payload):
        await self.get_thread(actor=actor, project_id=project_id, thread_id=thread_id)
        self.counters["cancels"] += 1
        return {"status": "accepted", "run_id": run_id}

    async def send_thread_command(
        self, *, actor, project_id, thread_id, payload, idempotency_key
    ):
        await self.get_thread(actor=actor, project_id=project_id, thread_id=thread_id)
        self.counters["commands"] += 1
        return {
            "type": "success",
            "id": payload.get("id", 1),
            "result": {"run_id": "fixture-run"},
        }


def serve():
    if os.environ.get("RUN_SSE_CONTRACT_E2E") != "1":
        raise SystemExit("Set RUN_SSE_CONTRACT_E2E=1 to start the isolated fixture")
    with tempfile.TemporaryDirectory(prefix="platform-sse-contract-") as directory:
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

        @app.post("/__test/reset")
        async def reset():
            gateway.reset()
            return {"ok": True}

        @app.post("/__test/scenario")
        async def scenario(payload: dict = Body(...)):
            gateway.scenario = str(payload["id"])
            return {"id": gateway.scenario}

        @app.post("/__test/advance")
        async def advance(payload: dict = Body(...)):
            gateway.advance(
                str(payload["thread_id"]), payload.get("event"), payload.get("chunks")
            )
            return {"ok": True}

        @app.post("/__test/revoke")
        async def revoke(payload: dict = Body(...)):
            gateway.revoked.add(str(payload["thread_id"]))
            return {"ok": True}

        @app.post("/__test/run")
        async def set_run(payload: dict = Body(...)):
            thread_id = str(payload["thread_id"])
            if thread_id not in gateway.threads:
                raise ValueError("Unknown fixture thread")
            gateway.run_status[thread_id] = str(payload["status"])
            return {"ok": True}

        @app.get("/__test/counters")
        async def counters():
            return {**gateway.counters, "open": sum(map(len, gateway.queues.values()))}

        @asynccontextmanager
        async def fixture_lifespan(application):
            async with lifespan(application):
                with session_scope(application.state.db_session_factory) as session:
                    projects = SqlAlchemyProjectsRepository(session)
                    tenant = projects.get_or_create_default_tenant()
                    project = projects.create_project(
                        tenant_id=tenant.id,
                        name="SSE Contract",
                        description="Temporary fixture",
                    )
                    users = SqlAlchemyIdentityRepository(session)
                    identities = {}
                    for name in ("owner", "peer"):
                        user = users.create_user(
                            username=f"sse-contract-{name}",
                            password_hash=hash_password(PASSWORD),
                            external_subject=f"sse-contract-{name}",
                            email=None,
                            is_super_admin=False,
                        )
                        identities[name] = str(user.id)
                        projects.upsert_project_member(
                            project_id=project.id,
                            user_id=user.id,
                            role=ProjectRole.EXECUTOR,
                        )
                    session.add(
                        RuntimeCatalogGraphRecord(
                            runtime_id="default",
                            graph_key="reference_agent",
                            display_name="SSE Fixture",
                            sync_status="ready",
                        )
                    )
                    session.flush()
                    agent = SqlAlchemyAssistantsRepository(session).create_assistant(
                        project_id=project.id,
                        name="SSE Fixture",
                        description="",
                        graph_id="reference_agent",
                        context={},
                        actor_user_id=user.id,
                    )
                STATE.write_text(
                    json.dumps(
                        {
                            "project_id": str(project.id),
                            "users": identities,
                            "agent_id": str(agent.id),
                        }
                    )
                )
                try:
                    yield
                finally:
                    STATE.unlink(missing_ok=True)

        app.router.lifespan_context = fixture_lifespan
        uvicorn.run(app, host="127.0.0.1", port=12144, log_level="warning")


if __name__ == "__main__":
    serve()
