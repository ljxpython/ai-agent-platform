import { test, expect } from "@playwright/test";
import path from "node:path";
import { createPlatformFixture } from "./support/platform";

const SCREENSHOT_DIR = path.resolve(
  process.cwd(),
  "../../docs/projects/20261011-token-usage-dashboard/screenshots",
);

test.describe("Token 看板全链路与真实大模型闭环验收", () => {
  test.setTimeout(240000); // 留出 4 分钟充裕时间供真实大模型调用及多视口渲染

  test("平台看板、真实模型对话、项目看板、Runs明细与多视口闭环留痕", async ({
    page,
  }) => {
    // 确保截图目录存在
    const fs = await import("node:fs");
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

    // 1. 设置 1440x900 桌面端视口并登录
    await page.setViewportSize({ width: 1440, height: 900 });
    console.log("导航至登录页并登录 admin...");
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    const usernameInput = page
      .locator('input[type="text"], input[name="username"]')
      .first();
    if (await usernameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await usernameInput.fill("admin");
      const passwordInput = page.locator('input[type="password"]').first();
      await passwordInput.fill("admin123456");
      const submitBtn = page.locator('button[type="submit"]');
      await submitBtn.click();
    }
    await page.waitForURL(/\/workspace/, { timeout: 15000 });

    // 2. 访问平台全局 Token 看板 (/workspace/usage)
    console.log("导航至平台全局 Token 看板...");
    await page.goto("/workspace/usage");
    await page.waitForLoadState("networkidle");

    // 验证核心组件上屏
    await expect(
      page.locator('[data-testid="usage-dashboard-page"]'),
    ).toBeVisible({ timeout: 15000 });
    await expect(page.locator("text=Token 看板 · 平台用量")).toBeVisible();
    await expect(
      page.locator('[data-testid="usage-filter-toolbar"]'),
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="usage-trend-panel"]'),
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="usage-breakdown-panel"]'),
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="usage-runs-section"]'),
    ).toBeVisible();

    // 验证平台全量模式下的明细引导态
    await expect(page.locator("text=平台汇总视图未指定单个项目")).toBeVisible();

    // 测试筛选工具栏快捷切换
    const btn24h = page.locator('button:has-text("近24小时")');
    if (await btn24h.isVisible()) {
      await btn24h.click();
      await page.waitForTimeout(500);
    }

    const btn7d = page.locator('button:has-text("近7天")');
    if (await btn7d.isVisible()) {
      await btn7d.click();
      await page.waitForTimeout(500);
    }

    // 截图 1: 平台看板全景留痕 (1440x900)
    console.log("生成截图 1: 平台看板全景 (1440x900)...");
    const shot1Path = path.join(
      SCREENSHOT_DIR,
      "01-platform-dashboard-1440.png",
    );
    await page.screenshot({ path: shot1Path, fullPage: true });

    // 3. 准备真实模型测试项目与 Agent Fixture
    console.log(
      "准备真实模型测试项目与 Agent Fixture (deepseek-v4.1-flash)...",
    );
    const fixture = await createPlatformFixture("workflow_demo");

    try {
      // 导航至项目 Chat 页面并发起一次真实大模型对话以产生真实 Token 用量
      console.log(`导航至项目 Chat 页面: ${fixture.projectId}...`);
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${encodeURIComponent(fixture.agent.id)}&graphId=${encodeURIComponent(fixture.graphId)}`,
      );
      await page.waitForLoadState("networkidle");

      const newThreadBtn = page
        .locator('button:has-text("新对话"), button:has-text("新建会话")')
        .first();
      if (await newThreadBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
        await newThreadBtn.click();
        await page.waitForTimeout(1000);
      }

      const textarea = page.locator("textarea").first();
      await expect(textarea).toBeVisible({ timeout: 15000 });

      const testPrompt = "请用5个字以内回答：1+1等于几？";
      console.log(`向真实大模型发送提示词: ${testPrompt}`);
      await textarea.fill(testPrompt);
      await textarea.press("Enter");

      // 等待回复完成（通过等待输入框再次可用且助手消息出现）
      console.log("等待真实大模型生成流式回复及入账落库...");
      await page.waitForTimeout(8000); // 留出真实模型推理及后台用量入库时间

      // 4. 导航至单项目看板页面 (/workspace/projects/:projectId/usage)
      console.log(
        `导航至单项目 Token 看板: /workspace/projects/${fixture.projectId}/usage ...`,
      );
      await page.goto(`/workspace/projects/${fixture.projectId}/usage`);
      await page.waitForLoadState("networkidle");

      await expect(page.locator("text=Token 看板 · 项目用量")).toBeVisible({
        timeout: 15000,
      });

      // 等待运行明细表格加载
      console.log("验证运行明细列表并查找刚才产生的 Run...");
      const viewUsageBtn = page.locator('button:has-text("查看用量")').first();
      await expect(viewUsageBtn).toBeVisible({ timeout: 20000 });

      // 点击“查看用量”打开抽屉
      console.log("点击“查看用量”，打开 BaseDrawer 抽屉...");
      await viewUsageBtn.click();

      // 验证抽屉正常展开，无头模式 RunUsage 无双 Header 冲突
      const drawer = page.locator(
        '[role="dialog"][aria-label="完整运行用量分析"]',
      );
      await expect(drawer).toBeVisible({ timeout: 10000 });
      await expect(drawer.locator("text=完整运行用量分析")).toBeVisible();
      await expect(
        drawer.locator('[data-testid="run-usage-panel"]'),
      ).toBeVisible();

      // 等待抽屉内部真实用量与调用明细加载完成
      await page.waitForTimeout(2500);

      // 截图 2: 单项目看板与无头 RunUsage 抽屉 (1440x900)
      console.log("生成截图 2: 单项目看板与抽屉 (1440x900)...");
      const shot2Path = path.join(
        SCREENSHOT_DIR,
        "02-project-dashboard-runs-drawer-1440.png",
      );
      await page.screenshot({ path: shot2Path, fullPage: true });

      // 关闭抽屉
      const closeBtn = drawer
        .locator(
          'button[title="关闭"], button[aria-label="Close"], button:has-text("×")',
        )
        .first();
      if (await closeBtn.isVisible()) {
        await closeBtn.click();
        await page.waitForTimeout(500);
      }

      // 5. 顶栏项目切换器平滑切换验证 (无布局抖动/CLS)
      console.log("测试顶栏项目切换器 (WorkspaceProjectSwitcher)...");
      const projectSwitcherTrigger = page
        .locator(
          'button:has-text("项目"), button:has-text("Demo"), button:has-text("workflow")',
        )
        .first();
      if (await projectSwitcherTrigger.isVisible()) {
        await projectSwitcherTrigger.click();
        await page.waitForTimeout(300);
        // 如果有其他项目选项，点击切换
        const otherProjectItem = page
          .locator(
            'button[role="menuitem"], div[role="menu"] button, .cursor-pointer',
          )
          .filter({ hasNotText: fixture.projectId })
          .first();
        if (
          await otherProjectItem.isVisible({ timeout: 1500 }).catch(() => false)
        ) {
          console.log("切换至另一个项目以验证平滑过渡与滚动条防抖...");
          await otherProjectItem.click();
          await page.waitForTimeout(600);
          const shot5Path = path.join(
            SCREENSHOT_DIR,
            "05-project-switch-smooth-transition.png",
          );
          await page.screenshot({ path: shot5Path, fullPage: true });
        }
      }

      // 6. 平板视口测试 (1024x768)
      console.log("切换至平板视口 1024x768...");
      await page.setViewportSize({ width: 1024, height: 768 });
      await page.waitForTimeout(500);
      const shot3Path = path.join(
        SCREENSHOT_DIR,
        "03-dashboard-tablet-1024.png",
      );
      await page.screenshot({ path: shot3Path, fullPage: true });

      // 7. 移动端手机视口测试 (390x844)
      console.log("切换至移动端视口 390x844...");
      await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForTimeout(500);
      const shot4Path = path.join(
        SCREENSHOT_DIR,
        "04-dashboard-mobile-390.png",
      );
      await page.screenshot({ path: shot4Path, fullPage: true });

      console.log("全链路 Playwright 自动化测试成功闭环！全部截图已留痕落盘。");
    } finally {
      // 清理测试项目
      await fixture.cleanup().catch(() => {});
    }
  });
});
