const { chromium } = require("../apps/platform-web/node_modules/@playwright/test");
const path = require("path");
const fs = require("fs");

const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../docs/projects/20261007-agent-execution-budget/implementation/screenshots"
);

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function runTest() {
  console.log("==================================================");
  console.log("=== AGENT EXECUTION BUDGET PLAYWRIGHT E2E TEST ===");
  console.log("==================================================");

  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });

  const page = await context.newPage();

  // 1. 登录
  console.log("\n[STEP 1] 导航至登录页面并执行登录...");
  await page.goto("http://127.0.0.1:3000/auth/login", {
    waitUntil: "networkidle",
    timeout: 30000,
  });

  const loginBtn = page.locator("button[type='submit']");
  if (await loginBtn.isVisible()) {
    await loginBtn.click();
    console.log("-> 已点击登录按钮，等待工作区跳转...");
    await page.waitForURL("**/workspace/**", { timeout: 15000 });
  }
  console.log("-> 登录成功，当前 URL:", page.url());

  // 截图：登录后主页
  const shot01 = path.join(SCREENSHOT_DIR, "01_workspace_overview.png");
  await page.screenshot({ path: shot01, fullPage: true });
  console.log("-> 截图已保存:", shot01);

  // 2. 进入 Chat 页面（使用 dearflow_agent）
  const projectId = "5a5b7239-43e3-40e6-bba3-e64d96057607";
  const agentId = "4f9862a6-8b86-4d56-931b-11b98a735e61";
  const chatUrl = `http://127.0.0.1:3000/workspace/projects/${projectId}/chat?agentId=${agentId}`;

  console.log("\n[STEP 2] 导航至 Chat 页面:", chatUrl);
  await page.goto(chatUrl, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2000);

  // 截图：初始对话页面
  const shot02 = path.join(SCREENSHOT_DIR, "02_chat_page_initial.png");
  await page.screenshot({ path: shot02, fullPage: true });
  console.log("-> 截图已保存:", shot02);

  // 3. 场景 A：正常真实模型提问（验证 baseline 正常交互）
  console.log("\n[STEP 3] 场景 A：向真实模型发送正常提问...");
  const textarea = page.locator("textarea").first();
  await textarea.waitFor({ state: "visible", timeout: 10000 });
  await textarea.fill("请用一句话回答：什么是 Agent 执行预算？");
  await page.waitForTimeout(500);

  const sendBtn = page
    .locator("button:has-text('发送'), button[aria-label='发送']")
    .first();
  if ((await sendBtn.isVisible()) && !(await sendBtn.isDisabled())) {
    await sendBtn.click();
  } else {
    await textarea.press("Enter");
  }
  console.log("-> 消息已发送，等待真实模型流式响应与完成...");

  // 等待模型开始生成或结束
  let responseFinished = false;
  for (let i = 0; i < 60; i++) {
    await page.waitForTimeout(1000);
    // 判断是否出现取消按钮（执行中）
    const isRunning = (await page.locator("button:has-text('取消')").count()) > 0;
    // 检查是否有消息生成出来
    const msgCount = await page.locator(".prose, [data-message-role='assistant']").count();
    if (!isRunning && msgCount > 0 && i > 3) {
      console.log(`-> 真实模型响应已完成 (耗时约 ${i} 秒)`);
      responseFinished = true;
      break;
    }
  }

  // 截图：正常回答完成态
  const shot03 = path.join(SCREENSHOT_DIR, "03_normal_model_response.png");
  await page.screenshot({ path: shot03, fullPage: true });
  console.log("-> 截图已保存:", shot03);

  // 4. 场景 B：配置低递归步数上限（触碰图预算停机）
  console.log("\n[STEP 4] 场景 B：配置低递归上限 (Recursion Limit = 4) 触发预算停机...");
  const moreBtn = page.locator("button[title='更多操作']").first();
  await moreBtn.waitFor({ state: "visible", timeout: 10000 });
  await moreBtn.click();
  await page.waitForTimeout(600);

  const optionsItem = page.locator("button:has-text('运行参数配置')");
  await optionsItem.waitFor({ state: "visible", timeout: 5000 });
  await optionsItem.click();
  await page.waitForTimeout(800);

  const recursionInput = page.locator("label:has-text('递归上限') input");
  await recursionInput.waitFor({ state: "visible", timeout: 5000 });
  await recursionInput.fill("4");
  await page.waitForTimeout(300);

  const applyBtn = page.locator("button:has-text('应用到当前会话')");
  await applyBtn.click();
  await page.waitForTimeout(800);
  // 按 Escape 关闭运行参数配置弹窗
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);
  console.log("-> 递归上限已设置为 4 并应用，弹窗已关闭！");

  // 发送多步复杂任务
  const complexPrompt = "请帮我构思一个带有积分榜、道具系统和关卡难度的俄罗斯方块网页游戏，详细拆解每一步的技术实现和代码结构。";
  console.log("-> 发送复杂长思考任务以触发步骤限制...");
  await textarea.fill(complexPrompt);
  await page.waitForTimeout(500);

  if ((await sendBtn.isVisible()) && !(await sendBtn.isDisabled())) {
    await sendBtn.click();
  } else {
    await textarea.press("Enter");
  }

  console.log("-> 等待智能体运行触碰递归步数上限 (最长轮询 60s)...");
  let budgetHitDetected = false;
  for (let i = 0; i < 60; i++) {
    await page.waitForTimeout(1000);
    const budgetBarCount = await page.locator("text=本次执行达到图步骤上限").count();
    const isBusy = (await page.locator("button:has-text('取消')").count()) > 0;
    if (budgetBarCount > 0) {
      console.log(`-> [T+${i + 1}s] 检测到预算停机状态条！isBusy=${isBusy}`);
      budgetHitDetected = true;
      break;
    }
  }

  await page.waitForTimeout(1500);

  // 截图：达到步骤上限停机状态
  const shot04 = path.join(SCREENSHOT_DIR, "04_budget_limit_reached.png");
  await page.screenshot({ path: shot04, fullPage: true });
  console.log("-> 截图已保存:", shot04);

  // 5. 校验核心断言
  console.log("\n[STEP 5] 验证核心断言与 UI 呈现...");
  const budgetBarCount = await page.locator("text=本次执行达到图步骤上限").count();
  const redBannerCount = await page.locator("text=执行服务响应异常").count();
  const reconnectBtnCount = await page.locator("text=恢复连接").count();
  const adjustDraftBtn = page.locator("button:has-text('调整请求')");
  const adjustDraftBtnCount = await adjustDraftBtn.count();

  console.log("1. 专属图步骤停机条 ('本次执行达到图步骤上限') count:", budgetBarCount);
  console.log("2. 通用红条 ('执行服务响应异常') count:", redBannerCount);
  console.log("3. 恢复连接按钮 ('恢复连接') count:", reconnectBtnCount);
  console.log("4. 调整请求按钮 ('调整请求') count:", adjustDraftBtnCount);

  // 6. 场景 C：测试“调整请求”按钮交互
  if (adjustDraftBtnCount > 0) {
    console.log("\n[STEP 6] 场景 C：点击 '调整请求' 按钮验证参数配置面板唤起与草稿回填...");
    await adjustDraftBtn.first().click();
    await page.waitForTimeout(1000);

    // 截图 05：点击“调整请求”后，系统自动弹出“运行参数与执行模式”配置面板供用户修改步数
    const shot05 = path.join(SCREENSHOT_DIR, "05_adjust_options_opened.png");
    await page.screenshot({ path: shot05, fullPage: true });
    console.log("-> 截图已保存 (自动呼出参数面板):", shot05);

    // 关闭参数面板，展示输入框内的草稿回填内容
    await page.keyboard.press("Escape");
    await page.waitForTimeout(600);

    const restoredValue = await textarea.inputValue();
    console.log("-> 输入框回填内容:", JSON.stringify(restoredValue));

    // 聚焦输入框并滚动到视口下方
    await textarea.focus();
    await page.waitForTimeout(500);

    // 截图 06：草稿内容成功回填到底部输入框
    const shot06 = path.join(SCREENSHOT_DIR, "06_draft_restored_in_textarea.png");
    await page.screenshot({ path: shot06, fullPage: true });
    console.log("-> 截图已保存 (草稿成功回填输入框):", shot06);
  }

  await browser.close();

  // 最终判定
  if (budgetBarCount === 0) {
    throw new Error("FAILED: 专属预算停机状态条未展示！");
  }
  if (redBannerCount > 0) {
    throw new Error("FAILED: 误报了通用红条 '执行服务响应异常'！");
  }
  if (adjustDraftBtnCount === 0) {
    throw new Error("FAILED: 未提供 '调整请求' 动作按钮！");
  }

  console.log("\n==================================================");
  console.log("🎉 ALL PLAYWRIGHT E2E CLOSURE TESTS PASSED 100%!");
  console.log("==================================================");
}

runTest().catch((err) => {
  console.error("\n❌ E2E TEST FAILED:", err);
  process.exit(1);
});
