"""Saved wire bytes survive lost ACKs; reconciliation never creates a Run."""

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import jwt
import pytest
from sqlalchemy import select

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import ForbiddenError, UpstreamServiceError
from platform_api.core.security.run_acceptance import receipt_binding, validate_grant
from platform_api.core.security.tokens import create_runtime_delegation_token
from platform_api.modules.agents.domain.models import ModelResilienceSettings
from platform_api.modules.projects.models import ProjectRecord, TenantRecord
from platform_api.modules.runtime_gateway.application import (
    background_completion as completion,
)
from platform_api.modules.runtime_gateway.application.run_acceptance import (
    grant_for,
    validate_receipt,
)
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunRequestRecord,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.repository import _stored

SECRET = "synthetic-receipt-test-secret-at-least-32-bytes"


def receipt(thread, key, digest, result="accepted"):
    now = datetime.now(UTC).isoformat()
    return {
        "schema_version": 1,
        "result": result,
        "thread_id": thread,
        "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
        "request_digest": digest,
        "run_id": str(uuid4()) if result == "accepted" else None,
        "accepted_at": now if result == "accepted" else None,
        "observed_at": now,
        "details_expires_at": now if result == "definitively_not_accepted" else None,
        "run_state": {
            "available": result == "accepted",
            "status": "pending" if result == "accepted" else None,
        },
        "reason": None
        if result == "accepted"
        else "multitask_rejected"
        if result == "definitively_not_accepted"
        else "no_receipt",
    }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine = build_engine(f"sqlite:///{tmp_path / 'receipts.db'}")
    factory = build_session_factory(engine)
    create_core_tables(engine)
    data = {
        "version": 1,
        "tenant_id": "tenant",
        "project_id": str(uuid4()),
        "owner_id": "owner",
        "credential_id": None,
        "graph_id": "showcase_demo",
        "thread_id": str(uuid4()),
        "origin_run_id": str(uuid4()),
        "task_id": str(uuid4()),
        "event_id": str(uuid4()),
        "status": "succeeded",
        "exit_code": 0,
        "reconcile_only": False,
    }
    upstream = SimpleNamespace(
        create_run_with_acceptance=AsyncMock(),
        get_run_acceptance=AsyncMock(),
        create_thread_run=AsyncMock(),
    )
    upstream.with_forwarded_headers = Mock(return_value=upstream)
    snapshot = {}

    def delegation(**values):
        snapshot.update(
            subject="owner",
            credential_id=None,
            tenant_id="tenant",
            project_id=data["project_id"],
            role="project_editor",
            permissions=[],
            policy_version="original",
            allowed_model_ids=["fixture-model"],
            tool_overrides={},
            tool_policy_version="original",
            scope={
                "tenant_id": "tenant",
                "project_id": data["project_id"],
                "assistant_id": data["graph_id"],
                "thread_id": data["thread_id"],
                "operation": "run-create",
            },
            context_hash=values["context_hash"],
        )
        values["auth_snapshot"].update(snapshot)
        return {"authorization": "Bearer synthetic"}

    service = RuntimeGatewayService(
        session_factory=factory,
        upstream=upstream,
        delegation_headers_factory=delegation,
    )
    service._model_resilience_snapshot = Mock(
        return_value=ModelResilienceSettings.disabled()
    )
    service._validate_run_options = Mock()
    service._load_thread = AsyncMock(
        return_value={"metadata": {"graph_id": data["graph_id"]}}
    )
    service._attach_runtime_model_reference = Mock(
        side_effect=lambda **kw: kw["payload"]
    )
    monkeypatch.setattr(
        "platform_api.core.context.get_current_request_context",
        lambda: SimpleNamespace(tenant=SimpleNamespace(tenant_id="tenant")),
    )
    settings = Settings(
        runtime_delegation_secret=SECRET, langgraph_upstream_url="http://fixture"
    )
    try:
        yield service, factory, upstream, data, settings
    finally:
        engine.dispose()


