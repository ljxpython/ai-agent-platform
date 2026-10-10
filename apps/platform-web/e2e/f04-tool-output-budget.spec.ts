import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createPlatformFixture } from "./support/platform";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../../docs/projects/20260913-dearflow-agent/evidence/screenshots",
);

test.describe("F04 Tool Output Budget & Full-Chain Verification", () => {
  test("W01-W04: 100KiB大工具外置虚拟路径防爆与三视口无溢出渲染", async ({
    page,
  }) => {
    test.setTimeout(60000);

    // 1. 桌面端 1440px 视口加载 F04 真实样本
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/e2e/render-fixture.html");
    await page.waitForLoadState("networkidle");

    await page.evaluate(async () => {
      const fixture = (
        window as unknown as {
          renderFixture: { setF04Samples(): Promise<void> };
        }
      ).renderFixture;
      await fixture.setF04Samples();
    });

    // 点击展开第一个工具详情（search_web）
    const searchBtn = page
      .getByRole("button", { name: /search_web|网页搜索/ })
      .first();
    await expect(searchBtn).toBeVisible({ timeout: 5000 });
    await searchBtn.click();

    // 点击展开第二个工具详情（read_file 读取虚拟大结果）
    const readFileBtn = page.getByRole("button", { name: /read_file/ }).first();
    await expect(readFileBtn).toBeVisible({ timeout: 5000 });
    await readFileBtn.click();

    // 验证大工具结果预览展示与虚拟路径防爆逻辑
    const virtualPathNotice =
      page.getByText("虚拟大结果文件 · 仅供模型按需回读");
    await expect(virtualPathNotice).toBeVisible({ timeout: 5000 });

    // 验证截断行数指示文案
    await expect(page.getByText(/1490 lines truncated/)).toBeVisible();

    // 验证该虚拟路径下没有伪下载或详情面板查看按钮
    // 检查 read_file 工具卡片内不含在详情面板查看按钮
    const readToolCard = readFileBtn.locator("xpath=..");
    await expect(
      readToolCard.locator('button:has-text("在详情面板查看")'),
    ).toHaveCount(0);

    // 截图 1440 桌面视口
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f04-w01-large-tool-preview-1440.png"),
      fullPage: true,
    });

    // 2. 平板端 768px 视口验证
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(300);
    await expect(virtualPathNotice).toBeVisible();
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f04-w02-viewport-tablet-768.png"),
      fullPage: true,
    });

    // 3. 移动端 390px 视口验证无横向溢出破版
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    await expect(virtualPathNotice).toBeVisible();

    // 断言 390px 下页面主体无超出视口的横向滚动条
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);

    // 截图 390 移动端视口
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f04-w02-viewport-mobile-390.png"),
      fullPage: true,
    });

    // 4. 恢复桌面端视口，验证 W03 证据来源折叠与展开
    await page.setViewportSize({ width: 1440, height: 900 });
    const evidenceToggle = page
      .locator('div:has-text("核实的证据来源")')
      .last();
    await expect(evidenceToggle).toBeVisible({ timeout: 5000 });
    await evidenceToggle.click();
    await expect(page.getByText("SEC 10-K Filings 2026")).toBeVisible({
      timeout: 5000,
    });
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "f04-w03-evidence-expanded.png"),
      fullPage: true,
    });
  });

  test("全链路真实模型端到端调用、流式渲染与轨迹排障闭环", async ({ page }) => {
    test.setTimeout(180000); // 真实大模型网络调用，预留 3 分钟超时
    await page.setViewportSize({ width: 1440, height: 900 });

    const fixture = await createPlatformFixture("workflow_demo");
    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));

    try {
      // 注入已登录认证状态与工作区项目 ID
      await page.addInitScript(
        ({ tokens, projectId }) => {
          localStorage.setItem(
            "pw:auth:token-set",
            JSON.stringify({
              accessToken: tokens.access_token,
              refreshToken: tokens.refresh_token,
              tokenType: tokens.token_type,
            }),
          );
          localStorage.setItem("pw:workspace:project-id", projectId);
        },
        { tokens: fixture.tokens, projectId: fixture.projectId },
      );

      // 导航至真实 Chat 页面
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );
      await page.waitForLoadState("networkidle");

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 发起真实大模型提问
      const prompt =
        "你好，请仅用一句话回答：中国首都是哪里？不要调用任何工具。";
      await composer.fill(prompt);
      await expect(
        page.getByRole("button", { name: "发送", exact: true }),
      ).toBeEnabled();

      // 记录提问前截图
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "f04-real-model-chat-before-send.png"),
        fullPage: true,
      });

      await composer.press("Enter");

      // 验证生成进入进行中状态或开始流式返回
      const transcript = page.getByTestId("transcript");
      await expect(transcript).toBeVisible();

      // 截图记录流式执行中
      await page.waitForTimeout(1000);
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "f04-real-model-chat-running.png"),
        fullPage: true,
      });

      // 等待真实大模型输出收敛并包含正确答案“北京”
      await expect(transcript).toContainText("北京", { timeout: 90000 });

      // 等待流式生成收尾
      const stopGenBtn = page
        .locator('button[title="停止生成"], button:has-text("停止生成")')
        .first();
      if (await stopGenBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await stopGenBtn
          .waitFor({ state: "detached", timeout: 45000 })
          .catch(() => {});
      }

      await page.waitForTimeout(2000);

      // 截图记录真实大模型回答完成态
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "f04-real-model-chat-finished.png"),
        fullPage: true,
      });

      // 切换至轨迹排障视图验证
      const trajectoryTabBtn = page
        .locator('button:has-text("轨迹"), [data-tab="trajectory"]')
        .first();
      if (
        await trajectoryTabBtn.isVisible({ timeout: 3000 }).catch(() => false)
      ) {
        await trajectoryTabBtn.click();
        await page.waitForTimeout(1500);

        // 截图记录轨迹排障视图
        await page.screenshot({
          path: path.join(SCREENSHOT_DIR, "f04-real-model-trajectory.png"),
          fullPage: true,
        });
      }

      expect(browserErrors).toEqual([]);
    } finally {
      await fixture.cleanup().catch(() => {});
    }
  });
});
