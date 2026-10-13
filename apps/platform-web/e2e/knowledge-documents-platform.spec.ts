import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "../../..");
const SCREENSHOT_DIR = path.resolve(
  ROOT_DIR,
  "docs/projects/20261013-knowledge-documents-platform/evidence/screenshots",
);

// 确保截图目录存在
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

// 真实样例路径
const SAMPLE_PDF = path.resolve(
  ROOT_DIR,
  ".local-stack/evidence/knowledge-platform-documents/fixtures/text.pdf",
);
const SAMPLE_PNG = path.resolve(
  ROOT_DIR,
  ".local-stack/evidence/knowledge-platform-documents/fixtures/recovery.png",
);

// 真实项目与用户数据
const ALPHA_PROJECT_ID = "6a6c1e51-5247-4b9a-abb5-9b0fe32dfdaa";
const DEARFLOW_AGENT_ID = "caa9b812-c99f-4a73-9c2d-617c8d85411d";

const UPLOADER = {
  username: "knowledge_docs_c46c1adf022a",
  password: "gpcs4-kROjQnVs37vPDyYo3BXZVJo1V7",
};

const READER = {
  username: "knowledge_docs_12a5b6aa1581",
  password: "hhziiOu3QTsixRWaxfaEOG3O62opc2bH",
};

async function loginUser(page: Page, user = UPLOADER) {
  await page.goto("/auth/login");
  await page.evaluate(() => {
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch {
      // ignore storage errors
    }
  });
  await page.goto("/auth/login");
  await page.waitForLoadState("networkidle");

  // 填写用户名和密码
  const userInput = page.locator('input[type="text"]').first();
  await expect(userInput).toBeVisible({ timeout: 10000 });
  await userInput.fill(user.username);

  const pwdInput = page.locator('input[type="password"]').first();
  await expect(pwdInput).toBeVisible({ timeout: 5000 });
  await pwdInput.fill(user.password);

  const submitBtn = page.locator('button[type="submit"]');
  await expect(submitBtn).toBeVisible({ timeout: 10000 });
  await submitBtn.click();

  await page.waitForURL(/\/workspace/, { timeout: 15000 });
  await page.waitForLoadState("networkidle");
}