def launch(service, data):
    return service.launch_runtime_run(
        actor=ActorContext(user_id="owner"),
        project_id=data["project_id"],
        thread_id=data["thread_id"],
        command={
            "method": "background-completion",
            "params": {k: v for k, v in data.items() if k != "reconcile_only"},
        },
        upstream_payload={
            "assistant_id": data["graph_id"],
            "input": {"text": "中文"},
            "multitask_strategy": "enqueue",
        },
        idempotency_key="background:" + data["event_id"],
        completion_config={
            completion.MARKER: completion.sign_marker(
                {
                    k: data[k]
                    for k in (
                        "tenant_id",
                        "project_id",
                        "owner_id",
                        "credential_id",
                        "graph_id",
                        "thread_id",
                        "origin_run_id",
                        "task_id",
                        "event_id",
                    )
                },
                SECRET,
            )
        },
    )


def saved(factory):
    with factory() as session:
        row = session.scalar(select(RunRequestRecord))
        return _stored(row)


def test_completion_records_check_event_digest_and_execution_identity(setup):
    service, factory, upstream, data, _ = setup
    tenant_id = uuid4()
    data["tenant_id"] = str(tenant_id)
    upstream.create_run_with_acceptance.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        asyncio.run(launch(service, data))
    with factory.begin() as session:
        session.add(TenantRecord(id=tenant_id, name="fixture", slug="fixture"))
        session.flush()
        session.add(
            ProjectRecord(
                id=UUID(data["project_id"]), tenant_id=tenant_id, name="fixture"
            )
        )
        session.add(
            RunRequestRecord(
                project_id=data["project_id"],
                thread_id=data["thread_id"],
                agent_key=data["graph_id"],
                requested_by=data["owner_id"],
                idempotency_key="source",
                request_digest="f" * 64,
                context_snapshot={},
                context_hash="f" * 64,
                run_id=data["origin_run_id"],
            )
        )
    source, existing = completion.records(factory, data)
    assert source.run_id == data["origin_run_id"] and existing.run_id is None
    with pytest.raises(ForbiddenError, match="receipt source denied"):
        completion.records(factory, {**data, "exit_code": 1})
    marker = {
        k: v
        for k, v in data.items()
        if k not in {"status", "exit_code", "reconcile_only"}
    }
    assert completion.records(factory, marker)[1].id == existing.id
    for field, value in (
        ("requested_by", "another-owner"),
        ("agent_key", "another-graph"),
    ):
        with factory.begin() as session:
            row = session.get(RunRequestRecord, UUID(existing.id))
            old = getattr(row, field)
            setattr(row, field, value)
        with pytest.raises(ForbiddenError, match="receipt source denied"):
            completion.records(factory, marker)
        with factory.begin() as session:
            setattr(session.get(RunRequestRecord, UUID(existing.id)), field, old)


@pytest.mark.parametrize("changed", [False, True])
def test_execution_authorization_requires_original_saved_marker(
    setup, monkeypatch, changed
):
    service, factory, upstream, data, settings = setup
    upstream.create_run_with_acceptance.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        asyncio.run(launch(service, data))
    existing = saved(factory)
    body = json.loads(existing.upstream_body)
    values = {
        **body["config"]["configurable"][completion.MARKER]["values"],
        "context_hash": existing.context_hash,
    }
    marker = completion.sign_marker(values, SECRET)
    body["config"]["configurable"][completion.MARKER] = marker
    existing = replace(existing, upstream_body=json.dumps(body).encode())
    if changed:
        marker = completion.sign_marker({**values, "task_id": str(uuid4())}, SECRET)
    monkeypatch.setattr(completion, "records", Mock(return_value=(None, existing)))
    save = Mock()
    actor = Mock(
        side_effect=ForbiddenError(code="denied", message="Current ACL denied")
    )
    monkeypatch.setattr(completion, "save_receipt", save)
    monkeypatch.setattr(completion, "current_actor", actor)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(settings=settings, db_session_factory=factory)
        )
    )
    result = asyncio.run(
        completion.authorize_completion(
            request,
            completion.CompletionAuthorization(
                marker=marker, run_id=uuid4(), context=existing.context_snapshot
            ),
        )
    )
    assert result == {"allowed": False, "error_code": "background_task_denied"}
    assert actor.call_count == save.call_count == (0 if changed else 1)


