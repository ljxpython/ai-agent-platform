from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.identity.application.ports import (
    StoredRefreshToken,
    StoredUser,
)
from app.modules.identity.infra.sqlalchemy.models import RefreshTokenRecord, UserRecord


def _to_user(record: UserRecord) -> StoredUser:
    return StoredUser(
        id=record.id,
        username=record.username,
        external_subject=record.external_subject,
        email=record.email,
        status=record.status,
        password_hash=record.password_hash,
        is_super_admin=record.is_super_admin,
    )


def _to_refresh_token(record: RefreshTokenRecord) -> StoredRefreshToken:
    return StoredRefreshToken(
        token_id=record.token_id,
        user_id=record.user_id,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
    )


class SqlAlchemyIdentityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user_by_username(self, username: str) -> StoredUser | None:
        stmt = select(UserRecord).where(UserRecord.username == username)
        record = self.session.scalar(stmt)
        return _to_user(record) if record is not None else None

    def get_user_by_id(self, user_id: UUID) -> StoredUser | None:
        record = self.session.get(UserRecord, user_id)
        return _to_user(record) if record is not None else None

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        external_subject: str,
        email: str | None,
        is_super_admin: bool,
    ) -> StoredUser:
        record = UserRecord(
            username=username,
            password_hash=password_hash,
            external_subject=external_subject,
            email=email,
            status="active",
            is_super_admin=is_super_admin,
        )
        self.session.add(record)
        self.session.flush()
        return _to_user(record)

    def count_super_admins(self) -> int:
        stmt = (
            select(func.count())
            .select_from(UserRecord)
            .where(
                UserRecord.is_super_admin.is_(True),
                UserRecord.status == "active",
            )
        )
        return int(self.session.scalar(stmt) or 0)

    def get_refresh_token(self, token_id: str) -> StoredRefreshToken | None:
        stmt = select(RefreshTokenRecord).where(RefreshTokenRecord.token_id == token_id)
        record = self.session.scalar(stmt)
        return _to_refresh_token(record) if record is not None else None

    def create_refresh_token(
        self,
        *,
        user_id: UUID,
        token_id: str,
        expires_at: datetime,
    ) -> StoredRefreshToken:
        record = RefreshTokenRecord(
            user_id=user_id,
            token_id=token_id,
            expires_at=expires_at,
        )
        self.session.add(record)
        self.session.flush()
        return _to_refresh_token(record)

    def revoke_refresh_token(self, token_id: str) -> None:
        stmt = select(RefreshTokenRecord).where(RefreshTokenRecord.token_id == token_id)
        record = self.session.scalar(stmt)
        if record is None:
            return
        if record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            self.session.flush()

    def revoke_all_refresh_tokens_for_user(self, user_id: UUID) -> int:
        stmt = select(RefreshTokenRecord).where(
            RefreshTokenRecord.user_id == user_id,
            RefreshTokenRecord.revoked_at.is_(None),
        )
        now = datetime.now(timezone.utc)
        changed = 0
        for record in self.session.scalars(stmt).all():
            record.revoked_at = now
            changed += 1
        if changed:
            self.session.flush()
        return changed

    def update_user_password_hash(self, user_id: UUID, password_hash: str) -> None:
        record = self.session.get(UserRecord, user_id)
        if record is None:
            return
        record.password_hash = password_hash
        self.session.flush()

    def update_user_profile(
        self,
        user_id: UUID,
        *,
        username: str,
        email: str | None,
    ) -> StoredUser | None:
        record = self.session.get(UserRecord, user_id)
        if record is None:
            return None
        record.username = username
        record.email = email
        self.session.flush()
        return _to_user(record)

    def reconcile_bootstrap_admin(
        self,
        *,
        username: str,
        password_hash: str,
    ) -> str | None:
        stmt = select(UserRecord).where(UserRecord.username == username)
        record = self.session.scalar(stmt)
        if record is None:
            if self.count_super_admins() > 0:
                return None
            self.create_user(
                username=username,
                password_hash=password_hash,
                external_subject=username,
                email=None,
                is_super_admin=True,
            )
            return "created"

        changed = False
        if record.status != "active":
            record.status = "active"
            changed = True
        if not record.is_super_admin:
            record.is_super_admin = True
            changed = True
        if not record.password_hash:
            record.password_hash = password_hash
            changed = True
        if changed:
            self.session.flush()
            return "reconciled"
        return None
