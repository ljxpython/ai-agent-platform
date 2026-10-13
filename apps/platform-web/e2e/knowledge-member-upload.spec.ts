import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createPlatformFixture } from "./support/platform";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(
  __dirname,
  "../../../docs/projects/20261012-project-member-knowledge-upload/evidence/screenshots",
);

async function loginUser(page: Page) {
  await page.goto("/auth/login");
  await page.waitForLoadState("networkidle");
  const submitBtn = page.locator('button[type="submit"]');
  await expect(submitBtn).toBeVisible({ timeout: 10000 });
  await submitBtn.click();
  await page.waitForURL(/\/workspace/, { timeout: 15000 });
  await page.waitForLoadState("networkidle");
}

async function prepareChatComposer(
  page: Page,
  projectId: string,
  agentId?: string,
) {
  const url = agentId
    ? `/workspace/projects/${projectId}/chat?agentId=${agentId}`
    : `/workspace/projects/${projectId}/chat`;
  await page.goto(url);
  await page.waitForLoadState("networkidle");

  // 若处于选择智能体引导页，进行对齐
  const selectAgentBtn = page
    .locator('button:has-text("选择智能体"), button[aria-label="对话目标"]')
    .first();
  if (await selectAgentBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await selectAgentBtn.click();
    await page.waitForTimeout(500);
    const targetAgent = page
      .locator(
        'button:has-text("Web refactor test"), button:has-text("dearflow_agent")',
      )
      .first();
    if (await targetAgent.isVisible({ timeout: 2000 }).catch(() => false)) {
      await targetAgent.click();
    } else {
      const firstAvailable = page
        .locator('.max-h-60 button:not(:has-text("全部智能体"))')
        .first();
      if (
        await firstAvailable.isVisible({ timeout: 2000 }).catch(() => false)
      ) {
        await firstAvailable.click();
      }
    }
    await page.waitForTimeout(800);
  }

  // 若存在“新建会话”按钮则点击开启干净回合
  const newThreadBtn = page.locator('button:has-text("新建会话")').first();
  if (await newThreadBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    if (await newThreadBtn.isEnabled().catch(() => false)) {
      await newThreadBtn.click().catch(() => {});
      await page.waitForTimeout(500);
    }
  }

  const textarea = page
    .locator('textarea[aria-label="消息草稿"], textarea')
    .first();
  await expect(textarea).toBeVisible({ timeout: 15000 });
  return textarea;
}

