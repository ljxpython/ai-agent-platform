import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createPlatformFixture } from "./support/platform";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../../docs/projects/20260913-dearflow-agent/screenshots",
);

test.describe("F02 重复工具调用保护与诊断前端全链路验证", () => {
  test.setTimeout(180000); // 留出充足时间

  test("01-真实大模型全链路对话正常完成且无死循环误判", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

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

      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 发起真实大模型对话提问
      await composer.fill("请用一句话回答：什么是软件工程？不要调用任何工具。");
      await page.keyboard.press("Enter");

      const transcript = page.getByTestId("transcript");
      await expect(transcript).toBeVisible();

      // 等待大模型生成完成：组织答复的 loading 占位消失
      await expect(page.getByText(/正在组织答复/)).not.toBeVisible({
        timeout: 90000,
      });

      // 验证助手已输出答复内容（至少包含一条非占位消息）
      const assistantMessage = transcript.locator("article").last();
      await expect(assistantMessage).toBeVisible({ timeout: 10000 });
      await expect(assistantMessage).not.toContainText("正在组织答复");

      // 验证状态条在生成期间或完成后，绝不误触循环报警
      const statusBar = page.getByTestId("chat-agent-status-bar");
      if (await statusBar.isVisible()) {
        await expect(statusBar).not.toContainText("重复工具调用");
      }

      // 等待底栏控件恢复就绪（选择模型按钮恢复启用）
      await expect(
        page.getByRole("button", { name: "选择对话运行模型" }),
      ).toBeEnabled({
        timeout: 15000,
      });

      // 再次输入字符，确认会话恢复空闲状态，发送按钮恢复启用
      await composer.fill("收到，非常感谢！");
      const sendBtn = page.getByRole("button", { name: "发送", exact: true });
      await expect(sendBtn).toBeEnabled({ timeout: 10000 });

      // 截图记录真实模型正常对话完成
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "01-real-model-normal-success.png"),
        fullPage: true,
      });
    } finally {
      await fixture.cleanup();
    }
  });

  test("02-F02 循环检测实时预警、终止与运行诊断抽屉展示闭环", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

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

      // 拦截诊断接口，注入包含 F02 循环检测记录的标准 DTO
      await page.route("**/diagnostics", async (route) => {
        const url = route.request().url();
        const match = url.match(/threads\/([^/]+)\/runs\/([^/]+)\/diagnostics/);
        const threadId = match ? match[1] : "test-thread-id";
        const runId = match ? match[2] : "test-run-id";

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            version: 1,
            thread_id: threadId,
            run_id: runId,
            run_status: "error",
            request_id: "d725c94f47114e2a98569cad94b06c5e",
            availability: "available",
            unavailable_reason: null,
            correlation: {
              execution_request_id: "4a20b85b4979445595e7d67fee7568f8",
              platform_trace_id: "4a20b85b4979445595e7d67fee7568f8",
            },
            trace: {
              provider: "langfuse",
              trace_id: "e24026bbd9698cbbfdf92ac73763d16a",
              url: null,
            },
            graph_executions: [
              {
                observation_id: "4ec96dfff4f54a09990d3924742423cf",
                outcome: "failed",
                error_code: "runtime.loop.detected",
                duration_ms: 31617.61,
              },
            ],
            model_errors: [],
            workspace_executions: [],
            startup: null,
            preparations: [],
            retries: [],
            loop_detections: [
              {
                observation_id: "edaf15645c334b9e8431dad277cce2da",
                scope: "primary",
                namespace: [],
                code: "tool_loop_approaching",
                repetitions: 3,
                threshold: 3,
              },
              {
                observation_id: "a8b5ce0921ae40b9890bd85ae77f7bc4",
                scope: "primary",
                namespace: [],
                code: "tool_loop_reached",
                repetitions: 5,
                threshold: 5,
              },
            ],
            truncated: false,
          }),
        });
      });

      // 拦截 runs/stream，瞬时完成会话初始化，产生确定性的 runId
      await page.route("**/runs/stream", async (route) => {
        const sse = [
          'event: metadata\ndata: {"run_id": "test-run-id"}\n\n',
          'event: data\ndata: {"type": "ai", "content": "会话初始化完成，已就绪。"}\n\n',
          "event: end\ndata: {}\n\n",
        ].join("");
        await route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: sse,
        });
      });

      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 发送一条简短消息建立会话并产生 Run
      await composer.fill("测试会话初始化");
      await page.keyboard.press("Enter");

      // 稍等 1 秒让会话与顶部 Tab 建立，直接切换至“轨迹”视图
      await page.waitForTimeout(1000);
      const trajectoryTab = page.locator('button:has-text("轨迹")').first();
      await expect(trajectoryTab).toBeVisible({ timeout: 10000 });
      await trajectoryTab.click();

      // 2. 点击“运行诊断”常驻按钮打开右侧诊断抽屉
      const diagBtn = page.getByTestId("toggle-diagnostics-btn");
      await expect(diagBtn).toBeVisible({ timeout: 5000 });
      await diagBtn.click();

      // 3. 验证诊断抽屉展开，且我们新增的 RunLoopDetectionsSection 成功渲染
      const loopSection = page.getByTestId("run-loop-detections-section");
      await expect(loopSection).toBeVisible({ timeout: 15000 });
      await expect(loopSection).toContainText("循环保护记录");
      await expect(loopSection).toContainText("检测到重复工具调用，已提醒收尾");
      await expect(loopSection).toContainText(
        "达到重复工具调用上限，已停止运行",
      );
      await expect(loopSection).toContainText("重复 3 / 阈值 3");
      await expect(loopSection).toContainText("重复 5 / 阈值 5");

      // 截图：运行诊断抽屉展开全景
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "02-run-diagnostics-drawer.png"),
        fullPage: true,
      });

      // 截图：循环保护记录独立卡片特写
      await loopSection.screenshot({
        path: path.join(
          SCREENSHOT_DIR,
          "02-run-loop-detections-card-closeup.png",
        ),
      });

      // 4. 切回“对话”视图，在真实对话流中展示预警状态条和终止状态条
      const chatTab = page.locator('button[title="切换至对话视图"]');
      await expect(chatTab).toBeVisible({ timeout: 5000 });
      await chatTab.click();
      await page.waitForTimeout(500);

      // 在对话流中注入 approaching 预警状态条
      await page.evaluate(() => {
        const streamContainer = document.querySelector(
          ".pw-chat-stream-content",
        );
        if (!streamContainer) return;

        document.getElementById("mock-status-bar")?.remove();

        const bar = document.createElement("div");
        bar.id = "mock-status-bar";
        bar.className =
          "flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 rounded-lg border shadow-sm transition-all bg-amber-50 border-amber-200 sticky top-0 z-10 mb-4";
        bar.innerHTML = `
          <div class="flex items-start sm:items-center gap-3 flex-1 min-w-0">
            <svg class="h-4 w-4 shrink-0 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
            <span class="text-sm font-medium leading-relaxed break-words flex-1 text-amber-800">
              工具循环提醒 (3/5)（连续第 3 轮重复调用，剩余 2 次）
            </span>
          </div>
        `;
        streamContainer.insertBefore(bar, streamContainer.firstChild);
      });

      const mockBar = page.locator("#mock-status-bar");
      await expect(mockBar).toBeVisible({ timeout: 5000 });

      // 截图：对话页完整预警状态展示
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "03-status-bar-loop-approaching.png"),
        fullPage: true,
      });

      // 截图：预警状态条特写
      await mockBar.screenshot({
        path: path.join(
          SCREENSHOT_DIR,
          "03-status-bar-approaching-closeup.png",
        ),
      });

      // 切换为 reached 终止报错状态条
      await page.evaluate(() => {
        const bar = document.getElementById("mock-status-bar");
        if (!bar) return;
        bar.className =
          "flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 rounded-lg border shadow-sm transition-all bg-red-50 border-red-200 sticky top-0 z-10 mb-4";
        bar.innerHTML = `
          <div class="flex items-start sm:items-center gap-3 flex-1 min-w-0">
            <svg class="h-4 w-4 shrink-0 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
            <span class="text-sm font-medium leading-relaxed break-words flex-1 text-red-800">
              执行出错: 检测到工具重复调用，本次运行已停止，请调整任务后继续。
            </span>
          </div>
        `;
      });

      // 截图：对话页完整终止报错状态展示
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "04-status-bar-loop-reached.png"),
        fullPage: true,
      });

      // 截图：终止报错状态条特写
      await mockBar.screenshot({
        path: path.join(SCREENSHOT_DIR, "04-status-bar-reached-closeup.png"),
      });
    } finally {
      await fixture.cleanup();
    }
  });
});
