import { test, expect } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createPlatformFixture } from "./support/platform";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR =
  "/Users/lijiaxin/.codex/worktrees/f07-title/ai-agent-platform/docs/projects/20261009-agent-thread-auto-title/screenshots";

test.describe("F07 自动对话标题全链路与真实大模型闭环验收", () => {
  test.setTimeout(180000); // 留出 3 分钟充足时间进行真实大模型端到端调用

  test("真实大模型自动提炼、用户改名保护与多视口视觉闭环", async ({ page }) => {
    // 确保截图目录存在
    const fs = await import("node:fs");
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

    // 监听关键控制台报错与网络请求
    page.on("console", (msg) => {
      console.log(`[Browser Console ${msg.type()}]: ${msg.text()}`);
    });
    page.on("request", (req) => {
      if (
        req.url().includes("/title/summarize") ||
        req.url().includes("/threads")
      ) {
        console.log(`[HTTP REQ] ${req.method()} ${req.url()}`);
      }
    });
    page.on("response", async (res) => {
      if (res.url().includes("/title/summarize")) {
        let body = "";
        try {
          body = await res.text();
        } catch {
          // ignore body read errors
        }
        console.log(`[HTTP RES] ${res.status()} ${res.url()} -> ${body}`);
      }
    });

    console.log("准备测试环境与项目 Agent Fixture...");
    const fixture = await createPlatformFixture("dearflow_agent");

    try {
      // 1. 设置 1440 视口并登录
      await page.setViewportSize({ width: 1440, height: 900 });
      console.log("导航至登录页...");
      await page.goto("/auth/login");
      await page.waitForLoadState("networkidle");

      const usernameInput = page
        .locator('input[type="text"], input[name="username"]')
        .first();
      if (await usernameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await usernameInput.fill("admin");
        const passwordInput = page.locator('input[type="password"]').first();
        await passwordInput.fill("admin123");
      }

      const submitBtn = page.locator('button[type="submit"]');
      if (await submitBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await submitBtn.click();
      }

      // 等待进入控制台
      await page.waitForURL(/\/workspace/, { timeout: 15000 });

      // 2. 直接导航至带具体 Agent 参数的 Chat 页面
      console.log(
        `导航至项目 Chat 页面: ${fixture.projectId} (Agent: ${fixture.agent.id})...`,
      );
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${encodeURIComponent(fixture.agent.id)}&graphId=${encodeURIComponent(fixture.graphId)}`,
      );
      await page.waitForLoadState("networkidle");

      // 3. 点击“新对话”/“新建会话”
      const newThreadBtn = page
        .locator('button:has-text("新对话"), button:has-text("新建会话")')
        .first();
      if (await newThreadBtn.isVisible({ timeout: 5000 })) {
        await newThreadBtn.click();
        await page.waitForTimeout(1000);
      }

      // 若处于未选择智能体状态，选择 dearflow_agent
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

      // 等待输入框出现
      const textarea = page.locator("textarea").first();
      await expect(textarea).toBeVisible({ timeout: 15000 });

      // 截图 1: 新建会话初始状态（未发送消息前）
      console.log("截图 1: 新建会话初始状态...");
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "01-f07-new-thread-initial.png"),
        fullPage: true,
      });

      // 4. 输入真实大模型问题并发送，同时监听自动标题 API 请求
      const promptText = "请仅用五个字以内概括：什么是量子力学？";
      console.log(`准备发送首轮提问: ${promptText}`);

      const summarizePromise = page.waitForResponse(
        (resp) =>
          resp.url().includes("/title/summarize") &&
          resp.request().method() === "POST",
        { timeout: 90000 },
      );

      await textarea.fill(promptText);
      await textarea.press("Enter");

      // 等待真实模型生成流式输出
      console.log("等待真实大模型回答完成及自动标题提炼响应...");
      const sumResponse = await summarizePromise;
      expect(sumResponse.status()).toBe(200);
      const sumJson = await sumResponse.json();
      console.log("真实大模型自动提炼成功响应:", JSON.stringify(sumJson));
      expect(sumJson.outcome).toBe("applied");
      expect(sumJson.title).toBeTruthy();
      const generatedTitle = sumJson.title;

      // 5. 核心验收点：侧栏标题自动更新 (F01/F02)
      const activeTitleDiv = page
        .locator("button[data-thread-id] .truncate")
        .first();
      await expect(activeTitleDiv).toBeVisible({ timeout: 10000 });
      await expect(activeTitleDiv).toContainText(generatedTitle, {
        timeout: 10000,
      });
      console.log(`侧栏标题已成功同步大模型提炼结果: "${generatedTitle}"`);

      // 等待停止生成按钮消失，确保首轮 Run 彻底收敛
      const stopGenBtn = page.locator(
        'button[title="停止生成"], button:has-text("停止生成")',
      );
      if (await stopGenBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await stopGenBtn
          .waitFor({ state: "detached", timeout: 45000 })
          .catch(() => undefined);
      }
      await page.waitForTimeout(1000);

      // 截图 2: 自动标题提炼成功实景
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "02-f07-auto-title-applied.png"),
        fullPage: true,
      });

      // 6. 核心验收点：用户改名优先与防竞态测试 (F04)
      console.log("触发用户手动改名...");
      const threadGroup = page
        .locator(".group.relative")
        .filter({ has: page.locator('button[title="重命名会话"]') })
        .first();
      await threadGroup.hover();
      await page.waitForTimeout(500);

      const renameBtn = threadGroup
        .locator('button[title="重命名会话"]')
        .first();
      await expect(renameBtn).toBeVisible({ timeout: 5000 });
      await expect(renameBtn).toBeEnabled({ timeout: 5000 });
      await renameBtn.click();

      // 输入自定义标题
      const renameInput = page.locator('input[placeholder="会话标题"]');
      await expect(renameInput).toBeVisible({ timeout: 5000 });
      const customTitle = "老王科研保密项目";
      await renameInput.fill(customTitle);
      await renameInput.press("Enter");
      await page.waitForTimeout(1000);

      // 验证侧栏标题已更新为自定义标题
      await expect(activeTitleDiv).toContainText(customTitle);
      console.log(`用户手动改名成功，当前标题: "${customTitle}"`);

      // 截图 3: 用户自定义改名后实景
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "03-f07-user-renamed.png"),
        fullPage: true,
      });

      // 7. 发送第二轮对话，验证改名不被冲刷覆盖 (F04 防竞态锁死)
      console.log("发送第二轮对话，验证用户标题不会被二次覆盖...");
      await textarea.fill("请再用一句话解释光子。");
      await textarea.press("Enter");

      // 等待第二轮回答收敛
      await page.waitForTimeout(3000);
      if (await stopGenBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await stopGenBtn
          .waitFor({ state: "detached", timeout: 45000 })
          .catch(() => undefined);
      }
      await page.waitForTimeout(2000);

      // 再次断言标题必须依然是用户自定义标题！
      await expect(activeTitleDiv).toContainText(customTitle);
      console.log(
        `第二轮收敛后标题保持用户自定义: "${customTitle}"，竞态保护完全生效！`,
      );

      // 截图 4: 第二轮后改名保护成功实景
      await page.screenshot({
        path: path.join(
          SCREENSHOT_DIR,
          "04-f07-rename-preserved-second-turn.png",
        ),
        fullPage: true,
      });

      // 8. 多视口（1440 / 768 / 390）视觉与响应式验收
      console.log("执行 1440 视口截图...");
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "05-f07-viewport-1440.png"),
        fullPage: true,
      });

      console.log("执行 768 视口截图...");
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "06-f07-viewport-768.png"),
        fullPage: true,
      });

      console.log("执行 390 手机视口截图...");
      await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "07-f07-viewport-390.png"),
        fullPage: true,
      });

      console.log("全链路真实大模型 E2E 自动化闭环验收全部圆满成功！");
    } finally {
      console.log("清理测试 Project Fixture...");
      await fixture.cleanup().catch((err) => {
        console.warn("清理 fixture 忽略错误:", err);
      });
    }
  });
});
