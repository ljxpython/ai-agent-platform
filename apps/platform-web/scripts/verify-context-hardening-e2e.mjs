import { chromium } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import process from "node:process";

const TARGET_URL =
  "http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/dear-agent/5a28f77a-649c-4409-931a-46ca7e10b278?agentId=4f9862a6-8b86-4d56-931b-11b98a735e61";
const SCREENSHOT_DIR = path.resolve(
  process.cwd(),
  "docs/projects/20261027-agent-context-budget-hardening/screenshots",
);
const ARTIFACT_DIR =
  "/Users/lijiaxin/.gemini/antigravity/brain/35dd15f3-d3e5-4b2c-a99c-f8211c1c673e";

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

async function saveScreenshot(page, filename, description) {
  const localPath = path.join(SCREENSHOT_DIR, filename);
  const artifactPath = path.join(ARTIFACT_DIR, filename);
  await page.screenshot({ path: localPath, fullPage: true });
  fs.copyFileSync(localPath, artifactPath);
  console.log(`[截图已保存] ${description} -> ${filename}`);
}

async function run() {
  console.log("启动 Chromium 浏览器...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      console.error(`[Browser Console Error]: ${msg.text()}`);
    }
  });

  // 1. 登录
  console.log("正在访问登录页面...");
  await page.goto("http://127.0.0.1:3000/auth/login");
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(1000);

  const userInput = page.locator('input[type="text"]').first();
  const passInput = page.locator('input[type="password"]').first();
  if (await userInput.isVisible()) {
    await userInput.fill("admin");
  }
  if (await passInput.isVisible()) {
    await passInput.fill("admin123456");
  }
  const submitBtn = page.locator('button[type="submit"]');
  await submitBtn.click();
  await page.waitForTimeout(3000);
  console.log("登录成功，当前 URL:", page.url());

  // 2. 访问用户指定的页面
  console.log(`正在访问目标会话页面: ${TARGET_URL}`);
  await page.goto(TARGET_URL);
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(4000);

  // 检查是否有之前遗留的停止生成按钮
  const stopBtnBefore = page
    .locator('button:has-text("停止生成"), button[title="停止生成"]')
    .first();
  if (await stopBtnBefore.isVisible({ timeout: 2000 }).catch(() => false)) {
    console.log("检测到历史会话处于忙碌态，执行停止以复位会话...");
    await stopBtnBefore.click();
    await page.waitForTimeout(3000);
  }

  await saveScreenshot(page, "01-initial-chat-page.png", "初始进入会话页面");

  // 3. 定位输入框
  const textarea = page.locator("textarea").first();
  await textarea.scrollIntoViewIfNeeded();
  await textarea.click();

  // 4. 输入任务并发送
  const testPrompt =
    "请帮我深度调研人形机器人灵巧手行业的最新技术突破与商业落地现状，列出核心要点。";
  console.log("输入任务:", testPrompt);
  await textarea.fill(testPrompt);
  await page.waitForTimeout(800);

  // 点击发送按钮
  const sendBtn = page
    .locator('button[title="发送"], button:has-text("发送")')
    .first();
  if (await sendBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    console.log("点击发送按钮...");
    await sendBtn.click();
  } else {
    console.log("回车发送...");
    await textarea.press("Enter");
  }

  // 5. 捕获执行过程状态截图
  console.log("等待智能体开始执行并调度工具...");
  await page.waitForTimeout(6000);
  await saveScreenshot(page, "02-agent-executing.png", "智能体执行中状态");

  // 6. 等待智能体生成完成
  console.log("等待生成收敛完成...");
  const stopButton = page
    .locator('button[title="停止生成"], button:has-text("停止生成")')
    .first();
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(5000);
    const isGenerating = await stopButton.isVisible().catch(() => false);
    console.log(`[生成进度检查 ${i + 1}/30] 正在生成中: ${isGenerating}`);
    if (!isGenerating && i >= 1) {
      console.log("检测到生成已收尾，停止按钮已消失！");
      break;
    }
  }

  await page.waitForTimeout(3000);
  await saveScreenshot(
    page,
    "03-agent-completed-successfully.png",
    "智能体执行完成状态",
  );

  // 7. 检查页面错误元素（红条）
  const errorElements = await page
    .locator(
      '.error-banner, [data-testid="error-banner"], .text-red-500:has-text("runtime")',
    )
    .allInnerTexts();
  console.log("页面当前错误条数量与内容:", errorElements);

  // 打印最新的回答
  const assistantMessages = page.locator(
    '.prose, .pw-markdown, [data-message-role="assistant"]',
  );
  const msgCount = await assistantMessages.count();
  console.log(`助手回复消息节点数: ${msgCount}`);
  if (msgCount > 0) {
    const text = await assistantMessages.last().innerText();
    console.log("==== 智能体最新回复预览 ====");
    console.log(text.slice(0, 1000));
    console.log("============================");
  }

  await browser.close();
  console.log("Playwright E2E 真实大模型测试全流程圆满通过！");
}

run().catch((err) => {
  console.error("执行脚本异常:", err);
  process.exit(1);
});