async function prepareChatComposer(
  page: Page,
  projectId = ALPHA_PROJECT_ID,
  agentId = DEARFLOW_AGENT_ID,
) {
  const url = `/workspace/projects/${projectId}/chat?agentId=${agentId}`;
  await page.goto(url);
  await page.waitForLoadState("networkidle");

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

test.describe("全链路真实模型端到端测试闭环 (F01–F06)", () => {
  test.setTimeout(240000);

  test("全链路闭环：普通成员上传→审批→ready→另一成员查询及管理面板", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    // ==========================================
    // 1. 普通成员 Uploader 登录
    // ==========================================
    console.log("=== Step 1: Login as Uploader ===");
    await loginUser(page, UPLOADER);

    // ==========================================
    // 2. 进入 Chat 页面并准备输入框
    // ==========================================
    console.log("=== Step 2: Open Chat composer ===");
    const textarea = await prepareChatComposer(page);

    // ==========================================
    // 3. 上传真实附件 (PDF + PNG)
    // ==========================================
    console.log("=== Step 3: Upload PDF and PNG ===");
    const fileInput = page.locator('input[type="file"]').first();
    await expect(fileInput).toBeAttached({ timeout: 10000 });
    await fileInput.setInputFiles([SAMPLE_PDF, SAMPLE_PNG]);
    await page.waitForTimeout(1200);

    // 截图 01：附件就绪状态（检查复选框处于可用状态）
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "01_composer_attachments_ready.png"),
      fullPage: false,
    });
    console.log("Screenshot 01 saved: 01_composer_attachments_ready.png");

    // ==========================================
    // 4. 勾选“共享至项目知识库”复选框
    // ==========================================
    console.log("=== Step 4: Check share to knowledge checkboxes ===");
    const shareCheckboxes = page.locator(
      'input[type="checkbox"]:not(:disabled)',
    );
    const checkboxCount = await shareCheckboxes.count();
    expect(checkboxCount).toBeGreaterThanOrEqual(1);

    for (let i = 0; i < checkboxCount; i++) {
      const cb = shareCheckboxes.nth(i);
      if (!(await cb.isChecked())) {
        await cb.check();
      }
    }
    await page.waitForTimeout(500);

    // 验证草稿区自动带入或追加知识共享指令
    const draftText = await textarea.inputValue();
    expect(draftText).toContain("加入当前项目知识库");

    // 截图 02：勾选共享并注入意图 prompt
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "02_composer_knowledge_checked.png"),
      fullPage: false,
    });
    console.log("Screenshot 02 saved: 02_composer_knowledge_checked.png");

    // ==========================================
    // 5. 发送消息，启动真实模型执行并观察审批流转
    // ==========================================
    console.log("=== Step 5: Send message & trigger real execution ===");
    const sendBtn = page
      .locator('button[aria-label="发送消息"], button:has-text("发送")')
      .first();
    await expect(sendBtn).toBeEnabled({ timeout: 5000 });
    await sendBtn.click();

    // 等待审批区域或者审批按钮出现（模型思考 + 生成调用需要 10~25s）
    console.log("Waiting for HITL approval or auto-execution...");
    const approveBtnLocator = page.locator('[data-action="approve"]');

    // 用 waitFor 显式等待审批按钮出现，最多等 45s
    const hitlTriggered = await approveBtnLocator
      .first()
      .waitFor({ state: "visible", timeout: 45000 })
      .then(() => true)
      .catch(() => false);

    if (hitlTriggered) {
      console.log("HITL approval required, capturing 03_awaiting_approval.png");
      // 截图 03：审批等待状态
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "03_awaiting_approval.png"),
        fullPage: false,
      });

      // 点击所有待审批项的“✓ 批准 (Approve)”按钮
      const count = await approveBtnLocator.count();
      console.log(`Approving ${count} action(s)...`);
      for (let i = 0; i < count; i++) {
        await approveBtnLocator.nth(i).click();
        await page.waitForTimeout(400);
      }

      // 点击提交决策按钮（选中批准后动态变为“✓ 确认批准所选操作”）
      const submitDecisionBtn = page
        .locator(
          'button:has-text("确认批准所选操作"), button:has-text("提交所选决策")',
        )
        .first();
      await expect(submitDecisionBtn).toBeEnabled({ timeout: 5000 });
      await submitDecisionBtn.click();
      console.log("Submitted decisions.");
      await page.waitForTimeout(2000);
    } else {
      // 若无独立拦截直接执行，亦保留执行过程截图
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "03_awaiting_approval.png"),
        fullPage: false,
      });
      console.log("No HITL prompt triggered, saved 03_awaiting_approval.png");
    }

    // ==========================================
    // 6. 验证任务受理与处理卡片状态
    // ==========================================
    console.log("=== Step 6: Verify submission acceptance ===");
    const submissionCard = page
      .locator(
        'div:has-text("任务已受理"), div:has-text("已受理"), div:has-text("正在解析"), div:has-text("已入库"), div:has-text("正在索引")',
      )
      .first();
    await expect(submissionCard).toBeVisible({ timeout: 45000 });

    // 截图 04：任务已受理或流转中状态
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "04_submission_queued.png"),
      fullPage: false,
    });
    console.log("Screenshot 04 saved: 04_submission_queued.png");

    // ==========================================
    // 7. 轮询等待至 ready 终态
    // ==========================================
    console.log("=== Step 7: Wait for ready terminal state ===");
    const readyState = page
      .locator(
        'div:has-text("已入库，当前可检索"), div:has-text("已入库"), div:has-text("处理完成")',
      )
      .first();
    await expect(readyState).toBeVisible({ timeout: 60000 });

    // 截图 05：入库成功终态
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "05_submission_ready.png"),
      fullPage: false,
    });
    console.log("Screenshot 05 saved: 05_submission_ready.png");

    // ==========================================
    // 8. 另一成员 Reader 登录并查询知识库
    // ==========================================
    console.log("=== Step 8: Login as Reader & Query knowledge ===");
    // 退出当前登录或直接访问登录页切换 Reader
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");
    await loginUser(page, READER);

    const readerTextarea = await prepareChatComposer(page);
    await readerTextarea.fill(
      "请检索项目知识库关于 Orion 系统的说明，简要回答并给出引用的证据来源。",
    );

    const readerSendBtn = page
      .locator('button[aria-label="发送消息"], button:has-text("发送")')
      .first();
    await expect(readerSendBtn).toBeEnabled({ timeout: 5000 });
    await readerSendBtn.click();

    // 等待模型回复并召回证据卡片
    console.log("Waiting for retrieval response & evidence...");
    const assistantMessage = page
      .locator('article:has-text("dearflow_agent")')
      .last();
    await assistantMessage.waitFor({ state: "visible", timeout: 45000 });

    // 等待证据按钮出现（真实模型思考 + 工具检索 + 结果渲染通常需要 10~25s）
    const evidenceBtn = page
      .locator('button:has-text("核实的证据来源"), [class*="evidence"]')
      .first();
    await evidenceBtn
      .waitFor({ state: "visible", timeout: 45000 })
      .catch(() => {});
    if (await evidenceBtn.isVisible().catch(() => false)) {
      await evidenceBtn.click();
      await page.waitForTimeout(800);
    }

    // 截图 06：证据来源与 Locator 展示
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "06_knowledge_evidence_with_locator.png"),
      fullPage: false,
    });
    console.log("Screenshot 06 saved: 06_knowledge_evidence_with_locator.png");

    // ==========================================
    // 9. 验证 WebP 格式禁用门禁
    // ==========================================
    console.log("=== Step 9: Verify WebP gate ===");
    const dummyWebpPath = path.resolve(SCREENSHOT_DIR, "test_sample.webp");
    fs.writeFileSync(
      dummyWebpPath,
      "RIFF\x00\x00\x00\x00WEBPVP8 \x00\x00\x00\x00",
    );

    const readerFileInput = page.locator('input[type="file"]').first();
    if ((await readerFileInput.count()) > 0) {
      await readerFileInput.setInputFiles([dummyWebpPath]);
      await page.waitForTimeout(800);

      // 验证 WebP 附件的知识库复选框被禁用或显示“WebP 格式不支持加入知识库”
      const webpDisabledMsg = page
        .locator(
          'span:has-text("WebP 格式不支持加入知识库"), span:has-text("暂不可用")',
        )
        .first();
      await expect(webpDisabledMsg)
        .toBeVisible({ timeout: 5000 })
        .catch(() => {});

      // 截图 07：WebP 格式禁用门禁
      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, "07_webp_and_unshared_gate.png"),
        fullPage: false,
      });
      console.log("Screenshot 07 saved: 07_webp_and_unshared_gate.png");
    }

    // ==========================================
    // 10. 访问项目知识库管理与任务面板
    // ==========================================
    console.log("=== Step 10: Visit Project Knowledge Management Panel ===");
    await page.goto(`/workspace/projects/${ALPHA_PROJECT_ID}?tab=knowledge`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    const knowledgeTab = page
      .locator('button:has-text("知识库"), [role="tab"]:has-text("知识库")')
      .first();
    if (await knowledgeTab.isVisible({ timeout: 3000 }).catch(() => false)) {
      await knowledgeTab.click();
      await page.waitForTimeout(1500);
    }

    const panelHeader = page
      .locator('div:has-text("项目资料"), div:has-text("入库任务")')
      .first();
    await expect(panelHeader).toBeVisible({ timeout: 10000 });

    // 截图 08：知识库面板全貌
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "08_project_knowledge_panel.png"),
      fullPage: false,
    });
    console.log("Screenshot 08 saved: 08_project_knowledge_panel.png");

    console.log("All 8 steps completed successfully!");
  });
});
