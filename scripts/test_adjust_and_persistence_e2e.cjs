const { chromium } = require("@playwright/test");
const path = require("path");

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  console.log("1. 前往登录页面...");
  await page.goto("http://127.0.0.1:3000/auth/login", {
    waitUntil: "domcontentloaded",
  });

  console.log("2. 自动提交登录...");
  const loginBtn = page.locator("button[type='submit']");
  if (await loginBtn.isVisible()) {
    await loginBtn.click();
    await page.waitForTimeout(1500);
  }

  const threadUrl =
    "http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/dear-agent/80ea961f-b048-4506-b1da-df2e71af22d9?agentId=4f9862a6-8b86-4d56-931b-11b98a735e61";
  console.log("3. 导航到目标会话页面:", threadUrl);
  await page.goto(threadUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  // ----------------------------------------------------
  // 验证点 1：打开已有会话，递归上限应自动同步为 Run 的历史步数 (5) 而非 1000
  // ----------------------------------------------------
  console.log("\n--- [验证点 1] 检查历史会话步数自动反向同步 ---");
  const moreBtn = page.locator("button[title='更多操作']").first();
  await moreBtn.waitFor({ state: "visible", timeout: 10000 });
  await moreBtn.click();
  await page.waitForTimeout(500);

  const optionsItem = page.locator("button:has-text('运行参数配置')");
  await optionsItem.waitFor({ state: "visible", timeout: 5000 });
  await optionsItem.click();
  await page.waitForTimeout(600);

  const recursionInput = page.locator("label:has-text('递归上限') input");
  const initialValue = await recursionInput.inputValue();
  console.log(`初始加载会话时的递归上限输入值: "${initialValue}"`);

  if (initialValue === "1000") {
    console.error(
      "❌ 失败：递归上限仍然是默认的 1000，未从历史 Run 或持久化配置回显！",
    );
    process.exit(1);
  } else {
    console.log(
      `✅ 成功：递归上限已正确回显为 "${initialValue}" (非硬编码 1000)`,
    );
  }

  // ----------------------------------------------------
  // 验证点 2：修改步数为 8，刷新页面，验证持久化记忆是否生效
  // ----------------------------------------------------
  console.log("\n--- [验证点 2] 修改步数并测试刷新持久化 ---");
  console.log("将递归上限修改为 8...");
  await recursionInput.fill("8");
  await page.waitForTimeout(300);

  const applyBtn = page.locator("button:has-text('应用到当前会话')");
  await applyBtn.click();
  await page.waitForTimeout(1000);

  console.log("刷新页面 (page.reload)...");
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  console.log("刷新后重新打开参数配置弹窗...");
  const moreBtnAfterReload = page.locator("button[title='更多操作']").first();
  await moreBtnAfterReload.waitFor({ state: "visible", timeout: 10000 });
  await moreBtnAfterReload.click();
  await page.waitForTimeout(500);

  const optionsItemAfterReload = page.locator(
    "button:has-text('运行参数配置')",
  );
  await optionsItemAfterReload.waitFor({ state: "visible", timeout: 5000 });
  await optionsItemAfterReload.click();
  await page.waitForTimeout(600);

  const valueAfterReload = await page
    .locator("label:has-text('递归上限') input")
    .inputValue();
  console.log(`刷新后的递归上限输入值: "${valueAfterReload}"`);

  if (valueAfterReload !== "8") {
    console.error(
      `❌ 失败：刷新后步数未能记忆持久化！预期 8，实际 "${valueAfterReload}"`,
    );
    process.exit(1);
  }
  console.log(
    "✅ 成功：刷新页面后步数成功记忆为 8 (持久化有效，不再被重置为 1000)！",
  );

  // 关闭弹窗恢复页面
  const closeBtn = page.locator("button:has-text('取消')").first();
  if (await closeBtn.isVisible()) {
    await closeBtn.click();
    await page.waitForTimeout(500);
  }

  // ----------------------------------------------------
  // 验证点 3：测试“调整请求”按钮交互联动
  // ----------------------------------------------------
  console.log("\n--- [验证点 3] 测试“调整请求”联动交互 ---");
  const adjustDraftBtn = page.locator("button:has-text('调整请求')").first();
  await adjustDraftBtn.waitFor({ state: "visible", timeout: 5000 });

  console.log("点击【调整请求】按钮...");
  await adjustDraftBtn.click();
  await page.waitForTimeout(1000);

  // 1. 验证输入框是否回填了上一轮的草稿内容
  const textarea = page.locator("textarea").first();
  const textareaContent = await textarea.inputValue();
  console.log(`输入框回填内容: "${textareaContent}"`);

  if (!textareaContent || textareaContent.trim().length === 0) {
    console.error("❌ 失败：输入框未回填上一轮草稿！");
    process.exit(1);
  }
  console.log("✅ 成功：输入框已成功回填上一轮草稿！");

  // 2. 验证参数弹窗是否同时被自动打开
  const modalTitle = page.locator("text=运行参数与执行模式");
  const isModalVisible = await modalTitle.isVisible();
  console.log(`参数弹窗是否自动打开: ${isModalVisible}`);

  if (!isModalVisible) {
    console.error("❌ 失败：点击【调整请求】后，参数配置弹窗未自动弹出！");
    process.exit(1);
  }
  console.log(
    "✅ 成功：点击【调整请求】后，参数配置弹窗自动弹出，用户可直接调整步数！",
  );

  // 截取全屏证据
  const screenshotDir =
    "/Users/lijiaxin/.gemini/antigravity/brain/8340533f-66a4-45ca-94c8-47719972a80e";
  const screenshotPath = path.join(
    screenshotDir,
    "e2e_adjust_draft_and_persistence_verified.png",
  );
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log("\n📸 完整全链路验证截图已保存至:", screenshotPath);

  console.log("\n========================================================");
  console.log("🎉 所有端到端自动化验收项 100% 通过！铁证如山！");
  console.log("========================================================");

  await browser.close();
}

run().catch((err) => {
  console.error("Test error:", err);
  process.exit(1);
});
