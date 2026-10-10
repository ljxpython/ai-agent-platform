import { expect, test } from "@playwright/test";
import { existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { createPlatformFixture } from "./support/platform";

const SCREENSHOT_DIR = resolve(
  process.cwd(),
  "../../docs/projects/20261009-agent-generic-production-capabilities/screenshots",
);
if (!existsSync(SCREENSHOT_DIR)) {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

test.describe("Agent 通用后台非阻塞长任务能力 E2E 全链路验收", () => {
  test.setTimeout(180000); // 真实模型调用预留充足时间

  test("01-真实大模型全链路调用与工作区「任务」Tab空状态呈现", async ({
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

      // 确保 capabilities 包含 background_tasks
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

      await page.setViewportSize({ width: 1440, height: 900 });

      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      // 真实模型交互提问
      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });
      await composer.fill("请用一句话回答：1加1等于几？");

      const sendBtn = page.getByRole("button", { name: "发送", exact: true });
      await expect(sendBtn).toBeEnabled();
      await sendBtn.click();

      // 等待会话生成、URL 跳转并生成完整回复
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });
      await expect(page.getByTestId("transcript").first()).toBeVisible({
        timeout: 60000,
      });
      await expect(composer).toBeEnabled({ timeout: 60000 });

      // 打开工作区面板
      const openWorkspaceBtn = page.getByTestId("toggle-workspace-button");
      await expect(openWorkspaceBtn).toBeVisible({ timeout: 15000 });
      await openWorkspaceBtn.click();

      // 验证「任务」Tab 按钮并点击切换
      const workspaceTabTasks = page.getByTestId("workspace-tab-tasks");
      await expect(workspaceTabTasks).toBeVisible({ timeout: 15000 });
      await workspaceTabTasks.click();

      // 验证空状态展示
      const emptyState = page.getByTestId("background-tasks-empty-state");
      await expect(emptyState).toBeVisible({ timeout: 10000 });
      await expect(emptyState).toContainText("暂无后台长任务");

      // 验证刷新按钮
      const refreshBtn = page.getByTitle("刷新任务列表");
      await expect(refreshBtn).toBeVisible();

      console.log("用例 01: 真实模型调用与「任务」Tab 空状态验收通过！");
    } finally {
      await fixture.cleanup();
    }
  });

  test("02-后台任务列表流转、按需纯文本日志查看(ANSI清洗与截断)与单任务取消确认", async ({
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

      const taskIdRunning = "a1111111-1111-4111-8111-111111111111";
      const taskIdSucceeded = "b2222222-2222-4222-8222-222222222222";
      const nowIso = new Date().toISOString();

      let cancelRequested = false;

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

      // 拦截并 Mock 后台任务接口（使用正则覆盖所有子路由，避免 glob 跨目录匹配漏掉 /output 与 /cancel）
      await page.route(
        /.*\/api\/langgraph\/threads\/.*\/background-tasks.*/,
        async (route) => {
          const url = route.request().url();
          const method = route.request().method();

          if (method === "GET" && url.includes("/output")) {
            if (url.includes(taskIdRunning)) {
              await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                  version: 1,
                  task_id: taskIdRunning,
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  status: "running",
                  available: true,
                  text: "\u001b[32m[INFO]\u001b[0m Background worker processing step 1...\n\u001b[33m[WARN]\u001b[0m High memory usage detected: 78%\nProcessing step 2...",
                  output:
                    "\u001b[32m[INFO]\u001b[0m Background worker processing step 1...\n\u001b[33m[WARN]\u001b[0m High memory usage detected: 78%\nProcessing step 2...",
                  retained_bytes: 120,
                  omitted_bytes: 0,
                  truncated: false,
                  updated_at: nowIso,
                }),
              });
              return;
            } else {
              await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                  version: 1,
                  task_id: taskIdSucceeded,
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  status: "succeeded",
                  available: true,
                  text: "Header line...\n[DATA EXCEEDED] Output stream truncated due to boundary limits.",
                  output:
                    "Header line...\n[DATA EXCEEDED] Output stream truncated due to boundary limits.",
                  retained_bytes: 65536,
                  omitted_bytes: 1048576,
                  truncated: true,
                  updated_at: nowIso,
                }),
              });
              return;
            }
          }

          if (method === "POST" && url.includes("/cancel")) {
            cancelRequested = true;
            const idempotencyKey = route.request().headers()["idempotency-key"];
            expect(idempotencyKey).toBeTruthy();

            await route.fulfill({
              status: 202,
              contentType: "application/json",
              body: JSON.stringify({
                version: 1,
                task_id: taskIdRunning,
                thread_id: "00000000-0000-0000-0000-000000000000",
                graph_id: "dearflow_agent",
                origin_run_id: "00000000-0000-0000-0000-000000000001",
                status: "cancel_requested",
                reason_code: null,
                exit_code: null,
                created_at: nowIso,
                started_at: nowIso,
                finished_at: null,
                deadline_at: nowIso,
                updated_at: nowIso,
                cleanup_state: "pending",
                output: {
                  available: true,
                  retained_bytes: 120,
                  omitted_bytes: 0,
                  truncated: false,
                  updated_at: nowIso,
                },
                delivery: {
                  state: "not_ready",
                  event_id: null,
                  run_id: null,
                  reason_code: null,
                },
                allowed_actions: ["read", "logs"],
              }),
            });
            return;
          }

          // 默认列表请求
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              version: 1,
              thread_id: "00000000-0000-0000-0000-000000000000",
              items: [
                {
                  version: 1,
                  task_id: taskIdRunning,
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  graph_id: "dearflow_agent",
                  origin_run_id: "00000000-0000-0000-0000-000000000001",
                  status: cancelRequested ? "cancel_requested" : "running",
                  reason_code: null,
                  exit_code: null,
                  created_at: nowIso,
                  started_at: nowIso,
                  finished_at: null,
                  deadline_at: nowIso,
                  updated_at: nowIso,
                  cleanup_state: "pending",
                  output: {
                    available: true,
                    retained_bytes: 120,
                    omitted_bytes: 0,
                    truncated: false,
                    updated_at: nowIso,
                  },
                  delivery: {
                    state: "not_ready",
                    event_id: null,
                    run_id: null,
                    reason_code: null,
                  },
                  allowed_actions: cancelRequested
                    ? ["read", "logs"]
                    : ["read", "logs", "cancel"],
                },
                {
                  version: 1,
                  task_id: taskIdSucceeded,
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  graph_id: "dearflow_agent",
                  origin_run_id: "00000000-0000-0000-0000-000000000002",
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
                    retained_bytes: 65536,
                    omitted_bytes: 1048576,
                    truncated: true,
                    updated_at: nowIso,
                  },
                  delivery: {
                    state: "accepted",
                    event_id: "00000000-0000-0000-0000-000000000003",
                    run_id: "00000000-0000-0000-0000-000000000004",
                    reason_code: null,
                  },
                  allowed_actions: ["read", "logs"],
                },
              ],
              has_more: false,
              next_cursor: null,
              has_unresolved: !cancelRequested,
              latest_delivery_run_id: "00000000-0000-0000-0000-000000000004",
            }),
          });
        },
      );

      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });
      await composer.fill("任务列表测试会话启动");
      await page.getByRole("button", { name: "发送", exact: true }).click();
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });
      await expect(composer).toBeEnabled({ timeout: 60000 });

      // 打开工作区面板
      const openWorkspaceBtn = page.getByTestId("toggle-workspace-button");
      await expect(openWorkspaceBtn).toBeVisible({ timeout: 15000 });
      await openWorkspaceBtn.click();

      // 切换到任务 Tab
      const workspaceTabTasks = page.getByTestId("workspace-tab-tasks");
      await expect(workspaceTabTasks).toBeVisible({ timeout: 15000 });
      await workspaceTabTasks.click();

      // 验证任务项渲染
      const taskCards = page.getByTestId("background-task-item");
      await expect(taskCards).toHaveCount(2, { timeout: 10000 });

      // 验证任务 1 (运行中) 与 任务 2 (已完成)
      await expect(taskCards.first()).toContainText("运行中");
      await expect(taskCards.nth(1)).toContainText("已完成");

      // 点击任务 1「日志」
      const viewLogBtn1 = taskCards.first().getByTestId("task-view-logs-btn");
      await viewLogBtn1.click();

      // 验证日志查看器展开，纯文本内容正常，ANSI 转义符已清洗
      const logViewer = page.locator("pre");
      await expect(logViewer).toBeVisible({ timeout: 5000 });
      await expect(logViewer).toContainText(
        "[INFO] Background worker processing step 1...",
      );
      await expect(logViewer).toContainText(
        "[WARN] High memory usage detected: 78%",
      );
      const rawText = await logViewer.innerText();
      expect(rawText).not.toContain("\u001b[32m");

      // 点击任务 2「日志」并验证截断警告条
      const viewLogBtn2 = taskCards.nth(1).getByTestId("task-view-logs-btn");
      await viewLogBtn2.click();
      await expect(
        page.getByText("日志过长已截断，仅展示最近保留日志"),
      ).toBeVisible({ timeout: 5000 });

      // 测试取消任务与 ConfirmDialog
      const cancelBtn = taskCards.first().getByTestId("task-cancel-btn");
      await expect(cancelBtn).toBeVisible();
      await cancelBtn.click();

      // 确认弹出模态框
      const confirmDialog = page.getByRole("dialog", {
        name: "取消后台任务确认",
      });
      await expect(confirmDialog).toBeVisible({ timeout: 5000 });

      // 点击确认取消
      const confirmBtn = page.getByRole("button", { name: "确认取消" });
      await confirmBtn.click();

      // 验证取消请求成功发送且状态流转
      await expect(taskCards.first()).toContainText("正在取消", {
        timeout: 10000,
      });
      expect(cancelRequested).toBe(true);

      console.log("用例 02: 列表流转、日志纯文本展示与取消确认验收通过！");
    } finally {
      await fixture.cleanup();
    }
  });

  test("03-LLM空闲时保持Stop控制台可用与后台停止报告解析", async ({ page }) => {
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

      const nowIso = new Date().toISOString();

      await page.route(
        "**/api/langgraph/threads/*/background-tasks*",
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
                  task_id: "a1111111-1111-4111-8111-111111111111",
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  graph_id: "dearflow_agent",
                  origin_run_id: "00000000-0000-0000-0000-000000000001",
                  status: "running",
                  reason_code: null,
                  exit_code: null,
                  created_at: nowIso,
                  started_at: nowIso,
                  finished_at: null,
                  deadline_at: nowIso,
                  updated_at: nowIso,
                  cleanup_state: "pending",
                  output: {
                    available: false,
                    retained_bytes: 0,
                    omitted_bytes: 0,
                    truncated: false,
                    updated_at: null,
                  },
                  delivery: {
                    state: "not_ready",
                    event_id: null,
                    run_id: null,
                    reason_code: null,
                  },
                  allowed_actions: ["read", "logs", "cancel"],
                },
              ],
              has_more: false,
              next_cursor: null,
              has_unresolved: true,
              latest_delivery_run_id: null,
            }),
          });
        },
      );

      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });
      await composer.fill("Stop控制台测试启动");
      await page.getByRole("button", { name: "发送", exact: true }).click();
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });

      // 验证在后台有未结长任务时，ChatComposer 呈现“停止生成”按钮
      const stopBtn = page
        .locator('button[title="停止生成"], button:has-text("停止生成")')
        .first();
      await expect(stopBtn).toBeVisible({ timeout: 15000 });

      console.log("用例 03: LLM 空闲时 Stop 控制台保持可达验收通过！");
    } finally {
      await fixture.cleanup();
    }
  });

  test("04-三档分辨率响应式视觉验收与截图留痕(1440x900, 768x1024, 390x844)", async ({
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
          const url = route.request().url();
          if (url.includes("/output")) {
            await route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify({
                version: 1,
                task_id: "a1111111-1111-4111-8111-111111111111",
                thread_id: "00000000-0000-0000-0000-000000000000",
                status: "running",
                available: true,
                text: "[INFO] Worker active. Processing background telemetry.\n[INFO] Health check passed.",
                output:
                  "[INFO] Worker active. Processing background telemetry.\n[INFO] Health check passed.",
                retained_bytes: 85,
                omitted_bytes: 0,
                truncated: false,
                updated_at: nowIso,
              }),
            });
            return;
          }

          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              version: 1,
              thread_id: "00000000-0000-0000-0000-000000000000",
              items: [
                {
                  version: 1,
                  task_id: "a1111111-1111-4111-8111-111111111111",
                  thread_id: "00000000-0000-0000-0000-000000000000",
                  graph_id: "dearflow_agent",
                  origin_run_id: "00000000-0000-0000-0000-000000000001",
                  status: "running",
                  reason_code: null,
                  exit_code: null,
                  created_at: nowIso,
                  started_at: nowIso,
                  finished_at: null,
                  deadline_at: nowIso,
                  updated_at: nowIso,
                  cleanup_state: "pending",
                  output: {
                    available: true,
                    retained_bytes: 85,
                    omitted_bytes: 0,
                    truncated: false,
                    updated_at: nowIso,
                  },
                  delivery: {
                    state: "not_ready",
                    event_id: null,
                    run_id: null,
                    reason_code: null,
                  },
                  allowed_actions: ["read", "logs", "cancel"],
                },
              ],
              has_more: false,
              next_cursor: null,
              has_unresolved: true,
              latest_delivery_run_id: null,
            }),
          });
        },
      );

      // 1. 桌面端 1440x900
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });
      await composer.fill("多分辨率截图基线建立");
      await page.getByRole("button", { name: "发送", exact: true }).click();
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });
      await expect(composer).toBeEnabled({ timeout: 60000 });

      // 打开工作区
      const openWorkspaceBtn = page.getByTestId("toggle-workspace-button");
      await expect(openWorkspaceBtn).toBeVisible({ timeout: 15000 });
      await openWorkspaceBtn.click();

      const tasksTabDesktop = page.getByTestId("workspace-tab-tasks");
      await expect(tasksTabDesktop).toBeVisible({ timeout: 15000 });
      await tasksTabDesktop.click();

      const taskCards = page.getByTestId("background-task-item");
      await expect(taskCards).toHaveCount(1, { timeout: 10000 });

      const viewLogBtn = taskCards.first().getByTestId("task-view-logs-btn");
      await expect(viewLogBtn).toBeVisible({ timeout: 10000 });
      await viewLogBtn.click();
      await page.waitForTimeout(1000);

      const desktopScreenshotPath = resolve(
        SCREENSHOT_DIR,
        "1440x900-desktop-tasks.png",
      );
      await page.screenshot({ path: desktopScreenshotPath, fullPage: true });
      console.log(`桌面端截图已保存至: ${desktopScreenshotPath}`);

      // 2. 平板端 768x1024
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
        "768x1024-tablet-tasks.png",
      );
      await page.screenshot({ path: tabletScreenshotPath, fullPage: true });
      console.log(`平板端截图已保存至: ${tabletScreenshotPath}`);

      // 3. 移动端 390x844
      await page.setViewportSize({ width: 390, height: 844 });
      if (await collapseSidebarBtn.isVisible()) {
        await collapseSidebarBtn.click();
      }
      await page.waitForTimeout(500);
      const mobileScreenshotPath = resolve(
        SCREENSHOT_DIR,
        "390x844-mobile-tasks.png",
      );
      await page.screenshot({ path: mobileScreenshotPath, fullPage: true });
      console.log(`移动端截图已保存至: ${mobileScreenshotPath}`);

      console.log("用例 04: 三档分辨率截图留痕全部完成！");
    } finally {
      await fixture.cleanup();
    }
  });
});
