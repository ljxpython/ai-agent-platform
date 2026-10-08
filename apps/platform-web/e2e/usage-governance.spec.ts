import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const fixturePath = path.resolve(
  __dirname,
  "../../../docs/projects/20261007-agent-usage-cost-governance/fixtures/usage-v1.json",
);
const usageFixtures = JSON.parse(fs.readFileSync(fixturePath, "utf-8"));

const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../../docs/projects/20261007-agent-usage-cost-governance/screenshots",
);

test.describe("Agent Token & Cost Governance E2E", () => {
  const baseRunComplete = {
    ...(usageFixtures as any).samples.run_complete_page1,
    run_id: "run-demo-1",
    thread_id: "thread-demo-1",
  };
  const baseThreadComplete = {
    ...(usageFixtures as any).samples.thread_complete,
    thread_id: "thread-demo-1",
  };

  test.beforeEach(async ({ page }) => {
    page.on("console", (msg) =>
      console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`),
    );
    page.on("pageerror", (err) =>
      console.error(`[Browser PageError]: ${err.message}`),
    );
  });

  test("01-完整 Run 用量与成本展示及 open-swe 水位仪表", async ({ page }) => {
    // 拦截 mock API
    await page.route(
      "**/api/langgraph/threads/thread-demo-1/runs/run-demo-1/usage*",
      (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(baseRunComplete),
        });
      },
    );

    await page.route(
      "**/api/langgraph/threads/thread-demo-1/usage*",
      (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(baseThreadComplete),
        });
      },
    );

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/usage-fixture.html");

    // 验证常驻入口
    const usageBtn = page.locator('[data-testid="toggle-usage-btn"]');
    await expect(usageBtn).toBeVisible();

    // 点击打开面板
    await usageBtn.click();

    // 验证 RunUsage 面板
    const panel = page.locator('[data-testid="run-usage-panel"]');
    await expect(panel).toBeVisible();

    // 验证 open-swe 运行水位仪表
    const meter = page.locator('[data-testid="context-meter-card"]');
    await expect(meter).toBeVisible();
    await expect(meter).toContainText("运行水位 (Usage Meter)");

    // 验证成本与 Token 明细
    await expect(panel).toContainText("Run 估算成本 (USD)");
    await expect(panel).toContainText("Token 消耗明细");
    await expect(panel).toContainText("会话累计已采集汇总");

    // 验证调用明细列表
    const calls = page.locator('[data-testid="usage-call-item"]');
    await expect(calls).toHaveCount(baseRunComplete.calls.items.length);

    // 截取全屏或面板截图
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "01-run-usage-complete.png"),
      fullPage: true,
    });
  });

  test("02-服务端截断告警卡片展示", async ({ page }) => {
    const truncatedRun = {
      ...baseRunComplete,
      truncated: true,
    };

    await page.route(
      "**/api/langgraph/threads/thread-demo-1/runs/run-demo-1/usage*",
      (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(truncatedRun),
        });
      },
    );

    await page.route(
      "**/api/langgraph/threads/thread-demo-1/usage*",
      (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(baseThreadComplete),
        });
      },
    );

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/usage-fixture.html");

    await page.locator('[data-testid="toggle-usage-btn"]').click();

    const alert = page.locator('[data-testid="usage-truncated-alert"]');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("用量数据已受限截断");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "02-run-usage-truncated.png"),
      fullPage: true,
    });
  });

  test("03-模型价格配置表单与可逆清空保护", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/usage-fixture.html");

    // 切换到编辑器 Tab
    await page.locator('[data-testid="tab-editor-btn"]').click();

    const pricingSection = page.locator(
      '[data-testid="model-pricing-section"]',
    );
    await expect(pricingSection).toBeVisible();
    await expect(pricingSection).toContainText(
      "模型费率配置 (USD / 百万 Token)",
    );

    // 测试 Decimal 规整 (.5 -> 0.5)
    const inputField = pricingSection.locator('input[placeholder="如 2.0"]');
    await inputField.fill(".5");
    await inputField.blur();
    await expect(inputField).toHaveValue("0.5");

    // 测试清空与撤销
    const clearBtn = page.locator('[data-testid="clear-pricing-btn"]');
    await clearBtn.click();

    const banner = page.locator('[data-testid="pricing-cleared-banner"]');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(
      "费率已标记待清空，保存后将移除该模型的价格配置",
    );

    // 截图清空待生效状态
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "03-model-pricing-editor.png"),
      fullPage: true,
    });

    // 撤销恢复
    const restoreBtn = page.locator('[data-testid="restore-pricing-btn"]');
    await restoreBtn.click();
    await expect(banner).toBeHidden();
    await expect(inputField).toHaveValue("3.0000000000");
  });

  test("04-模型详情弹窗 6 项费率完整展示", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/usage-fixture.html");

    // 切换到详情弹窗 Tab
    await page.locator('[data-testid="tab-dialog-btn"]').click();

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("用量费率配置");
    await expect(dialog).toContainText("In: $3.0000000000");
    await expect(dialog).toContainText("Out: $15.0000000000");
    await expect(dialog).toContainText("CacheRead: $0.3000000000");
    await expect(dialog).toContainText("CacheWrite: $3.7500000000");
    await expect(dialog).toContainText("Write5m: $3.7500000000");
    await expect(dialog).toContainText("Write1h: $6.0000000000");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "04-model-pricing-detail-dialog.png"),
      fullPage: true,
    });
  });
});
