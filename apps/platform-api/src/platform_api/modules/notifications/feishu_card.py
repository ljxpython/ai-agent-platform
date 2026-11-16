from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def generate_feishu_sign(secret: str, timestamp: str) -> str:
    """生成飞书自定义机器人安全签名 (HMAC-SHA256)."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


class FeishuCardRenderer:
    """飞书富文本交互卡片 (Interactive Card) 模板渲染器."""

    LEVEL_TEMPLATE_MAP = {
        "info": "blue",
        "warning": "orange",
        "error": "carmine",
        "critical": "red",
        "resolved": "green",
    }

    LEVEL_ICON_MAP = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨",
        "resolved": "🟢",
    }

    @classmethod
    def render_card(
        cls,
        title: str,
        summary: str,
        level: str = "info",
        fields: list[tuple[str, str]] | None = None,
        action_url: str | None = None,
        action_button_text: str = "🔍 查看详情 / 轨迹",
        extra_content: str | None = None,
    ) -> dict[str, Any]:
        """构建飞书 Interactive Card JSON 结构."""
        template_color = cls.LEVEL_TEMPLATE_MAP.get(level.lower(), "blue")
        icon = cls.LEVEL_ICON_MAP.get(level.lower(), "📢")
        header_title = f"{icon} {title}"

        elements: list[dict[str, Any]] = []

        # 1. 核心摘要描述
        if summary:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**摘要：** {summary}",
                    },
                }
            )

        # 2. 键值对表格字段 (两列紧凑排列)
        if fields:
            lark_fields = [
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{label}：** {val}",
                    },
                }
                for label, val in fields
            ]
            elements.append(
                {
                    "tag": "div",
                    "fields": lark_fields,
                }
            )

        # 3. 额外说明文本（如有）
        if extra_content:
            elements.append(
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": extra_content,
                    },
                }
            )

        # 4. 可操作 Action 按钮（若提供了跳转链接）
        if action_url:
            elements.append({"tag": "hr"})
            elements.append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": action_button_text,
                            },
                            "type": "primary"
                            if level in ("critical", "error")
                            else "default",
                            "url": action_url,
                        }
                    ],
                }
            )

        # 5. 底部时间戳与品牌标识
        elements.append(
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"EvalFlow 智能体平台 · {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    }
                ],
            }
        )

        return {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": header_title,
                },
                "template": template_color,
            },
            "elements": elements,
        }


class FeishuBotClient:
    """飞书群自定义机器人异步客户端."""

    def __init__(self, timeout: float = 3.5) -> None:
        self.timeout = timeout

    async def send_card(
        self,
        webhook_url: str,
        card: dict[str, Any],
        secret: str | None = None,
    ) -> tuple[bool, str]:
        """向飞书 Webhook 发送交互卡片."""
        payload: dict[str, Any] = {
            "msg_type": "interactive",
            "card": card,
        }

        if secret:
            timestamp = str(int(time.time()))
            sign = generate_feishu_sign(secret, timestamp)
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(webhook_url, json=payload)
                data = resp.json()
                if resp.status_code == 200 and data.get("code") == 0:
                    return True, "发送成功"
                error_msg = data.get("msg") or f"HTTP {resp.status_code}: {resp.text}"
                logger.warning("飞书卡片发送失败: %s", error_msg)
                return False, error_msg
        except Exception as exc:
            logger.error("飞书 Webhook 网络请求异常: %s", exc)
            return False, f"请求异常: {exc}"
