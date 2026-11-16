import asyncio
import os
import sys

from platform_api.modules.notifications.feishu_card import (
    FeishuBotClient,
    FeishuCardRenderer,
)

DEFAULT_WEBHOOK = os.environ.get(
    "FEISHU_TEST_WEBHOOK_URL",
    "",
)


async def main():
    webhook_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WEBHOOK
    if not webhook_url:
        print("错误: 请通过参数或 FEISHU_TEST_WEBHOOK_URL 环境变量提供 Webhook 地址")
        sys.exit(1)
    print("🚀 开始向飞书机器人发送交互测试卡片...")
    client = FeishuBotClient()
    card = FeishuCardRenderer.render_card(
        title="[联调通航] EvalFlow & Agent 告警中枢上线就绪",
        summary="恭喜！大模型与智能体全栈监控告警中心已成功连通你的飞书测试群！",
        level="resolved",
        fields=[
            ("监控中枢", "ai-agent-platform"),
            ("评测基座", "mlflow-eval-platform (9128)"),
            ("知识引擎", "LightRAG"),
            ("触达通道", "飞书 Interactive Card"),
            ("防抖状态", "已启用 (5分钟滑动窗口)"),
            ("当前模式", "Worktree 极速验证"),
        ],
        action_url="http://49.233.222.54:9128/#/experiments",
        action_button_text="📊 前往 EvalFlow 评测大盘",
        extra_content="此消息由 `platform-api` 告警哨兵服务自动生成，支持彩色状态条、紧凑字段表格与可点击 DeepLink 按钮。",
    )

    success, msg = await client.send_card(webhook_url, card)
    print(f"发送结果: success={success}, msg={msg}")
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