@pytest.mark.parametrize("failure", [TimeoutError(), 401, 403, 404, 405, 409, 422, 503])
def test_final_bytes_commit_before_send_and_no_repeat_after_unknown(setup, failure):
    service, factory, upstream, data, _ = setup

    async def send(thread, body, key, digest):
        record = saved(factory)
        assert record.upstream_body == body and record.upstream_idempotency_key == key
        assert (
            record.upstream_request_digest
            == "sha256:" + hashlib.sha256(body).hexdigest()
            == digest
        )
        value = json.loads(body)
        assert value["version"] == "v3" and value["stream_resumable"] is True
        assert "idempotency_key" not in value
        assert grant_for(record, "create")["request_digest"] == digest
        if isinstance(failure, Exception):
            raise failure
        raise UpstreamServiceError(
            upstream="langgraph",
            message="synthetic",
            status_code=failure,
            upstream_status_code=failure,
        )

    upstream.create_run_with_acceptance.side_effect = send
    with pytest.raises((TimeoutError, UpstreamServiceError)):
        asyncio.run(launch(service, data))
    assert saved(factory).submission_status == "unknown"
    service._attach_runtime_model_reference.side_effect = AssertionError(
        "recovery rebuilt model reference"
    )
    with pytest.raises(UpstreamServiceError, match="reconciliation"):
        asyncio.run(launch(service, data))
    assert upstream.create_run_with_acceptance.await_count == 1
    upstream.create_thread_run.assert_not_awaited()


@pytest.mark.parametrize(
    "outcome",
    ["accepted", "unknown", "definitively_not_accepted", "malformed", "timeout"],
)
def test_reconcile_only_uses_original_bytes_and_never_current_authorization(
    setup, monkeypatch, outcome
):
    service, factory, upstream, data, settings = setup
    upstream.create_run_with_acceptance.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        asyncio.run(launch(service, data))
    record = saved(factory)
    value = receipt(
        record.thread_id,
        record.upstream_idempotency_key,
        record.upstream_request_digest,
        outcome
        if outcome in {"accepted", "unknown", "definitively_not_accepted"}
        else "accepted",
    )
    if outcome == "malformed":
        value["thread_id"] = str(uuid4())
    upstream.get_run_acceptance.return_value = value
    if outcome == "timeout":
        upstream.get_run_acceptance.side_effect = UpstreamServiceError(
            upstream="langgraph", message="timeout"
        )
    monkeypatch.setattr(
        "platform_api.adapters.langgraph.runtime_gateway_upstream.LangGraphRuntimeGatewayUpstream",
        Mock(return_value=upstream),
    )
    actor = Mock(side_effect=AssertionError("recovery asked for current write ACL"))
    monkeypatch.setattr(completion, "current_actor", actor)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(settings=settings, db_session_factory=factory)
        )
    )
    result = asyncio.run(
        completion.reconcile_acceptance(
            request, {**data, "reconcile_only": True}, record
        )
    )
    assert result["state"] == (
        "accepted"
        if outcome == "accepted"
        else "blocked"
        if outcome == "definitively_not_accepted"
        else "unknown"
    )
    upstream.get_run_acceptance.assert_awaited_once_with(
        record.thread_id,
        record.upstream_idempotency_key,
        record.upstream_request_digest,
    )
    assert upstream.create_run_with_acceptance.await_count == 1
    actor.assert_not_called()
    if outcome == "accepted":
        assert saved(factory).run_id == value["run_id"]


