import { test, expect } from '@playwright/test';

test('verify sync backend agent and diagnose 403', async ({ page }) => {
  test.setTimeout(60000);

  const networkLogs: Array<{ url: string; method: string; status: number; body?: string }> = [];

  page.on('console', (msg) => {
    console.log(`[BROWSER CONSOLE ${msg.type()}]: ${msg.text()}`);
  });

  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/api/')) {
      let body = '';
      try {
        body = await response.text();
      } catch (e) {
        body = '<failed to read body>';
      }
      networkLogs.push({
        url,
        method: response.request().method(),
        status: response.status(),
        body
      });
      if (response.status() >= 400) {
        console.log(`[HTTP ERROR ${response.status()}] ${response.request().method()} ${url}`);
        console.log(`Response Body: ${body}`);
      }
    }
  });

  // 1. 登录
  console.log('Step 1: Navigating to login...');
  await page.goto('/auth/login');
  await page.fill('input[type="text"], input[name="username"]', 'admin');
  await page.fill('input[type="password"]', 'admin123456');
  await page.click('button:has-text("Log in"), button:has-text("登录")');
  await page.waitForURL('**/workspace**', { timeout: 15000 });
  console.log('Login successful.');

  // 2. 跳转到 /workspace/assistants
  console.log('Step 2: Navigating to /workspace/assistants...');
  await page.goto('/workspace/assistants');
  await page.waitForURL('**/workspace/assistants', { timeout: 15000 });
  await page.waitForTimeout(1000);

  // 3. 截图初始状态
  await page.screenshot({
    path: '/Users/lijiaxin/.gemini/antigravity/brain/f77af44b-093b-4696-8566-55d14d41de08/assistants_initial.png',
    fullPage: true
  });

  // 4. 找到并点击【同步后端 Agent】按钮
  console.log('Step 3: Looking for "同步后端 Agent" button...');
  const syncBtn = page.locator('button', { hasText: '同步后端 Agent' });
  await expect(syncBtn).toBeVisible({ timeout: 10000 });
  console.log('Clicking "同步后端 Agent" button...');
  await syncBtn.click();

  // 5. 等待同步完成：等待按钮解除 disabled/loading 状态，并且页面不显示 403 错误
  console.log('Step 4: Waiting for sync operation to complete...');
  // 等待按钮的 loading spinner 消失，最长等 30 秒
  await expect(syncBtn).toBeEnabled({ timeout: 30000 });
  // 额外缓冲 1 秒确保 DOM 更新和列表渲染完毕
  await page.waitForTimeout(1000);

  // 6. 截图点击后的状态
  await page.screenshot({
    path: '/Users/lijiaxin/.gemini/antigravity/brain/f77af44b-093b-4696-8566-55d14d41de08/assistants_after_sync.png',
    fullPage: true
  });

  // 7. 检查页面上是否有 403 报错
  const errorText = page.locator('text=Request failed with status code 403');
  await expect(errorText).toHaveCount(0);

  // 8. 进入新建页，验证 Graph 下拉框不再置灰且可选
  console.log('Step 5: Navigating to /workspace/assistants/new...');
  await page.goto('/workspace/assistants/new');
  await page.waitForURL('**/workspace/assistants/new', { timeout: 15000 });
  await page.waitForTimeout(1000);

  const graphTrigger = page.locator('.pw-select-trigger').first();
  await expect(graphTrigger).toBeVisible({ timeout: 5000 });
  await expect(graphTrigger).toBeEnabled({ timeout: 5000 });

  // 截图新建 Agent 页面状态
  await page.screenshot({
    path: '/Users/lijiaxin/.gemini/antigravity/brain/f77af44b-093b-4696-8566-55d14d41de08/assistant_create_page.png',
    fullPage: true
  });

  console.log('=== All Network Requests ===');
  for (const log of networkLogs) {
    if (log.url.includes('/api/operations') || log.url.includes('/api/runtime/graphs')) {
      console.log(`[DETAIL] ${log.method} ${log.url} -> ${log.status} | Body: ${log.body}`);
    } else {
      console.log(`${log.method} ${log.url} -> ${log.status} | ${log.body?.slice(0, 100)}`);
    }
  }
});