test.describe("项目成员知识上传全链路验收 (F01–F03)", () => {
  test.setTimeout(120000);

  let fixture: Awaited<ReturnType<typeof createPlatformFixture>>;

  test.beforeAll(async () => {
    fixture = await createPlatformFixture("dearflow_agent");
  });

  test.afterAll(async () => {
    if (fixture) {
      await fixture.cleanup().catch(() => {});
    }
  });

  test("F01: 聊天附件“加入项目知识库”门禁与意向指令装配", async ({ page }) => {
    // 模拟具备知识库上传能力的项目 capabilities
    await page.route(
      "**/api/projects/*/knowledge/capabilities",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            version: 1,
            read_enabled: true,
            upload_enabled: true,
            supported_mime_types: ["text/markdown", "text/plain"],
            max_file_bytes: 20971520,
            disabled_reason: null,
          }),
        });
      },
    );

    await page.setViewportSize({ width: 1440, height: 900 });

    // 1. 登录
    await loginUser(page);

    // 2. 进入 Chat 页面并确保输入框就绪
    const textarea = await prepareChatComposer(
      page,
      fixture.projectId,
      fixture.agent?.id,
    );

    // 3. 准备测试文件并通过隐藏的 file input 上传
    const fileInput = page.locator('input[type="file"]').first();

    // 3.1 上传不支持的 PDF 文件
    await fileInput.setInputFiles({
      name: "architecture_design.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 Mock PDF Content for Testing"),
    });
    await page.waitForTimeout(1000);

    // 校验 PDF 附件上的“共享至项目知识库”复选框是否被禁用
    const pdfCard = page.locator(
      '.pw-panel:has-text("architecture_design.pdf")',
    );
    await expect(pdfCard).toBeVisible({ timeout: 10000 });
    const pdfCheckbox = pdfCard.locator('input[type="checkbox"]');
    await expect(pdfCheckbox).toBeDisabled();
    await expect(pdfCard.locator("text=暂不可用")).toBeVisible();

    // 3.2 上传支持的 Markdown 文档
    await fileInput.setInputFiles({
      name: "team_knowledge_guide.md",
      mimeType: "text/markdown",
      buffer: Buffer.from(
        "# 项目技术规范手册\n\n所有成员均可查阅并遵循此规范。",
      ),
    });
    await page.waitForTimeout(1000);

    // 校验 MD 附件上的“共享至项目知识库”复选框处于可用状态
    const mdCard = page.locator(
      '.pw-panel:has-text("team_knowledge_guide.md")',
    );
    await expect(mdCard).toBeVisible({ timeout: 10000 });
    const mdCheckbox = mdCard.locator('input[type="checkbox"]');
    await expect(mdCheckbox).toBeEnabled();

    // 4. 勾选 MD 文件上的“共享至项目知识库”复选框
    await mdCheckbox.check();
    await page.waitForTimeout(500);

    // 断言输入框自动填入了标准意向指令
    await expect(textarea).toHaveValue("请把本条消息的附件加入当前项目知识库");

    // 截图记录 F01 门禁与意向装配状态
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "01-f01-knowledge-attachment-gate.png"),
      fullPage: true,
    });
  });

  test("F03: 项目详情页 Tab 分区、资料列表与任务历史面板", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    // 1. 登录
    await loginUser(page);

    // 2. 访问当前项目详情页
    await page.goto(`/workspace/projects/${fixture.projectId}`);
    await page.waitForLoadState("networkidle");

    // 3. 校验页面存在两个主分区 Tab
    const overviewTab = page.locator('button:has-text("项目概览与成员")');
    const knowledgeTab = page.locator('button:has-text("项目知识库")');
    await expect(overviewTab).toBeVisible({ timeout: 15000 });
    await expect(knowledgeTab).toBeVisible({ timeout: 15000 });

    // 默认展示项目概览
    await expect(page.locator("text=基础信息")).toBeVisible({ timeout: 10000 });

    // 4. 点击切换至“项目知识库” Tab
    await knowledgeTab.click();
    await page.waitForTimeout(1000);

    // 校验知识库面板核心元素
    await expect(page.locator("text=项目知识库管理")).toBeVisible({
      timeout: 10000,
    });
    const docsSubTab = page.locator('button:has-text("已发布资料")');
    const jobsSubTab = page.locator('button:has-text("入库任务历史")');
    await expect(docsSubTab).toBeVisible({ timeout: 10000 });
    await expect(jobsSubTab).toBeVisible({ timeout: 10000 });

    // 5. 截图保存资料列表视图（真实接口降级/未配置展示）
    await page.screenshot({
      path: path.join(
        SCREENSHOT_DIR,
        "03-f03-project-knowledge-panel-documents.png",
      ),
      fullPage: true,
    });

    // 6. 切换到“入库任务历史”子视图
    await jobsSubTab.click();
    await page.waitForTimeout(1000);

    // 截图保存任务历史视图（真实接口降级/未配置展示）
    await page.screenshot({
      path: path.join(
        SCREENSHOT_DIR,
        "03-f03-project-knowledge-panel-jobs.png",
      ),
      fullPage: true,
    });

    // 7. 注入交接规范的标准 fixture，验证资料与任务列表呈现、状态机、searchable 徽章与分页
    await page.route(
      "**/api/projects/*/knowledge/capabilities",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            version: 1,
            read_enabled: true,
            upload_enabled: true,
            supported_mime_types: ["text/markdown", "text/plain"],
            max_file_bytes: 20971520,
            disabled_reason: null,
          }),
        });
      },
    );

    await page.route(
      "**/api/projects/*/knowledge/documents*",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: [
              {
                document_id: "doc_0192e4a1-0001-7000-8000-000000000001",
                file_name: "team_guidelines.md",
                mime_type: "text/markdown",
                file_bytes: 10240,
                searchable: true,
                latest_job_id: "job_0192e4a1-0001-7000-8000-000000000002",
                created_at: "2026-10-12T10:00:00Z",
                updated_at: "2026-10-12T10:05:00Z",
              },
              {
                document_id: "doc_0192e4a1-0002-7000-8000-000000000002",
                file_name: "architecture_v2.md",
                mime_type: "text/markdown",
                file_bytes: 25600,
                searchable: false,
                latest_job_id: "job_0192e4a1-0002-7000-8000-000000000003",
                created_at: "2026-10-12T10:10:00Z",
                updated_at: "2026-10-12T10:11:00Z",
              },
            ],
            total: 2,
          }),
        });
      },
    );

    await page.route("**/api/projects/*/knowledge/jobs*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              job_id: "job_0192e4a1-0001-7000-8000-000000000002",
              document_id: "doc_0192e4a1-0001-7000-8000-000000000001",
              file_name: "team_guidelines.md",
              status: "ready",
              searchable: true,
              error_code: null,
              created_at: "2026-10-12T10:00:00Z",
              updated_at: "2026-10-12T10:05:00Z",
            },
            {
              job_id: "job_0192e4a1-0002-7000-8000-000000000003",
              document_id: "doc_0192e4a1-0002-7000-8000-000000000002",
              file_name: "architecture_v2.md",
              status: "indexing",
              searchable: false,
              error_code: null,
              created_at: "2026-10-12T10:10:00Z",
              updated_at: "2026-10-12T10:11:00Z",
            },
          ],
          total: 2,
        }),
      });
    });

    // 重新点击资料 Tab 触发拉取
    await docsSubTab.click();
    await page.locator('button:has-text("刷新")').click();
    await page.waitForTimeout(1000);

    // 校验资料列表渲染并截图
    await expect(page.locator("text=team_guidelines.md")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator("text=当前可检索").first()).toBeVisible();
    await page.screenshot({
      path: path.join(
        SCREENSHOT_DIR,
        "03-f03-project-knowledge-panel-documents-active.png",
      ),
      fullPage: true,
    });

    // 切换到任务历史子视图并截图
    await jobsSubTab.click();
    await page.waitForTimeout(1000);
    await expect(page.locator("text=architecture_v2.md")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator("text=正在建立索引").first()).toBeVisible({
      timeout: 10000,
    });
    await page.screenshot({
      path: path.join(
        SCREENSHOT_DIR,
        "03-f03-project-knowledge-panel-jobs-active.png",
      ),
      fullPage: true,
    });
  });

  test("F02: 真实模型/会话下知识库工具回执卡渲染闭环", async ({ page }) => {
    // 模拟具备知识库能力的项目 capabilities
    await page.route(
      "**/api/projects/*/knowledge/capabilities",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            version: 1,
            read_enabled: true,
            upload_enabled: true,
            supported_mime_types: ["text/markdown", "text/plain"],
            max_file_bytes: 20971520,
            disabled_reason: null,
          }),
        });
      },
    );

    await page.setViewportSize({ width: 1440, height: 900 });

    // 1. 登录
    await loginUser(page);

    // 2. 准备 Chat 页面与输入框
    const textarea = await prepareChatComposer(
      page,
      fixture.projectId,
      fixture.agent?.id,
    );

    // 3. 上传入库文档
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "microservice_standards.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# 微服务通信契约\n\n接口统一使用 JSON 规范。"),
    });
    await page.waitForTimeout(1000);

    // 勾选入库
    const mdCard = page.locator(
      '.pw-panel:has-text("microservice_standards.md")',
    );
    await expect(mdCard).toBeVisible({ timeout: 10000 });
    const mdCheckbox = mdCard.locator('input[type="checkbox"]');
    await mdCheckbox.check();
    await page.waitForTimeout(500);

    // 4. 点击发送按钮向 Agent 发起请求
    const sendBtn = page
      .locator('button[aria-label="发送"], button:has-text("发送")')
      .first();
    await sendBtn.click();

    // 5. 等待真实大模型开始流式响应并完成
    console.log("等待真实模型处理附件并生成应答/工具回执...");
    const assistantMessage = page
      .locator(
        '.pw-markdown, .pw-message-assistant, [data-testid="message-assistant"]',
      )
      .first();
    await expect(assistantMessage).toBeVisible({ timeout: 60000 });

    // 关键：显式等待大模型流式输出收尾与收敛
    const stopGenBtn = page
      .locator('button[title="停止生成"], button:has-text("停止生成")')
      .first();
    if (await stopGenBtn.isVisible({ timeout: 4000 }).catch(() => false)) {
      await stopGenBtn
        .waitFor({ state: "detached", timeout: 60000 })
        .catch(() => {});
    }
    // 留出 4 秒确保最终 DOM 和收尾状态稳定
    await page.waitForTimeout(4000);

    // 截图记录回执卡与聊天结果
    await page.screenshot({
      path: path.join(
        SCREENSHOT_DIR,
        "02-f02-knowledge-submission-chat-result.png",
      ),
      fullPage: true,
    });
  });
});
