"""Short transactions for platform origins, idempotent events and receipts."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, text, update

from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionEventRecord as Event,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionOriginRecord as Origin,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionReceiptRecord as Receipt,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)


def reserve_origin(session, **values) -> str:
    row = Origin(origin_ref=str(uuid4()), **values)
    session.add(row)
    session.flush()
    return row.origin_ref


def serialize_thread(session, thread_id):
    if session.bind.dialect.name == "postgresql":
        key = int.from_bytes(
            hashlib.sha256(f"completion:{thread_id}".encode()).digest()[:8],
            "big",
            signed=True,
        )
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def get_origin(session, origin_ref):
    return session.get(Origin, str(origin_ref), with_for_update=True)


def event_for_run(session, runtime_id, run_id):
    return session.scalar(
        select(Event).where(Event.runtime_id == runtime_id, Event.run_id == run_id)
    )


def get_event(session, event_id):
    return session.get(Event, event_id)


def create_event(session, origin, terminal, digest, *, suppressed):
    now = datetime.now(UTC)
    outcome = terminal.outcome
    reason_code = outcome.reason_code
    if terminal.status == "timeout":
        reason_code = "runtime_run_timeout"
    elif terminal.status == "error":
        reason_code = reason_code or "runtime_execution_failed"
    row = Event(
        event_id=terminal.event_id,
        runtime_id=origin.runtime_id,
        origin_ref=origin.origin_ref,
        project_id=origin.project_id,
        run_id=str(terminal.run_id),
        thread_id=str(terminal.thread_id) if terminal.thread_id else None,
        agent_key=origin.agent_key,
        recipient_user_id=origin.requested_by,
        status=terminal.status,
        reason=terminal.reason,
        reason_code=reason_code,
        model_error_code=outcome.model_error_code,
        sequence=terminal.sequence,
        occurred_at=terminal.occurred_at,
        body_digest=digest,
        payload={},
        suppressed=suppressed,
        accepted_at=now,
        detail_expires_at=now + timedelta(days=30),
        dedup_expires_at=now + timedelta(days=90),
    )
    session.add(row)
    session.flush()
    return row


def receipt(session, event_id, actor_id):
    return session.scalar(
        select(Receipt).where(
            Receipt.event_id == event_id, Receipt.actor_user_id == actor_id
        )
    )


def write_receipt(session, event_id, actor_id):
    row = receipt(session, event_id, actor_id)
    if row is None:
        row = Receipt(
            event_id=event_id, actor_user_id=actor_id, read_at=datetime.now(UTC)
        )
        session.add(row)
        session.flush()
    return row.read_at


def feed_batch(session, *, actor_id, project_id, unread_only, upper, after, limit):
    candidates = select(Event.event_id).where(
        Event.project_id == project_id,
        Event.recipient_user_id == actor_id,
        Event.suppressed.is_(False),
        Event.status.in_(("error", "timeout")),
        Event.detail_expires_at > datetime.now(UTC),
        Event.accepted_at <= upper,
    )
    if unread_only:
        candidates = candidates.where(
            ~select(Receipt.id)
            .where(
                Receipt.event_id == Event.event_id, Receipt.actor_user_id == actor_id
            )
            .exists()
        )
    if after:
        stamp, event_id = after
        candidates = candidates.where(
            or_(
                Event.accepted_at < stamp,
                and_(Event.accepted_at == stamp, Event.event_id < event_id),
            )
        )
    # Limit indexed candidates before ACL joins; missing ACL rows still advance the scan cursor.
    candidates = (
        candidates.order_by(Event.accepted_at.desc(), Event.event_id.desc())
        .limit(limit)
        .subquery()
    )
    query = (
        select(Event, ThreadAccessRecord, Receipt.read_at)
        .join(candidates, candidates.c.event_id == Event.event_id)
        .outerjoin(
            ThreadAccessRecord,
            and_(
                ThreadAccessRecord.thread_id == Event.thread_id,
                ThreadAccessRecord.project_id == project_id,
            ),
        )
        .outerjoin(
            Receipt,
            and_(Receipt.event_id == Event.event_id, Receipt.actor_user_id == actor_id),
        )
    )
    return session.execute(
        query.order_by(Event.accepted_at.desc(), Event.event_id.desc())
    ).all()


def deleted(session, *, project_id, thread_id, run_id=None):
    targets = [
        and_(
            AuditLogRecord.action == "thread.deleted",
            AuditLogRecord.target_id == thread_id,
        )
    ]
    if run_id:
        targets.append(
            and_(
                AuditLogRecord.action == "run.deleted",
                AuditLogRecord.target_id == run_id,
            )
        )
    return (
        session.scalar(
            select(AuditLogRecord.id)
            .where(AuditLogRecord.project_id == project_id, or_(*targets))
            .limit(1)
        )
        is not None
    )


def suppress(session, *, project_id, thread_id, run_id=None):
    serialize_thread(session, thread_id)
    filters = [Event.project_id == project_id, Event.thread_id == thread_id]
    origin_filters = [Origin.project_id == project_id, Origin.thread_id == thread_id]
    if run_id:
        filters.append(Event.run_id == run_id)
        origin_filters.append(Origin.run_id == run_id)
    session.execute(update(Origin).where(*origin_filters).values(state="deleted"))
    session.get(ThreadAccessRecord, thread_id, with_for_update=True)
    session.execute(update(Event).where(*filters).values(suppressed=True))
    if run_id:
        session.add(
            AuditLogRecord(
                request_id=str(uuid4()),
                plane="runtime_gateway",
                action="run.deleted",
                target_type="run",
                target_id=run_id,
                project_id=project_id,
                result="success",
                method="DELETE",
                path=f"/api/langgraph/threads/{thread_id}/runs/{run_id}",
                status_code=200,
                duration_ms=0,
                metadata_json={},
            )
        )
