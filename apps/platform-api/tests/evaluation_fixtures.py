"""Shared platform fixture and persisted legacy evaluation records; no retired APIs."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from platform_api.core.context.models import ActorContext
from platform_api.core.db import (
    build_engine,
    build_session_factory,
    create_core_tables,
    session_scope,
)
from platform_api.modules.evaluation.models import EvaluationExport, FeedbackEvent
from platform_api.modules.evaluation.service import audit, digest
from platform_api.modules.identity.models import UserRecord
from platform_api.modules.projects.models import ProjectMemberRecord, ProjectRecord
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


def add_feedback(factory, actor, scope, *, rating="negative", revision=1):
    event_id = str(uuid4())
    with session_scope(factory) as session:
        project = session.get(ProjectRecord, UUID(scope[0]))
        session.add(
            FeedbackEvent(
                event_id=event_id,
                tenant_id=str(project.tenant_id),
                project_id=scope[0],
                thread_id=scope[1],
                message_id=scope[2],
                actor_id=actor.user_id,
                revision=revision,
                digest=digest({"fixture": event_id}),
                payload={"rating": rating, "run_ids": [], "comment": "private comment"},
            )
        )
    return event_id


def make_export(setup):
    factory, actor, scope = setup
    event_id = add_feedback(factory, actor, scope)
    export_id = str(uuid4())
    payload = {
        "scenario": "2+3",
        "expected": "5",
        "data_class": "synthetic",
        "purpose": "regression",
        "policy_version": "synthetic-local-v1",
        "retention_policy": "local-synthetic-20261114",
        "source_event": event_id,
        "feedback": {
            "event_id": event_id,
            "revision": 1,
            "rating": "negative",
            "actor_id": actor.user_id,
            "thread_id": scope[1],
            "message_id": scope[2],
            "run_ids": [],
        },
        "snapshot_timing": "human_reconstruction",
        "content_hash": digest({"scenario": "2+3", "expected": "5"}),
    }
    with session_scope(factory) as session:
        session.add(
            EvaluationExport(
                export_id=export_id,
                event_id=event_id,
                project_id=scope[0],
                actor_id=actor.user_id,
                digest=digest(payload),
                status="ready",
                expires_at=datetime.now(UTC) + timedelta(hours=24),
                payload=payload,
                receipt={},
            )
        )
        audit(
            session,
            actor,
            scope[0],
            export_id,
            "evaluation.export.authorized",
            retention_policy=payload["retention_policy"],
        )
    return export_id
