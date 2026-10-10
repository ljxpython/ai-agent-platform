/* eslint-disable */
import { chromium } from "@playwright/test";
import { resolve } from "node:path";
import { existsSync, mkdirSync } from "node:fs";

const SCREENSHOT_DIR =
  "/Users/lijiaxin/.codex/worktrees/99f7/ai-agent-platform/docs/projects/20261009-agent-generic-production-capabilities/screenshots";
if (!existsSync(SCREENSHOT_DIR)) {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function run() {
  console.log("启动 Chromium 浏览器...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  // 1. 登录
  console.log("登录...");
  await page.goto("http://127.0.0.1:24335/auth/login");
  await page.waitForLoadState("domcontentloaded");
  await page.locator('input[type="text"]').first().fill("admin");
  await page.locator('input[type="password"]').first().fill("admin123");
  await page.getByRole("button", { name: /log in|登录/i }).click();
  await page.waitForFunction(
    () => !window.location.pathname.startsWith("/auth/login"),
    { timeout: 15000 },
  );

  // 2. 跳转到目标真实会话页面
  const targetUrl =
    "http://127.0.0.1:24335/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/chat/812af807-e17c-44b2-8922-4eb38ecfec98?agentId=cec2267a-d96d-47e0-8363-71b083fd7d1f";
  console.log("跳转到目标会话页面:", targetUrl);
  await page.goto(targetUrl);
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(6000);

  // 3. 定位微胶囊
  const capsule = page.getByTestId("system-task-completion-capsule").first();
  await capsule.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1000);

  // 截图系统微胶囊特写
  const capsuleScreenshotPath = resolve(
    SCREENSHOT_DIR,
    "capsule-close-up-verified.png",
  );
  await capsule.screenshot({ path: capsuleScreenshotPath });
  console.log("微胶囊特写截图已保存至:", capsuleScreenshotPath);

  const artifactCapsulePath =
    "/Users/lijiaxin/.gemini/antigravity/brain/cdf6a04d-60e8-4db0-bd61-4256c89d6731/capsule-close-up-verified.png";
  await capsule.screenshot({ path: artifactCapsulePath });
  console.log("Artifact 微胶囊特写已保存至:", artifactCapsulePath);

  // 展开系统提示词看详情
  const expandSummary = capsule.locator("summary");
  if (await expandSummary.isVisible()) {
    await expandSummary.click();
    await page.waitForTimeout(500);
  }

  // 截图整个包含胶囊与 Agent 回复的对话区域
  const fullPagePath = resolve(
    SCREENSHOT_DIR,
    "real-session-capsule-scrolled.png",
  );
  await page.screenshot({ path: fullPagePath, fullPage: true });
  console.log("完整对话流长图已保存至:", fullPagePath);

  const artifactFullPath =
    "/Users/lijiaxin/.gemini/antigravity/brain/cdf6a04d-60e8-4db0-bd61-4256c89d6731/real-session-capsule-scrolled.png";
  await page.screenshot({ path: artifactFullPath, fullPage: true });

  await browser.close();
  console.log("特写截图完成！");
}

run().catch((err) => {
  console.error("执行出错:", err);
  process.exit(1);
});
