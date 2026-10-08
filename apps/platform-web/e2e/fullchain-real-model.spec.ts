import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../../docs/projects/20261007-agent-usage-cost-governance/screenshots",
);

test.describe("Full-Chain Real Model End-to-End Governance", () => {
  test.setTimeout(120000); // 真实大模型调用，留出充足的 2 分钟超时

  test("05-真实大模型全链路调用与用量成本展示闭环", async ({ page }) => {
    // 监听关键日志
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        console.error(`[Browser Error]: ${msg.text()}`);
      }
    });

    await page.setViewportSize({ width: 1440, height: 900 });

    // 1. 登录管理员账号
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    const submitBtn = page.locator('button[type="submit"]');
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // 2. 等待进入主工作台
    await page.waitForURL(/\/workspace/, { timeout: 15000 });

    // 3. 导航至真实 Chat 页面
    const projectId = "5a5b7239-43e3-40e6-bba3-e64d96057607";
    await page.goto(`/workspace/projects/${projectId}/chat`);
    await page.waitForLoadState("networkidle");

    // 4. 点击“新建会话”开启干净回合
    const newThreadBtn = page.locator('button:has-text("新建会话")').first();
    if (await newThreadBtn.isVisible({ timeout: 3000 })) {
      await newThreadBtn.click();
      await page.waitForTimeout(1000);
    }

    // 若处于欢迎选择页，选择 dearflow_agent
    const selectAgentBtn = page
      .locator('button:has-text("选择智能体")')
      .first();
    if (await selectAgentBtn.isVisible({ timeout: 2000 })) {
      await selectAgentBtn.click();
      await page.waitForTimeout(500);
      const dearflowOption = page
        .locator('button:has-text("dearflow_agent")')
        .first();
      if (await dearflowOption.isVisible()) {
        await dearflowOption.click();
        await page.waitForTimeout(500);
      }
    }

    // 5. 显式选择已配置真实费率的模型：百炼 · qwen-plus 或 deepseek-v4-flash
    const modelSelectorBtn = page
      .locator(
        'button[aria-label="选择对话运行模型"], button[title="选择对话运行模型"]',
      )
      .first();
    if (await modelSelectorBtn.isVisible({ timeout: 3000 })) {
      await modelSelectorBtn.click();
      await page.waitForTimeout(500);
      const targetModelOption = page
        .locator(
          'div[role="button"]:has-text("百炼 · qwen-plus"), div[role="button"]:has-text("deepseek-v4-flash")',
        )
        .first();
      if (await targetModelOption.isVisible({ timeout: 2000 })) {
        console.log("切换到已配置真实费率的模型...");
        await targetModelOption.click();
        await page.waitForTimeout(500);
      } else {
        // 如果没找到特定模型，按 Escape 关闭选择面板
        await page.keyboard.press("Escape");
      }
    }

    // 定位输入框
    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 15000 });

    // 截图记录提问前状态
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "05-before-send.png"),
      fullPage: true,
    });

    // 6. 向真实模型发起提问
    const promptText = "请仅用一句话回答：1加1等于几？";
    await textarea.fill(promptText);
    await textarea.press("Enter");

    // 7. 等待真实大模型开始流式输出并结束运行
    console.log("等待真实大模型响应与 Run 终态收敛...");

    // 等待至少一条包含回答的 markdown 内容渲染出现
    await page.locator(".pw-markdown").first().waitFor({
      timeout: 60000,
    });

    // 关键：等待大模型流式生成彻底收尾（停止生成按钮彻底从 DOM 移除）
    console.log("等待大模型流式输出收敛与 Run 终态落库...");
    const stopGenBtn = page
      .locator('button[title="停止生成"], button:has-text("停止生成")')
      .first();
    if (await stopGenBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await stopGenBtn
        .waitFor({ state: "detached", timeout: 45000 })
        .catch(() => {});
    }

    // 稍等 4 秒确保后端 RunUsage 完成持久化和最终收尾
    await page.waitForTimeout(4000);

    // 截图记录真实模型回答完成态
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "06-chat-answered.png"),
      fullPage: true,
    });

    // 8. 切换至轨迹排障视图 (TrajectoryView)
    const trajectoryTabBtn = page.locator('button:has-text("轨迹")').first();
    await expect(trajectoryTabBtn).toBeVisible({ timeout: 10000 });
    await trajectoryTabBtn.click();
    await page.waitForTimeout(1000);

    // 9. 打开“用量与成本”独立面板
    const usageBtn = page
      .locator(
        '[data-testid="toggle-usage-btn"], button:has-text("用量与成本")',
      )
      .first();
    await expect(usageBtn).toBeVisible({ timeout: 10000 });
    await usageBtn.click();

    // 10. 刷新用量面板拉取终态持久化结果
    const refreshBtn = page.locator('[data-testid="refresh-usage-btn"]');
    if (await refreshBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await refreshBtn.click();
      await page.waitForTimeout(2000);
    }

    // 11. 验证 RunUsage 真实用量展示
    const usagePanel = page.locator('[data-testid="run-usage-panel"]');
    await expect(usagePanel).toBeVisible({ timeout: 10000 });

    // 验证核心组件与 open-swe 风格运行水位仪表
    const meter = page.locator('[data-testid="context-meter-card"]');
    await expect(meter).toBeVisible();
    await expect(meter).toContainText("运行水位 (Usage Meter)");

    await expect(usagePanel).toContainText("Run 估算成本 (USD)");
    await expect(usagePanel).toContainText("Token 消耗明细");

    // 12. 截取全链路真实大模型用量与成本最终验收截图
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "07-fullchain-real-model-usage.png"),
      fullPage: true,
    });

    console.log("全链路真实大模型自动化闭环验收完成！");
  });
});
