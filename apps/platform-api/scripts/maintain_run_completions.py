"""Explicit completion retention maintenance; preview by default."""

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update

from platform_api.config import load_settings
from platform_api.core.db import build_engine, build_session_factory
from platform_api.modules.runtime_gateway.infra.sqlalchemy.completion_repository import (
    Event,
    Receipt,
)


def maintain(factory, *, apply=False, now=None):
    now = now or datetime.now(UTC)
    with factory.begin() as session:
        expired = select(Event.event_id).where(Event.detail_expires_at <= now)
        report = {
            "expired_details": session.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.detail_expires_at <= now)
            ),
            "expired_tombstones": session.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.dedup_expires_at <= now)
            ),
        }
        if apply:
            session.execute(delete(Receipt).where(Receipt.event_id.in_(expired)))
            session.execute(
                update(Event)
                .where(Event.detail_expires_at <= now)
                .values(
                    payload={},
                    reason_code=None,
                    model_error_code=None,
                )
            )
            session.execute(delete(Event).where(Event.dedup_expires_at <= now))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("Platform database is required")
    engine = build_engine(settings.database_url)
    try:
        print(json.dumps(maintain(build_session_factory(engine), apply=args.apply)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
