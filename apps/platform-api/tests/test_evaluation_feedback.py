from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from platform_api.core.context.models import ActorContext
from platform_api.core.db import (
    build_engine,
    build_session_factory,
    create_core_tables,
    session_scope,
)
from platform_api.core.errors import BadRequestError, ConflictError, ForbiddenError
from platform_api.modules.evaluation.contracts import ExportBody, FeedbackBody
from platform_api.modules.evaluation.privacy import clean_synthetic
from platform_api.modules.evaluation.service import (
    authorized_package,
    create_export,
    read_feedback,
    revoke_export,
    save_feedback,
    save_receipt,
)
from platform_api.modules.identity.models import UserRecord
from platform_api.modules.projects.models import ProjectMemberRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_gateway.application import thread_access


@pytest.fixture
def setup(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'feedback.db'}")
    factory = build_session_factory(engine)
    create_core_tables(engine)
    with session_scope(factory) as session:
        repository = SqlAlchemyProjectsRepository(session)
        tenant = repository.get_or_create_default_tenant()
        project = repository.create_project(
            tenant_id=tenant.id, name="Synthetic", description=""
        )
        project_id = str(project.id)
    actor = ActorContext(
        user_id=str(uuid4()), project_roles={project_id: ("project_admin",)}
    )
    with session_scope(factory) as session:
        session.add(
            UserRecord(
                id=UUID(actor.user_id), username="reviewer", external_subject="test"
            )
        )
        session.add(
            ProjectMemberRecord(
                project_id=UUID(project_id),
                user_id=UUID(actor.user_id),
                role="project_admin",
            )
        )
    thread_id = str(uuid4())
    thread_access.register(
        factory, thread_id=thread_id, project_id=project_id, actor=actor
    )
    yield factory, actor, (project_id, thread_id, "message-1")
    engine.dispose()


def body(**values):
    return FeedbackBody(
        event_id=uuid4(), expected_revision=0, rating="negative", **values
    )


def test_feedback_idempotency_revision_and_no_trace(setup):
    factory, actor, scope = setup
    request = body()
    saved = save_feedback(factory, actor, scope, request, run_ids=[])
    assert saved["revision"] == 1 and saved["link_status"] == "pending"
    assert saved == save_feedback(factory, actor, scope, request, run_ids=[])
    with pytest.raises(ConflictError):
        save_feedback(factory, actor, scope, body(), run_ids=[])
    changed = request.model_copy(update={"comment": "different"})
    with pytest.raises(ConflictError):
        save_feedback(factory, actor, scope, changed, run_ids=[])
    withdrawal = FeedbackBody(event_id=uuid4(), expected_revision=1, rating="withdrawn")
    save_feedback(factory, actor, scope, withdrawal, run_ids=[])
    assert read_feedback(factory, actor, scope)["rating"] == "withdrawn"


def test_authorized_feedback_projection_is_minimal_and_revoke_safe(setup):
    from platform_api.modules.evaluation.contracts import ProjectionBody
    from platform_api.modules.evaluation.service import save_projection

    factory, actor, scope = setup
    event = save_feedback(
        factory, actor, scope, body(comment="private comment"), run_ids=[str(uuid4())]
    )
    export = ExportBody(
        export_id=uuid4(),
        event_id=event["event_id"],
        data_class="synthetic",
        purpose="regression",
        scenario="Sum 2 and 3",
        expected="5",
        synthetic_attestation=True,
    )
    create_export(factory, actor, scope[0], export)
    package = authorized_package(factory, scope[0], export.export_id)
    assert "comment" not in package["feedback"]
    assert "private comment" not in str(package)
    projection = ProjectionBody(
        export_id=export.export_id,
        event_id=event["event_id"],
        status="linked",
        links={"tr-test": uuid4()},
    )
    saved = save_projection(factory, scope[0], projection)
    assert save_projection(factory, scope[0], projection) == saved
    assert read_feedback(factory, actor, scope)["link_status"] == "linked"
    revoke_export(factory, actor, scope[0], export.export_id)
    result = read_feedback(factory, actor, scope)
    assert result["link_status"] == "unavailable"
    assert result["link_reason"] == "source_revoked_or_expired"
    with pytest.raises(ForbiddenError):
        save_projection(factory, scope[0], projection)


def test_cross_project_and_other_user_rejected(setup):
    factory, actor, scope = setup
    with pytest.raises(ForbiddenError):
        save_feedback(factory, actor, (str(uuid4()), *scope[1:]), body(), run_ids=[])
    peer = ActorContext(user_id=str(uuid4()), project_roles=actor.project_roles)
    with pytest.raises(ForbiddenError):
        save_feedback(factory, peer, scope, body(), run_ids=[])


