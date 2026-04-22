from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.platform_config.infra.sqlalchemy.models import PlatformConfigEntryRecord


class SqlAlchemyPlatformConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_json(self, key: str) -> dict | None:
        stmt = select(PlatformConfigEntryRecord).where(PlatformConfigEntryRecord.key == key)
        row = self.session.scalar(stmt)
        return dict(row.value_json) if row is not None and isinstance(row.value_json, dict) else None

    def upsert_json(self, *, key: str, value: dict, updated_by: str | None) -> PlatformConfigEntryRecord:
        stmt = select(PlatformConfigEntryRecord).where(PlatformConfigEntryRecord.key == key)
        row = self.session.scalar(stmt)
        if row is None:
            row = PlatformConfigEntryRecord(key=key)
            self.session.add(row)
        row.value_json = dict(value)
        row.updated_by = updated_by
        self.session.flush()
        return row
