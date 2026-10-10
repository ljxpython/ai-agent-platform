from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.core.errors import ConflictError
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionOriginRecord,
    RunRequestRecord,
)


@dataclass(frozen=True)
class StoredRunRequest:
    id: str
    project_id: str
    thread_id: str
    agent_key: str
    requested_by: str
    idempotency_key: str
    request_digest: str
    context_snapshot: dict
    config_snapshot: dict
    context_hash: str
    run_id: str | None
    submission_status: str
    parent_run_id: str | None
    interrupt_id: str | None
    origin_ref: str | None = None
    upstream_idempotency_key: str | None = None
    upstream_body: bytes | None = None
    upstream_request_digest: str | None = None
    upstream_receipt_scope_id: str | None = None
    upstream_receipt_credential_id: str | None = None
    upstream_auth_snapshot: dict | None = None


def _stored(row: RunRequestRecord) -> StoredRunRequest:
    values = {
        name: getattr(row, name) for name in StoredRunRequest.__dataclass_fields__
    }
    values["id"] = str(row.id)
    values["context_snapshot"] = dict(row.context_snapshot)
    return StoredRunRequest(**values)


class RunRequestsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, *, project_id: str, thread_id: str, idempotency_key: str):
        row = self.session.scalar(
            select(RunRequestRecord).where(
                RunRequestRecord.project_id == project_id,
                RunRequestRecord.thread_id == thread_id,
                RunRequestRecord.idempotency_key == idempotency_key,
            )
        )
        return _stored(row) if row else None

    def for_run(self, *, project_id: str, thread_id: str, run_id: str):
        row = self.session.scalar(
            select(RunRequestRecord)
            .where(
                RunRequestRecord.project_id == project_id,
                RunRequestRecord.thread_id == thread_id,
                RunRequestRecord.run_id == run_id,
            )
            .limit(1)
        )
        return _stored(row) if row else None

    def create(self, **values):
        row = RunRequestRecord(**values)
        self.session.add(row)
        self.session.flush()
        return _stored(row)

    def mark(self, request_id: str, status: str, run_id: str | None = None):
        origin_ref = self.session.scalar(
            select(RunRequestRecord.origin_ref).where(
                RunRequestRecord.id == UUID(request_id)
            )
        )
        origin = (
            self.session.get(
                RunCompletionOriginRecord, origin_ref, with_for_update=True
            )
            if origin_ref
            else None
        )
        row = self.session.get(RunRequestRecord, UUID(request_id), with_for_update=True)
        if row is None:
            raise RuntimeError("Run request disappeared")
        if row.run_id:
            if run_id and row.run_id != run_id:
                raise ConflictError(
                    code="upstream_idempotency_violation",
                    message="Agent Server returned different runs for one key",
                )
            return
        row.submission_status = status
        if run_id:
            if origin:
                if origin and origin.run_id and origin.run_id != run_id:
                    raise ConflictError(
                        code="completion_run_conflict",
                        message="Completion origin run conflicts",
                    )
                origin.run_id = run_id
            row.run_id = run_id
        self.session.flush()

    def bind_acceptance(self, request_id: str, **values):
        row = self.session.get(RunRequestRecord, UUID(request_id), with_for_update=True)
        if row is None:
            raise RuntimeError("Run request disappeared")
        if row.upstream_body is not None:
            if any(getattr(row, name) != value for name, value in values.items()):
                raise ConflictError(
                    code="upstream_request_conflict",
                    message="Acceptance request is already bound",
                )
            return _stored(row)
        for name, value in values.items():
            if name not in {
                "upstream_idempotency_key",
                "upstream_body",
                "upstream_request_digest",
                "upstream_receipt_scope_id",
                "upstream_receipt_credential_id",
                "upstream_auth_snapshot",
            }:
                raise ValueError("Invalid acceptance field")
            setattr(row, name, value)
        self.session.flush()
        return _stored(row)
