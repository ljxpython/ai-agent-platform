"""Historical source authorization, privacy and retention remain after UI retirement."""

from uuid import UUID, uuid4

import pytest
from evaluation_fixtures import add_feedback, make_export
from sqlalchemy import select

from platform_api.core.db import session_scope
from platform_api.core.errors import BadRequestError, ConflictError, ForbiddenError
from platform_api.modules.evaluation.privacy import clean_synthetic
from platform_api.modules.evaluation.service import authorized_package, revoke_export
from platform_api.modules.identity.models import UserRecord
from platform_api.modules.projects.models import ProjectMemberRecord


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
        add_feedback(factory, actor, scope, rating="withdrawn", revision=2)
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


def test_historical_projection_is_minimal_idempotent_and_revoke_safe(setup):
    from platform_api.modules.evaluation.contracts import ProjectionBody
    from platform_api.modules.evaluation.service import save_projection

    factory, actor, scope = setup
    export_id = make_export(setup)
    package = authorized_package(factory, scope[0], export_id)
    assert "private comment" not in str(package)
    body = ProjectionBody(
        export_id=export_id,
        event_id=package["source_event"],
        status="linked",
        links={"tr-test": uuid4()},
    )
    assert save_projection(factory, scope[0], body) == save_projection(
        factory, scope[0], body
    )
    with pytest.raises(ConflictError):
        save_projection(
            factory, scope[0], body.model_copy(update={"links": {"different": uuid4()}})
        )
    revoke_export(factory, actor, scope[0], export_id)
    with pytest.raises(ForbiddenError):
        save_projection(factory, scope[0], body)
