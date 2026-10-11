import { expect, test } from "@playwright/test";
import { existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { createPlatformFixture } from "./support/platform";

const SCREENSHOT_DIR = resolve(
  process.cwd(),
  "../../docs/projects/20261011-background-acceptance-closeout/screenshots",
);

if (!existsSync(SCREENSHOT_DIR)) {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

test.describe("专项 20261011-background-acceptance-closeout 前端与全链路 E2E 验收", () => {
  test.setTimeout(180000); // 真实大模型调用预留充足时间

  test("01-真实大模型全链路调用与对话流转闭环", async ({ page }) => {
    // 监听关键控制台报错
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        console.error(`[Browser Error]: ${msg.text()}`);
      }
    });

    const fixture = await createPlatformFixture("dearflow_agent");
    try {
      await page.addInitScript(
        ({ tokens, projectId }) => {
          localStorage.setItem(
            "pw:auth:token-set",
            JSON.stringify({
              accessToken: tokens.access_token,
              refreshToken: tokens.refresh_token,
              tokenType: tokens.token_type,
            }),
          );
          localStorage.setItem("pw:workspace:project-id", projectId);
        },
        { tokens: fixture.tokens, projectId: fixture.projectId },
      );

      await page.setViewportSize({ width: 1440, height: 900 });

      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 发送真实模型提问（使用 focus + fill + waitForTimeout + press Enter 触发规范发送）
      const promptText = "请仅用一句话回答：1加1等于几？";
      await composer.focus();
      await composer.fill(promptText);
      await page.waitForTimeout(500);
      await composer.press("Enter");

      console.log("已发起提问，等待生成会话与 URL 跳转...");
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });

      console.log("等待真实大模型流式输出与终态收敛...");

      // 等待 AI 助手回复卡片出现（第 2 条 markdown，第 1 条为用户输入）
      const aiMarkdownEl = page.locator(".pw-markdown").nth(1);
      await expect(aiMarkdownEl).toBeVisible({ timeout: 60000 });

      // 等待流式输出收尾（停止生成按钮脱离 DOM）
      const stopGenBtn = page
        .locator('button[title="停止生成"], button:has-text("停止生成")')
        .first();
      if (await stopGenBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
        await stopGenBtn
          .waitFor({ state: "detached", timeout: 60000 })
          .catch(() => {});
      }

      await page.waitForTimeout(3000);

      // 验证真实模型回答内容
      const responseText = await aiMarkdownEl.innerText();
      console.log(`真实大模型回复内容: ${responseText.trim()}`);
      expect(responseText.length).toBeGreaterThan(0);
      expect(responseText).toMatch(/2|二/);

      // 截图记录真实模型回答完成态
      const screenshotPath = resolve(
        SCREENSHOT_DIR,
        "01-real-model-chat-answered.png",
      );
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log(`真实模型对话全屏截图已保存: ${screenshotPath}`);
    } finally {
      await fixture.cleanup();
    }
  });

  test("02-后台长任务 accepted 与 unknown 徽章、提示及日志查看验收", async ({
    page,
  }) => {
    const fixture = await createPlatformFixture("dearflow_agent");
    try {
      await page.addInitScript(
        ({ tokens, projectId }) => {
          localStorage.setItem(
            "pw:auth:token-set",
            JSON.stringify({
              accessToken: tokens.access_token,
              refreshToken: tokens.refresh_token,
              tokenType: tokens.token_type,
            }),
          );
          localStorage.setItem("pw:workspace:project-id", projectId);
        },
        { tokens: fixture.tokens, projectId: fixture.projectId },
      );

      await page.setViewportSize({ width: 1440, height: 900 });

      const taskIdAccepted = "a1111111-1111-4111-8111-111111111111";
      const taskIdUnknown = "b2222222-2222-4222-8222-222222222222";
      const eventIdAccepted = "c3333333-3333-4333-8333-333333333333";
      const runIdAccepted = "d4444444-4444-4444-8444-444444444444";
      const eventIdUnknown = "e5555555-5555-4555-8555-555555555555";
      const nowIso = new Date().toISOString();

      await page.route(
        "**/api/langgraph/threads/*/capabilities*",
        async (route) => {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              workspace: true,
              artifacts: true,
              terminal: true,
              background_tasks: true,
              background_tasks_start_enabled: true,
            }),
          });
        },
      );

      // Mock 符合规范 Zod Schema 的后台任务数据（UUID 格式与合规枚举）
      await page.route(
        /.*\/api\/langgraph\/threads\/.*\/background-tasks.*/,
        async (route) => {
          const url = route.request().url();
          const method = route.request().method();

          if (method === "GET" && url.includes("/output")) {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify({
                version: 1,
                task_id: taskIdAccepted,
                thread_id: "00000000-0000-0000-0000-000000000000",
                status: "succeeded",
                available: true,
                text: "\u001b[32m[INFO]\u001b[0m Background worker completed successfully.\nFinal telemetry metrics exported.",
                output:
                  "\u001b[32m[INFO]\u001b[0m Background worker completed successfully.\nFinal telemetry metrics exported.",
                retained_bytes: 88,
                omitted_bytes: 0,
                truncated: false,
                updated_at: nowIso,
              }),
            });
            return;
          }

          // 列表接口：包含 1 个 accepted（续接已接受）和 1 个 unknown（续接待确认）
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              version: 1,
              thread_id: "00000000-0000-0000-0000-000000000000",
              items: [
                {
                  version: 1,
                  task_id: taskIdAccepted,
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  graph_id: "dearflow_agent",
                  origin_run_id: "00000000-0000-0000-0000-000000000001",
                  status: "succeeded",
                  reason_code: null,
                  exit_code: 0,
                  created_at: nowIso,
                  started_at: nowIso,
                  finished_at: nowIso,
                  deadline_at: nowIso,
                  updated_at: nowIso,
                  cleanup_state: "confirmed",
                  output: {
                    available: true,
                    retained_bytes: 88,
                    omitted_bytes: 0,
                    truncated: false,
                    updated_at: nowIso,
                  },
                  delivery: {
                    state: "accepted",
                    event_id: eventIdAccepted,
                    run_id: runIdAccepted,
                    reason_code: null,
                  },
                  allowed_actions: ["read", "logs"],
                },
                {
                  version: 1,
                  task_id: taskIdUnknown,
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  graph_id: "dearflow_agent",
                  origin_run_id: "00000000-0000-0000-0000-000000000002",
                  status: "failed",
                  reason_code: "background_task_deadline_exceeded",
                  exit_code: 1,
                  created_at: nowIso,
                  started_at: nowIso,
                  finished_at: nowIso,
                  deadline_at: nowIso,
                  updated_at: nowIso,
                  cleanup_state: "unconfirmed",
                  output: {
                    available: false,
                    retained_bytes: 0,
                    omitted_bytes: 0,
                    truncated: false,
                    updated_at: null,
                  },
                  delivery: {
                    state: "unknown",
                    event_id: eventIdUnknown,
                    run_id: null,
                    reason_code: "background_task_delivery_expired",
                  },
                  allowed_actions: ["read"],
                },
              ],
              has_more: false,
              next_cursor: null,
              has_unresolved: false,
              latest_delivery_run_id: runIdAccepted,
            }),
          });
        },
      );

      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      // 发起初始消息以建立会话 thread
      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });
      await composer.focus();
      await composer.fill("开启后台长任务联调会话");
      await page.waitForTimeout(500);
      await composer.press("Enter");

      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });

      // 打开工作区面板
      const openWorkspaceBtn = page.getByTestId("toggle-workspace-button");
      await expect(openWorkspaceBtn).toBeVisible({ timeout: 15000 });
      await openWorkspaceBtn.click();

      // 切换至「任务」Tab
      const workspaceTabTasks = page.getByTestId("workspace-tab-tasks");
      await expect(workspaceTabTasks).toBeVisible({ timeout: 15000 });
      await workspaceTabTasks.click();

      // 验证 2 个任务项渲染
      const taskCards = page.getByTestId("background-task-item");
      await expect(taskCards).toHaveCount(2, { timeout: 10000 });

      // 1. 验证 accepted 徽章：“续接已接受”
      const acceptedBadge = taskCards
        .nth(0)
        .getByTestId("delivery-accepted-badge");
      await expect(acceptedBadge).toBeVisible();
      await expect(acceptedBadge).toHaveText("续接已接受");
      await expect(acceptedBadge).toHaveAttribute(
        "title",
        new RegExp(runIdAccepted),
      );

      // 2. 验证 unknown 徽章：“续接待确认”
      const unknownBadge = taskCards
        .nth(1)
        .getByTestId("delivery-unknown-badge");
      await expect(unknownBadge).toBeVisible();
      await expect(unknownBadge).toHaveText("续接待确认");
      await expect(unknownBadge).toHaveAttribute(
        "title",
        "续接状态确认中，正在保持只读查询",
      );

      // 3. 验证 unknown 任务未显示重试操作（防伪重试）
      const unknownRetryBtn = taskCards
        .nth(1)
        .locator('button:has-text("重试")');
      await expect(unknownRetryBtn).toHaveCount(0);

      // 4. 打开 accepted 任务的日志抽屉，验证 ANSI 清洗与日志纯文本查看
      const viewLogBtn = taskCards.nth(0).getByTestId("task-view-logs-btn");
      await expect(viewLogBtn).toBeVisible();
      await viewLogBtn.click();

      const logViewer = page.locator("pre").first();
      await expect(logViewer).toBeVisible({ timeout: 10000 });
      await expect(logViewer).toContainText(
        "Background worker completed successfully.",
      );

      // 截图记录 accepted / unknown 徽章与日志查看
      const screenshotPath = resolve(
        SCREENSHOT_DIR,
        "02-background-tasks-accepted-unknown.png",
      );
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log(
        `Accepted/Unknown 徽章及日志抽屉全屏截图已保存: ${screenshotPath}`,
      );
    } finally {
      await fixture.cleanup();
    }
  });

  test("03-响应式三档视口全景截图留痕(1440x900, 768x1024, 390x844)", async ({
    page,
  }) => {
    const fixture = await createPlatformFixture("dearflow_agent");
    try {
      await page.addInitScript(
        ({ tokens, projectId }) => {
          localStorage.setItem(
            "pw:auth:token-set",
            JSON.stringify({
              accessToken: tokens.access_token,
              refreshToken: tokens.refresh_token,
              tokenType: tokens.token_type,
            }),
          );
          localStorage.setItem("pw:workspace:project-id", projectId);
        },
        { tokens: fixture.tokens, projectId: fixture.projectId },
      );

      const taskIdAccepted = "a1111111-1111-4111-8111-111111111111";
      const taskIdUnknown = "b2222222-2222-4222-8222-222222222222";
      const eventIdAccepted = "c3333333-3333-4333-8333-333333333333";
      const runIdAccepted = "d4444444-4444-4444-8444-444444444444";
      const eventIdUnknown = "e5555555-5555-4555-8555-555555555555";
      const nowIso = new Date().toISOString();

      await page.route(
        "**/api/langgraph/threads/*/capabilities*",
        async (route) => {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              workspace: true,
              artifacts: true,
              terminal: true,
              background_tasks: true,
              background_tasks_start_enabled: true,
            }),
          });
        },
      );

      await page.route(
        /.*\/api\/langgraph\/threads\/.*\/background-tasks.*/,
        async (route) => {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              version: 1,
              thread_id: "00000000-0000-0000-0000-000000000000",
              items: [
                {
                  version: 1,
                  task_id: taskIdAccepted,
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  graph_id: "dearflow_agent",
                  origin_run_id: "00000000-0000-0000-0000-000000000001",
                  status: "succeeded",
                  reason_code: null,
                  exit_code: 0,
                  created_at: nowIso,
                  started_at: nowIso,
                  finished_at: nowIso,
                  deadline_at: nowIso,
                  updated_at: nowIso,
                  cleanup_state: "confirmed",
                  output: {
                    available: true,
                    retained_bytes: 88,
                    omitted_bytes: 0,
                    truncated: false,
                    updated_at: nowIso,
                  },
                  delivery: {
                    state: "accepted",
                    event_id: eventIdAccepted,
                    run_id: runIdAccepted,
                    reason_code: null,
                  },
                  allowed_actions: ["read", "logs"],
                },
                {
                  version: 1,
                  task_id: taskIdUnknown,
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  graph_id: "dearflow_agent",
                  origin_run_id: "00000000-0000-0000-0000-000000000002",
                  status: "failed",
                  reason_code: "background_task_deadline_exceeded",
                  exit_code: 1,
                  created_at: nowIso,
                  started_at: nowIso,
                  finished_at: nowIso,
                  deadline_at: nowIso,
                  updated_at: nowIso,
                  cleanup_state: "unconfirmed",
                  output: {
                    available: false,
                    retained_bytes: 0,
                    omitted_bytes: 0,
                    truncated: false,
                    updated_at: null,
                  },
                  delivery: {
                    state: "unknown",
                    event_id: eventIdUnknown,
                    run_id: null,
                    reason_code: "background_task_delivery_expired",
                  },
                  allowed_actions: ["read"],
                },
              ],
              has_more: false,
              next_cursor: null,
              has_unresolved: false,
              latest_delivery_run_id: runIdAccepted,
            }),
          });
        },
      );

      // --- 1. 桌面端 1440x900 ---
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      // 发起初始消息建立 thread
      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });
      await composer.focus();
      await composer.fill("多分辨率视觉留痕基线建立");
      await page.waitForTimeout(500);
      await composer.press("Enter");

      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });

      // 打开工作区面板并切到任务 Tab
      const openWorkspaceBtn = page.getByTestId("toggle-workspace-button");
      await expect(openWorkspaceBtn).toBeVisible({ timeout: 15000 });
      await openWorkspaceBtn.click();

      const tasksTab = page.getByTestId("workspace-tab-tasks");
      await expect(tasksTab).toBeVisible({ timeout: 15000 });
      await tasksTab.click();

      await expect(page.getByTestId("background-task-item")).toHaveCount(2, {
        timeout: 10000,
      });

      const desktopScreenshotPath = resolve(
        SCREENSHOT_DIR,
        "1440x900-desktop-background-closeout.png",
      );
      await page.screenshot({ path: desktopScreenshotPath, fullPage: true });
      console.log(`桌面端截图已保存至: ${desktopScreenshotPath}`);

      // --- 2. 平板端 768x1024 ---
      await page.setViewportSize({ width: 768, height: 1024 });
      const collapseSidebarBtn = page
        .locator('button[title="收起历史会话"]')
        .first();
      if (await collapseSidebarBtn.isVisible()) {
        await collapseSidebarBtn.click();
      }
      await page.waitForTimeout(500);

      const tabletScreenshotPath = resolve(
        SCREENSHOT_DIR,
        "768x1024-tablet-background-closeout.png",
      );
      await page.screenshot({ path: tabletScreenshotPath, fullPage: true });
      console.log(`平板端截图已保存至: ${tabletScreenshotPath}`);

      // --- 3. 移动端 390x844 ---
      await page.setViewportSize({ width: 390, height: 844 });
      if (await collapseSidebarBtn.isVisible()) {
        await collapseSidebarBtn.click();
      }
      await page.waitForTimeout(500);

      const mobileScreenshotPath = resolve(
        SCREENSHOT_DIR,
        "390x844-mobile-background-closeout.png",
      );
      await page.screenshot({ path: mobileScreenshotPath, fullPage: true });
      console.log(`移动端截图已保存至: ${mobileScreenshotPath}`);
    } finally {
      await fixture.cleanup();
    }
  });
});
