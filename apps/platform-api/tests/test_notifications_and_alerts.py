from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from platform_api.core.db import (
    build_engine,
    build_session_factory,
    create_core_tables,
    session_scope,
)
from platform_api.modules.notifications.alert_governance import (
    AlertGovernanceEngine,
)
from platform_api.modules.notifications.feishu_card import (
    FeishuBotClient,
    FeishuCardRenderer,
    generate_feishu_sign,
)
from platform_api.modules.notifications.repository import (
    SqlAlchemyNotificationsRepository,
)
from platform_api.modules.notifications.schemas import (
    AlertIncomingPayload,
    CreateChannelRequest,
    NotificationCategory,
    NotificationLevel,
)
from platform_api.modules.notifications.service import NotificationService


class NotificationsAndAlertsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "test-notifications.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_feishu_card_rendering_and_signature(self) -> None:
        """测试飞书卡片格式生成与签名逻辑."""
        card = FeishuCardRenderer.render_card(
            title="测试告警卡片",
            summary="这是一条测试摘要信息",
            level="critical",
            fields=[("来源", "eval_platform"), ("指标", "Accuracy")],
            action_url="http://localhost:3000/#/test",
            action_button_text="点击排查",
        )
        self.assertEqual(card["header"]["template"], "red")
        self.assertIn("🚨", card["header"]["title"]["content"])
        self.assertEqual(
            len(card["elements"]), 5
        )  # 摘要, 字段表格, 分割线, 按钮, 底部Note

        # 检查签名生成
        sign = generate_feishu_sign(secret="test-secret-key", timestamp="1700000000")
        self.assertIsInstance(sign, str)
        self.assertTrue(len(sign) > 10)

    def test_alert_governance_throttling_cooldown(self) -> None:
        """测试告警防抖治理引擎 (滑动窗口抑制告警风暴)."""
        engine = AlertGovernanceEngine(cooldown_seconds=0.2)
        source = "agent_runtime"
        alert_type = "tool_loop"
        target_id = "run_12345"

        # 1. 第一次触发，应当被允许分发 (should_dispatch = True)
        fp, should_dispatch, count = engine.evaluate(source, alert_type, target_id)
        self.assertTrue(should_dispatch)
        self.assertEqual(count, 1)

        # 2. 连续突发 20 次，应当全被抑制 (should_dispatch = False)
        for expected_count in range(2, 22):
            fp, should_dispatch, count = engine.evaluate(source, alert_type, target_id)
            self.assertFalse(should_dispatch)
            self.assertEqual(count, expected_count)

        # 3. 等待超出冷却期 (0.2s)
        time.sleep(0.25)

        # 4. 再次触发，冷却期已过，应当重新放行并重置计数器
        fp, should_dispatch, count = engine.evaluate(source, alert_type, target_id)
        self.assertTrue(should_dispatch)
        self.assertEqual(count, 1)

    async def test_notification_service_crud_and_dispatch(self) -> None:
        """测试通知与告警综合业务服务."""
        mock_feishu = AsyncMock(spec=FeishuBotClient)
        mock_feishu.send_card.return_value = (True, "ok")

        with session_scope(self._session_factory) as session:
            repo = SqlAlchemyNotificationsRepository(session)
            service = NotificationService(
                repository=repo,
                governance_engine=AlertGovernanceEngine(cooldown_seconds=300.0),
                feishu_client=mock_feishu,
            )

            # 1. 创建站内信
            n = service.create_notification(
                title="系统常规巡检通知",
                content="一切正常",
                level=NotificationLevel.INFO,
                category=NotificationCategory.SYSTEM,
            )
            self.assertIsNotNone(n.id)

            # 2. 查询列表与未读数
            unread_count = service.get_unread_count()
            self.assertEqual(unread_count, 1)

            page = service.list_notifications(limit=10)
            self.assertEqual(page.total, 1)
            self.assertEqual(page.items[0].title, "系统常规巡检通知")

            # 3. 标记为已读
            success = service.mark_as_read(n.id)
            self.assertTrue(success)
            self.assertEqual(service.get_unread_count(), 0)

            # 4. 配置一个飞书通知渠道
            ch = service.create_channel(
                CreateChannelRequest(
                    name="生产告警群",
                    channel_type="feishu",
                    endpoint_url="https://open.feishu.cn/open-apis/bot/v2/hook/mock-hook",
                    is_enabled=True,
                )
            )
            self.assertIsNotNone(ch.id)

            # 5. 模拟接入告警并触发分发
            payload = AlertIncomingPayload(
                source="mlflow_eval",
                alert_type="eval_score_drop",
                target_id="dataset_core_bench",
                level=NotificationLevel.CRITICAL,
                summary="核心大模型评测集得分断崖式下跌 12%",
                action_url="http://localhost:9128/#/experiments",
            )
            dispatched, fingerprint, count = await service.process_incoming_alert(
                payload
            )
            self.assertTrue(dispatched)
            self.assertEqual(count, 1)
            # 验证确实调用了飞书客户端
            mock_feishu.send_card.assert_called_once()

            # 6. 立即再次收到同一告警，应被防抖抑制
            mock_feishu.send_card.reset_mock()
            dispatched2, _, count2 = await service.process_incoming_alert(payload)
            self.assertFalse(dispatched2)
            self.assertEqual(count2, 2)
            mock_feishu.send_card.assert_not_called()

            # 7. 触发告警恢复通知
            resolved = await service.resolve_alert(
                source="mlflow_eval",
                alert_type="eval_score_drop",
                target_id="dataset_core_bench",
            )
            self.assertTrue(resolved)
            mock_feishu.send_card.assert_called_once()
            call_args = mock_feishu.send_card.call_args[0]
            self.assertIn("已恢复", call_args[1]["header"]["title"]["content"])


class NotificationHttpRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from platform_api.main import create_app

        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "test-http.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.database_url = str(self._engine.url)
        settings.auth_required = False  # 简化 HTTP 路由功能检验
        self.app.state.db_session_factory = self._session_factory
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_alert_incoming_and_notification_routes(self) -> None:
        # 1. 发起外部告警上报
        resp = self.client.post(
            "/api/alerts/incoming",
            json={
                "source": "mlflow_eval",
                "alert_type": "quota_429",
                "target_id": "deepseek-v4.1",
                "level": "warning",
                "summary": "DeepSeek API 网关触发 429 限流",
                "details": {"retry_after": 60},
                "action_url": "http://localhost:9128/#/gateway",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["occurrence_count"], 1)

        # 2. 查询站内信未读数
        resp_count = self.client.get("/api/notifications/unread-count")
        self.assertEqual(resp_count.status_code, 200)
        self.assertEqual(resp_count.json()["unread_count"], 1)

        # 3. 查询站内信列表
        resp_list = self.client.get("/api/notifications?limit=10")
        self.assertEqual(resp_list.status_code, 200)
        list_data = resp_list.json()
        self.assertEqual(list_data["total"], 1)
        item_id = list_data["items"][0]["id"]

        # 4. 标记单条已读
        resp_read = self.client.patch(f"/api/notifications/{item_id}/read")
        self.assertEqual(resp_read.status_code, 200)

        # 5. 校验未读数变为 0
        resp_count2 = self.client.get("/api/notifications/unread-count")
        self.assertEqual(resp_count2.json()["unread_count"], 0)

        # 6. 新增通知渠道
        resp_ch = self.client.post(
            "/api/notifications/channels",
            json={
                "name": "飞书应急群",
                "channel_type": "feishu",
                "endpoint_url": "https://open.feishu.cn/open-apis/bot/v2/hook/mock",
                "is_enabled": True,
            },
        )
        self.assertEqual(resp_ch.status_code, 201)
        self.assertIn("id", resp_ch.json())

        # 7. 查询渠道列表
        resp_channels = self.client.get("/api/notifications/channels")
        self.assertEqual(resp_channels.status_code, 200)
        self.assertEqual(len(resp_channels.json()), 1)

        # 8. 告警恢复上报
        resp_resolve = self.client.post(
            "/api/alerts/resolve?source=mlflow_eval&alert_type=quota_429&target_id=deepseek-v4.1"
        )
        self.assertEqual(resp_resolve.status_code, 200)
        self.assertTrue(resp_resolve.json()["resolved"])


if __name__ == "__main__":
    unittest.main()
