from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    register_exception_handlers,
)
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.entrypoints.http.middleware.request_context import (
    register_request_context_middleware,
)
from platform_api.modules.runtime_gateway.application.completion import (
    accept_completion,
    get_completion,
    list_notifications,
    mark_read,
    parse_callback,
)
from platform_api.modules.runtime_gateway.domain.completion import TerminalCompletion
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionEventRecord as Event,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionOriginRecord as Origin,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunRequestRecord,
    ThreadAccessRecord,
)
from platform_api.modules.runtime_gateway.presentation.completion_http import router
from platform_api.modules.runtime_gateway.presentation.http import (
    get_runtime_gateway_service,
)


@pytest.fixture
def fixture(tmp_path):
    schema = None
    if os.getenv("RUN_COMPLETION_PG_TEST") == "1":
        target = make_url(os.environ["POSTGRES_URI"]).set(
            drivername="postgresql+psycopg"
        )
        if (
            target.host != "127.0.0.1"
            or target.database != "graphharbor_event_retention_verify"
        ):
            raise RuntimeError("Only the disposable completion database is allowed")
        schema = "completion_" + uuid4().hex
        admin = create_engine(target, hide_parameters=True)
        with admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(
            target,
            connect_args={"options": f"-csearch_path={schema}"},
            hide_parameters=True,
        )
    else:
        engine = build_engine(f"sqlite:///{tmp_path / 'completion.db'}")
    factory = build_session_factory(engine)
    create_core_tables(engine)
    project, user, thread = map(str, (uuid4(), uuid4(), uuid4()))
    actor = ActorContext(user_id=user, project_roles={project: ("project_member",)})
    settings = Settings(
        _env_file=None,
        runtime_completion_enabled=True,
        runtime_completion_secret="c" * 32,
        runtime_completion_key_id="runtime-v1",
        runtime_delegation_secret="d" * 32,
    )
    with factory.begin() as session:
        session.add(
            ThreadAccessRecord(
                thread_id=thread,
                project_id=project,
                owner_user_id=user,
                visibility="private",
            )
        )
    yield SimpleNamespace(
        factory=factory,
        project=project,
        user=user,
        thread=thread,
        actor=actor,
        settings=settings,
    )
    engine.dispose()
    if schema:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def terminal(fixture, *, status="error", origin_ref=None, run_id=None, **changes):
    origin_ref = origin_ref or str(uuid4())
    if not changes.pop("existing_origin", False):
        with fixture.factory.begin() as session:
            session.add(
                Origin(
                    origin_ref=origin_ref,
                    project_id=fixture.project,
                    thread_id=fixture.thread,
                    agent_key="probe",
                    requested_by=fixture.user,
                    runtime_id="default",
                    source_kind="submission",
                    state="active",
                )
            )
    payload = {
        "schema_version": 1,
        "event_type": "run.terminal",
        "event_id": str(uuid4()),
        "origin_ref": origin_ref,
        "run_id": run_id or str(uuid4()),
        "thread_id": fixture.thread,
        "graph_id": "probe",
        "status": status,
        "reason": {
            "success": "completed",
            "error": "business_error",
            "timeout": "timeout",
            "interrupted": "hitl_interrupt",
        }[status],
        "outcome": {},
        "execution_stopped": True,
        "sequence": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
        **changes,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return TerminalCompletion.model_validate_json(raw), raw


def signed(f, body, event_id, *, stamp=None, kid="runtime-v1"):
    stamp = str(stamp if stamp is not None else int(time.time()))
    canonical = (
        f"{kid}\n{stamp}\nPOST\n/api/runtime/internal/run-completion\n".encode() + body
    )
    return {
        "content-type": "application/json",
        "x-run-completion-key-id": kid,
        "x-run-completion-timestamp": stamp,
        "x-run-completion-event-id": str(event_id),
        "x-run-completion-signature": "sha256="
        + hmac.new(
            f.settings.runtime_completion_secret.encode(), canonical, hashlib.sha256
        ).hexdigest(),
    }


def accept(f, t, body):
    return accept_completion(
        f.factory, t, digest=hashlib.sha256(body).hexdigest(), runtime_id="default"
    )


@pytest.mark.parametrize("status", ["success", "error", "timeout", "interrupted"])
def test_terminal_only_failures_enter_private_feed(fixture, status):
    t, body = terminal(fixture, status=status)
    assert not accept(fixture, t, body).duplicate
    assert accept(fixture, t, body).duplicate
    page = list_notifications(
        fixture.factory,
        fixture.settings,
        actor=fixture.actor,
        project_id=fixture.project,
        limit=20,
        cursor=None,
        unread_only=True,
    )
    assert len(page["items"]) == int(status in {"error", "timeout"})
    availability, summary = get_completion(
        fixture.factory,
        actor=fixture.actor,
        project_id=fixture.project,
        thread_id=fixture.thread,
        run_id=str(t.run_id),
    )
    assert availability == "available"
    assert summary["status"] == status
    if status in {"error", "timeout"}:
        read_at = mark_read(
            fixture.factory,
            actor=fixture.actor,
            project_id=fixture.project,
            event_id=t.event_id,
        )
        assert (
            mark_read(
                fixture.factory,
                actor=fixture.actor,
                project_id=fixture.project,
                event_id=t.event_id,
            )
            == read_at
        )
        assert not list_notifications(
            fixture.factory,
            fixture.settings,
            actor=fixture.actor,
            project_id=fixture.project,
            limit=20,
            cursor=None,
            unread_only=True,
        )["items"]


def test_conflicting_body_second_run_and_second_event_cannot_overwrite(fixture):
    t, body = terminal(fixture)
    accept(fixture, t, body)
    with pytest.raises(ConflictError):
        accept(fixture, t, body + b" ")
    for run_id in (str(t.run_id), str(uuid4())):
        other, raw = terminal(
            fixture, origin_ref=str(t.origin_ref), run_id=run_id, existing_origin=True
        )
        with pytest.raises(ConflictError):
            accept(fixture, other, raw)


def test_signature_covers_raw_bytes_time_key_method_and_path(fixture):
    t, body = terminal(fixture)
    headers = signed(fixture, body, t.event_id)
    assert (
        parse_callback(
            fixture.settings,
            body,
            headers,
            method="POST",
            path="/api/runtime/internal/run-completion",
        )[0]
        == t
    )
    for raw, hdr, method, path in (
        (body + b" ", headers, "POST", "/api/runtime/internal/run-completion"),
        (
            body,
            signed(fixture, body, t.event_id, stamp=1),
            "POST",
            "/api/runtime/internal/run-completion",
        ),
        (
            body,
            signed(fixture, body, t.event_id, kid="unknown"),
            "POST",
            "/api/runtime/internal/run-completion",
        ),
        (body, headers, "GET", "/api/runtime/internal/run-completion"),
        (body, headers, "POST", "/other"),
    ):
        with pytest.raises(ForbiddenError):
            parse_callback(fixture.settings, raw, hdr, method=method, path=path)


def test_shared_history_has_no_other_user_feed_or_receipt(fixture):
    t, body = terminal(fixture)
    accept(fixture, t, body)
    other_user = str(uuid4())
    other = ActorContext(
        user_id=other_user, project_roles={fixture.project: ("project_member",)}
    )
    with fixture.factory.begin() as session:
        session.get(ThreadAccessRecord, fixture.thread).shared_actions = {
            other_user: ["read"]
        }
    summary = get_completion(
        fixture.factory,
        actor=other,
        project_id=fixture.project,
        thread_id=fixture.thread,
        run_id=str(t.run_id),
    )[1]
    assert not summary["can_mark_read"]
    assert not list_notifications(
        fixture.factory,
        fixture.settings,
        actor=other,
        project_id=fixture.project,
        limit=20,
        cursor=None,
        unread_only=False,
    )["items"]
    with pytest.raises(NotFoundError):
        mark_read(
            fixture.factory,
            actor=other,
            project_id=fixture.project,
            event_id=t.event_id,
        )


def test_paging_skips_revoked_entries_binds_actor_filter_and_expires_detail(fixture):
    events = [terminal(fixture) for _ in range(4)]
    for t, body in events:
        accept(fixture, t, body)
    page = list_notifications(
        fixture.factory,
        fixture.settings,
        actor=fixture.actor,
        project_id=fixture.project,
        limit=2,
        cursor=None,
        unread_only=True,
    )
    assert len(page["items"]) == 2 and page["next_cursor"]
    next_page = list_notifications(
        fixture.factory,
        fixture.settings,
        actor=fixture.actor,
        project_id=fixture.project,
        limit=2,
        cursor=page["next_cursor"],
        unread_only=True,
    )
    assert {item["event_id"] for item in page["items"]}.isdisjoint(
        item["event_id"] for item in next_page["items"]
    )
    with pytest.raises(Exception, match="cursor"):
        list_notifications(
            fixture.factory,
            fixture.settings,
            actor=fixture.actor,
            project_id=fixture.project,
            limit=2,
            cursor=page["next_cursor"],
            unread_only=False,
        )
    t, raw = events[0]
    with fixture.factory.begin() as session:
        session.get(Event, t.event_id).detail_expires_at = datetime.now(
            UTC
        ) - timedelta(days=1)
    assert (
        get_completion(
            fixture.factory,
            actor=fixture.actor,
            project_id=fixture.project,
            thread_id=fixture.thread,
            run_id=str(t.run_id),
        )[0]
        == "expired"
    )
    assert accept(fixture, t, raw).duplicate


def test_http_ack_after_commit_unknown_fields_headers_and_safe_errors(fixture):
    app = FastAPI()
    app.state.settings, app.state.db_session_factory = fixture.settings, fixture.factory
    register_exception_handlers(app)
    app.include_router(router)

    @app.middleware("http")
    async def context(request, call_next):
        request.state.platform_context = SimpleNamespace(
            project=SimpleNamespace(project_id=fixture.project),
            request=SimpleNamespace(request_id="completion-test"),
            actor=fixture.actor,
        )
        return await call_next(request)

    app.dependency_overrides[get_actor_context] = lambda: fixture.actor
    t, raw = terminal(fixture)
    with TestClient(app) as client:
        result = client.post(
            "/api/runtime/internal/run-completion",
            content=raw,
            headers=signed(fixture, raw, t.event_id),
        )
        assert result.status_code == 200, result.text
        with fixture.factory() as session:
            assert session.get(Event, t.event_id) is not None
        assert (
            client.get("/api/runtime/run-notifications").headers["cache-control"]
            == "private, no-store"
        )
        malformed = json.loads(raw) | {"input": "CANARY-secret"}
        unsafe = json.dumps(malformed).encode()
        result = client.post(
            "/api/runtime/internal/run-completion",
            content=unsafe,
            headers=signed(fixture, unsafe, t.event_id),
        )
        assert result.status_code == 400 and "CANARY" not in result.text
        assert result.headers["cache-control"] == "private, no-store"
        assert (
            client.get("/api/runtime/run-notifications?recipient=other").status_code
            == 400
        )
        assert (
            client.post(
                "/api/runtime/run-notifications/" + str(t.event_id) + "/read", json={}
            ).status_code
            == 200
        )
        invalid = client.post(
            "/api/runtime/run-notifications/" + str(t.event_id) + "/read",
            json={"recipient": "CANARY"},
        )
        assert (
            invalid.status_code == 422
            and invalid.headers["cache-control"] == "private, no-store"
        )
        fixture.settings.runtime_completion_enabled = False
        disabled = client.post(
            "/api/runtime/run-notifications/" + str(t.event_id) + "/read", json={}
        )
        assert (
            disabled.status_code == 503
            and disabled.headers["cache-control"] == "private, no-store"
        )


def test_public_completion_http_matrix(fixture, tmp_path):
    from sqlalchemy.exc import OperationalError

    app = FastAPI()
    app.state.settings, app.state.db_session_factory = fixture.settings, fixture.factory
    register_exception_handlers(app)
    register_request_context_middleware(app)
    app.include_router(router)
    app.dependency_overrides[get_actor_context] = lambda: fixture.actor

    async def snapshot(**kwargs):
        return {"thread_id": kwargs["thread_id"], "run_id": kwargs["run_id"]}

    app.dependency_overrides[get_runtime_gateway_service] = lambda: SimpleNamespace(
        get_thread_run=snapshot
    )
    t, raw = terminal(fixture)
    with fixture.factory.begin() as session:
        session.get(Origin, str(t.origin_ref)).run_id = str(t.run_id)
    history = f"/api/langgraph/threads/{fixture.thread}/runs/{t.run_id}/completion"
    feed = "/api/runtime/run-notifications"
    read = f"{feed}/{t.event_id}/read"
    evidence = []

    def capture(name, response, status):
        assert response.status_code == status, response.text
        assert response.headers["cache-control"] == "private, no-store"
        assert "CANARY" not in response.text
        evidence.append(
            {
                "scenario": name,
                "method": response.request.method,
                "path": response.request.url.path,
                "status_code": status,
                "cache_control": response.headers["cache-control"],
                "body": response.json(),
            }
        )
        return response.json()

    with TestClient(app, headers={"x-project-id": fixture.project}) as client:
        assert capture("pending", client.get(history), 200)["availability"] == "pending"
        unsupported = (
            f"/api/langgraph/threads/{fixture.thread}/runs/{uuid4()}/completion"
        )
        assert (
            capture("unsupported", client.get(unsupported), 200)["availability"]
            == "unsupported"
        )
        accept(fixture, t, raw)
        summary = capture("available", client.get(history), 200)
        assert summary["completion"]["can_mark_read"]
        item = capture("private_feed", client.get(feed), 200)["items"][0]
        assert item["can_mark_read"] and item["event_id"] == str(t.event_id)
        receipt = capture("read", client.post(read, json={}), 200)
        assert (
            capture("read_duplicate", client.post(read, json={}), 200)["read_at"]
            == receipt["read_at"]
        )
        assert capture("empty_unread", client.get(feed), 200)["items"] == []
        capture("invalid_query", client.get(feed, params={"recipient": "CANARY"}), 400)
        capture("invalid_read_body", client.post(read, json={"secret": "CANARY"}), 422)
        fixture.settings.runtime_completion_enabled = False
        assert capture("disabled", client.get(feed), 200)["availability"] == "disabled"
        capture("disabled_read", client.post(read, json={}), 503)
        fixture.settings.runtime_completion_enabled = True

        revoked = ActorContext(user_id=fixture.user, project_roles={})
        app.dependency_overrides[get_actor_context] = lambda: revoked
        capture("revoked_history", client.get(history), 404)
        capture("revoked_feed", client.get(feed), 403)
        app.dependency_overrides[get_actor_context] = lambda: fixture.actor

        def broken():
            raise OperationalError("CANARY-private", {}, RuntimeError("CANARY-private"))

        app.state.db_session_factory = SimpleNamespace(begin=broken)
        capture("storage_unavailable", client.get(history), 503)
        app.state.db_session_factory = fixture.factory
        with fixture.factory.begin() as session:
            session.get(Event, t.event_id).detail_expires_at = datetime.now(
                UTC
            ) - timedelta(seconds=1)
        assert capture("expired", client.get(history), 200)["availability"] == "expired"
        capture("expired_read", client.post(read, json={}), 404)

    target = Path(
        os.getenv(
            "RUN_COMPLETION_CONTRACT_EVIDENCE", str(tmp_path / "http-matrix.json")
        )
    )
    target.write_text(
        json.dumps(
            {
                "source": "HTTP contract test with real PostgreSQL; upstream Run lookup fixture",
                "responses": evidence,
            },
            indent=2,
        )
    )


@pytest.mark.parametrize("value", [1, 0, "true", False, None])
def test_stopped_requires_literal_boolean(fixture, value):
    with pytest.raises(ValueError):
        terminal(fixture, execution_stopped=value)


@pytest.mark.parametrize("value", [True, 0, -1, 2**63, "1"])
def test_terminal_sequence_rejects_non_integer_or_overflow(fixture, value):
    with pytest.raises(ValidationError):
        terminal(fixture, sequence=value)


def test_terminal_sequence_persists_above_32bit(fixture):
    value, raw = terminal(fixture, sequence=2**63 - 1)
    accept_completion(
        fixture.factory,
        value,
        digest=hashlib.sha256(raw).hexdigest(),
        runtime_id="default",
    )
    with fixture.factory() as session:
        assert session.get(Event, value.event_id).sequence == 2**63 - 1


@pytest.mark.parametrize(
    "value", ["sha256=" + "\u00e9" * 64, "sha256=" + "a" * 10000, "bad"]
)
def test_malformed_signature_is_denied_without_server_error(fixture, value):
    event, raw = terminal(fixture)
    headers = signed(fixture, raw, event.event_id)
    headers["x-run-completion-signature"] = value
    with pytest.raises(ForbiddenError):
        parse_callback(
            fixture.settings,
            raw,
            headers,
            method="POST",
            path="/api/runtime/internal/run-completion",
        )


def test_early_callback_cas_preserves_same_run(fixture):
    from platform_api.modules.runtime_gateway.infra.sqlalchemy.repository import (
        RunRequestsRepository,
    )

    t, body = terminal(fixture)
    request_id = uuid4()
    with fixture.factory.begin() as session:
        session.add(
            RunRequestRecord(
                id=request_id,
                origin_ref=str(t.origin_ref),
                project_id=fixture.project,
                thread_id=fixture.thread,
                agent_key="probe",
                requested_by=fixture.user,
                idempotency_key="early",
                request_digest="d" * 64,
                context_snapshot={},
                config_snapshot={},
                context_hash="hash",
            )
        )
    accept(fixture, t, body)
    with fixture.factory.begin() as session:
        repository = RunRequestsRepository(session)
        repository.mark(str(request_id), "unknown")
        repository.mark(str(request_id), "accepted", str(t.run_id))
        row = session.get(RunRequestRecord, request_id)
        assert row.submission_status == "accepted" and row.run_id == str(t.run_id)
        with pytest.raises(ConflictError):
            repository.mark(str(request_id), "accepted", str(uuid4()))


def test_delete_before_callback_cannot_reappear_in_feed(fixture):
    from platform_api.modules.runtime_gateway.infra.sqlalchemy.completion_repository import (
        suppress,
    )

    t, body = terminal(fixture)
    with fixture.factory.begin() as session:
        origin = session.get(Origin, str(t.origin_ref))
        origin.source_kind = "schedule"
        origin.run_id = None
        suppress(
            session,
            project_id=fixture.project,
            thread_id=fixture.thread,
            run_id=str(t.run_id),
        )
    accept(fixture, t, body)
    assert not list_notifications(
        fixture.factory,
        fixture.settings,
        actor=fixture.actor,
        project_id=fixture.project,
        limit=20,
        cursor=None,
        unread_only=False,
    )["items"]
    with pytest.raises(NotFoundError):
        get_completion(
            fixture.factory,
            actor=fixture.actor,
            project_id=fixture.project,
            thread_id=fixture.thread,
            run_id=str(t.run_id),
        )


def test_current_revocation_and_availability(fixture):
    t, body = terminal(fixture)
    with fixture.factory.begin() as session:
        session.get(Origin, str(t.origin_ref)).run_id = str(t.run_id)
    args = dict(
        actor=fixture.actor,
        project_id=fixture.project,
        thread_id=fixture.thread,
        run_id=str(t.run_id),
    )
    assert get_completion(fixture.factory, **args)[0] == "pending"
    assert (
        get_completion(fixture.factory, **(args | {"run_id": str(uuid4())}))[0]
        == "unsupported"
    )
    accept(fixture, t, body)
    revoked = ActorContext(user_id=fixture.user, project_roles={})
    with pytest.raises(NotFoundError):
        get_completion(fixture.factory, **(args | {"actor": revoked}))
    with pytest.raises(ForbiddenError):
        list_notifications(
            fixture.factory,
            fixture.settings,
            actor=revoked,
            project_id=fixture.project,
            limit=20,
            cursor=None,
            unread_only=True,
        )


def test_storage_failure_is_503_and_rotation_accepts_previous_key(fixture):
    from sqlalchemy.exc import OperationalError

    def broken():
        raise OperationalError("CANARY-private", {}, RuntimeError("CANARY-private"))

    with pytest.raises(ServiceUnavailableError) as error:
        get_completion(
            SimpleNamespace(begin=broken),
            actor=fixture.actor,
            project_id=fixture.project,
            thread_id=fixture.thread,
            run_id=str(uuid4()),
        )
    assert "CANARY" not in error.value.message
    t, raw = terminal(fixture)
    fixture.settings.runtime_completion_verification_keys = {
        "old": fixture.settings.runtime_completion_secret
    }
    assert (
        parse_callback(
            fixture.settings,
            raw,
            signed(fixture, raw, t.event_id, kid="old"),
            method="POST",
            path="/api/runtime/internal/run-completion",
        )[0]
        == t
    )


def test_duplicate_signature_header_fails_closed(fixture):
    from starlette.datastructures import Headers

    t, raw = terminal(fixture)
    entries = [
        (key.encode(), value.encode())
        for key, value in signed(fixture, raw, t.event_id).items()
    ]
    entries.append((b"x-run-completion-key-id", b"runtime-v1"))
    with pytest.raises(ForbiddenError):
        parse_callback(
            fixture.settings,
            raw,
            Headers(raw=entries),
            method="POST",
            path="/api/runtime/internal/run-completion",
        )


@pytest.mark.skipif(
    os.getenv("RUN_COMPLETION_PG_TEST") != "1", reason="disposable PostgreSQL opt-in"
)
def test_concurrent_callback_and_dispatch_cas_are_idempotent(fixture):
    from sqlalchemy import func, select

    from platform_api.modules.runtime_gateway.infra.sqlalchemy.repository import (
        RunRequestsRepository,
    )

    t, raw = terminal(fixture)
    request_id = uuid4()
    with fixture.factory.begin() as session:
        session.add(
            RunRequestRecord(
                id=request_id,
                origin_ref=str(t.origin_ref),
                project_id=fixture.project,
                thread_id=fixture.thread,
                agent_key="probe",
                requested_by=fixture.user,
                idempotency_key="parallel",
                request_digest="d" * 64,
                context_snapshot={},
                config_snapshot={},
                context_hash="hash",
            )
        )

    def submit(_):
        with fixture.factory.begin() as session:
            RunRequestsRepository(session).mark(
                str(request_id), "accepted", str(t.run_id)
            )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(accept, fixture, t, raw) for _ in range(6)] + [
            pool.submit(submit, i) for i in range(2)
        ]
        for future in futures:
            future.result(timeout=10)
    with fixture.factory() as session:
        assert session.scalar(select(func.count()).select_from(Event)) == 1
        assert session.get(RunRequestRecord, request_id).run_id == str(t.run_id)


def test_retention_preview_preserves_dedup_and_pending(fixture):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "completion_retention",
        Path(__file__).resolve().parents[1] / "scripts/maintain_run_completions.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    t, raw = terminal(fixture)
    accept(fixture, t, raw)
    with fixture.factory.begin() as session:
        session.get(Event, t.event_id).detail_expires_at = datetime.now(
            UTC
        ) - timedelta(days=1)
    assert module.maintain(fixture.factory)["expired_details"] == 1
    assert module.maintain(fixture.factory, apply=True)["expired_details"] == 1
    assert accept(fixture, t, raw).duplicate
    pending, _ = terminal(fixture)
    with fixture.factory.begin() as session:
        session.get(Event, t.event_id).dedup_expires_at = datetime.now(UTC) - timedelta(
            days=1
        )
    assert module.maintain(fixture.factory, apply=True)["expired_tombstones"] == 1
    for item, availability in ((t, "expired"), (pending, "unsupported")):
        assert get_completion(
            fixture.factory,
            actor=fixture.actor,
            project_id=fixture.project,
            thread_id=fixture.thread,
            run_id=str(item.run_id),
        ) == (availability, None)
    with fixture.factory() as session:
        assert session.get(Origin, str(pending.origin_ref)).state == "active"