@pytest.mark.parametrize(
    "text",
    [
        "api_key=sample-secret",
        "Ｂｅａｒｅｒ fake-value",
        "tok\u200ben=sample",
        "-----BEGIN PRIVATE KEY-----",
    ],
)
def test_secrets_fail_closed(text):
    with pytest.raises(BadRequestError):
        clean_synthetic(text)


def test_redaction_is_consistent():
    cleaned = clean_synthetic(
        "test@example.invalid / test@example.invalid / 13800138000"
    )
    assert cleaned == "[REDACTED_1] / [REDACTED_1] / [REDACTED_2]"


def test_export_consent_and_withdrawal(setup):
    factory, actor, scope = setup
    event = save_feedback(factory, actor, scope, body(), run_ids=[])
    export = ExportBody(
        export_id=uuid4(),
        event_id=event["event_id"],
        data_class="synthetic",
        purpose="regression",
        scenario="2+3",
        expected="5",
        synthetic_attestation=True,
    )
    result = create_export(factory, actor, scope[0], export)
    assert result["status"] == "ready"
    assert create_export(factory, actor, scope[0], export) == result
    save_feedback(
        factory,
        actor,
        scope,
        FeedbackBody(event_id=uuid4(), expected_revision=1, rating="withdrawn"),
        run_ids=[],
    )
    with pytest.raises(ConflictError):
        create_export(factory, actor, scope[0], export)


def make_export(setup):
    factory, actor, scope = setup
    event = save_feedback(factory, actor, scope, body(), run_ids=[])
    request = ExportBody(
        export_id=uuid4(),
        event_id=event["event_id"],
        data_class="synthetic",
        purpose="regression",
        scenario="2+3",
        expected="5",
        synthetic_attestation=True,
    )
    create_export(factory, actor, scope[0], request)
    return request.export_id


def test_managed_retention_cleans_content_and_preserves_access_denial(setup):
    from datetime import UTC, datetime, timedelta

    from platform_api.modules.evaluation.models import EvaluationExport
    from platform_api.modules.evaluation.retention import sweep

    factory, actor, scope = setup
    export_id = make_export(setup)
    now = datetime.now(UTC)
    with session_scope(factory) as session:
        row = session.get(EvaluationExport, str(export_id))
        row.expires_at = now - timedelta(seconds=1)
        row.receipt = {"unexpected_copy": "should be removed"}
    with pytest.raises(ForbiddenError):
        authorized_package(factory, scope[0], export_id)
    assert sweep(factory, "other", now=now) == {
        "cleaned": 0,
        "removed": 0,
        "audit_removed": 0,
    }
    assert sweep(factory, scope[0], now=now) == {
        "cleaned": 1,
        "removed": 0,
        "audit_removed": 0,
    }
    assert sweep(factory, scope[0], now=now) == {
        "cleaned": 0,
        "removed": 0,
        "audit_removed": 0,
    }
    with session_scope(factory) as session:
        row = session.get(EvaluationExport, str(export_id))
        assert row.status == "expired" and row.receipt == {}
        assert "scenario" not in row.payload and "expected" not in row.payload
        assert row.payload["content_hash"] and row.payload["purged_at"]
    result = sweep(factory, scope[0], now=now + timedelta(days=91))
    assert result["removed"] == 1 and result["audit_removed"] == 1


def test_retention_does_not_delete_legacy_or_business_content(setup):
    from datetime import UTC, datetime, timedelta

    from platform_api.modules.evaluation.models import EvaluationExport
    from platform_api.modules.evaluation.retention import sweep

    factory, _, scope = setup
    export_id = make_export(setup)
    with session_scope(factory) as session:
        row = session.get(EvaluationExport, str(export_id))
        payload = dict(row.payload)
        payload.pop("retention_policy")
        row.payload = payload
        # Existing records without a policy marker are outside this cleanup.
        from platform_api.modules.audit.models import AuditLogRecord

        for audit in session.scalars(select(AuditLogRecord)):
            audit.metadata_json = {}
    assert sweep(factory, scope[0], now=datetime.now(UTC) + timedelta(days=100)) == {
        "cleaned": 0,
        "removed": 0,
        "audit_removed": 0,
    }


def test_revoked_export_rejects_late_receipt(setup):
    factory, actor, scope = setup
    export_id = make_export(setup)
    package = authorized_package(factory, scope[0], export_id)
    receipt = {
        "export_id": str(export_id),
        "content_hash": package["content_hash"],
        "trace_id": "tr-test",
    }
    save_receipt(factory, export_id, receipt)
    assert read_feedback(factory, actor, scope)["export"]["receipt"] == receipt
    revoke_export(factory, actor, scope[0], export_id)
    with pytest.raises(ForbiddenError):
        save_receipt(factory, export_id, receipt)
    result = read_feedback(factory, actor, scope)["export"]
    assert result["status"] == "revoked" and result["scenario"] == ""


