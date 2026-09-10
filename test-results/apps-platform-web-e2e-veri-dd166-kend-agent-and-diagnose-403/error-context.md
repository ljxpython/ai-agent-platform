# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: apps/platform-web/e2e/verify_sync_agent.spec.ts >> verify sync backend agent and diagnose 403
- Location: apps/platform-web/e2e/verify_sync_agent.spec.ts:3:1

# Error details

```
Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
Call log:
  - navigating to "/auth/login", waiting until "load"

```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test('verify sync backend agent and diagnose 403', async ({ page }) => {
  4  |   test.setTimeout(60000);
  5  | 
  6  |   const networkLogs: Array<{ url: string; method: string; status: number; body?: string }> = [];
  7  | 
  8  |   page.on('console', (msg) => {
  9  |     console.log(`[BROWSER CONSOLE ${msg.type()}]: ${msg.text()}`);
  10 |   });
  11 | 
  12 |   page.on('response', async (response) => {
  13 |     const url = response.url();
  14 |     if (url.includes('/api/')) {
  15 |       let body = '';
  16 |       try {
  17 |         body = await response.text();
  18 |       } catch (e) {
  19 |         body = '<failed to read body>';
  20 |       }
  21 |       networkLogs.push({
  22 |         url,
  23 |         method: response.request().method(),
  24 |         status: response.status(),
  25 |         body
  26 |       });
  27 |       if (response.status() >= 400) {
  28 |         console.log(`[HTTP ERROR ${response.status()}] ${response.request().method()} ${url}`);
  29 |         console.log(`Response Body: ${body}`);
  30 |       }
  31 |     }
  32 |   });
  33 | 
  34 |   // 1. 登录
  35 |   console.log('Step 1: Navigating to login...');
> 36 |   await page.goto('/auth/login');
     |              ^ Error: page.goto: Protocol error (Page.navigate): Cannot navigate to invalid URL
  37 |   await page.fill('input[type="text"], input[name="username"]', 'admin');
  38 |   await page.fill('input[type="password"]', 'admin123456');
  39 |   await page.click('button:has-text("Log in"), button:has-text("登录")');
  40 |   await page.waitForURL('**/workspace**', { timeout: 15000 });
  41 |   console.log('Login successful.');
  42 | 
  43 |   // 2. 跳转到 /workspace/assistants
  44 |   console.log('Step 2: Navigating to /workspace/assistants...');
  45 |   await page.goto('/workspace/assistants');
  46 |   await page.waitForURL('**/workspace/assistants', { timeout: 15000 });
  47 |   await page.waitForTimeout(1000);
  48 | 
  49 |   // 3. 截图初始状态
  50 |   await page.screenshot({
  51 |     path: '/Users/lijiaxin/.gemini/antigravity/brain/f77af44b-093b-4696-8566-55d14d41de08/assistants_initial.png',
  52 |     fullPage: true
  53 |   });
  54 | 
  55 |   // 4. 找到并点击【同步后端 Agent】按钮
  56 |   console.log('Step 3: Looking for "同步后端 Agent" button...');
  57 |   const syncBtn = page.locator('button', { hasText: '同步后端 Agent' });
  58 |   await expect(syncBtn).toBeVisible({ timeout: 10000 });
  59 |   console.log('Clicking "同步后端 Agent" button...');
  60 |   await syncBtn.click();
  61 | 
  62 |   // 5. 等待请求完成
  63 |   await page.waitForTimeout(4000);
  64 | 
  65 |   // 6. 截图点击后的状态
  66 |   await page.screenshot({
  67 |     path: '/Users/lijiaxin/.gemini/antigravity/brain/f77af44b-093b-4696-8566-55d14d41de08/assistants_after_sync.png',
  68 |     fullPage: true
  69 |   });
  70 | 
  71 |   console.log('=== All Network Requests ===');
  72 |   for (const log of networkLogs) {
  73 |     console.log(`${log.method} ${log.url} -> ${log.status} | ${log.body?.slice(0, 150)}`);
  74 |   }
  75 | });
  76 | 
```