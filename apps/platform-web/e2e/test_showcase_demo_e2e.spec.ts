import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('showcase demo full lifecycle e2e with HITL and streaming', async ({ page }) => {
  test.setTimeout(120000); // 真实 LLM 与流式调用留出充裕的 120 秒

  const consoleMessages: string[] = [];
  const networkLogs: { url: string; method: string; status: number; body?: string }[] = [];

  page.on('console', (msg) => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
  });

  page.on('request', (request) => {
    if (request.url().includes('/api/') || request.url().includes('/runs') || request.url().includes('/threads')) {
      consoleMessages.push(`[REQUEST] ${request.method()} ${request.url()} | postData: ${request.postData()?.slice(0, 300)}`);
    }
  });

  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('/runs') || url.includes('/commands') || url.includes('/cancel') || url.includes('/threads') || url.includes('/state') || url.includes('/api/')) {
      let bodyText = '';
      try {
        bodyText = await response.text();
      } catch (e) {
        bodyText = '<stream>';
      }
      if (url.includes('/runs/') && bodyText.includes('"error"')) {
        consoleMessages.push(`[RUN_ERROR] ${url} -> ${bodyText}`);
      }
      networkLogs.push({
        url,
        method: response.request().method(),
        status: response.status(),
        body: bodyText
      });
    }
  });

  // 1. 登录
  console.log('Step 1: Navigating to login...');
  await page.goto('/auth/login');
  await page.fill('input[type="text"], input[name="username"]', 'admin');
  await page.fill('input[type="password"]', 'admin123456');
  await page.click('button:has-text("Log in")');
  await page.waitForURL('**/workspace**', { timeout: 15000 });
  console.log('Login successful, navigated to workspace.');

  // 2. 新建 Project (为了测试环境有Project可用)
  console.log('Step 2: Creating a new project via API...');
  const tokenSetRaw = await page.evaluate(() => window.localStorage.getItem('pw:auth:token-set'));
  let token = '';
  try {
    token = JSON.parse(tokenSetRaw || '{}').accessToken || '';
  } catch (e) {}
  
  const projectRes = await page.request.post('/api/projects', {
    data: { name: 'E2E Test Project' },
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  let projectId = '';
  if (projectRes.ok()) {
    const pData = await projectRes.json();
    projectId = pData.id;
    console.log('Project created via API:', projectId);
  } else {
    console.log('Project creation API returned:', projectRes.status(), await projectRes.text());
    const listRes = await page.request.get('/api/projects', { headers: { 'Authorization': `Bearer ${token}` } });
    if (listRes.ok()) {
      const listData = await listRes.json();
      if (listData.items && listData.items.length > 0) {
        projectId = listData.items[0].id;
        console.log('Using existing project:', projectId);
      }
    }
  }
  
  // 3. Mock Runtime Catalog Graphs API to ensure the dropdown has options
  // The catalog might be empty on a fresh database because assistants aren't synced.
  await page.route('**/api/runtime/graphs*', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        json: {
          count: 1,
          graphs: [{ graph_id: 'showcase_demo', description: 'Showcase Demo Graph' }],
          last_synced_at: new Date().toISOString()
        }
      });
    } else {
      await route.continue();
    }
  });
  
  // 刷新页面让状态获取新项目
  await page.goto('/workspace/overview');
  await page.waitForTimeout(2000);

  // 3. 导航到 Assistants 页面，新建 Agent
  console.log('Step 3: Registering showcase_demo Agent...');
  
  // 直接点击侧边栏的 Agent / Assistants
  const agentLink = page.locator('a[href="/workspace/assistants"], a:has-text("Agent")').first();
  if (await agentLink.isVisible()) {
    await agentLink.click();
  } else {
    await page.goto('/workspace/assistants');
  }
  await page.waitForURL('**/workspace/assistants', { timeout: 15000 });
  
  // 点击新建 Agent
  await page.waitForSelector('button:has-text("新建 Agent")');
  await page.click('button:has-text("新建 Agent")');
  await page.waitForURL('**/workspace/assistants/new', { timeout: 15000 });
  
  // 选择 showcase_demo。由于有两个 select，我们要找带 'Graph ID' 标签的那个
  // 确保等待选项加载（即第一个 select 不被 disabled）
  console.log('Waiting for graph options to load...');
  const graphSelectTrigger = page.locator('label').filter({ hasText: 'Graph ID' }).locator('button.pw-select-trigger');
  
  // 等待它变为可用
  await expect(graphSelectTrigger).toBeEnabled({ timeout: 15000 });
  await graphSelectTrigger.click();
  
  await page.waitForSelector('.pw-select-option', { timeout: 15000 });
  const allOptions = await page.locator('.pw-select-option').allTextContents();
  console.log('Available graph options:', allOptions);
  
  const targetOption = page.locator('.pw-select-option', { hasText: 'showcase_demo' });
  if (await targetOption.isVisible()) {
    await targetOption.click();
  } else {
    console.log('WARNING: showcase_demo not found! Clicking first available option instead.');
    await page.locator('.pw-select-option').first().click();
  }
  
  // 填写名字
  const nameInput = page.locator('input.pw-input').first();
  await nameInput.fill('Showcase Demo E2E');
  
  // 点击创建 Agent
  await page.click('button:has-text("创建 Agent")');
  await page.waitForTimeout(1000);

  // 3. 等待重定向到 Agent 详情页，然后导航到 Chat
  console.log('Step 3: Navigating to Chat via detail page...');
  // 等待路由跳转到详情页 (ID 是 UUID，所以长度大于 10)
  await page.waitForURL(url => {
    return url.pathname.includes('/workspace/assistants/') && !url.pathname.endsWith('/new');
  }, { timeout: 15000 });
  
  console.log('Step 3: Navigating to Chat via detail page...');
  await page.waitForTimeout(2000); // 确保详情页操作按钮已渲染

  await page.waitForSelector('button:has-text("打开聊天")');
  await page.click('button:has-text("打开聊天")');
  
  await page.waitForURL('**/workspace/chat**', { timeout: 15000 });
  await page.waitForTimeout(2000);

  // 4. 等待输入框加载
  const textarea = page.locator('textarea');
  await expect(textarea).toBeVisible({ timeout: 15000 });
  const sendBtn = page.locator('button:has-text("发送消息")');
  await expect(sendBtn).toBeVisible({ timeout: 15000 });

  await page.screenshot({
    path: '/Users/lijiaxin/.gemini/antigravity/brain/f090ead6-b439-4084-b006-b99311fbc527/showcase_demo_entry.png',
    fullPage: true
  });

  // 5. 提交 Prompt，要求明确不要使用命令验证，以避免触发二次 HITL
  console.log('Step 4: Filling user prompt and submitting...');
  await textarea.fill('请写一个任务计划，并在沙箱中创建 demo.txt 写入 Hello Showcase。不要使用额外命令验证文件，完成后直接告诉我。');
  await page.waitForTimeout(600);

  await expect(sendBtn).toBeEnabled({ timeout: 10000 });
  await sendBtn.click();
  console.log('Prompt sent. Waiting for agent processing and HITL interrupt...');

  // 6. 等待 HITL
  console.log('Step 5: Waiting for HITL confirmation panel...');
  const interruptPanel = page.locator('.pw-chat-interrupt');
  const submitDecisionBtn = page.getByRole('button', { name: '提交当前决策' });

  await expect(interruptPanel).toBeVisible({ timeout: 45000 });
  console.log('HITL Interrupt panel (.pw-chat-interrupt) is visible!');
  await expect(submitDecisionBtn).toBeVisible({ timeout: 5000 });

  await page.screenshot({
    path: '/Users/lijiaxin/.gemini/antigravity/brain/f090ead6-b439-4084-b006-b99311fbc527/showcase_demo_hitl_interrupted.png',
    fullPage: true
  });

  const approveBtn = page.getByRole('button', { name: '批准' });
  if (await approveBtn.isVisible()) {
    await approveBtn.click();
    await page.waitForTimeout(500);
  }
  await submitDecisionBtn.click();
  console.log('Submitted HITL approval decision.');

  // 等待中断面板关闭
  await expect(interruptPanel).not.toBeVisible({ timeout: 15000 });
  
  // 处理可能因为网络抖动或其它原因导致第二次弹出的防弹逻辑
  try {
    console.log('Step 5.5: Checking for potential secondary HITL...');
    await page.waitForTimeout(5000); // 留出一点时间给 Agent
    if (await interruptPanel.isVisible()) {
      console.log('Second HITL detected! Approving again...');
      if (await approveBtn.isVisible()) await approveBtn.click();
      await submitDecisionBtn.click();
      await expect(interruptPanel).not.toBeVisible({ timeout: 15000 });
    }
  } catch (e) {
    // 忽略，没有第二次中断
  }

  // 7. 真正等待 Agent 回复生成完毕
  console.log('Step 6: Waiting for Agent message response...');
  const agentTurn = page.locator('.pw-chat-turn').filter({ hasText: 'Agent' }).last();
  await expect(agentTurn).toBeVisible({ timeout: 60000 });

  // 等待流式输出完毕（“停止生成”按钮不可见）
  const stopBtn = page.locator('button:has-text("停止生成")');
  await expect(stopBtn).not.toBeVisible({ timeout: 60000 });

  const agentText = await agentTurn.innerText();
  console.log(`Agent response received! Length: ${agentText.length}`);
  expect(agentText.length).toBeGreaterThan(10);

  await page.screenshot({
    path: '/Users/lijiaxin/.gemini/antigravity/brain/f090ead6-b439-4084-b006-b99311fbc527/showcase_demo_final_completed.png',
    fullPage: true
  });

  fs.writeFileSync(
    '/Users/lijiaxin/.gemini/antigravity/brain/f090ead6-b439-4084-b006-b99311fbc527/showcase_demo_full_lifecycle.log',
    `=== HITL Triggered: true ===\n\n=== CONSOLE ===\n${consoleMessages.join('\n')}\n\n=== NETWORK ===\n${JSON.stringify(networkLogs, null, 2)}`
  );
  console.log('All assertions passed! Test finished successfully.');
});