@pytest.mark.parametrize("state", ["expired", "revoked", "pending", "deadline"])
def test_projection_read_without_receipt(setup, state):
    from datetime import UTC, datetime, timedelta

    from platform_api.modules.evaluation.models import EvaluationExport

    factory, actor, scope = setup
    export_id = make_export(setup)
    with session_scope(factory) as session:
        export = session.get(EvaluationExport, str(export_id))
        if state == "expired":
            export.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif state == "revoked":
            export.status = "revoked"
        elif state == "deadline":
            export.created_at = datetime.now(UTC) - timedelta(minutes=16)
    result = read_feedback(factory, actor, scope)
    assert result["link_status"] == ("pending" if state == "pending" else "unavailable")
    if state in {"expired", "revoked"}:
        assert result["link_reason"] == "source_revoked_or_expired"
    elif state == "deadline":
        assert result["link_reason"] == "projection_deadline_exceeded"


@pytest.mark.parametrize(
    "reason", ["disabled_user", "removed_member", "withdrawn_feedback", "expired"]
)
def test_export_rechecks_live_authorization(setup, reason):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    from platform_api.modules.evaluation.models import EvaluationExport

    factory, actor, scope = setup
    export_id = make_export(setup)
    authorized_package(factory, scope[0], export_id)
    with session_scope(factory) as session:
        if reason == "disabled_user":
            session.get(UserRecord, UUID(actor.user_id)).status = "disabled"
        elif reason == "removed_member":
            session.execute(
                delete(ProjectMemberRecord).where(
                    ProjectMemberRecord.user_id == UUID(actor.user_id)
                )
            )
        elif reason == "expired":
            session.get(EvaluationExport, str(export_id)).expires_at = datetime.now(
                UTC
            ) - timedelta(seconds=1)
    if reason == "withdrawn_feedback":
        save_feedback(
            factory,
            actor,
            scope,
            FeedbackBody(event_id=uuid4(), expected_revision=1, rating="withdrawn"),
            run_ids=[],
        )
    with pytest.raises(ForbiddenError):
        authorized_package(factory, scope[0], export_id)


def test_migration_rollback_preserves_facts_and_reupgrade(tmp_path):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text

    path = (
        Path(__file__).parents[1]
        / "migrations/versions/20261113_0011_evaluation_feedback.py"
    )
    spec = importlib.util.spec_from_file_location("feedback_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        connection.execute(
            text(
                "INSERT INTO evaluation_feedback_events VALUES ('e','t','p','th','m','u',1,'hash','{}',CURRENT_TIMESTAMP)"
            )
        )
        migration.downgrade()
        migration.upgrade()
        assert (
            connection.scalar(text("SELECT count(*) FROM evaluation_feedback_events"))
            == 1
        )
    engine.dispose()


def test_internal_authorization_batch_requires_token_and_returns_only_decisions(setup):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from platform_api.core.errors import register_exception_handlers
    from platform_api.modules.evaluation.router import router

    factory, actor, scope = setup
    export_id = make_export(setup)
    missing_id = uuid4()
    app = FastAPI()
    app.state.db_session_factory = factory
    app.state.settings = SimpleNamespace(
        evaluation_feedback_enabled=True,
        evaluation_synthetic_export_enabled=True,
        evaluation_source_token="synthetic-unit-test",
        evaluation_project_id=scope[0],
    )
    register_exception_handlers(app)
    app.include_router(router)
    client = TestClient(app)
    path = "/api/evaluation/internal/authorizations"
    body = {"export_ids": [str(export_id), str(missing_id)]}
    assert client.post(path, json=body).status_code == 403
    headers = {"Authorization": "Bearer synthetic-unit-test"}
    assert client.post(path, json=body, headers=headers).json() == {
        "authorizations": {str(export_id): True, str(missing_id): False}
    }
    revoke_export(factory, actor, scope[0], export_id)
    assert client.post(path, json=body, headers=headers).json() == {
        "authorizations": {str(export_id): False, str(missing_id): False}
    }
    for ids in ([], ["invalid"], [str(export_id)] * 1001):
        assert (
            client.post(path, json={"export_ids": ids}, headers=headers).status_code
            == 422
        )
    app.state.settings.evaluation_feedback_enabled = False
    assert client.post(path, json=body, headers=headers).status_code == 503
