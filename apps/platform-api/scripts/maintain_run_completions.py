"""Explicit completion retention maintenance; preview by default."""

import argparse
import json
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, text, update

from platform_api.config import load_settings
from platform_api.core.db import build_engine, build_session_factory
from platform_api.modules.runtime_gateway.application.retention import (
    maintenance_lock,
    register_missing,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.completion_repository import (
    Event,
    Receipt,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionOriginRecord as Origin,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunRequestRecord as Request,
)


def maintain(factory, *, apply=False, now=None, limit=100, budget_seconds=30):
    if not 1 <= limit <= 1000 or not 1 <= budget_seconds <= 300:
        raise ValueError("invalid maintenance bounds")
    now = now or datetime.now(UTC)
    deadline = time.monotonic() + budget_seconds
    terminal = (
        select(Event.event_id)
        .where(
            Event.run_id == Request.run_id,
            Event.project_id == Request.project_id,
            Event.status.in_(("success", "error", "timeout", "interrupted")),
            or_(Event.reason.is_(None), Event.reason != "hitl_interrupt"),
            Event.accepted_at <= now - timedelta(days=30),
        )
        .exists()
    )
    unresolved_request = (
        select(Request.id)
        .where(
            Request.origin_ref == Origin.origin_ref,
            Request.snapshots_cleared_at.is_(None),
        )
        .exists()
    )
    uncleared_request = (
        select(Request.id)
        .where(
            Request.run_id == Event.run_id,
            Request.project_id == Event.project_id,
            Request.snapshots_cleared_at.is_(None),
        )
        .exists()
    )
    queries = {
        "expired_snapshots": select(Request.id)
        .where(Request.snapshots_cleared_at.is_(None), terminal)
        .order_by(Request.created_at),
        "expired_details": select(Event.event_id)
        .where(Event.detail_expires_at <= now, Event.details_cleared_at.is_(None))
        .order_by(Event.detail_expires_at),
        "expired_tombstones": select(Event.event_id)
        .where(Event.dedup_expires_at <= now, ~uncleared_request)
        .order_by(Event.dedup_expires_at),
        "expired_origins": select(Origin.origin_ref)
        .where(
            Origin.state.in_(("completed", "deleted")),
            Origin.updated_at <= now - timedelta(days=90),
            ~select(Event.event_id)
            .where(Event.origin_ref == Origin.origin_ref)
            .exists(),
            ~unresolved_request,
        )
        .order_by(Origin.updated_at),
    }
    report = {key: 0 for key in queries}
    with maintenance_lock(factory, 74013002) as acquired:
        if not acquired:
            return {**report, "skipped": "maintenance_busy"}
        for key, query in queries.items():
            if time.monotonic() >= deadline:
                report["budget_exhausted"] = True
                break
            with factory.begin() as session:
                if session.bind.dialect.name == "postgresql":
                    session.execute(text("SET LOCAL lock_timeout='500ms'"))
                    session.execute(text("SET LOCAL statement_timeout='5s'"))
                query = query.limit(limit)
                if apply:
                    query = query.with_for_update(skip_locked=True)
                ids = list(session.scalars(query))
                report[key] = len(ids)
                if not apply or not ids:
                    continue
                if key == "expired_snapshots":
                    session.execute(
                        update(Request)
                        .where(Request.id.in_(ids))
                        .values(
                            upstream_body=None,
                            upstream_auth_snapshot=None,
                            context_snapshot={},
                            config_snapshot={},
                            snapshots_cleared_at=now,
                        )
                    )
                elif key == "expired_details":
                    session.execute(delete(Receipt).where(Receipt.event_id.in_(ids)))
                    session.execute(
                        update(Event)
                        .where(Event.event_id.in_(ids))
                        .values(
                            payload={},
                            reason_code=None,
                            model_error_code=None,
                            details_cleared_at=now,
                        )
                    )
                elif key == "expired_tombstones":
                    session.execute(delete(Receipt).where(Receipt.event_id.in_(ids)))
                    session.execute(delete(Event).where(Event.event_id.in_(ids)))
                else:
                    session.execute(delete(Origin).where(Origin.origin_ref.in_(ids)))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--budget-seconds", type=int, default=30)
    parser.add_argument("--register-retention", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("Platform database is required")
    engine = build_engine(settings.database_url)
    try:
        factory = build_session_factory(engine)
        report = maintain(
            factory,
            apply=args.apply,
            limit=args.limit,
            budget_seconds=args.budget_seconds,
        )
        if args.register_retention:
            report["retention_registration"] = register_missing(
                factory,
                settings,
                apply=args.apply,
                limit=args.limit,
                budget_seconds=args.budget_seconds,
            )
        print(json.dumps(report))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
