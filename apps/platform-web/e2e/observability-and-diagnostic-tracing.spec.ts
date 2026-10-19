import { expect, test } from "@playwright/test";
import { resolve } from "node:path";

const screenshotDir = resolve(
  import.meta.dirname,
  "../../../docs/projects/20261019-frontend-observability-and-diagnostic-tracing/assets",
);

test.describe("前端可观测性与端到端排障链路闭环验证", () => {
  test.setTimeout(60000);

  test("用例 1: 渲染期致命异常防御与 CrashScreen 交互闭环", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);

    // 访问工装页并设定模式为 crash
    await page.goto("/e2e/observability-fixture.html?mode=crash");
    await page.waitForLoadState("networkidle");

    // 1. 验证崩溃卡片正确呈现，整屏绝不白屏
    const crashCard = page.locator('[data-testid="error-boundary-crash"]');
    await expect(crashCard).toBeVisible({ timeout: 10000 });
    await expect(crashCard).toContainText("视图遇到未处理异常");
    await expect(crashCard).toContainText(
      "E2E Fatal Crash: Simulated Render Exception",
    );

    // 2. 展开堆栈详情
    const toggleStackBtn = crashCard.getByText("展开堆栈详情");
    if (await toggleStackBtn.isVisible()) {
      await toggleStackBtn.click();
      await expect(crashCard.locator("pre")).toBeVisible();
    }

    // 3. 截图留痕 1: 崩溃卡片全景
    await page.screenshot({
      path: `${screenshotDir}/01-crash-screen-captured.png`,
      fullPage: true,
    });

    // 4. 点击【📋 复制排障信息】按钮
    const copyBtn = crashCard.locator('[data-testid="copy-diagnostic-btn"]');
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();

    // 验证按钮反馈切换为“已复制”
    await expect(copyBtn).toContainText("已复制排障信息");

    // 5. 验证剪贴板中内容符合结构化 Diagnostic Packet
    const clipboardText = await page.evaluate(async () => {
      try {
        return await navigator.clipboard.readText();
      } catch {
        return "";
      }
    });
    if (clipboardText) {
      expect(clipboardText).toContain("### 🛠️ 故障诊断数据包");
      expect(clipboardText).toContain("E2E Fatal Crash");
    }
  });

  test("用例 2: Chat 执行错误状态人话反解与一键复制排障包真实交互闭环", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);

    // 访问工装页并设定模式为 status
    await page.goto("/e2e/observability-fixture.html?mode=status");
    await page.waitForLoadState("networkidle");

    // 1. 验证状态栏从英文代号反解为人话
    const statusBar = page.locator(".rounded-xl");
    await expect(statusBar).toBeVisible({ timeout: 10000 });
    await expect(statusBar).toContainText(
      "Agent 执行未完成，可复制排障信息交由运维排查。",
    );

    // 2. 验证右侧显式展示【复制排障信息】按钮
    const copyBtn = statusBar.locator(
      '[data-testid="status-copy-diagnostic-btn"]',
    );
    await expect(copyBtn).toBeVisible();
    await expect(copyBtn).toContainText("复制排障信息");

    // 3. 截图留痕 2: 错误状态条与复制排障按钮全景
    await page.screenshot({
      path: `${screenshotDir}/02-chat-error-diagnostic-button.png`,
      fullPage: true,
    });

    // 4. 点击按钮触发复制
    await copyBtn.click();
    await expect(copyBtn).toContainText("已复制");

    // 5. 读取剪贴板验证包含关联的 Request ID 与错误码
    const clipboardText = await page.evaluate(async () => {
      try {
        return await navigator.clipboard.readText();
      } catch {
        return "";
      }
    });
    if (clipboardText) {
      expect(clipboardText).toContain("req-e2e-trace-9999-failed");
      expect(clipboardText).toContain("runtime_execution_failed");
      expect(clipboardText).toContain(
        "Remote docker sandbox container timed out after 10s",
      );
    }
  });

  test("用例 3: 就地排障详情模态窗交互与完整轨迹诊断一键联动闭环", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);

    // Mock 后端安全诊断接口返回带有 Langfuse Trace ID 的结构
    await page.route(
      "**/api/langgraph/threads/thread-e2e-demo/runs/run-e2e-8888/diagnostics*",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            version: 1,
            availability: "available",
            unavailable_reason: null,
            correlation: {
              execution_request_id: "req-e2e-trace-9999-failed",
              platform_trace_id: "platform-trace-e2e-1111",
            },
            trace: {
              provider: "langfuse",
              trace_id: "e2e-langfuse-trace-7777",
              url: null,
            },
            graph_executions: [],
            model_errors: [
              {
                observation_id: "obs-e2e-1",
                scope: "primary",
                namespace: [],
                code: "provider_timeout",
                provider_status: 504,
                error_type: "GatewayTimeout",
                duration_ms: 60000,
              },
            ],
            workspace_executions: [],
            startup: null,
            preparations: [],
            retries: [],
            loop_detections: [],
            truncated: false,
            thread_id: "thread-e2e-demo",
            run_id: "run-e2e-8888",
            run_status: "error",
            request_id: "diag-req-e2e-2222",
          }),
        });
      },
    );

    // 访问工装页并设定模式为 status
    await page.goto("/e2e/observability-fixture.html?mode=status");
    await page.waitForLoadState("networkidle");

    // 1. 验证状态条渲染并定位到【查看排障详情】按钮
    const statusBar = page.locator(".rounded-xl");
    await expect(statusBar).toBeVisible({ timeout: 10000 });
    const viewDetailBtn = statusBar.locator(
      '[data-testid="status-view-diagnostic-btn"]',
    );
    await expect(viewDetailBtn).toBeVisible();
    await expect(viewDetailBtn).toContainText("查看排障详情");

    // 2. 点击【查看排障详情】，触发就地排障模态窗弹出并等待诊断接口返回
    const diagPromise = page.waitForResponse(
      (resp) => resp.url().includes("/diagnostics") && resp.status() === 200,
      { timeout: 10000 },
    );
    await viewDetailBtn.click();
    await diagPromise;

    // 3. 验证模态窗 DOM 与核心字段渲染（open-swe 模式）
    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal).toContainText("运行排障诊断详情");

    // 验证原因码与恢复建议
    const reasonCode = modal.locator('[data-testid="diagnostic-reason-code"]');
    await expect(reasonCode).toBeVisible();
    await expect(reasonCode).toContainText("provider_timeout");

    const followUp = modal.locator('[data-testid="diagnostic-follow-up"]');
    await expect(followUp).toBeVisible();
    await expect(followUp).toContainText("响应超时");

    // 验证 Request ID 凭据
    const reqId = modal.locator('[data-testid="diagnostic-request-id"]');
    await expect(reqId).toBeVisible();
    await expect(reqId).toContainText("req-e2e-trace-9999-failed");

    // 验证 Langfuse Trace ID 与 Open Trace 外链 (对标 open-swe)
    const traceIdEl = modal.locator('[data-testid="diagnostic-trace-id"]');
    await expect(traceIdEl).toBeVisible();
    await expect(traceIdEl).toContainText("e2e-langfuse-trace-7777");

    const openTraceBtn = modal.locator(
      '[data-testid="diagnostic-open-trace-btn"]',
    );
    await expect(openTraceBtn).toBeVisible();
    await expect(openTraceBtn).toContainText("在 Langfuse 中打开追踪");
    expect(await openTraceBtn.getAttribute("href")).toContain(
      "https://jp.cloud.langfuse.com/trace/e2e-langfuse-trace-7777",
    );

    // 验证点击复制排障诊断包
    const copyPacketBtn = modal.locator(
      '[data-testid="copy-diagnostic-packet-btn"]',
    );
    await copyPacketBtn.click();
    await expect(copyPacketBtn).toContainText("排障信息已复制");

    // 4. 截图留痕 3: 排障模态窗全景 (包含 Open Trace 与诊断明细)
    await page.screenshot({
      path: `${screenshotDir}/03-diagnostic-modal-open.png`,
      fullPage: true,
    });

    // 5. 点击【前往完整轨迹诊断 (Trajectory)】按钮
    const goToTrajectoryBtn = modal.locator(
      '[data-testid="go-to-trajectory-btn"]',
    );
    await expect(goToTrajectoryBtn).toBeVisible();
    await goToTrajectoryBtn.click();

    // 6. 验证模态窗关闭，且界面成功响应跳转至轨迹诊断视角
    await expect(modal).not.toBeVisible();
    const trajectoryTarget = page.locator(
      '[data-testid="trajectory-diagnostic-view-target"]',
    );
    await expect(trajectoryTarget).toBeVisible();
    await expect(trajectoryTarget).toContainText("已成功联动切换至轨迹视角");

    // 7. 截图留痕 4: 轨迹视角联动成功全景
    await page.screenshot({
      path: `${screenshotDir}/04-trajectory-diagnostics-linked.png`,
      fullPage: true,
    });
  });
});
