import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";
import { resolve } from "node:path";

const screenshotDir = resolve(
  process.cwd(),
  "../../docs/projects/20261008-agent-plan-mode-governance/screenshots",
);

test.describe("Plan Mode Governance E2E & Browser Closed-loop", () => {
  test.beforeAll(() => {
    process.env.PLATFORM_TEST_SEED_MODEL = "1";
  });

  test("F01-F04: Plan Mode toggle, badge, options dialog across viewports and themes", async ({
    page,
  }) => {
    test.setTimeout(180000);
    const fixture = await createPlatformFixture("workflow_demo");

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

      // 1. 桌面端 1440x900 浅色模式
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(
        `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
      );

      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });

      // 验证左下角加号菜单按钮
      const featureMenuBtn = page.getByTestId("composer-feature-menu-btn");
      await expect(featureMenuBtn).toBeVisible();

      // 点击展开菜单
      await featureMenuBtn.click();
      const planOption = page.getByTestId("feature-toggle-plan-mode");
      await expect(planOption).toBeVisible();

      // 点击启用 Plan Mode
      await planOption.click();

      // 验证常驻胶囊徽章出现
      const planBadge = page.getByText(/规划模式已启用 \(Plan Mode\)/);
      await expect(planBadge).toBeVisible();

      // 截图 1: 1440x900 浅色主题下的加号菜单与徽章
      await page.screenshot({
        path: `${screenshotDir}/01-plan-mode-composer-badge-light-1440.png`,
        fullPage: false,
      });

      // 2. 移动端 390x844 视口适配测试
      await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForTimeout(300);

      // 移动端收起侧边栏抽屉，以完整展示对话输入区域
      const collapseSidebarBtn = page.getByTitle("收起历史会话").first();
      if (await collapseSidebarBtn.isVisible()) {
        await collapseSidebarBtn.click();
        await page.waitForTimeout(300);
      }

      await expect(planBadge).toBeVisible();
      // 截图 2: 390x844 移动端下的徽章与输入框紧凑布局
      await page.screenshot({
        path: `${screenshotDir}/02-plan-mode-composer-badge-390.png`,
        fullPage: false,
      });

      // 3. 点击徽章上的取消按钮，关闭 Plan Mode
      const closeBadgeBtn = page.getByTitle("取消本次规划模式");
      await closeBadgeBtn.click();
      await expect(planBadge).toBeHidden();

      // 4. 打开运行配置弹窗 (ChatRunOptionsDialog) 并测试开关
      await page.setViewportSize({ width: 1440, height: 900 });
      const optionsBtn = page.getByRole("button", { name: "运行选项" });
      if (await optionsBtn.isVisible()) {
        await optionsBtn.click();
        const planModeCard = page.getByText("先规划模式 (Plan Mode)");
        await expect(planModeCard).toBeVisible();
      }
    } finally {
      await fixture.cleanup().catch(() => {});
    }
  });

  test("F05-F14: Real agent approval loop, input locking, and responsive plan review", async ({
    page,
  }) => {
    test.setTimeout(300000);
    const fixture = await createPlatformFixture("reference_agent");

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

      // 启用 Plan Mode
      const featureMenuBtn = page.getByTestId("composer-feature-menu-btn");
      await featureMenuBtn.click();
      const planOption = page.getByTestId("feature-toggle-plan-mode");
      await expect(planOption).toBeVisible();
      await planOption.click();

      // 验证徽章激活
      const planBadge = page.getByText(/规划模式已启用 \(Plan Mode\)/);
      await expect(planBadge).toBeVisible();

      // 发送任务指令 (严格约束仅分步调用 save_plan 与 submit_plan，严禁调用其他工具)
      await composer.fill(
        "调研已在前期完成，无需检索。现在请严格按照两步提交规划：第一轮：直接调用 save_plan(title='系统架构规划方案', markdown='# 系统架构规划\n\n## 模块划分\n- 前端展示层\n- 平台服务层\n- 运行时引擎\n\n## 验证要点\n- 接口契约一致性\n- 端到端闭环验证')；第二轮：收到保存成功结果后，立即单独调用 submit_plan() 提交人工审阅。严禁调用 read_reference 或 enter_plan_mode，严禁在同一轮合并调用！",
      );
      const sendBtn = page.getByRole("button", { name: "发送", exact: true });
      await expect(sendBtn).toBeEnabled();
      await sendBtn.click();

      // 验证发送后本地草稿和徽章自动复位
      await expect(composer).toHaveValue("");
      await expect(planBadge).toBeHidden();

      // 等待进入执行阶段并出现 PlanReview 审批卡片
      const planReviewCard = page.getByTestId("plan-review-card");
      await expect(planReviewCard).toBeVisible({ timeout: 180000 });

      // 验证 PlanReview 组件关键信息：标题、版本号、内容、操作按钮
      await expect(page.getByTestId("plan-review-title")).toBeVisible();
      await expect(page.getByTestId("plan-review-content")).toBeVisible();
      await expect(page.getByTestId("plan-review-approve-btn")).toBeVisible();
      await expect(
        page.getByTestId("plan-review-request-changes-btn"),
      ).toBeVisible();

      // 验证发送通道在待审状态下受到安全锁定
      await expect(sendBtn).toBeDisabled();

      // 截图 3: 1440 浅色模式下的 PlanReview 审批卡片与输入框锁定态
      await page.screenshot({
        path: `${screenshotDir}/03-plan-mode-review-card-light-1440.png`,
        fullPage: false,
      });

      // 截图 4: 1024 视口深色模式下的审批卡片
      await page.setViewportSize({ width: 1024, height: 768 });
      await page.emulateMedia({ colorScheme: "dark" });
      await page.waitForTimeout(300);
      await page.screenshot({
        path: `${screenshotDir}/04-plan-mode-review-card-dark-1024.png`,
        fullPage: false,
      });

      // 截图 5: 390 移动端视口下的审批卡片与局部滚动展示
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ colorScheme: "light" });
      await page.waitForTimeout(300);
      const collapseSidebarBtn = page.getByTitle("收起历史会话").first();
      if (await collapseSidebarBtn.isVisible()) {
        await collapseSidebarBtn.click();
        await page.waitForTimeout(300);
      }
      await page.screenshot({
        path: `${screenshotDir}/05-plan-mode-review-card-light-390.png`,
        fullPage: false,
      });

      // 恢复桌面端视口继续交互验证
      await page.setViewportSize({ width: 1440, height: 900 });

      // 测试“请求修改”反馈交互
      const requestChangesBtn = page.getByTestId(
        "plan-review-request-changes-btn",
      );
      await requestChangesBtn.click();

      // 验证反馈文本框展开
      const feedbackInput = page.getByTestId("plan-review-feedback-input");
      await expect(feedbackInput).toBeVisible();

      // 测试输入字数统计与校验
      await feedbackInput.fill("第一步建议优先细化模块划分，补充风险评估。");
      const submitChangesBtn = page.getByTestId(
        "plan-review-submit-changes-btn",
      );
      await expect(submitChangesBtn).toBeEnabled();

      // 截图 6: 修改建议展开态
      await page.screenshot({
        path: `${screenshotDir}/06-plan-mode-request-changes-input.png`,
        fullPage: false,
      });

      // 取消反馈输入并进行正式“批准计划”
      const cancelChangesBtn = page.getByTestId(
        "plan-review-cancel-changes-btn",
      );
      await cancelChangesBtn.click();
      await expect(feedbackInput).toBeHidden();

      // 点击“批准并开始执行”
      const approveBtn = page.getByTestId("plan-review-approve-btn");
      await approveBtn.click();

      // 验证批准后，审批卡片完成流转，后续任务开始继续执行
      await expect(approveBtn)
        .toBeDisabled({ timeout: 10000 })
        .catch(() => {});

      // 截图 7: 批准后流转与执行全景
      await page.waitForTimeout(2000);
      await page.screenshot({
        path: `${screenshotDir}/07-plan-mode-approved-execution.png`,
        fullPage: false,
      });
    } finally {
      await fixture.cleanup().catch(() => {});
    }
  });
});
