import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const fixturePath = path.resolve(
  __dirname,
  "../../../docs/projects/20260913-dearflow-agent/fixtures/token-budget-v1.json",
);
const budgetFixtures = JSON.parse(fs.readFileSync(fixturePath, "utf-8"));

const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../../docs/projects/20260913-dearflow-agent/screenshots",
);

test.describe("Run Token Budget Governance E2E & Real Model Closed-Loop", () => {
  const normalUsage = {
    ...budgetFixtures.samples.normal,
    thread_id: "thread-budget-e2e",
    run_id: "run-normal",
  };
  const exhaustedUsage = {
    ...budgetFixtures.samples.exhausted,
    thread_id: "thread-budget-e2e",
    run_id: "run-exhausted",
  };
  const overCapUsage = {
    ...budgetFixtures.samples.warning_then_natural_final,
    thread_id: "thread-budget-e2e",
    run_id: "run-over-cap",
  };
  const unverifiableUsage = {
    ...budgetFixtures.samples.unverifiable,
    thread_id: "thread-budget-e2e",
    run_id: "run-unverifiable",
  };
  const disabledUsage = {
    ...budgetFixtures.samples.disabled,
    thread_id: "thread-budget-e2e",
    run_id: "run-disabled",
  };

  const threadComplete = {
    thread_id: "thread-budget-e2e",
    run_count: 5,
    calls_total: 10,
    cost_usd_total: "0.0150",
    tokens_total: 120000,
    model_counts: { "deepseek-chat": 10 },
  };

  test.beforeEach(async ({ page }) => {
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        console.error(`[Browser Error]: ${msg.text()}`);
      }
    });

    // 默认拦截通配路由，将 threadId/runId 对齐
    await page.route(
      /\/api\/langgraph\/threads\/thread-budget-e2e(\/.*)?/,
      async (route) => {
        const url = route.request().url();
        if (url.includes("/runs/")) {
          if (url.includes("run-exhausted")) {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify(exhaustedUsage),
            });
          } else if (url.includes("run-over-cap")) {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify(overCapUsage),
            });
          } else if (url.includes("run-unverifiable")) {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify(unverifiableUsage),
            });
          } else if (url.includes("run-disabled")) {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify(disabledUsage),
            });
          } else {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify(normalUsage),
            });
          }
        } else {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(threadComplete),
          });
        }
      },
    );
  });

  test("01-Token额度水位与Usage Meter结合及多端响应式(1440/768/390)", async ({
    page,
  }) => {
    // 1. 桌面端 1440 验证
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/token-budget-fixture.html");
    await page.waitForLoadState("networkidle");

    const meter = page.locator('[data-testid="context-meter-card"]');
    await expect(meter).toBeVisible({ timeout: 10000 });
    await expect(meter).toContainText("Token 额度保护 (Run Cap)");
    await expect(meter).toContainText("4 / 10");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "01-token-budget-meter-desktop-1440.png"),
      fullPage: true,
    });

    // 2. 平板端 768 验证
    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(meter).toBeVisible();
    await expect(meter).toContainText("4 / 10");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "02-token-budget-meter-tablet-768.png"),
      fullPage: true,
    });

    // 3. 手机端 390 验证
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(meter).toBeVisible();
    await expect(meter).toContainText("Token 额度保护 (Run Cap)");

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "03-token-budget-meter-mobile-390.png"),
      fullPage: true,
    });

    // 4. 验证超额 120% 样本 (warning_then_natural_final)：视觉 clamp 至 100%，数字保真展示为 12 / 10 (120%)
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.route(
      /\/api\/langgraph\/threads\/thread-budget-e2e\/runs\/.*\/usage/,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ...overCapUsage, run_id: "run-normal" }),
        });
      },
    );
    const refreshBtn = page.locator('[data-testid="refresh-usage-btn"]');
    await expect(refreshBtn).toBeVisible({ timeout: 5000 });
    await refreshBtn.click();
    await page.waitForTimeout(600);

    await expect(meter).toContainText("12 / 10 (120%)");
    // 进度条宽度视觉 clamp 到 100%
    const progressBar = meter
      .locator('.bg-red-500, [style*="width: 100%"]')
      .first();
    await expect(progressBar).toBeVisible();

    // 5. 验证 disabled/null 额度：完全隐藏 Token 额度条，不显示“无限额度”
    await page.route(
      /\/api\/langgraph\/threads\/thread-budget-e2e\/runs\/.*\/usage/,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ...disabledUsage, run_id: "run-normal" }),
        });
      },
    );
    await refreshBtn.click();
    await page.waitForTimeout(600);
    await expect(meter).not.toContainText("Token 额度保护 (Run Cap)");
    await expect(meter).not.toContainText("无限额度");
  });

  test("02-在途硬停过渡态与终态流转及草稿回填保护", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/token-budget-fixture.html");
    await page.waitForLoadState("networkidle");

    const statusBar = page.locator('[data-testid="chat-agent-status-bar"]');
    const userInput = page.locator('[data-testid="chat-user-input"]');

    // 1. 触发在途触限（硬停中）
    await page
      .locator('[data-testid="btn-scenario-in-flight-exhausted"]')
      .click();
    await expect(statusBar).toBeVisible({ timeout: 5000 });
    await expect(statusBar).toContainText("已触发额度保护，正在确认执行结果");

    // 验证在途状态下取消按钮变为“等待停止中...”且置灰禁用
    const cancelWaitBtn = statusBar.locator('button:has-text("等待停止中...")');
    await expect(cancelWaitBtn).toBeVisible();
    await expect(cancelWaitBtn).toBeDisabled();

    // 验证在途状态下绝不展示“调整请求”或“重发”按钮（防止并发）
    await expect(statusBar.locator('button:has-text("调整请求")')).toHaveCount(
      0,
    );

    // 2. 原生终态到达：收到 error 终态
    await page
      .locator('[data-testid="btn-scenario-terminal-exhausted"]')
      .click();
    await expect(statusBar).toContainText("本次执行因Token额度停止");

    // 验证终态提供【调整请求】按钮
    const adjustBtn = statusBar.locator('button:has-text("调整请求")');
    await expect(adjustBtn).toBeVisible();
    await expect(adjustBtn).toBeEnabled();

    // 3. 点击【调整请求】，草稿回填至输入框，且输入框保持可用
    await adjustBtn.click();
    await expect(userInput).toHaveValue("已回填草稿：请帮我分析这份超长财报");
    await expect(userInput).toBeEnabled();

    // 截图记录在途硬停过渡态与终态回填
    await page.screenshot({
      path: path.join(
        SCREENSHOT_DIR,
        "04-in-flight-to-terminal-transition.png",
      ),
      fullPage: true,
    });
  });

  test("03-在途不可确认通知与终态安全防线", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/token-budget-fixture.html");
    await page.waitForLoadState("networkidle");

    const statusBar = page.locator('[data-testid="chat-agent-status-bar"]');

    // 1. 注入不可确认通知
    await page.evaluate(() => {
      (window as any).__tokenBudgetTestController.setRunning(true);
      (window as any).__tokenBudgetTestController.setNotice({
        version: 1,
        type: "runtime_budget_notice",
        code: "token_budget_unverifiable",
        budget_scope: "run",
        unit: "tokens_total",
        limit: 100000,
        used: 50000,
        remaining: null,
        action: "stop",
        message: "Usage unverifiable",
      });
    });

    await expect(statusBar).toBeVisible({ timeout: 5000 });
    await expect(statusBar).toContainText("已触发额度保护，正在确认执行结果");

    // 2. 原生终态到达
    await page.evaluate(() => {
      (window as any).__tokenBudgetTestController.setSafetyError({
        code: "runtime_token_budget_unverifiable",
        message: "Token usage unverifiable",
      });
    });

    await expect(statusBar).toContainText(
      "用量无法确认，本次执行已停止新增工作",
    );
    // 严禁显示为“余额 0”，严禁显示重试按钮
    await expect(statusBar).not.toContainText("余额 0");
    await expect(statusBar.locator('button:has-text("重试")')).toHaveCount(0);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "05-unverifiable-terminal.png"),
      fullPage: true,
    });
  });

  test("04-自然完成边界安全验证(stop_code=null)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/token-budget-fixture.html");
    await page.waitForLoadState("networkidle");

    const statusBar = page.locator('[data-testid="chat-agent-status-bar"]');

    // 点击自然完成
    await page.locator('[data-testid="btn-scenario-natural-final"]').click();

    // 状态栏不应渲染错误或报警，保持正常就绪
    await expect(statusBar).toHaveCount(0);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "06-natural-final-at-cap.png"),
      fullPage: true,
    });
  });

  test("05-刷新后的历史原因单次静默对账闭环", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/token-budget-fixture.html");
    await page.waitForLoadState("networkidle");

    const statusBar = page.locator('[data-testid="chat-agent-status-bar"]');

    // 1. 模拟刷新进入历史错误 Run：无 notice，通过静默对账注入 historicalStopCode
    await page.evaluate(() => {
      (window as any).__tokenBudgetTestController.reset();
      (window as any).__tokenBudgetTestController.setHistoricalStopCode(
        "token_budget_exhausted",
      );
    });

    // 状态栏成功恢复为精准的额度停止
    await expect(statusBar).toBeVisible({ timeout: 5000 });
    await expect(statusBar).toContainText("本次执行因Token额度停止");
    await expect(
      statusBar.locator('button:has-text("调整请求")'),
    ).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "07-refresh-silent-reconciliation.png"),
      fullPage: true,
    });
  });

  test("06-真实三服务与真实大模型全链路调用闭环验证", async ({ page }) => {
    test.setTimeout(120000); // 留出真实大模型运行与落库时间

    await page.setViewportSize({ width: 1440, height: 900 });

    // 1. 登录管理员
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");
    const submitBtn = page.locator('button[type="submit"]');
    await expect(submitBtn).toBeVisible({ timeout: 10000 });
    await submitBtn.click();

    // 2. 等待进入主工作台
    await page.waitForURL(/\/workspace/, { timeout: 15000 });

    // 3. 进入 Chat 页面
    const projectId = "5a5b7239-43e3-40e6-bba3-e64d96057607";
    await page.goto(`/workspace/projects/${projectId}/chat`);
    await page.waitForLoadState("networkidle");

    // 4. 新建会话
    const newThreadBtn = page.locator('button:has-text("新建会话")').first();
    if (await newThreadBtn.isVisible({ timeout: 3000 })) {
      await newThreadBtn.click();
      await page.waitForTimeout(1000);
    }

    // 若有智能体选择，确保选择 dearflow_agent
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

    // 5. 显式选择已配置真实模型
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
        await targetModelOption.click();
        await page.waitForTimeout(500);
      } else {
        await page.keyboard.press("Escape");
      }
    }

    // 6. 输入 Prompt 并发送真实请求
    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 15000 });
    await textarea.fill("请用一句话回答：地球到月球的平均距离是多少？");
    await textarea.press("Enter");

    // 7. 等待大模型流式生成收敛
    console.log("等待真实大模型回答与 Run 终态收敛...");
    await page.locator(".pw-markdown").first().waitFor({ timeout: 60000 });

    const stopGenBtn = page
      .locator('button[title="停止生成"], button:has-text("停止生成")')
      .first();
    if (await stopGenBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await stopGenBtn
        .waitFor({ state: "detached", timeout: 45000 })
        .catch(() => {});
    }

    await page.waitForTimeout(4000);

    // 8. 切换到轨迹排障视图并打开用量面板
    const trajectoryTabBtn = page.locator('button:has-text("轨迹")').first();
    await expect(trajectoryTabBtn).toBeVisible({ timeout: 10000 });
    await trajectoryTabBtn.click();
    await page.waitForTimeout(1000);

    const usageBtn = page
      .locator(
        '[data-testid="toggle-usage-btn"], button:has-text("用量与成本")',
      )
      .first();
    await expect(usageBtn).toBeVisible({ timeout: 10000 });
    await usageBtn.click();

    // 9. 刷新并验证用量水位
    const refreshBtn = page.locator('[data-testid="refresh-usage-btn"]');
    if (await refreshBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await refreshBtn.click();
      await page.waitForTimeout(2000);
    }

    const usagePanel = page.locator('[data-testid="run-usage-panel"]');
    await expect(usagePanel).toBeVisible({ timeout: 10000 });

    const meter = page.locator('[data-testid="context-meter-card"]');
    await expect(meter).toBeVisible();
    await expect(meter).toContainText("运行水位 (Usage Meter)");

    // 10. 截取真实大模型端到端闭环验证最终证据
    await page.screenshot({
      path: path.join(
        SCREENSHOT_DIR,
        "08-real-model-fullchain-token-budget.png",
      ),
      fullPage: true,
    });

    console.log("真实大模型 Token 额度全链路闭环验证通过！");
  });
});
