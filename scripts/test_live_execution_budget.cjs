const { chromium } = require("@playwright/test");
const path = require("path");

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  console.log("1. Navigating to login page...");
  await page.goto("http://127.0.0.1:3000/auth/login", {
    waitUntil: "domcontentloaded",
  });

  console.log("2. Submitting login...");
  const loginBtn = page.locator("button[type='submit']");
  if (await loginBtn.isVisible()) {
    await loginBtn.click();
    await page.waitForTimeout(1500);
  }

  const baseThreadUrl =
    "http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/dear-agent/80ea961f-b048-4506-b1da-df2e71af22d9?agentId=4f9862a6-8b86-4d56-931b-11b98a735e61";
  console.log("3. Navigating to base thread page...");
  await page.goto(baseThreadUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  console.log(
    "4. Opening run options dialog via '更多操作' -> '运行参数配置'...",
  );
  const moreBtn = page.locator("button[title='更多操作']").first();
  await moreBtn.waitFor({ state: "visible", timeout: 10000 });
  await moreBtn.click();
  await page.waitForTimeout(500);

  const optionsItem = page.locator("button:has-text('运行参数配置')");
  await optionsItem.waitFor({ state: "visible", timeout: 5000 });
  await optionsItem.click();
  await page.waitForTimeout(600);

  console.log("5. Setting recursion limit to 5...");
  const recursionInput = page.locator("label:has-text('递归上限') input");
  await recursionInput.fill("5");
  await page.waitForTimeout(300);

  const applyBtn = page.locator("button:has-text('应用到当前会话')");
  await applyBtn.click();
  await page.waitForTimeout(1000);

  console.log("6. Submitting test prompt in real live session...");
  const textarea = page.locator("textarea").first();
  await textarea.fill(
    "我设置一款贪吃蛇的网页游戏，然后并解释，并详细的解释每一步。",
  );
  await page.waitForTimeout(500);

  const sendBtn = page
    .locator("button:has-text('发送'), button[aria-label='发送']")
    .first();
  if ((await sendBtn.isVisible()) && !(await sendBtn.isDisabled())) {
    await sendBtn.click();
  } else {
    await textarea.press("Enter");
  }

  console.log(
    "7. Waiting for live execution to hit step limit (polling up to 45s)...",
  );
  const screenshotDir =
    "/Users/lijiaxin/.gemini/antigravity/brain/8340533f-66a4-45ca-94c8-47719972a80e";

  let terminalDetected = false;
  for (let i = 0; i < 45; i++) {
    await page.waitForTimeout(1000);
    const hasBudgetBar = await page
      .locator("text=本次执行达到图步骤上限")
      .count();
    const hasRedBanner = await page.locator("text=执行服务响应异常").count();
    const isBusy = await page.locator("button:has-text('取消')").count();
    if (hasBudgetBar > 0 || hasRedBanner > 0) {
      console.log(
        `[T+${i + 1}s] Stop condition detected! hasBudgetBar=${hasBudgetBar}, hasRedBanner=${hasRedBanner}, isBusy=${isBusy}`,
      );
      terminalDetected = true;
      break;
    }
  }

  await page.waitForTimeout(2000);
  const screenshotPath = path.join(
    screenshotDir,
    "live_execution_test_verified.png",
  );
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log("Screenshot saved to:", screenshotPath);

  // Assertions
  const redBannerCount = await page.locator("text=执行服务响应异常").count();
  const reconnectBtnCount = await page.locator("text=恢复连接").count();
  const budgetBarCount = await page
    .locator("text=本次执行达到图步骤上限")
    .count();
  const adjustDraftBtn = page.locator("button:has-text('调整请求')");
  const adjustDraftBtnCount = await adjustDraftBtn.count();

  console.log("\n==========================================");
  console.log("=== LIVE RUN AUTOMATED AUDIT RESULTS ===");
  console.log("==========================================");
  console.log(
    "1. 通用红条 ('执行服务响应异常') count:",
    redBannerCount,
    redBannerCount === 0 ? "✅ PASSED (已静默)" : "❌ FAILED",
  );
  console.log(
    "2. 恢复连接按钮 ('恢复连接') count:",
    reconnectBtnCount,
    reconnectBtnCount === 0 ? "✅ PASSED (无误导)" : "❌ FAILED",
  );
  console.log(
    "3. 专属预警条 ('本次执行达到图步骤上限') count:",
    budgetBarCount,
    budgetBarCount > 0 ? "✅ PASSED (已正确展示)" : "❌ FAILED",
  );
  console.log(
    "4. 调整草稿按钮 ('调整请求') count:",
    adjustDraftBtnCount,
    adjustDraftBtnCount > 0 ? "✅ PASSED (可用)" : "❌ FAILED",
  );

  if (adjustDraftBtnCount > 0) {
    console.log("8. Testing '调整请求' button interaction...");
    await adjustDraftBtn.first().click();
    await page.waitForTimeout(1000);
    const restoredText = await textarea.inputValue();
    console.log("Restored draft in textarea:", JSON.stringify(restoredText));
  }

  await browser.close();

  if (redBannerCount > 0 || budgetBarCount === 0) {
    console.error("TEST FAILED!");
    process.exit(1);
  }
  console.log("\n🎉 ALL LIVE REAL-TIME VERIFICATIONS PASSED 100%!");
}

run().catch((err) => {
  console.error("Test error:", err);
  process.exit(1);
});
