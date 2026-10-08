const { chromium } = require("@playwright/test");
const path = require("path");
const fs = require("fs");

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  console.log("1. Navigating to login page...");
  await page.goto("http://127.0.0.1:3000/auth/login", { waitUntil: "networkidle" });

  console.log("2. Submitting login...");
  const loginBtn = await page.locator("button[type='submit']");
  if (await loginBtn.isVisible()) {
    await loginBtn.click();
    await page.waitForNavigation({ waitUntil: "networkidle" }).catch(() => {});
  }
  await page.waitForTimeout(1000);

  const targetUrl = "http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/dear-agent/80ea961f-b048-4506-b1da-df2e71af22d9?agentId=4f9862a6-8b86-4d56-931b-11b98a735e61";
  console.log("3. Navigating to target thread page:", targetUrl);
  await page.goto(targetUrl, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);

  const screenshotDir = "/Users/lijiaxin/.gemini/antigravity/brain/8340533f-66a4-45ca-94c8-47719972a80e";
  const screenshotPath = path.join(screenshotDir, "thread_80ea961f_result.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log("Screenshot saved to:", screenshotPath);

  // Check DOM elements
  const redBanner = page.locator("text=执行服务响应异常");
  const redBannerCount = await redBanner.count();
  console.log("Red banner ('执行服务响应异常') count:", redBannerCount);

  const reconnectBtn = page.locator("text=恢复连接");
  const reconnectBtnCount = await reconnectBtn.count();
  console.log("Reconnect button ('恢复连接') count:", reconnectBtnCount);

  const budgetBar = page.locator("text=本次执行达到图步骤上限");
  const budgetBarCount = await budgetBar.count();
  console.log("Budget bar ('本次执行达到图步骤上限') count:", budgetBarCount);

  const adjustDraftBtn = page.locator("text=调整请求");
  const adjustDraftBtnCount = await adjustDraftBtn.count();
  console.log("Adjust draft button ('调整请求') count:", adjustDraftBtnCount);

  await browser.close();
}

run().catch((err) => {
  console.error("Test error:", err);
  process.exit(1);
});
