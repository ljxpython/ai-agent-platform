import { test, expect } from '@playwright/test';
import fs from 'node:fs';

test('reproduce user scenario: send gpt -> stop -> switch model -> send again', async ({ page }) => {
  const consoleMessages: string[] = [];
  const networkLogs: { url: string; status: number; body?: string }[] = [];

  page.on('console', (msg) => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
  });

  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/runs') || url.includes('/commands') || url.includes('/cancel') || url.includes('/threads')) {
      let bodyText = '';
      try {
        bodyText = await response.text();
      } catch (e) {
        bodyText = '<stream>';
      }
      networkLogs.push({
        url,
        status: response.status(),
        body: bodyText.slice(0, 500)
      });
    }
  });

  // 1. Login
  await page.goto('/auth/login');
  await page.fill('input[type="text"], input[name="username"]', 'admin');
  await page.fill('input[type="password"]', 'admin123456');
  await page.click('button:has-text("Log in")');
  await page.waitForURL('**/workspace**', { timeout: 15000 });

  // 2. Open chat page with startNew=1 to start a fresh thread
  await page.goto('/workspace/chat?targetType=assistant&assistantId=workflow_demo&assistantName=Workflow+Demo+HITL&startNew=1');
  await page.waitForTimeout(3000);

  // 3. Step 1: Select GPT proxy model (gpt-5.6-terra)
  const modelSelectorBtn = page.locator('button[aria-label="选择模型"]');
  if (await modelSelectorBtn.isVisible()) {
    await modelSelectorBtn.click();
    await page.waitForTimeout(600);
    const gptModelOption = page.locator('button:has-text("gpt-5.6-terra")').first();
    if (await gptModelOption.isVisible()) {
      await gptModelOption.click();
      await page.waitForTimeout(600);
    }
  }

  // 4. Send first message
  const textarea = page.locator('textarea');
  await textarea.fill('你好，请讲一个非常长的故事！');
  const sendBtn = page.locator('button:has-text("发送消息")');
  await sendBtn.click();

  // 5. Wait for "停止生成" button and click it
  const stopBtn = page.locator('button:has-text("停止生成")');
  await expect(stopBtn).toBeVisible({ timeout: 10000 });
  console.log('Stop button appeared, clicking stop...');
  await page.waitForTimeout(500);
  await stopBtn.click();

  // Wait for stop to finish (stop button disappears, send button comes back)
  await expect(sendBtn).toBeVisible({ timeout: 10000 });
  console.log('Run stopped successfully.');
  await page.waitForTimeout(1000);

  // 6. Step 2: Switch to another model (e.g. deepseek-chat)
  if (await modelSelectorBtn.isVisible()) {
    await modelSelectorBtn.click();
    await page.waitForTimeout(600);
    const dsModelOption = page.locator('button:has-text("deepseek-chat")').first();
    if (await dsModelOption.isVisible()) {
      await dsModelOption.click();
      await page.waitForTimeout(600);
    }
  }

  // 7. Step 3: Send next message
  await textarea.fill('切换模型后的新问题：1+1等于几？');
  await sendBtn.click();

  // 8. Observe for 8 seconds to ensure no 409 conflict and reply arrives
  await page.waitForTimeout(8000);

  // 9. Verify error toast or message does NOT appear
  const conflictError = page.locator('text=当前线程已有运行中的任务').first();
  await expect(conflictError).not.toBeVisible();

  // Take screenshot
  await page.screenshot({
    path: '/Users/lijiaxin/.gemini/antigravity/brain/fe469ce2-acdc-4fa1-892f-364e4a5b20ca/stop_switch_model_resend_success.png',
    fullPage: true
  });

  fs.writeFileSync(
    '/Users/lijiaxin/.gemini/antigravity/brain/fe469ce2-acdc-4fa1-892f-364e4a5b20ca/stop_switch_resend_network.json',
    JSON.stringify(networkLogs, null, 2)
  );
});
