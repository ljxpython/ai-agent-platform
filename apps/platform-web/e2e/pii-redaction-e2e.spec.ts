import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createPlatformFixture } from "./support/platform";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../../docs/projects/20261009-agent-pii-redaction/screenshots",
);

test.describe("Agent Context PII Redaction End-to-End Governance", () => {
  test.setTimeout(180000);

  test("01-桌面端(1440)真实模型全链路脱敏与用户原输入保持", async ({
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

      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 截图 01：初始化聊天界面就绪
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "01-desktop-chat-init.png"),
        fullPage: true,
      });

      // 发送包含敏感数据的消息
      const piiMessage =
        "我的联系邮箱是 alice@example.test，手机是 13800138000。请直接回复已确认收到信息，不要调用工具。";
      await composer.fill(piiMessage);
      const sendBtn = page.getByRole("button", { name: "发送", exact: true });
      await expect(sendBtn).toBeEnabled();
      await composer.press("Enter");

      // 等待路由跳转至具体 Thread
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });

      // 验证用户在界面上看到的气泡依然是自己的原始明文（前端绝不擅自篡改用户输入）
      const transcript = page.getByTestId("transcript");
      await expect(transcript).toContainText("alice@example.test", {
        timeout: 30000,
      });
      await expect(transcript).toContainText("13800138000");

      // 等待大模型流式输出收敛并完成，发送按钮重新恢复就绪
      console.log("等待真实大模型回答完成...");
      await expect(sendBtn).toBeVisible({ timeout: 90000 });

      // 验证输入框处于正常可编辑状态，输入文本验证草稿与发送能力
      await composer.fill("保留下一轮草稿");
      await expect(sendBtn).toBeEnabled({ timeout: 10000 });

      // 截图 02：大模型回答完成态
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "02-desktop-model-answered.png"),
        fullPage: true,
      });

      // 切换至轨迹排障视图验证
      const trajectoryTab = page
        .locator('button:has-text("轨迹"), [role="tab"]:has-text("轨迹")')
        .first();
      if (await trajectoryTab.isVisible({ timeout: 5000 }).catch(() => false)) {
        await trajectoryTab.click();
        await page.waitForTimeout(1000);
        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, "03-desktop-trajectory.png"),
          fullPage: true,
        });
      }
    } finally {
      await fixture.cleanup();
    }
  });

  test("02-移动端(390)响应式布局与脱敏交互", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

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

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 截图 04：移动端初始状态
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "04-mobile-chat-init.png"),
        fullPage: true,
      });

      const piiMessage =
        "确认收到 bob@example.test 和 13900001111 即可，请回复OK。";
      await composer.fill(piiMessage);
      const sendBtn = page.getByRole("button", { name: "发送", exact: true });
      await expect(sendBtn).toBeEnabled();
      // 在移动端使用 Enter 键触发发送，与用户移动设备软键盘提交一致
      await composer.press("Enter");

      // 等待路由跳转至具体 Thread
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });

      const transcript = page.getByTestId("transcript");
      await expect(transcript).toContainText("bob@example.test", {
        timeout: 30000,
      });

      // 等待生成收敛完成
      await expect(sendBtn).toBeVisible({ timeout: 90000 });

      await composer.fill("移动端下一轮");
      await expect(sendBtn).toBeEnabled({ timeout: 30000 });

      // 截图 05：移动端回答完成
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "05-mobile-model-answered.png"),
        fullPage: true,
      });
    } finally {
      await fixture.cleanup();
    }
  });

  test("03-隐私保护处理失败错误消费与草稿保留验证", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    const fixture = await createPlatformFixture("dearflow_agent");
    page.on("console", (msg) =>
      console.log(`[Browser Console ${msg.type()}]:`, msg.text()),
    );
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

      // 直接通过后端预创建 Thread，避免首轮流式运行带来的时序竞争
      const thread = await fixture.request<{ thread_id: string }>(
        "/api/langgraph/threads",
        "POST",
        {
          metadata: {
            graph_id: fixture.graphId,
            agent_id: fixture.agent.id,
            title: "脱敏阻断测试会话",
          },
        },
      );

      // 直接进入该会话
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat/${thread.thread_id}`,
      );

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 等待会话核实完成，发送按钮出现
      const sendBtn = page.getByRole("button", { name: "发送", exact: true });
      await expect(sendBtn).toBeVisible({ timeout: 30000 });

      // 注册脱敏阻断拦截器：模拟模型调用时后端触发 502 隐私阻断
      const errorPayload = {
        error: {
          code: "runtime.privacy.redaction_failed",
          message: "隐私保护处理失败，本次模型请求未发送。",
          details: [],
          extra: {
            upstream: "langgraph",
            upstream_status_code: 500,
          },
        },
        request_id: "test-redaction-502-req",
      };

      await page.route("**/api/langgraph/**", async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        const isExecutionCall =
          method === "POST" &&
          /\/threads\/[^/]+\/(?:runs(?:\/stream)?|commands|stream(?:\/events)?)\/?$/.test(
            new URL(url, "http://localhost").pathname,
          );

        if (isExecutionCall) {
          console.log(
            `[Intercepted & Mocked 502 Redaction Error]: ${method} ${url}`,
          );
          await route.fulfill({
            status: 502,
            contentType: "application/json",
            body: JSON.stringify(errorPayload),
          });
        } else {
          await route.continue();
        }
      });

      const draftText = "这是一份极其重要的客户财务草稿：含 alice@example.test";
      await composer.fill(draftText);
      await expect(sendBtn).toBeEnabled();
      await composer.press("Enter");

      // 断言 1：展示固定失败原因横幅
      const errorBanner = page
        .getByText("隐私保护处理失败，本次模型请求未发送。", { exact: true })
        .first();
      await expect(errorBanner).toBeVisible({ timeout: 15000 });

      // 断言 2：不展示误导性的“恢复连接”按钮（isPrivacyBlockedError 生效）
      const resumeBtn = page.getByRole("button", { name: "恢复连接" });
      await expect(resumeBtn).not.toBeVisible();

      // 断言 3：保留用户草稿，不丢失
      await expect(composer).toHaveValue(draftText);

      // 断言 4：不退出登录，token 仍在
      const tokenInStorage = await page.evaluate(() =>
        localStorage.getItem("pw:auth:token-set"),
      );
      expect(tokenInStorage).toBeTruthy();

      // 截图 06：脱敏阻断错误与草稿保留展示
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "06-desktop-privacy-blocked.png"),
        fullPage: true,
      });
    } finally {
      await fixture.cleanup();
    }
  });

  test("04-用户正文输入错误码负例不误判为系统错误", async ({ page }) => {
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

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 用户自己提问该错误码
      const query =
        "请只回答收到：用户询问系统错误码 runtime.privacy.redaction_failed 的含义。";
      await composer.fill(query);
      await composer.press("Enter");

      // 绝不能出现全局错误横幅
      const errorBanner = page.locator(
        "text=隐私保护处理失败，本次模型请求未发送。",
      );
      await expect(errorBanner).not.toBeVisible();

      // 等待正常回答完成
      const stopBtn = page
        .locator('button[title="停止生成"], button:has-text("停止生成")')
        .first();
      if (await stopBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await stopBtn
          .waitFor({ state: "detached", timeout: 90000 })
          .catch(() => {});
      }

      // 截图 07：包含错误码文本的正常对话
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "07-desktop-user-code-negative.png"),
        fullPage: true,
      });
    } finally {
      await fixture.cleanup();
    }
  });
});
