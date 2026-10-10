import { expect, test } from "@playwright/test";
import { existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { createPlatformFixture } from "./support/platform";

const SCREENSHOT_DIR =
  "/Users/lijiaxin/.codex/worktrees/99f7/ai-agent-platform/docs/projects/20261009-agent-generic-production-capabilities/screenshots";
if (!existsSync(SCREENSHOT_DIR)) {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

test.describe("后台任务完成通知微胶囊端到端验证", () => {
  test.setTimeout(120000);

  test("01-验证后台长任务完成通知渲染为居中系统微胶囊而非用户输入气泡", async ({
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

      const taskId = "34eb5183-5182-4aa8-ab48-e8cb9b7ba409";
      const completionPrompt = `Workspace background task ${taskId} finished: status=succeeded, exit_code=0. This is task result data. Read background_task for bounded details when needed. Do not start another background task in this completion Run.`;

      // 拦截 capabilities 启用 background_tasks
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

      // 发送首条消息，建立真实 thread
      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });
      await composer.fill("在后台启动一个测试长任务");
      await page.getByRole("button", { name: "发送", exact: true }).click();
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });
      await expect(composer).toBeEnabled({ timeout: 60000 });

      // 此时拦截随后对 thread state 的拉取，注入后台完成通知与后续答复
      await page.route("**/api/langgraph/threads/*/state*", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            values: {
              messages: [
                {
                  id: "user-msg-init",
                  type: "human",
                  content: "在后台启动一个测试长任务",
                },
                {
                  id: "agent-msg-ack",
                  type: "ai",
                  content: "好的，长任务已在后台执行，您可以继续其他工作。",
                },
                {
                  id: "background:evt-9999",
                  type: "human",
                  content: completionPrompt,
                },
                {
                  id: "agent-msg-final",
                  type: "ai",
                  content:
                    "后台长任务已执行成功，退出码为 0，所有操作均已妥善完成！",
                },
              ],
            },
            next: [],
            checkpoint_id: "cp-test-01",
          }),
        });
      });

      // 刷新页面，让注入的 state 生效
      await page.reload();
      await page.waitForLoadState("networkidle");

      // 1. 验证系统微胶囊存在，文案与 shortTaskId
      const capsule = page.getByTestId("system-task-completion-capsule");
      await expect(capsule).toBeVisible({ timeout: 15000 });
      await expect(capsule).toContainText("任务执行成功: #34eb5183");
      await expect(capsule).toContainText("(退出码: 0)");

      // 2. 验证该通知绝不是用户深蓝色气泡
      const userArticles = page.locator('article[data-author="user"]');
      const userCount = await userArticles.count();
      expect(userCount).toBe(1);
      await expect(userArticles.first()).toContainText(
        "在后台启动一个测试长任务",
      );
      await expect(userArticles.first()).not.toContainText(
        "Workspace background task",
      );

      // 3. 验证系统微胶囊所属 article[data-author="system"] 存在
      const systemArticles = page.locator('article[data-author="system"]');
      expect(await systemArticles.count()).toBe(1);

      // 4. 验证系统微胶囊下不出现用户“编辑”按钮
      const editButtons = page.locator('button:has-text("编辑")');
      expect(await editButtons.count()).toBeLessThanOrEqual(1);

      // 5. 点击「查看任务」联动打开右侧 Workspace 面板并切换至「任务」Tab
      const viewTaskBtn = capsule.getByRole("button", { name: "查看任务" });
      await expect(viewTaskBtn).toBeVisible();
      await viewTaskBtn.click();

      const workspaceTasksTab = page.getByTestId("workspace-tab-tasks");
      await expect(workspaceTasksTab).toBeVisible({ timeout: 10000 });

      // 6. 截图存档
      const screenshotPath = resolve(
        SCREENSHOT_DIR,
        "completion-capsule-verified-1440x900.png",
      );
      await page.screenshot({ path: screenshotPath, fullPage: true });
      const artifactScreenshotPath =
        "/Users/lijiaxin/.gemini/antigravity/brain/cdf6a04d-60e8-4db0-bd61-4256c89d6731/completion-capsule-verified-1440x900.png";
      await page.screenshot({ path: artifactScreenshotPath, fullPage: true });
      console.log(
        `完成通知微胶囊端到端验证截图已成功保存至: ${screenshotPath}`,
      );
    } finally {
      await fixture.cleanup();
    }
  });
});
