import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";
import { resolve } from "node:path";
import { existsSync } from "node:fs";

const screenshotsDir = resolve(
  process.cwd(),
  "../../docs/projects/20261010-agent-document-reading/screenshots",
);

const sampleDocx = resolve(
  process.cwd(),
  "../../.local-stack/evidence/office/showcase_demo/sample.docx",
);

const samplePptx = resolve(
  process.cwd(),
  "../../.local-stack/evidence/office/dearflow_agent/sample.pptx",
);

test.describe("F10 Office Document Reading & UI Visualization E2E", () => {
  test.beforeAll(() => {
    process.env.PLATFORM_TEST_SEED_MODEL = "1";
  });

  test("01: Showcase DOCX full upload, Agent reading, ToolResult sections projection & screenshot", async ({
    page,
  }) => {
    test.setTimeout(180000);
    expect(existsSync(sampleDocx)).toBe(true);

    const fixture = await createPlatformFixture("showcase_demo");

    try {
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

      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 上传 DOCX 附件
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(sampleDocx);

      // 验证附件卡片出现，并且识别为 Word 文档
      const attachmentCard = page
        .locator(".pw-panel")
        .filter({ hasText: "sample.docx" });
      await expect(attachmentCard).toBeVisible({ timeout: 10000 });
      await expect(attachmentCard).toContainText("Word 文档");

      // 发送消息指令让 Agent 读取
      await composer.fill(
        "请使用 parse_document 读取上传的 sample.docx 方案文档，告诉我文档里的具体内容。",
      );
      const sendBtn = page
        .locator('button[aria-label="发送"], button:has-text("发送")')
        .last();
      await expect(sendBtn).toBeEnabled({ timeout: 15000 });
      await sendBtn.click();
      if ((await composer.inputValue()) !== "") {
        await composer.press("Enter");
      }
      await expect(composer).toHaveValue("", { timeout: 15000 });

      // 等待工具执行完成并返回（真实大模型调用 parse_document）
      const docToolCards = page
        .locator(".pw-tool-call")
        .filter({ hasText: /解析文档|parse_document/ });
      await expect(docToolCards.first()).toBeVisible({ timeout: 90000 });
      const finishedToolCard = docToolCards
        .filter({ hasText: "已返回" })
        .first();
      await expect(finishedToolCard).toBeVisible({ timeout: 90000 });

      // 工具已稳定返回，点击展开卡片
      await finishedToolCard.locator("button").first().click();

      // 验证 DOCX 语义化呈现：sections、命中段落、警告与正文
      await expect(finishedToolCard).toContainText(/DOCX/i, { timeout: 15000 });
      await expect(finishedToolCard).toContainText(/段落|表格|段/, {
        timeout: 15000,
      });

      // 等待回答生成完毕以截取完整长图
      await expect(page.locator('button[aria-label="停止生成"]'))
        .toBeHidden({ timeout: 60000 })
        .catch(() => {});

      // 截图留痕 01
      await page.screenshot({
        path: resolve(screenshotsDir, "01-showcase-docx-success.png"),
        fullPage: true,
      });
    } finally {
      await fixture.cleanup().catch(() => {});
    }
  });

  test("02: DearFlow PPTX upload, slide semantics projection & screenshot", async ({
    page,
  }) => {
    test.setTimeout(180000);
    expect(existsSync(samplePptx)).toBe(true);

    const fixture = await createPlatformFixture("dearflow_agent");

    try {
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

      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 上传 PPTX 附件
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(samplePptx);

      // 验证附件卡片识别为 PPT 演示文稿
      const attachmentCard = page
        .locator(".pw-panel")
        .filter({ hasText: "sample.pptx" });
      await expect(attachmentCard).toBeVisible({ timeout: 10000 });
      await expect(attachmentCard).toContainText("PPT 演示文稿");

      // 发送消息
      await composer.fill(
        "请使用 parse_document 读取上传的 sample.pptx 演示文稿，告诉我幻灯片里的具体内容。",
      );
      const sendBtn = page
        .locator('button[aria-label="发送"], button:has-text("发送")')
        .last();
      await expect(sendBtn).toBeEnabled({ timeout: 15000 });
      await sendBtn.click();
      if ((await composer.inputValue()) !== "") {
        await composer.press("Enter");
      }
      await expect(composer).toHaveValue("", { timeout: 15000 });

      // 等待工具卡片执行完成并返回（真实大模型调用 parse_document）
      const docToolCards = page
        .locator(".pw-tool-call")
        .filter({ hasText: /解析文档|parse_document/ });
      await expect(docToolCards.first()).toBeVisible({ timeout: 90000 });
      const finishedToolCard = docToolCards
        .filter({ hasText: "已返回" })
        .first();
      await expect(finishedToolCard).toBeVisible({ timeout: 90000 });

      // 工具调用已完成，展开工具调用卡片检查投影细节
      const toolToggleBtn = finishedToolCard.locator("button").first();
      await toolToggleBtn.click();

      // 验证 PPTX 幻灯片语义
      await expect(finishedToolCard).toContainText(/PPTX/i, { timeout: 15000 });
      await expect(finishedToolCard).toContainText(/幻灯片/, {
        timeout: 15000,
      });

      // 等待回答生成完毕以截取完整长图
      await expect(page.locator('button[aria-label="停止生成"]'))
        .toBeHidden({ timeout: 60000 })
        .catch(() => {});

      // 截图留痕 02
      await page.screenshot({
        path: resolve(screenshotsDir, "02-dearflow-pptx-success.png"),
        fullPage: true,
      });

      // 03: 刷新页面恢复历史
      await page.reload();
      await expect(composer).toBeVisible({ timeout: 30000 });
      const restoredDocTool = page
        .locator(".pw-tool-call")
        .filter({ hasText: /解析文档|parse_document/ })
        .filter({ hasText: "已返回" })
        .first();
      await expect(restoredDocTool).toBeVisible({ timeout: 30000 });

      // 展开历史工具卡片
      await restoredDocTool.locator("button").first().click();
      await expect(restoredDocTool).toContainText(/PPTX/i, { timeout: 15000 });
      await expect(restoredDocTool).toContainText(/幻灯片/, { timeout: 15000 });

      // 截图留痕 03
      await page.screenshot({
        path: resolve(screenshotsDir, "03-history-restored.png"),
        fullPage: true,
      });
    } finally {
      await fixture.cleanup().catch(() => {});
    }
  });

  test("04: Mobile viewport and dark theme visual inspection & screenshot", async ({
    page,
  }) => {
    test.setTimeout(120000);
    const fixture = await createPlatformFixture("showcase_demo");

    try {
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
          // 切换深色模式
          document.documentElement.classList.add("dark");
        },
        { tokens: fixture.tokens, projectId: fixture.projectId },
      );

      // 移动端视口 375x667
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 上传 DOCX
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles(sampleDocx);

      const attachmentCard = page
        .locator(".pw-panel")
        .filter({ hasText: "sample.docx" });
      await expect(attachmentCard).toBeVisible({ timeout: 10000 });

      // 截图留痕 04: 移动端深色模式无溢出
      await page.screenshot({
        path: resolve(screenshotsDir, "04-mobile-dark-theme.png"),
        fullPage: true,
      });
    } finally {
      await fixture.cleanup().catch(() => {});
    }
  });
});
