"""Persistent event reception and per-channel retry without global broadcasts."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import apprise
from sqlalchemy import select

from platform_api.core.errors import ForbiddenError, PlatformApiError
from platform_api.modules.identity.models import (
    UserRecord,
    normalize_user_platform_roles,
)
from platform_api.modules.notifications.feishu_card import (
    FeishuBotClient,
    FeishuCardRenderer,
)
from platform_api.modules.notifications.models import (
    NotificationChannelRecord,
    NotificationRecord,
)
from platform_api.modules.notifications.service import NotificationService
from platform_api.modules.projects.models import ProjectMemberRecord
from platform_api.modules.runtime_policies.domain.budgets import BudgetEvent
from platform_api.modules.runtime_policies.infra.sqlalchemy.budgets import (
    BudgetDeliveryRecord,
    BudgetPolicyRecord,
    BudgetReceiptRecord,
)


def subscribed(channel, project_id):
    scoped = [str(p) for p in channel.project_ids]
    return (
        not scoped or project_id in scoped
    ) and NotificationService._is_event_subscribed(
        channel.subscribed_events, "gateway_budget_exceeded"
    )


def receive(service, session, payload):
    validated = BudgetEvent.model_validate(payload)
    payload = validated.model_dump(mode="json")
    event_id = str(UUID(payload["event_id"]))
    tenant = payload["tenant_id"]
    service._lock(session, tenant)
    existing = session.get(BudgetReceiptRecord, event_id)
    if existing:
        if existing.payload != payload or existing.tenant_id != tenant:
            raise PlatformApiError(
                status_code=409,
                code="budget_event_conflict",
                message="Budget event conflict",
            )
        return
    policy = validated.policy
    source = session.get(BudgetPolicyRecord, str(policy.id))
    if (
        source is None
        or source.tenant_id != tenant
        or source.payload["version"] < policy.version
        or source.payload["created_at"] != payload["policy"]["created_at"]
    ):
        raise ForbiddenError(
            code="budget_event_denied", message="Budget event scope unavailable"
        )
    # Never broadcast a GLOBAL financial amount to every platform user.
    recipients = set()
    for user in session.scalars(
        select(UserRecord).where(UserRecord.status == "active")
    ):
        if "platform_super_admin" in normalize_user_platform_roles(
            user.platform_roles_json, is_super_admin=user.is_super_admin
        ):
            recipients.add(user.id)
    if policy.project_id:
        recipients.update(
            session.scalars(
                select(ProjectMemberRecord.user_id)
                .join(UserRecord, UserRecord.id == ProjectMemberRecord.user_id)
                .where(
                    ProjectMemberRecord.project_id == policy.project_id,
                    ProjectMemberRecord.role.in_(["admin", "project_admin"]),
                    UserRecord.status == "active",
                )
            )
        )
    title = "AI 网关预算已达到上限"
    content = f"已确认费用 {payload['known_spend']} / {policy.budget_amount} USD；{policy.action}；重置 {payload['window_end']}"
    action = (
        f"/workspace/projects/{policy.project_id}/usage?tab=budgets"
        if policy.project_id
        else "/workspace/usage?tab=budgets"
    )
    session.add(BudgetReceiptRecord(id=event_id, tenant_id=tenant, payload=payload))
    for recipient in recipients:
        session.add(
            NotificationRecord(
                id=uuid5(NAMESPACE_URL, f"gateway-budget:{event_id}:{recipient}"),
                recipient_user_id=recipient,
                project_id=policy.project_id,
                title=title,
                content=content,
                category="system",
                level="warning",
                action_url=action,
                extra_metadata={
                    "event_id": event_id,
                    "type": "gateway_budget_exceeded",
                },
            )
        )
    for channel in session.scalars(
        select(NotificationChannelRecord).where(
            NotificationChannelRecord.is_enabled.is_(True)
        )
    ):
        if subscribed(channel, str(policy.project_id) if policy.project_id else None):
            session.add(
                BudgetDeliveryRecord(
                    event_id=event_id,
                    channel_id=str(channel.id),
                    next_attempt_at=datetime.now(UTC),
                )
            )


async def deliver(factory):
    now = datetime.now(UTC)
    with factory.begin() as session:
        rows = session.scalars(
            select(BudgetDeliveryRecord)
            .where(
                BudgetDeliveryRecord.delivered_at.is_(None),
                BudgetDeliveryRecord.next_attempt_at <= now,
            )
            .with_for_update(skip_locked=True)
            .limit(20)
        ).all()
        claimed = []
        for row in rows:
            row.attempts += 1
            row.next_attempt_at = now + timedelta(seconds=30)
            claimed.append((row.event_id, row.channel_id))
    for event_id, channel_id in claimed:
        try:
            with factory() as session:
                channel = session.get(NotificationChannelRecord, UUID(channel_id))
                receipt = session.get(BudgetReceiptRecord, event_id)
                payload = receipt.payload
                project = payload["policy"].get("project_id")
                if (
                    channel is None
                    or not channel.is_enabled
                    or not subscribed(channel, project)
                ):
                    raise ValueError("budget_channel_unavailable")
                endpoint, secret, kind = (
                    channel.endpoint_url,
                    channel.secret_token,
                    channel.channel_type,
                )
            summary = (
                f"AI 网关预算超额；事件 {event_id}；已用 {payload['known_spend']} USD"
            )
            if kind == "feishu":
                card = FeishuCardRenderer.render_card(
                    title="AI 网关预算已达到上限",
                    summary=summary,
                    level="warning",
                    fields=[("事件", event_id)],
                    action_url=None,
                )
                ok, _ = await FeishuBotClient().send_card(endpoint, card, secret=secret)
            else:
                client = apprise.Apprise()
                client.add(endpoint)
                ok = await asyncio.to_thread(
                    client.notify, title="AI 网关预算已达到上限", body=summary
                )
            if not ok:
                raise ValueError("budget_channel_send_failed")
            with factory.begin() as session:
                row = session.get(BudgetDeliveryRecord, (event_id, channel_id))
                row.delivered_at, row.last_error = datetime.now(UTC), None
        except Exception:
            with factory.begin() as session:
                row = session.get(BudgetDeliveryRecord, (event_id, channel_id))
                row.last_error = "budget_channel_delivery_failed"
