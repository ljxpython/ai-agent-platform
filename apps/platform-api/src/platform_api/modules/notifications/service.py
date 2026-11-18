from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import apprise

from platform_api.modules.notifications.alert_governance import (
    AlertGovernanceEngine,
)
from platform_api.modules.notifications.feishu_card import (
    FeishuBotClient,
    FeishuCardRenderer,
)
from platform_api.modules.notifications.models import (
    NotificationChannelRecord,
    NotificationRecord,
)
from platform_api.modules.notifications.repository import (
    SqlAlchemyNotificationsRepository,
)
from platform_api.modules.notifications.schemas import (
    AlertIncomingPayload,
    CreateChannelRequest,
    NotificationCategory,
    NotificationItem,
    NotificationLevel,
    NotificationPage,
    NotificationStatus,
    TestChannelResponse,
    UpdateChannelRequest,
)

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        repository: SqlAlchemyNotificationsRepository,
        governance_engine: AlertGovernanceEngine | None = None,
        feishu_client: FeishuBotClient | None = None,
    ) -> None:
        self.repo = repository
        self.governance = governance_engine or AlertGovernanceEngine()
        self.feishu_client = feishu_client or FeishuBotClient()

    # --- 站内信业务 ---

    def create_notification(
        self,
        title: str,
        content: str,
        level: NotificationLevel = NotificationLevel.INFO,
        category: NotificationCategory = NotificationCategory.SYSTEM,
        recipient_user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        action_url: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> NotificationRecord:
        return self.repo.create_notification(
            title=title,
            content=content,
            level=level.value,
            category=category.value,
            recipient_user_id=recipient_user_id,
            project_id=project_id,
            action_url=action_url,
            extra_metadata=extra_metadata,
        )

    def list_notifications(
        self,
        recipient_user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        status: NotificationStatus | None = None,
        level: NotificationLevel | None = None,
        category: NotificationCategory | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> NotificationPage:
        records, total, unread_count = self.repo.list_notifications(
            recipient_user_id=recipient_user_id,
            project_id=project_id,
            status=status.value if status else None,
            level=level.value if level else None,
            category=category.value if category else None,
            limit=limit,
            offset=offset,
        )
        items = [
            NotificationItem(
                id=r.id,
                recipient_user_id=r.recipient_user_id,
                project_id=r.project_id,
                title=r.title,
                content=r.content,
                level=NotificationLevel(r.level),
                category=NotificationCategory(r.category),
                status=NotificationStatus(r.status),
                action_url=r.action_url,
                extra_metadata=r.extra_metadata or {},
                created_at=r.created_at,
                read_at=r.read_at,
            )
            for r in records
        ]
        return NotificationPage(
            items=items,
            total=total,
            unread_count=unread_count,
            limit=limit,
            offset=offset,
        )

    def get_unread_count(self, recipient_user_id: uuid.UUID | None = None) -> int:
        return self.repo.get_unread_count(recipient_user_id)

    def mark_as_read(
        self, notification_id: uuid.UUID, recipient_user_id: uuid.UUID | None = None
    ) -> bool:
        return self.repo.mark_as_read(notification_id, recipient_user_id)

    def mark_all_read(self, recipient_user_id: uuid.UUID | None = None) -> int:
        return self.repo.mark_all_read(recipient_user_id)

    # --- 渠道管理业务 ---

    def create_channel(self, req: CreateChannelRequest) -> NotificationChannelRecord:
        return self.repo.create_channel(
            name=req.name,
            channel_type=req.channel_type.value,
            endpoint_url=req.endpoint_url,
            secret_token=req.secret_token,
            project_ids=req.project_ids,
            is_enabled=req.is_enabled,
            subscribed_events=req.subscribed_events,
        )

    def list_channels(
        self,
        project_id: uuid.UUID | None = None,
        enabled_only: bool = False,
    ) -> list[NotificationChannelRecord]:
        return self.repo.list_channels(project_id=project_id, enabled_only=enabled_only)

    def update_channel(
        self, channel_id: uuid.UUID, req: UpdateChannelRequest
    ) -> NotificationChannelRecord | None:
        updates = req.model_dump(exclude_unset=True)
        return self.repo.update_channel(channel_id, **updates)

    def delete_channel(self, channel_id: uuid.UUID) -> bool:
        return self.repo.delete_channel(channel_id)

    async def test_channel(self, channel_id: uuid.UUID) -> TestChannelResponse:
        channel = self.repo.get_channel(channel_id)
        if not channel:
            return TestChannelResponse(
                success=False,
                channel_id=channel_id,
                channel_name="Unknown",
                message="渠道未找到",
            )

        if channel.channel_type == "feishu":
            card = FeishuCardRenderer.render_card(
                title="[连通性测试] 飞书群告警渠道已接通",
                summary="恭喜！你配置的飞书自定义机器人渠道连通性校验通过，后续告警将实时推送至本群。",
                level="info",
                fields=[
                    ("渠道名称", channel.name),
                    ("渠道标识", str(channel.id)[:8]),
                    ("状态", "正常就绪"),
                ],
                action_button_text="✅ 收到确认",
            )
            success, msg = await self.feishu_client.send_card(
                channel.endpoint_url, card, secret=channel.secret_token
            )
            return TestChannelResponse(
                success=success,
                channel_id=channel.id,
                channel_name=channel.name,
                message=msg,
            )

        # 其他渠道使用 Apprise 进行通用投递测试
        try:
            ap_obj = apprise.Apprise()
            ap_obj.add(channel.endpoint_url)
            sent = ap_obj.notify(
                title=f"[平台测试] {channel.name}",
                body="这是一条由智能体平台发起的通知渠道连通性测试消息。",
            )
            return TestChannelResponse(
                success=bool(sent),
                channel_id=channel.id,
                channel_name=channel.name,
                message="投递成功" if sent else "Apprise 投递失败，请检查配置 URL",
            )
        except Exception as exc:
            return TestChannelResponse(
                success=False,
                channel_id=channel.id,
                channel_name=channel.name,
                message=f"测试异常: {exc}",
            )

    def _normalize_alert_action_url(
        self, action_url: str | None, details: dict[str, Any]
    ) -> str:
        """规范化告警动作链接，彻底杜绝无 thread 的空对话跳转。"""
        thread_id = details.get("thread_id") or details.get("threadId")
        if thread_id:
            return f"/workspace/chat/{thread_id}"

        # 检查是否为通用空白 chat 路径或空 URL
        is_generic_chat = False
        if action_url:
            cleaned = action_url.strip().rstrip("/")
            if cleaned.endswith("/workspace/chat") or cleaned.endswith("/chat"):
                is_generic_chat = True

        if not action_url or is_generic_chat:
            trace_id = details.get("trace_id") or details.get("traceId")
            if trace_id:
                return f"/workspace/trace-diagnostics?traceId={trace_id}"
            return "/workspace/trace-diagnostics"

        return action_url

    @staticmethod
    def _is_event_subscribed(
        subscribed_events: list[str] | None, alert_type: str
    ) -> bool:
        """检查渠道是否订阅了指定类型的告警。"""
        if not subscribed_events or "*" in subscribed_events:
            return True
        for evt in subscribed_events:
            if evt == alert_type:
                return True
            if evt.endswith("*") and alert_type.startswith(evt[:-1]):
                return True
            if alert_type.startswith(evt + "_") or evt.startswith(alert_type + "_"):
                return True
            # 大类聚合匹配 (如 eval_degraded 订阅能接收 eval_score_drop)
            if ("eval" in evt and "eval" in alert_type) or (
                "agent" in evt and "agent" in alert_type
            ):
                return True
            if ("budget" in evt and "budget" in alert_type) or (
                "model" in evt and "model" in alert_type
            ):
                return True
        return False

    # --- 统一告警接入与治理分发 (Task 3 核心) ---

    async def process_incoming_alert(
        self, payload: AlertIncomingPayload
    ) -> tuple[bool, str, int]:
        """处理进入的告警。

        返回: (dispatched, fingerprint, occurrence_count)
        """
        fingerprint, should_dispatch, occurrences = self.governance.evaluate(
            source=payload.source,
            alert_type=payload.alert_type,
            target_id=payload.target_id,
        )

        # 1. 记录或累加告警流水
        self.repo.record_alert_event(
            fingerprint=fingerprint,
            source=payload.source,
            alert_type=payload.alert_type,
            target_id=payload.target_id,
            level=payload.level.value,
            summary=payload.summary,
            details=payload.details,
        )

        resolved_action_url = self._normalize_alert_action_url(
            payload.action_url, payload.details
        )

        # 2. 写入一条站内信 (所有进入的事件均留痕)
        self.create_notification(
            title=f"[{payload.level.value.upper()}] {payload.summary}",
            content=f"来源: {payload.source} | 目标: {payload.target_id} | 累计发生: {occurrences} 次",
            level=payload.level,
            category=NotificationCategory.EVAL
            if "eval" in payload.source
            else NotificationCategory.SYSTEM,
            recipient_user_id=payload.recipient_user_id,
            project_id=payload.project_id,
            action_url=resolved_action_url,
            extra_metadata={
                "fingerprint": fingerprint,
                "occurrences": occurrences,
                **payload.details,
            },
        )

        # 3. 如果在冷却期内被抑制，则不向外部群发刷屏
        if not should_dispatch:
            logger.info(
                "告警已在冷却期抑制: fingerprint=%s, count=%d",
                fingerprint,
                occurrences,
            )
            return False, fingerprint, occurrences

        # 4. 触发外部多渠道分发 (查询该项目或全局启用的渠道)
        channels = self.list_channels(project_id=payload.project_id, enabled_only=True)
        if not channels:
            logger.warning("未配置启用的通知渠道，告警仅保留站内信: %s", fingerprint)
            return False, fingerprint, occurrences

        tasks = []
        for ch in channels:
            # 严格依据渠道订阅事件过滤：非订阅事件不予推送外部群
            if not self._is_event_subscribed(ch.subscribed_events, payload.alert_type):
                logger.info(
                    "渠道 %s 未订阅告警类别 %s，跳过外部推送",
                    ch.name,
                    payload.alert_type,
                )
                continue

            tasks.append(
                self._dispatch_to_channel(ch, payload, occurrences, resolved_action_url)
            )
        await asyncio.gather(*tasks, return_exceptions=True)

        return True, fingerprint, occurrences

    async def _dispatch_to_channel(
        self,
        channel: NotificationChannelRecord,
        payload: AlertIncomingPayload,
        occurrences: int,
        action_url: str | None = None,
    ) -> None:
        target_action_url = action_url or payload.action_url
        if channel.channel_type == "feishu":
            fields = [
                ("来源", f"`{payload.source}`"),
                ("类型", f"`{payload.alert_type}`"),
                ("目标对象", f"`{payload.target_id}`"),
                ("当前级别", payload.level.value.upper()),
            ]
            if payload.project_id:
                fields.append(("所属项目", f"`{str(payload.project_id)[:8]}`"))
            if occurrences > 1:
                fields.append(("累计触发", f"{occurrences} 次"))

            card = FeishuCardRenderer.render_card(
                title=f"[{payload.level.value.upper()}] {payload.summary}",
                summary=payload.summary,
                level=payload.level.value,
                fields=fields,
                action_url=target_action_url,
                action_button_text="🔍 查看详情 / 排障",
            )
            success, msg = await self.feishu_client.send_card(
                channel.endpoint_url, card, secret=channel.secret_token
            )
            if not success:
                logger.error("分发至飞书渠道 %s 失败: %s", channel.name, msg)
        else:
            try:
                ap_obj = apprise.Apprise()
                ap_obj.add(channel.endpoint_url)
                ap_obj.notify(
                    title=f"[{payload.level.value.upper()}] {payload.summary}",
                    body=f"来源: {payload.source}\n类型: {payload.alert_type}\n目标: {payload.target_id}\n详情: {payload.details}",
                )
            except Exception as exc:
                logger.error("Apprise 渠道 %s 分发异常: %s", channel.name, exc)

    async def resolve_alert(self, source: str, alert_type: str, target_id: str) -> bool:
        """告警自愈与发送恢复通知."""
        stats = self.governance.get_and_clear_resolve_stats(
            source, alert_type, target_id
        )
        active = self.repo.resolve_alert(
            self.governance.evaluate(source, alert_type, target_id)[0]
        )
        if not active:
            return False

        duration_sec = 0.0
        total_occurrences = 1
        if stats:
            _, duration_sec, total_occurrences = stats

        channels = self.list_channels(enabled_only=True)
        title = f"[已恢复] {active.summary}"
        duration_str = (
            f"{int(duration_sec // 60)} 分 {int(duration_sec % 60)} 秒"
            if duration_sec > 60
            else f"{int(duration_sec)} 秒"
        )

        for ch in channels:
            if ch.channel_type == "feishu":
                card = FeishuCardRenderer.render_card(
                    title=title,
                    summary=f"此前触发的异常已恢复正常运行。故障持续时间：{duration_str}，累计触发 {total_occurrences} 次。",
                    level="resolved",
                    fields=[
                        ("来源", f"`{source}`"),
                        ("目标对象", f"`{target_id}`"),
                        ("持续时长", duration_str),
                        ("状态", "🟢 恢复正常"),
                    ],
                )
                await self.feishu_client.send_card(
                    ch.endpoint_url, card, secret=ch.secret_token
                )

        return True
