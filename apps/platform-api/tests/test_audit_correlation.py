from __future__ import annotations

import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

from dotenv import dotenv_values
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from platform_api.core.context.models import ActorContext
from platform_api.core.db.base import Base
from platform_api.core.errors import ForbiddenError, register_exception_handlers
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.audit.contracts import ListAuditEventsQuery
from platform_api.modules.audit.http_resolution import (
    AuditHttpRequest,
    resolve_http_audit,
)
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.audit.repository import SqlAlchemyAuditRepository
from platform_api.modules.audit.router import get_audit_service, router
from platform_api.modules.audit.schemas import AuditResult
from platform_api.modules.audit.service import AuditService


class AuditCorrelationTest(unittest.TestCase):
    def test_invalid_http_query_returns_422(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router)
        app.dependency_overrides[get_actor_context] = lambda: object()
        service = Mock()
        app.dependency_overrides[get_audit_service] = lambda: service
        for query in (
            "run_id=run-1",
            "submission_id=not-a-uuid",
            "run_id=run-1&created_from=2026-09-27T00:00:00Z&created_to=2026-09-19T00:00:00Z",
            "run_id=run-1&created_from=2026-09-19T00:00:00Z&created_to=2026-09-27T00:00:00Z",
            "request_id=" + "x" * 65,
        ):
            with self.subTest(query=query):
                response = TestClient(app).get("/api/audit?" + query)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn("Traceback", response.text)
        service.list_events.assert_not_called()

    def test_query_requires_bounded_time_range(self) -> None:
        now = datetime.now(UTC)
        for values in (
            {"run_id": "run-1"},
            {"thread_id": "thread-1", "created_from": now},
            {
                "run_id": "run-1",
                "created_from": now,
                "created_to": now + timedelta(days=8),
            },
            {"request_id": "bad\nvalue"},
            {"thread_id": "bad\u0085value", "created_from": now, "created_to": now},
            {
                "run_id": "run-1",
                "created_from": now,
                "created_to": now.replace(tzinfo=None),
            },
            {
                "run_id": "run-1",
                "created_from": now,
                "created_to": now - timedelta(seconds=1),
            },
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                ListAuditEventsQuery(**values)
        ListAuditEventsQuery(
            run_id="run-1", created_from=now, created_to=now + timedelta(days=7)
        )
        ListAuditEventsQuery(request_id="legacy-id")

    def test_audit_metadata_whitelists_correlation_on_write_and_read(self) -> None:
        metadata = {
            "platform_trace_id": "request-1",
            "submission_id": str(uuid4()),
            "thread_id": "thread-1",
            "run_id": "run-1",
            "parent_run_id": "run-0",
            "target_run_id": "run-2",
            "interrupt_key": "interrupt-1",
            "operation": "approve",
            "outcome": "accepted",
            "stream_kind": "run",
            "close_reason": "client_disconnect",
            "reused_submission": True,
            "correlation_version": 1,
            "token": "secret",
        }
        resolved = resolve_http_audit(
            request=AuditHttpRequest(
                method="POST",
                path="/api/langgraph/threads/thread-1/runs",
                query_params={},
                query_string=None,
                state_project_id="p1",
                client_ip=None,
                user_agent=None,
                response_content_length=None,
                metadata=metadata,
            ),
            response_payload=None,
            actor_user_id="owner",
            status_code=200,
            result=AuditResult.SUCCESS,
        )
        for key, value in metadata.items():
            if key != "token":
                self.assertEqual(resolved.metadata[key], value)
        self.assertNotIn("token", resolved.metadata)
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[AuditLogRecord.__table__])
        with Session(engine) as session:
            session.add(
                AuditLogRecord(
                    request_id="request-1",
                    plane="runtime_gateway",
                    action="runtime.run.item.created",
                    result="success",
                    method="POST",
                    path="/api/langgraph/threads/thread-1/runs",
                    status_code=200,
                    duration_ms=1,
                    project_id="p1",
                    metadata_json=resolved.metadata,
                )
            )
            session.commit()
        page = AuditService(session_factory=sessionmaker(bind=engine)).list_events(
            actor=ActorContext(
                user_id="owner", project_roles={"p1": ("project_admin",)}
            ),
            query=ListAuditEventsQuery(project_id="p1", request_id="request-1"),
        )
        self.assertEqual(page.items[0].metadata, resolved.metadata)
        engine.dispose()

    def test_correlation_filter_requires_project_audit_permission(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[AuditLogRecord.__table__])
        service = AuditService(session_factory=sessionmaker(bind=engine))
        query = ListAuditEventsQuery(project_id="p1", request_id="request-1")
        try:
            with self.assertRaises(ForbiddenError):
                service.list_events(actor=ActorContext(user_id="peer"), query=query)
            page = service.list_events(
                actor=ActorContext(
                    user_id="editor", project_roles={"p1": ("project_editor",)}
                ),
                query=query,
            )
            self.assertEqual(page.total, 0)
            with self.assertRaises(ForbiddenError):
                service.list_events(
                    actor=ActorContext(
                        user_id="editor", project_roles={"p1": ("project_editor",)}
                    ),
                    query=ListAuditEventsQuery(request_id="request-1"),
                )
        finally:
            engine.dispose()

    def _assert_json_filters(self, session: Session) -> None:
        submission = str(uuid4())
        run_id = str(uuid4())
        projects = (str(uuid4()), str(uuid4()))
        for project, field in (
            (projects[0], "run_id"),
            (projects[0], "target_run_id"),
            (projects[0], "parent_run_id"),
            (projects[1], "run_id"),
        ):
            session.add(
                AuditLogRecord(
                    request_id=uuid4().hex,
                    plane="runtime_gateway",
                    action="runtime.run.item.created",
                    result="success",
                    method="POST",
                    path="/api/langgraph/threads/t/runs",
                    status_code=200,
                    duration_ms=1,
                    project_id=project,
                    metadata_json={
                        field: run_id,
                        "submission_id": submission,
                        "thread_id": "thread-1",
                    },
                )
            )
        session.flush()
        repo = SqlAlchemyAuditRepository(session)
        filters = {
            "project_id": projects[0],
            "plane": None,
            "action": None,
            "target_type": None,
            "target_id": None,
            "actor_user_id": None,
            "method": None,
            "result": None,
            "status_code": None,
            "created_from": None,
            "created_to": None,
            "limit": 2,
            "offset": 0,
            "submission_id": submission,
            "thread_id": "thread-1",
            "run_id": run_id,
        }
        items, total = repo.list_events(**filters)
        self.assertEqual((len(items), total), (2, 3))
        self.assertEqual({item.project_id for item in items}, {projects[0]})
        _, other_total = repo.list_events(**(filters | {"project_id": projects[1]}))
        self.assertEqual(other_total, 1)

    def test_json_filters_keep_project_scope_and_count(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[AuditLogRecord.__table__])
        with Session(engine) as session:
            self._assert_json_filters(session)
        engine.dispose()

    @unittest.skipUnless(
        os.getenv("RUN_LOCAL_TRACE_POSTGRES") == "1", "local PostgreSQL opt-in"
    )
    def test_postgres_json_filters_keep_project_scope_and_count(self) -> None:
        url = dotenv_values("apps/platform-api/.env").get("PLATFORM_API_DATABASE_URL")
        self.assertTrue(url and ("127.0.0.1" in url or "localhost" in url))
        engine = create_engine(url)
        try:
            self.assertIn("audit_logs", inspect(engine).get_table_names())
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    with Session(connection) as session:
                        self._assert_json_filters(session)
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
