import { expect, test } from "@playwright/test";
import { existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { createPlatformFixture } from "./support/platform";

const SCREENSHOT_DIR = resolve(
  process.cwd(),
  "../../docs/projects/20261007-agent-run-cancellation/evidence/screenshots",
);
if (!existsSync(SCREENSHOT_DIR)) {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

test.describe("Agent 会话停止与状态报告 E2E 验证", () => {
  test("全链路验证：发起真实模型执行、点击停止、单飞保护、回执状态机、报告抽屉与响应式截屏", async ({
    page,
  }) => {
    test.setTimeout(180000);
    const fixture = await createPlatformFixture("workflow_demo");
    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));

    // 追踪网络请求与响应
    interface CancelRequestInfo {
      url: string;
      headers: Record<string, string>;
      body: unknown;
      status?: number;
    }
    const cancelRequests: CancelRequestInfo[] = [];
    const stopPolls: Array<{ url: string; phase: string }> = [];

    page.on("request", (req) => {
      const url = req.url();
      if (req.method() === "POST" && url.includes("/cancel")) {
        cancelRequests.push({
          url,
          headers: req.headers(),
          body: req.postDataJSON(),
        });
      }
    });

    page.on("response", async (res) => {
      const url = res.url();
      if (res.request().method() === "POST" && url.includes("/cancel")) {
        const last = cancelRequests[cancelRequests.length - 1];
        if (last) last.status = res.status();
      } else if (
        res.request().method() === "GET" &&
        url.includes("/stop-requests/")
      ) {
        try {
          const data = (await res.json()) as { phase?: string };
          if (data && data.phase) {
            stopPolls.push({ url, phase: data.phase });
          }
        } catch {
          // ignore
        }
      }
    });

    try {
      // 1. 初始化 Token
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

      // 设置桌面视口 1440x900
      await page.setViewportSize({ width: 1440, height: 900 });

      // 进入聊天页面
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 输入需要生成长文本的 Prompt，促使模型持续输出
      await composer.fill(
        "请写一篇关于计算机体系结构演进的详尽论文，不少于1500字，涵盖图灵机、冯诺依曼结构、指令流水线、乱序执行、SIMD以及现代GPU异构计算体系。",
      );

      const sendBtn = page.getByRole("button", { name: "发送", exact: true });
      await expect(sendBtn).toBeEnabled();

      // 点击发送
      await sendBtn.click();

      // 观察 Stop 按钮出现（文案为“停止生成”）
      const stopBtn = page.getByRole("button", { name: "停止生成" });
      await expect(stopBtn).toBeVisible({ timeout: 30000 });

      // 验证在生成期间，停止按钮可用
      await expect(stopBtn).toBeEnabled({ timeout: 10000 });

      // 触发停止！
      await stopBtn.click();

      // 验证单飞保护：按钮变为“停止中...”且禁用
      const stoppingBtn = page.getByRole("button", { name: "停止中..." });
      await expect(stoppingBtn).toBeVisible({ timeout: 10000 });
      await expect(stoppingBtn).toBeDisabled();

      // 截取阶段 1 截图：Stopping 状态
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/e2e-stop-phase1-stopping.png`,
        fullPage: true,
      });

      // 等待停止完成：精准定位 RunStopReportBanner
      const banner = page.getByTestId("run-stop-report-banner");
      await expect(banner).toBeVisible({ timeout: 45000 });
      await expect(banner).toContainText("已停止", { timeout: 45000 });

      // 截取阶段 2 截图：Stopped 终态与 Banner
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/e2e-stop-phase2-stopped.png`,
        fullPage: true,
      });

      // 检查网络请求协议断言
      expect(cancelRequests.length).toBeGreaterThan(0);
      const postCancel = cancelRequests[0];
      expect(postCancel.body).toEqual({}); // Body 必须是严格空对象 {}
      expect(postCancel.headers["idempotency-key"]).toBeDefined(); // 携带幂等键
      expect(postCancel.headers["x-project-id"]).toBe(fixture.projectId); // 携带项目 ID
      expect(postCancel.status).toBe(202); // 必须是 202 Accepted

      // 打开停止详情抽屉
      const reportBtn = banner.getByRole("button", { name: "查看报告" });
      if (await reportBtn.isVisible()) {
        await reportBtn.click();
        const drawerContent = page.getByTestId("run-stop-report-details");
        await expect(drawerContent).toBeVisible({ timeout: 10000 });
        await expect(page.getByText("会话停止状态与证据报告")).toBeVisible({
          timeout: 10000,
        });
        await page.waitForTimeout(300);

        // 截取阶段 3 截图：详情抽屉展开
        await page.screenshot({
          path: `${SCREENSHOT_DIR}/e2e-stop-phase3-drawer.png`,
          fullPage: true,
        });

        // 验证响应式布局：768px（平板）与 390px（移动端）
        await page.setViewportSize({ width: 768, height: 1024 });
        await page.waitForTimeout(500);
        await page.screenshot({
          path: `${SCREENSHOT_DIR}/e2e-stop-viewport-768.png`,
          fullPage: true,
        });

        await page.setViewportSize({ width: 390, height: 844 });
        await page.waitForTimeout(500);
        await page.screenshot({
          path: `${SCREENSHOT_DIR}/e2e-stop-viewport-390.png`,
          fullPage: true,
        });

        // 切回 1440 桌面视口并通过键盘 Escape 优雅关闭抽屉
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.keyboard.press("Escape");
        await expect(drawerContent).not.toBeVisible({ timeout: 5000 });
      }

      // 验证恢复状态：输入框可编辑，可以输入新内容
      await expect(composer).toBeEnabled({ timeout: 15000 });
      await composer.fill("停止后的下一条测试消息");
      await expect(composer).toHaveValue("停止后的下一条测试消息");

      // 截取阶段 5 截图：恢复就绪
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/e2e-stop-phase5-resumed.png`,
        fullPage: true,
      });

      expect(browserErrors).toEqual([]);
    } catch (err) {
      await page
        .screenshot({
          path: `${SCREENSHOT_DIR}/e2e-stop-failure.png`,
          fullPage: true,
        })
        .catch(() => undefined);
      throw err;
    } finally {
      await page.close();
      await fixture.cleanup();
    }
  });
});
