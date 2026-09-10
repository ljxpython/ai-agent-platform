import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

from anyio import CancelScope
import httpx
from fastapi import FastAPI
from sqlalchemy import event, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, create_core_tables, session_scope
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.entrypoints.http.middleware.audit_log import register_audit_log_middleware
from platform_api.modules.projects.router import router, get_projects_service
from platform_api.modules.projects.service import ProjectsService
from platform_api.modules.runtime_catalog.application.service import (
    RuntimeCatalogService,
)


class TransactionBoundariesTest(unittest.IsolatedAsyncioTestCase):
    async def test_http_crud_and_async_refresh_keep_sessions_off_loop(self):
        loop_thread = threading.get_ident()
        sessions = []
        testcase = self

        class CheckedSession(Session):
            def __init__(self, *args, **kwargs):
                testcase.assertNotEqual(threading.get_ident(), loop_thread)
                self.owner = threading.get_ident()
                self.closed = False
                sessions.append(self)
                super().__init__(*args, **kwargs)

            def close(self):
                testcase.assertEqual(threading.get_ident(), self.owner)
                self.closed = True
                return super().close()

        @event.listens_for(CheckedSession, "before_commit")
        def check_commit_thread(session):
            self.assertEqual(threading.get_ident(), session.owner)

        @event.listens_for(CheckedSession, "do_orm_execute")
        def check_session_thread(state):
            self.assertEqual(threading.get_ident(), state.session.owner)

        with tempfile.TemporaryDirectory() as directory:
            engine = build_engine(f"sqlite:///{Path(directory) / 'platform.db'}")
            self.addCleanup(engine.dispose)
            create_core_tables(engine)
            factory = sessionmaker(
                engine, class_=CheckedSession, expire_on_commit=False
            )

            @event.listens_for(engine, "before_cursor_execute")
            def check_query_thread(*args):
                self.assertNotEqual(threading.get_ident(), loop_thread)

            actor = ActorContext(
                user_id=str(uuid4()), platform_roles=("platform_super_admin",)
            )
            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_actor_context] = lambda: actor
            app.dependency_overrides[get_projects_service] = lambda: ProjectsService(
                session_factory=factory
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/projects", json={"name": "Thread boundaries"}
                )
                self.assertEqual(response.status_code, 200, response.text)
                project_id = response.json()["id"]
                response = await client.get("/api/projects")
                self.assertEqual(response.status_code, 200, response.text)
            actor = ActorContext(
                user_id=actor.user_id,
                platform_roles=("platform_super_admin",),
                project_roles={project_id: ("project_admin",)},
            )

            async def discover(**kwargs):
                self.assertEqual(threading.get_ident(), loop_thread)
                self.assertTrue(
                    sessions and all(session.closed for session in sessions)
                )
                await asyncio.sleep(0)
                return []

            catalog = RuntimeCatalogService(
                session_factory=factory,
                upstream=SimpleNamespace(list_deployed_graphs=discover),
                runtime_base_url="http://runtime",
                settings=Settings(runtime_delegation_secret="x" * 32),
            )
            await catalog.refresh_graphs(actor=actor, project_id=project_id)
            self.assertTrue(all(session.closed for session in sessions))

    async def test_native_transaction_commits_rolls_back_and_releases_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = build_engine(f"sqlite:///{Path(directory) / 'transactions.db'}")
            self.addCleanup(engine.dispose)
            factory = sessionmaker(engine)
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE sample (value INTEGER UNIQUE)"))
            with session_scope(factory) as session:
                session.execute(text("INSERT INTO sample VALUES (1)"))
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                with session_scope(factory) as session:
                    session.execute(text("INSERT INTO sample VALUES (2)"))
                    raise RuntimeError("rollback")
            with engine.connect() as connection:
                self.assertEqual(
                    connection.execute(text("SELECT value FROM sample"))
                    .scalars()
                    .all(),
                    [1],
                )
            self.assertEqual(engine.pool.checkedout(), 0)

    async def test_cancelled_request_still_writes_audit_off_loop(self):
        loop_thread = threading.get_ident()
        app = FastAPI()
        app.state.db_session_factory = sessionmaker()
        register_audit_log_middleware(app)
        dispatch = app.user_middleware[0].kwargs["dispatch"]
        request = Request({"type": "http", "method": "POST", "path": "/api/projects", "headers": [], "app": app})
        writes = []

        def write(**kwargs):
            self.assertNotEqual(threading.get_ident(), loop_thread)
            writes.append(kwargs["status_code"])

        async def cancelled(request):
            raise asyncio.CancelledError()

        with patch("platform_api.entrypoints.http.middleware.audit_log._write_audit_event", side_effect=write):
            with CancelScope() as scope:
                scope.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await dispatch(request, cancelled)
        self.assertEqual(writes, [499])