def test_binding_issuer_and_short_read_delegation(setup):
    service, factory, upstream, data, settings = setup
    upstream.create_run_with_acceptance.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        asyncio.run(launch(service, data))
    record = saved(factory)
    grant = grant_for(record)
    snapshot = {
        **record.upstream_auth_snapshot,
        "scope": {
            **record.upstream_auth_snapshot["scope"],
            "operation": "run-acceptance-read",
        },
    }
    token = create_runtime_delegation_token(
        **snapshot, settings=settings, run_acceptance=grant
    )
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] <= 60 and claims["run_acceptance"] == grant
    for field, changed in (
        ("tenant_id", "other"),
        ("project_id", str(uuid4())),
        ("subject", "other"),
        ("credential_id", str(uuid4())),
    ):
        with pytest.raises(ValueError):
            validate_grant(
                grant,
                subject=snapshot["subject"] if field != "subject" else changed,
                tenant_id=snapshot["tenant_id"] if field != "tenant_id" else changed,
                project_id=snapshot["project_id"] if field != "project_id" else changed,
                credential_id=snapshot["credential_id"]
                if field != "credential_id"
                else changed,
                scope=snapshot["scope"],
            )
    assert receipt_binding("tenant", data["project_id"], "owner") != receipt_binding(
        "other", data["project_id"], "owner"
    )


@pytest.mark.parametrize(
    "field,changed",
    [
        ("schema_version", True),
        ("accepted_at", "bad"),
        ("accepted_at", "2026-10-10T00:00:00"),
        ("observed_at", None),
        ("run_id", "bad"),
        ("run_state", {"available": True, "status": None}),
        ("run_state", {"available": False, "status": "pending"}),
        ("run_state", {"available": True, "status": "invented"}),
        ("reason", "multitask_rejected"),
    ],
)
def test_malformed_receipt_is_never_evidence(field, changed):
    thread, key, digest = str(uuid4()), "key", "sha256:" + "a" * 64
    value = {**receipt(thread, key, digest), field: changed}
    with pytest.raises(UpstreamServiceError):
        validate_receipt(value, thread, key, digest)


@pytest.mark.parametrize("fallback", [None, 404, 405])
@pytest.mark.parametrize("found", [False, True])
def test_legacy_reconcile_is_bounded_read_only_and_matches_source(
    setup, monkeypatch, fallback, found
):
    service, factory, upstream, data, settings = setup
    upstream.create_run_with_acceptance.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        asyncio.run(launch(service, data))
    record = saved(factory)
    if fallback is None:
        record = replace(record, upstream_body=None)
    else:
        upstream.get_run_acceptance.side_effect = UpstreamServiceError(
            upstream="langgraph", message="legacy", upstream_status_code=fallback
        )
    monkeypatch.setattr(
        "platform_api.adapters.langgraph.runtime_gateway_upstream.LangGraphRuntimeGatewayUpstream",
        Mock(return_value=upstream),
    )
    actor = Mock(return_value=ActorContext(user_id="owner"))
    monkeypatch.setattr(completion, "current_actor", actor)
    monkeypatch.setattr(completion, "bind_request", Mock())
    gateway = SimpleNamespace(
        _load_thread=AsyncMock(return_value={}),
        _thread_upstream=AsyncMock(return_value=upstream),
    )
    monkeypatch.setattr(
        "platform_api.modules.runtime_gateway.presentation.http.get_runtime_gateway_service",
        Mock(return_value=gateway),
    )
    match_id = str(uuid4())
    matching = {
        "run_id": match_id,
        "metadata": {
            "background_event_id": data["event_id"],
            "background_task_id": data["task_id"],
            "origin_run_id": data["origin_run_id"],
        },
    }
    wrong = {
        **matching,
        "metadata": {**matching["metadata"], "background_task_id": str(uuid4())},
    }
    pages = [[wrong] * 100] * (2 if found else 10)
    if found:
        pages.append([matching])
    upstream.list_thread_runs = AsyncMock(side_effect=pages)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(settings=settings, db_session_factory=factory)
        )
    )
    result = asyncio.run(completion.reconcile_acceptance(request, data, record))
    assert result["state"] == ("accepted" if found else "unknown")
    assert upstream.create_run_with_acceptance.await_count == 1
    upstream.create_thread_run.assert_not_awaited()
    assert upstream.list_thread_runs.await_count == (3 if found else 10)
    assert upstream.list_thread_runs.await_args_list[-1].args[1] == {
        "limit": 100,
        "offset": 200 if found else 900,
    }
    gateway._load_thread.assert_awaited_once_with(
        actor=actor.return_value,
        project_id=data["project_id"],
        thread_id=data["thread_id"],
        write=False,
    )
    assert saved(factory).run_id == (match_id if found else None)
