"""Managed callbacks prove execution facts; current Platform ACL controls visibility."""

import base64
import hashlib
import hmac
import json
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from platform_api.core.db import session_scope
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.domain.completion import (
    CompletionAck,
    TerminalCompletion,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy import (
    completion_repository as repo,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionOriginRecord as Origin,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunRequestRecord,
    ThreadAccessRecord,
)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@contextmanager
def storage_session(factory):
    try:
        with session_scope(factory) as session:
            yield session
    except SQLAlchemyError as exc:
        raise ServiceUnavailableError(
            code="completion_storage_unavailable",
            message="Completion storage is unavailable",
        ) from exc


def completion_summary(event, actor, read_at=None):
    failure = event.status in {"error", "timeout"}
    notification = None
    if failure:
        notification = (
            "run_timed_out"
            if event.status == "timeout"
            else "run_failed_" + event.model_error_code
            if event.model_error_code
            else "run_failed_step_limit"
            if event.reason_code == "runtime_graph_step_limit_reached"
            else "run_failed_workspace"
            if (event.reason_code or "").startswith("runtime.workspace.")
            else "run_failed"
        )
    recipient = (
        actor.principal_type == "user" and actor.user_id == event.recipient_user_id
    )
    return {
        "event_id": event.event_id,
        "graph_id": event.agent_key,
        "status": event.status,
        "reason": event.reason,
        "reason_code": event.reason_code,
        "model_error_code": event.model_error_code,
        "notification_code": notification,
        "occurred_at": utc(event.occurred_at),
        "can_mark_read": bool(recipient and failure),
        "read_at": utc(read_at) if recipient and read_at else None,
    }


def verify_signature(settings, raw_body, headers, *, method, path):
    if hasattr(headers, "getlist") and any(
        len(headers.getlist(name)) != 1
        for name in (
            "x-run-completion-key-id",
            "x-run-completion-timestamp",
            "x-run-completion-signature",
            "x-run-completion-event-id",
        )
    ):
        raise ForbiddenError(
            code="completion_signature_invalid", message="Invalid completion signature"
        )
    key_id = headers.get("x-run-completion-key-id", "")
    keys = {**settings.runtime_completion_verification_keys}
    if settings.runtime_completion_secret:
        keys[settings.runtime_completion_key_id] = settings.runtime_completion_secret
    secret = keys.get(key_id)
    stamp = headers.get("x-run-completion-timestamp", "")
    try:
        timely = (
            stamp.isascii()
            and stamp.isdigit()
            and abs(time.time() - int(stamp))
            <= settings.runtime_completion_clock_skew_seconds
        )
    except (TypeError, ValueError):
        timely = False
    signature = headers.get("x-run-completion-signature", "")
    if (
        len(key_id) > 128
        or len(stamp) > 20
        or len(signature) != 71
        or not signature.startswith("sha256=")
        or any(c not in "0123456789abcdef" for c in signature[7:])
    ):
        raise ForbiddenError(
            code="completion_signature_invalid", message="Invalid completion signature"
        )
    canonical = f"{key_id}\n{stamp}\n{method}\n{path}\n".encode() + raw_body
    expected = (
        "sha256="
        + hmac.new((secret or "").encode(), canonical, hashlib.sha256).hexdigest()
    )
    if not secret or not timely or not hmac.compare_digest(signature, expected):
        raise ForbiddenError(
            code="completion_signature_invalid", message="Invalid completion signature"
        )
    return "default"


def _fresh_thread(session, origin, terminal, factory):
    if terminal.thread_id is None or repo.deleted(
        session,
        project_id=origin.project_id,
        thread_id=str(terminal.thread_id),
        run_id=str(terminal.run_id),
    ):
        return None
    thread_id = str(terminal.thread_id)
    access = session.get(ThreadAccessRecord, thread_id, with_for_update=True)
    if access or origin.source_kind != "schedule" or origin.thread_mode != "fresh":
        return access
    if repo.deleted(
        session,
        project_id=origin.project_id,
        thread_id=thread_id,
        run_id=str(terminal.run_id),
    ):
        return None
    deleted = session.scalar(
        select(AuditLogRecord.id)
        .where(
            AuditLogRecord.action == "thread.deleted",
            AuditLogRecord.target_id == thread_id,
        )
        .limit(1)
    )
    if deleted or not origin.requested_by:
        return None
    from platform_api.modules.identity.actors import load_user_actor
    from platform_api.modules.scheduled_tasks.service import require_active_project

    actor = load_user_actor(
        session_factory=factory,
        user_id=origin.requested_by,
        project_id=origin.project_id,
    )
    if not actor or not actor.project_role_set(origin.project_id):
        return None
    try:
        require_active_project(factory, origin.project_id)
    except ForbiddenError:
        return None
    fields = thread_access.initial_metadata(actor, {"project_id": origin.project_id})
    access = ThreadAccessRecord(
        thread_id=thread_id,
        **{
            name: fields[name]
            for name in (
                "project_id",
                "owner_user_id",
                "visibility",
                "shared_actions",
                "project_actions",
                "takeovers",
            )
        },
    )
    session.add(access)
    session.flush()
    return access


def _accept(session, factory, terminal, digest, runtime_id):
    repo.serialize_thread(session, str(terminal.thread_id))
    # Lock the precommitted origin before checking duplicates so early callbacks serialize with dispatch binding.
    origin = repo.get_origin(session, terminal.origin_ref)
    if origin is None:
        raise ServiceUnavailableError(
            code="completion_origin_unavailable",
            message="Completion origin is temporarily unavailable",
        )
    if (
        origin.runtime_id != runtime_id
        or origin.agent_key != terminal.graph_id
        or (
            origin.thread_id is not None and origin.thread_id != str(terminal.thread_id)
        )
    ):
        raise ConflictError(
            code="completion_origin_mismatch", message="Completion source mismatch"
        )
    existing = repo.get_event(session, terminal.event_id)
    if existing:
        if existing.body_digest != digest or existing.origin_ref != origin.origin_ref:
            raise ConflictError(
                code="completion_event_conflict", message="Completion event conflicts"
            )
        return CompletionAck(event_id=terminal.event_id, duplicate=True)
    if repo.event_for_run(session, runtime_id, str(terminal.run_id)):
        raise ConflictError(
            code="completion_run_conflict", message="Run already has a terminal event"
        )
    if origin.source_kind == "submission":
        if origin.run_id and origin.run_id != str(terminal.run_id):
            raise ConflictError(
                code="completion_run_conflict",
                message="Origin already belongs to another run",
            )
        origin.run_id = str(terminal.run_id)
        submission = session.scalar(
            select(RunRequestRecord)
            .where(RunRequestRecord.origin_ref == origin.origin_ref)
            .with_for_update()
        )
        if submission:
            if submission.run_id and submission.run_id != origin.run_id:
                raise ConflictError(
                    code="completion_run_conflict", message="Submission run conflicts"
                )
            submission.run_id = origin.run_id
            submission.submission_status = "accepted"
    access = _fresh_thread(session, origin, terminal, factory)
    suppressed = (
        origin.state == "deleted"
        or access is None
        or access.project_id != origin.project_id
        or terminal.reason == "rollback"
        or terminal.occurred_at < datetime.now(UTC) - timedelta(days=30)
    )
    repo.create_event(session, origin, terminal, digest, suppressed=suppressed)
    if origin.source_kind == "submission" and origin.state != "deleted":
        origin.state = "completed"
    return CompletionAck(event_id=terminal.event_id, duplicate=False)


def accept_completion(factory, terminal, *, digest, runtime_id):
    try:
        try:
            with session_scope(factory) as session:
                ack = _accept(session, factory, terminal, digest, runtime_id)
            return ack
        except IntegrityError:
            # A different schedule origin can race on the same event/run; re-read committed facts once.
            with session_scope(factory) as session:
                return _accept(session, factory, terminal, digest, runtime_id)
    except SQLAlchemyError as exc:
        raise ServiceUnavailableError(
            code="completion_storage_unavailable",
            message="Completion storage is unavailable",
        ) from exc


def parse_callback(settings, raw_body, headers, *, method, path):
    runtime_id = verify_signature(settings, raw_body, headers, method=method, path=path)
    try:
        terminal = TerminalCompletion.model_validate_json(raw_body)
    except ValueError as exc:
        raise BadRequestError(
            code="completion_payload_invalid", message="Invalid completion payload"
        ) from exc
    if headers.get("x-run-completion-event-id") != str(terminal.event_id):
        raise BadRequestError(
            code="completion_event_id_mismatch", message="Completion event ID mismatch"
        )
    if terminal.occurred_at > datetime.now(UTC) + timedelta(
        seconds=settings.runtime_completion_clock_skew_seconds
    ):
        raise BadRequestError(
            code="completion_time_invalid", message="Invalid completion timestamp"
        )
    return terminal, runtime_id


def get_completion(factory, *, actor, project_id, thread_id, run_id):
    with storage_session(factory) as session:
        access = session.get(ThreadAccessRecord, thread_id)
        if not access or not thread_access.allowed(
            actor, project_id, thread_access.record_metadata(access), "read"
        ):
            raise NotFoundError(
                code="completion_not_found", message="Completion unavailable"
            )
        event = repo.event_for_run(session, "default", run_id)
        if event:
            if (
                event.suppressed
                or event.project_id != project_id
                or event.thread_id != thread_id
            ):
                raise NotFoundError(
                    code="completion_not_found", message="Completion unavailable"
                )
            if utc(event.detail_expires_at) <= datetime.now(UTC):
                return "expired", None
            read = repo.receipt(session, event.event_id, actor.user_id)
            return "available", completion_summary(
                event, actor, read.read_at if read else None
            )
        origin = session.scalar(
            select(Origin).where(
                Origin.project_id == project_id,
                Origin.thread_id == thread_id,
                Origin.run_id == run_id,
            )
        )
        if origin and origin.state == "completed":
            return "expired", None
        return ("pending" if origin else "unsupported"), None


def _cursor(secret, *, scope, value=None, upper=None, after=None):
    if value:
        try:
            encoded, signature = value.split(".")
            expected = hmac.new(
                secret.encode(), encoded.encode(), hashlib.sha256
            ).hexdigest()
            payload = json.loads(
                base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            )
            if (
                not hmac.compare_digest(signature, expected)
                or payload["scope"] != scope
            ):
                raise ValueError()
            upper = datetime.fromisoformat(payload["upper"])
            after = (
                datetime.fromisoformat(payload["after"][0]),
                UUID(payload["after"][1]),
            )
            if upper.tzinfo is None or after[0].tzinfo is None:
                raise ValueError()
            return upper, after
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise BadRequestError(
                code="invalid_completion_cursor", message="Invalid completion cursor"
            ) from exc
    payload = {
        "scope": scope,
        "upper": upper.isoformat(),
        "after": [after[0].isoformat(), str(after[1])],
    }
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    return (
        encoded
        + "."
        + hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    )


def list_notifications(
    factory, settings, *, actor, project_id, limit, cursor, unread_only
):
    if (
        actor.principal_type != "user"
        or not actor.user_id
        or not actor.project_role_set(project_id)
    ):
        raise ForbiddenError(
            code="completion_user_required", message="User notifications unavailable"
        )
    scope = [actor.user_id, project_id, "default", unread_only]
    secret = settings.runtime_delegation_secret
    upper, after = (
        _cursor(secret, scope=scope, value=cursor)
        if cursor
        else (datetime.now(UTC), None)
    )
    items, scanned, more = [], 0, True
    with storage_session(factory) as session:
        while more and len(items) < limit and scanned < 500:
            rows = repo.feed_batch(
                session,
                actor_id=actor.user_id,
                project_id=project_id,
                unread_only=unread_only,
                upper=upper,
                after=after,
                limit=50,
            )
            more = len(rows) == 50
            for event, access, read_at in rows:
                scanned += 1
                after = (utc(event.accepted_at), event.event_id)
                if access is not None and thread_access.allowed(
                    actor, project_id, thread_access.record_metadata(access), "read"
                ):
                    items.append(
                        {
                            **completion_summary(event, actor, read_at),
                            "thread_id": event.thread_id,
                            "run_id": event.run_id,
                            "received_at": utc(event.accepted_at),
                        }
                    )
                if len(items) == limit:
                    more = True
                    break
    return {
        "items": items,
        "next_cursor": _cursor(secret, scope=scope, upper=upper, after=after)
        if more and after
        else None,
        "scan_limit_reached": scanned >= 500 and len(items) < limit,
    }


def mark_read(factory, *, actor, project_id, event_id):
    if actor.principal_type != "user" or not actor.user_id:
        raise ForbiddenError(
            code="completion_user_required", message="User notifications unavailable"
        )
    with storage_session(factory) as session:
        event = session.get(repo.Event, event_id, with_for_update=True)
        if (
            not event
            or event.recipient_user_id != actor.user_id
            or event.project_id != project_id
            or event.suppressed
            or event.status not in {"error", "timeout"}
            or utc(event.detail_expires_at) <= datetime.now(UTC)
        ):
            raise NotFoundError(
                code="notification_not_found", message="Notification unavailable"
            )
        access = session.get(ThreadAccessRecord, event.thread_id)
        if access is None or not thread_access.allowed(
            actor, project_id, thread_access.record_metadata(access), "read"
        ):
            raise NotFoundError(
                code="notification_not_found", message="Notification unavailable"
            )
        return utc(repo.write_receipt(session, event_id, actor.user_id))
