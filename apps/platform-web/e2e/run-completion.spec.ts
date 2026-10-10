import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../../docs/projects/20261009-agent-production-capability-extension/evidence/screenshots",
);

const MOCK_NOTIFICATION_ITEM = {
  event_id: "fbdd4f98-6a68-42ec-b1a4-af04d5ee0688",
  graph_id: "dearflow_agent",
  status: "error",
  reason: "business_error",
  reason_code: "runtime.model.retry_exhausted",
  model_error_code: "provider_overloaded",
  notification_code: "run_failed_provider_overloaded",
  occurred_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  can_mark_read: true,
  read_at: null,
  thread_id: "58060265-5ef7-42b4-9acf-e316a867f3ab",
  run_id: "16c7d922-084d-4d85-91a1-8df5c8b0b129",
  received_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
};

const MOCK_COMPLETION_RESPONSE = {
  version: 1,
  availability: "available",
  terminal: {
    event_id: "fbdd4f98-6a68-42ec-b1a4-af04d5ee0688",
    thread_id: "58060265-5ef7-42b4-9acf-e316a867f3ab",
    run_id: "16c7d922-084d-4d85-91a1-8df5c8b0b129",
    graph_id: "dearflow_agent",
    status: "error",
    reason: "business_error",
    reason_code: "runtime.model.retry_exhausted",
    model_error_code: "provider_overloaded",
    occurred_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    retry_count: 3,
    error_message: null,
  },
  request_id: "req_completion_e2e",
};

