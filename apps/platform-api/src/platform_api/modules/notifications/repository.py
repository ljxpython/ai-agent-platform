from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from platform_api.modules.notifications.models import (
    AlertEventRecord,
    NotificationChannelRecord,
    NotificationRecord,
)


def _now() -> datetime:
    return datetime.now(UTC)


class SqlAlchemyNotificationsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- 站内信 (Notifications) 操作 ---

    def create_notification(
        self,
        *,
        title: str,
        content: str,
        level: str = "info",
        category: str = "system",
        recipient_user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        action_url: str | None = None,
        extra_metadata: dict | None = None,
    ) -> NotificationRecord:
        record = NotificationRecord(
            title=title,
            content=content,
            level=level,
            category=category,
            recipient_user_id=recipient_user_id,
            project_id=project_id,
            action_url=action_url,
            extra_metadata=extra_metadata or {},
            status="unread",
            created_at=_now(),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def list_notifications(
        self,
        *,
        recipient_user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        status: str | None = None,
        level: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[NotificationRecord], int, int]:
        """返回 (列表, 总数, 未读总数)."""
        base_stmt = select(NotificationRecord)
        if recipient_user_id is not None:
            # 匹配当前用户或全局未指定接收人的广播
            base_stmt = base_stmt.where(
                (NotificationRecord.recipient_user_id == recipient_user_id)
                | (NotificationRecord.recipient_user_id.is_(None))
            )
        if project_id is not None:
            base_stmt = base_stmt.where(
                (NotificationRecord.project_id == project_id)
                | (NotificationRecord.project_id.is_(None))
            )
        if status:
            base_stmt = base_stmt.where(NotificationRecord.status == status)
        if level:
            base_stmt = base_stmt.where(NotificationRecord.level == level)
        if category:
            base_stmt = base_stmt.where(NotificationRecord.category == category)

        # 统计总数
        total = (
            self.session.scalar(select(func.count()).select_from(base_stmt.subquery()))
            or 0
        )

        # 统计未读总数
        unread_stmt = (
            select(func.count())
            .select_from(NotificationRecord)
            .where(NotificationRecord.status == "unread")
        )
        if recipient_user_id is not None:
            unread_stmt = unread_stmt.where(
                (NotificationRecord.recipient_user_id == recipient_user_id)
                | (NotificationRecord.recipient_user_id.is_(None))
            )
        unread_count = self.session.scalar(unread_stmt) or 0

        # 分页列表
        records = list(
            self.session.scalars(
                base_stmt.order_by(desc(NotificationRecord.created_at))
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return records, total, unread_count

    def get_unread_count(self, recipient_user_id: uuid.UUID | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(NotificationRecord)
            .where(NotificationRecord.status == "unread")
        )
        if recipient_user_id is not None:
            stmt = stmt.where(
                (NotificationRecord.recipient_user_id == recipient_user_id)
                | (NotificationRecord.recipient_user_id.is_(None))
            )
        return self.session.scalar(stmt) or 0

    def mark_as_read(
        self, notification_id: uuid.UUID, recipient_user_id: uuid.UUID | None = None
    ) -> bool:
        stmt = (
            update(NotificationRecord)
            .where(NotificationRecord.id == notification_id)
            .values(status="read", read_at=_now())
        )
        if recipient_user_id is not None:
            stmt = stmt.where(
                (NotificationRecord.recipient_user_id == recipient_user_id)
                | (NotificationRecord.recipient_user_id.is_(None))
            )
        result = self.session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)

    def mark_all_read(self, recipient_user_id: uuid.UUID | None = None) -> int:
        stmt = (
            update(NotificationRecord)
            .where(NotificationRecord.status == "unread")
            .values(status="read", read_at=_now())
        )
        if recipient_user_id is not None:
            stmt = stmt.where(
                (NotificationRecord.recipient_user_id == recipient_user_id)
                | (NotificationRecord.recipient_user_id.is_(None))
            )
        result = self.session.execute(stmt)
        return int(result.rowcount or 0)

    # --- 渠道配置 (Notification Channels) 操作 ---

    def create_channel(
        self,
        *,
        name: str,
        channel_type: str,
        endpoint_url: str,
        secret_token: str | None = None,
        project_id: uuid.UUID | None = None,
        is_enabled: bool = True,
        subscribed_events: list[str] | None = None,
    ) -> NotificationChannelRecord:
        record = NotificationChannelRecord(
            name=name,
            channel_type=channel_type,
            endpoint_url=endpoint_url,
            secret_token=secret_token,
            project_id=project_id,
            is_enabled=is_enabled,
            subscribed_events=subscribed_events or [],
            created_at=_now(),
            updated_at=_now(),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_channel(self, channel_id: uuid.UUID) -> NotificationChannelRecord | None:
        return self.session.get(NotificationChannelRecord, channel_id)

    def list_channels(
        self,
        *,
        project_id: uuid.UUID | None = None,
        channel_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[NotificationChannelRecord]:
        stmt = select(NotificationChannelRecord)
        if project_id is not None:
            stmt = stmt.where(
                (NotificationChannelRecord.project_id == project_id)
                | (NotificationChannelRecord.project_id.is_(None))
            )
        if channel_type:
            stmt = stmt.where(NotificationChannelRecord.channel_type == channel_type)
        if enabled_only:
            stmt = stmt.where(NotificationChannelRecord.is_enabled.is_(True))
        return list(
            self.session.scalars(
                stmt.order_by(desc(NotificationChannelRecord.created_at))
            ).all()
        )

    def update_channel(
        self,
        channel_id: uuid.UUID,
        **updates: object,
    ) -> NotificationChannelRecord | None:
        channel = self.get_channel(channel_id)
        if not channel:
            return None
        for k, v in updates.items():
            if v is not None and hasattr(channel, k):
                setattr(channel, k, v)
        channel.updated_at = _now()
        self.session.flush()
        return channel

    def delete_channel(self, channel_id: uuid.UUID) -> bool:
        channel = self.get_channel(channel_id)
        if not channel:
            return False
        self.session.delete(channel)
        self.session.flush()
        return True

    # --- 告警事件 (Alert Events) 与防抖记录 ---

    def get_active_alert(self, fingerprint: str) -> AlertEventRecord | None:
        stmt = (
            select(AlertEventRecord)
            .where(
                AlertEventRecord.fingerprint == fingerprint,
                AlertEventRecord.resolved_at.is_(None),
            )
            .order_by(desc(AlertEventRecord.last_seen_at))
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def record_alert_event(
        self,
        *,
        fingerprint: str,
        source: str,
        alert_type: str,
        target_id: str,
        level: str,
        summary: str,
        details: dict,
    ) -> tuple[AlertEventRecord, bool]:
        """记录告警事件。返回 (record, is_new_or_cooldown_expired)."""
        active = self.get_active_alert(fingerprint)
        now = _now()
        if active:
            active.occurrence_count += 1
            active.last_seen_at = now
            active.summary = summary
            active.details = details
            self.session.flush()
            return active, False

        new_alert = AlertEventRecord(
            fingerprint=fingerprint,
            source=source,
            alert_type=alert_type,
            target_id=target_id,
            level=level,
            summary=summary,
            details=details,
            occurrence_count=1,
            first_seen_at=now,
            last_seen_at=now,
        )
        self.session.add(new_alert)
        self.session.flush()
        return new_alert, True

    def resolve_alert(self, fingerprint: str) -> AlertEventRecord | None:
        active = self.get_active_alert(fingerprint)
        if active:
            active.resolved_at = _now()
            self.session.flush()
        return active
