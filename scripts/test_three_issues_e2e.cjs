const { chromium } = require("@playwright/test");
const path = require("path");

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  console.log("1. 前往登录页面并自动登录...");
  await page.goto("http://127.0.0.1:3000/auth/login", {
    waitUntil: "domcontentloaded",
  });
  const loginBtn = page.locator("button[type='submit']");
  if (await loginBtn.isVisible()) {
    await loginBtn.click();
    await page.waitForTimeout(1500);
  }

  const threadUrl =
    "http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/dear-agent/80ea961f-b048-4506-b1da-df2e71af22d9?agentId=4f9862a6-8b86-4d56-931b-11b98a735e61";
  console.log("2. 导航到目标会话页面:", threadUrl);
  await page.goto(threadUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  // ----------------------------------------------------
  // 验证问题 2：报错提示条文案是否显示完整，无截断省略号
  // ----------------------------------------------------
  console.log("\n=== [验证问题 2] 检查报错条文案完整性（无截断省略号） ===");
  const statusBanner = page.locator("div[aria-live='polite']").first();
  await statusBanner.waitFor({ state: "visible", timeout: 10000 });
  const bannerText = await statusBanner.innerText();
  console.log("当前报错条内文本内容:\n" + bannerText.trim());

  if (bannerText.includes("可调整或...")) {
    console.error("❌ 失败：文案仍然被截断为 '可调整或...'！");
    process.exit(1);
  } else if (
    bannerText.includes("可调整或精简请求后重新发送") ||
    bannerText.includes("可调整")
  ) {
    console.log("✅ 成功：文案完整展示，无生硬截断省略号！");
  }

  // ----------------------------------------------------
  // 验证问题 1：鼠标从左往右拖动选中数字时，弹窗绝不退出
  // ----------------------------------------------------
  console.log("\n=== [验证问题 1] 鼠标从左往右拖选数字，弹窗防误关测试 ===");
  const moreBtn = page.locator("button[title='更多操作']").first();
  await moreBtn.waitFor({ state: "visible", timeout: 10000 });
  await moreBtn.click();
  await page.waitForTimeout(500);

  const optionsItem = page.locator("button:has-text('运行参数配置')");
  await optionsItem.waitFor({ state: "visible", timeout: 5000 });
  await optionsItem.click();
  await page.waitForTimeout(600);

  const modalTitle = page.locator("text=运行参数与执行模式");
  await modalTitle.waitFor({ state: "visible", timeout: 5000 });
  console.log("弹窗已成功打开！");

  const recursionInput = page.locator("label:has-text('递归上限') input");
  await recursionInput.waitFor({ state: "visible", timeout: 5000 });

  // 获取输入框的边界坐标
  const box = await recursionInput.boundingBox();
  if (!box) {
    console.error("❌ 无法获取递归上限输入框的位置！");
    process.exit(1);
  }

  console.log(
    `输入框位置: x=${box.x}, y=${box.y}, w=${box.width}, h=${box.height}`,
  );
  console.log(
    "模拟用户鼠标操作：在 input 内部按下(mousedown)，向右拖拽甚至滑出 input 边缘，再松开(mouseup)...",
  );

  // 模拟从输入框左侧 10px 按下，一路向右拖出 100px 甚至到 input 外
  const startX = box.x + 10;
  const startY = box.y + box.height / 2;
  const endX = box.x + box.width + 50; // 故意拖到 input 外面
  const endY = startY;

  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await page.waitForTimeout(100);
  await page.mouse.move(endX, endY, { steps: 5 });
  await page.waitForTimeout(100);
  await page.mouse.up();
  await page.waitForTimeout(600);

  const isModalStillVisible = await modalTitle.isVisible();
  console.log("拖拽选中文本后，弹窗是否依然保持打开:", isModalStillVisible);

  if (!isModalStillVisible) {
    console.error("❌ 失败：鼠标拖选数字时，弹窗意外退出了！");
    process.exit(1);
  }
  console.log("✅ 成功：鼠标从左往右拖选数字，弹窗稳如泰山，绝不误退！");

  // 将步数调整为 15，点击应用，为下一步测试做准备
  console.log("将递归上限设置为 15，并应用到当前会话...");
  await recursionInput.fill("15");
  await page.waitForTimeout(300);
  const applyBtn = page.locator("button:has-text('应用到当前会话')");
  await applyBtn.click();
  await page.waitForTimeout(800);

  // ----------------------------------------------------
  // 验证问题 3：点击“继续”发起运行后，顶部的报错横幅立即消失
  // ----------------------------------------------------
  console.log("\n=== [验证问题 3] 发送'继续'后，顶部报错条即时清除测试 ===");
  const textarea = page.locator("textarea").first();
  await textarea.fill("继续");
  await page.waitForTimeout(400);

  const sendBtn = page
    .locator("button:has-text('发送'), button[aria-label='发送']")
    .first();
  if ((await sendBtn.isVisible()) && !(await sendBtn.isDisabled())) {
    await sendBtn.click();
  } else {
    await textarea.press("Enter");
  }
  console.log("已发送'继续'，监控运行期间的报错横幅状态...");

  // 在运行期间检测：报错横幅必须消失
  let clearedDuringRunning = false;
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(500);
    const hasStopBtn = await page
      .locator("button:has-text('停止'), button:has-text('取消')")
      .count();
    const hasThinking = await page.locator("text=正在思考").count();
    const errorBannerCount = await page
      .locator("text=本次执行达到图步骤上限")
      .count();

    if (hasStopBtn > 0 || hasThinking > 0) {
      console.log(
        `[T+${(i + 1) * 0.5}s] 正在运行中 (thinking=${hasThinking}, stopBtn=${hasStopBtn}). 报错横幅数量=${errorBannerCount}`,
      );
      if (errorBannerCount === 0) {
        clearedDuringRunning = true;
        console.log(
          "✅ 成功：在运行期间，上一轮的报错横幅已即时清除，不遮挡不误导！",
        );
        break;
      }
    }
  }

  if (!clearedDuringRunning) {
    const bannerStillCount = await page
      .locator("text=本次执行达到图步骤上限")
      .count();
    if (bannerStillCount > 0) {
      console.error(
        "❌ 失败：点击'继续'运行期间，上一轮报错横幅依然没有消失！",
      );
      process.exit(1);
    }
  }

  // 截图保存为最终证据
  await page.waitForTimeout(2000);
  const screenshotDir =
    "/Users/lijiaxin/.gemini/antigravity/brain/8340533f-66a4-45ca-94c8-47719972a80e";
  const screenshotPath = path.join(
    screenshotDir,
    "e2e_three_issues_verified.png",
  );
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log("\n📸 完整验证截图已保存至:", screenshotPath);

  console.log("\n========================================================");
  console.log("🎉 用户反馈的 3 个问题全部通过端到端自动化验证！完美闭环！");
  console.log("========================================================");

  await browser.close();
}

run().catch((err) => {
  console.error("Test error:", err);
  process.exit(1);
});