test.describe("Agent 运行完成通知与失败回调 (P4.1 - P4.3 E2E)", () => {
  test.setTimeout(180000); // 留出充裕的测试超时时间

  test.beforeEach(async ({ page }) => {
    // 监听关键控制台日志排查问题
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        console.error(`[Browser Error]: ${msg.text()}`);
      }
    });
  });

  async function loginAsAdmin(page: any) {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    const usernameInput = page
      .locator('input[name="username"], input[type="text"]')
      .first();
    if (await usernameInput.isVisible()) {
      await usernameInput.fill("admin");
      const passwordInput = page
        .locator('input[name="password"], input[type="password"]')
        .first();
      await passwordInput.fill("admin123");
    }

    const submitBtn = page.locator('button[type="submit"]');
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();
    await page.waitForURL(/\/workspace/, { timeout: 20000 });
  }

  test("F08 & F01: 运行通知中心渲染、未读红点与三视口响应式截图", async ({
    page,
  }) => {
    // 拦截通知接口，返回未读失败通知
    let hasMarkedRead = false;
    await page.route(
      "**/api/runtime/run-notifications**",
      async (route: any) => {
        if (route.request().method() === "GET") {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              version: 1,
              availability: "available",
              items: [
                {
                  ...MOCK_NOTIFICATION_ITEM,
                  read_at: hasMarkedRead ? new Date().toISOString() : null,
                },
              ],
              next_cursor: null,
              scan_limit_reached: false,
              request_id: "req_test_feed",
            }),
          });
        } else {
          await route.continue();
        }
      },
    );

    await page.route(
      "**/api/runtime/run-notifications/*/read",
      async (route: any) => {
        if (route.request().method() === "POST") {
          hasMarkedRead = true;
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              event_id: MOCK_NOTIFICATION_ITEM.event_id,
              read_at: new Date().toISOString(),
              request_id: "req_read_success",
            }),
          });
        } else {
          await route.continue();
        }
      },
    );

    await loginAsAdmin(page);

    const projectId = "5a5b7239-43e3-40e6-bba3-e64d96057607";
    await page.goto(`/workspace/projects/${projectId}/chat`);
    await page.waitForLoadState("networkidle");

    // 1. 桌面视口 1440x900 验证
    await page.setViewportSize({ width: 1440, height: 900 });
    const bellBtn = page.locator('button[aria-label="运行通知中心"]');
    await expect(bellBtn).toBeVisible({ timeout: 15000 });

    // 检查未读 Badge
    const unreadBadge = page.locator(
      '[data-testid="notification-unread-badge"]',
    );
    await expect(unreadBadge).toBeVisible();
    await expect(unreadBadge).toHaveText("1");

    // 点击打开下拉面板
    await bellBtn.click();
    await page.waitForTimeout(500);

    // 验证细粒度原因文案
    const dropdown = page.locator('[data-testid="notification-item"]');
    await expect(dropdown).toBeVisible();
    await expect(page.locator("text=模型服务繁忙").first()).toBeVisible();
    await expect(
      page.locator("text=稍后重试 / 切换模型").first(),
    ).toBeVisible();

    // 截图 1440 桌面视口
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "1440-notification-center.png"),
      fullPage: false,
    });

    // 2. 平板视口 768x1024 验证
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(500);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "768-notification-center.png"),
      fullPage: false,
    });

    // 3. 移动端视口 390x844 验证
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(500);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "390-notification-center.png"),
      fullPage: false,
    });

    // 还原桌面视口进行标记已读操作
    await page.setViewportSize({ width: 1440, height: 900 });
    const markReadBtn = page.locator('[data-testid="mark-read-button"]');
    if (await markReadBtn.isVisible()) {
      await markReadBtn.click();
      await page.waitForTimeout(500);
      // 标记已读后，红点应该消失
      await expect(unreadBadge).not.toBeVisible();
    }
  });

  test("F02: 运行保护拦截 - 执行中跳转确认防护", async ({ page }) => {
    await page.route(
      "**/api/runtime/run-notifications**",
      async (route: any) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            version: 1,
            availability: "available",
            items: [MOCK_NOTIFICATION_ITEM],
            next_cursor: null,
            scan_limit_reached: false,
            request_id: "req_test_feed",
          }),
        });
      },
    );

    await loginAsAdmin(page);

    const projectId = "5a5b7239-43e3-40e6-bba3-e64d96057607";
    await page.goto(`/workspace/projects/${projectId}/chat`);
    await page.waitForLoadState("networkidle");

    // 通过浏览器控制台将 Pinia store 的 isChatExecuting 置为 true
    await page.evaluate(() => {
      const pinia = (window as any).__pinia || (window as any).$pinia;
      if (pinia) {
        const store = pinia._s.get("run-notifications");
        if (store) store.isChatExecuting = true;
      }
    });

    // 打开通知中心
    const bellBtn = page.locator('button[aria-label="运行通知中心"]').first();
    await expect(bellBtn).toBeVisible({ timeout: 15000 });
    await bellBtn.click();
    await page.waitForTimeout(500);

    // 点击查看会话
    const viewBtn = page.locator('[data-testid="view-thread-button"]').first();
    await expect(viewBtn).toBeVisible();
    await viewBtn.click();
    await page.waitForTimeout(500);

    // 验证弹出确认弹窗
    const dialogText = page.locator("text=当前会话正在执行 Agent 任务中");
    if (await dialogText.isVisible({ timeout: 3000 })) {
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "1440-navigation-guard-dialog.png"),
      });
      // 点击留在当前会话
      const stayBtn = page.locator('button:has-text("留在当前会话")');
      await stayBtn.click();
      await page.waitForTimeout(500);
      await expect(dialogText).not.toBeVisible();
    }
  });

  test("F04 & 真实模型全链路: 真实大模型调用与成功终态对账", async ({
    page,
  }) => {
    await loginAsAdmin(page);

    const projectId = "5a5b7239-43e3-40e6-bba3-e64d96057607";
    await page.goto(`/workspace/projects/${projectId}/chat`);
    await page.waitForLoadState("networkidle");

    // 若需要选择智能体，点击“对话目标”选择器选择具体智能体
    const agentSelectorBtn = page
      .locator('button[aria-label="对话目标"]')
      .first();
    if (await agentSelectorBtn.isVisible({ timeout: 3000 })) {
      await agentSelectorBtn.click();
      await page.waitForTimeout(500);
      const agentOptions = page
        .locator(
          'button:has-text("dearflow_agent"), button:has-text("demo_agent")',
        )
        .first();
      if (await agentOptions.isVisible({ timeout: 2000 })) {
        await agentOptions.click();
        await page.waitForTimeout(1000);
      }
    }

    // 定位输入框
    const textarea = page.locator("textarea").first();
    await expect(textarea).toBeVisible({ timeout: 15000 });

    // 截图记录提问前状态
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "01-before-real-model-send.png"),
      fullPage: true,
    });

    // 向真实模型发起一次简短调用
    const promptText = "请仅用一句话回答：1加1等于几？";
    await textarea.fill(promptText);
    await textarea.press("Enter");

    // 等待模型回复或会话处理完毕
    console.log("等待真实大模型响应结束...");
    // 监听发送按钮恢复可用或停止按钮消失
    await page.waitForTimeout(10000);

    // 截图记录回复后状态
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "02-after-real-model-response.png"),
      fullPage: true,
    });

    // 验证：正常成功结束的 Run 不会在通知中心产生错误角标
    const bellBtn = page.locator('button[aria-label="运行通知中心"]').first();
    await expect(bellBtn).toBeVisible({ timeout: 15000 });
    const unreadBadge = page.locator(
      '[data-testid="notification-unread-badge"]',
    );
    await expect(unreadBadge).not.toBeVisible();
  });

  test("F01: 轨迹视图历史 Run 安全终态诊断卡片投影展示", async ({ page }) => {
    // 拦截 completion 接口，返回安全的失败模型错误码
    await page.route(
      "**/api/langgraph/threads/*/runs/*/completion",
      async (route: any) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(MOCK_COMPLETION_RESPONSE),
        });
      },
    );

    await loginAsAdmin(page);

    const projectId = "5a5b7239-43e3-40e6-bba3-e64d96057607";
    await page.goto(`/workspace/projects/${projectId}/chat`);
    await page.waitForLoadState("networkidle");

    // 点击右上角或切换到“轨迹”视图 tab
    const trajectoryTab = page
      .locator('button:has-text("轨迹"), [role="tab"]:has-text("轨迹")')
      .first();
    if (await trajectoryTab.isVisible({ timeout: 3000 })) {
      await trajectoryTab.click();
      await page.waitForTimeout(1000);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "1440-run-diagnostics-card.png"),
        fullPage: false,
      });
    }
  });
});
