import { chromium } from "@playwright/test";
import path from "node:path";
import process from "node:process";

const TARGET_URLS = [
  "http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/dear-agent/d98998bf-ebaf-4120-a2a0-2d86fe77db0c?agentId=4f9862a6-8b86-4d56-931b-11b98a735e61",
  "http://127.0.0.1:3000/workspace/projects/5a5b7239-43e3-40e6-bba3-e64d96057607/dear-agent/4af71d7c-73a6-4674-9c4d-ca805289a64d?agentId=4f9862a6-8b86-4d56-931b-11b98a735e61",
];
const ARTIFACT_DIR =
  "/Users/lijiaxin/.gemini/antigravity/brain/35dd15f3-d3e5-4b2c-a99c-f8211c1c673e";

async function verifyUrl(page, targetUrl, index) {
  console.log(
    `\n正在访问会话 [${index + 1}/${TARGET_URLS.length}]: ${targetUrl}`,
  );
  let offloadSeen = false;
  let offloadTexts = [];

  await page.goto(targetUrl);

  const checkInterval = setInterval(async () => {
    try {
      const banner = page.locator(
        ':text("正在整理上下文"), :text("整理上下文"), :text("上下文已整理")',
      );
      const count = await banner.count();
      if (count > 0) {
        for (let i = 0; i < count; i++) {
          const el = banner.nth(i);
          if (await el.isVisible()) {
            offloadSeen = true;
            const text = await el.innerText().catch(() => "");
            if (!offloadTexts.includes(text)) {
              offloadTexts.push(text);
              console.warn(`[WARNING] 检测到整理上下文提示可见: "${text}"`);
            }
          }
        }
      }
    } catch {
      // ignore
    }
  }, 200);

  for (let s = 1; s <= 8; s++) {
    await page.waitForTimeout(1000);
    process.stdout.write(`已监听 ${s}s...\r`);
  }
  clearInterval(checkInterval);
  console.log(`\n会话 [${index + 1}] 监听结束！`);

  const filename = `verify-session-${index + 1}-clean.png`;
  const screenshotPath = path.join(ARTIFACT_DIR, filename);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`[截图已生成] ${screenshotPath}`);

  const lingeringOffload = page.locator(':text("正在整理上下文")');
  const isLingering = await lingeringOffload.isVisible().catch(() => false);

  if (offloadSeen || isLingering) {
    throw new Error(
      `历史 Replay 期间检测到上下文整理浮条闪烁或悬挂！详细文字: ${JSON.stringify(offloadTexts)}`,
    );
  }
  console.log(`✅ 会话 [${index + 1}] 验证通过：无任何历史回放误伤！`);
}

async function run() {
  console.log("启动无头 Chromium 浏览器...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

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
  await page.waitForTimeout(2500);

  for (let i = 0; i < TARGET_URLS.length; i++) {
    await verifyUrl(page, TARGET_URLS[i], i);
  }

  await browser.close();
  console.log("\n🎉 全部历史会话验证通过，状态机免疫验证 100% 达成！");
}

run().catch((err) => {
  console.error("执行脚本异常:", err);
  process.exit(1);
});
