import { expect, test, type Page } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { platformUrl, testCredentials } from "./support/platform";

const evidenceDir = resolve(
  import.meta.dirname,
  "../../../docs/projects/20261107-session-hydration-and-artifact-offloading",
);
const saved = JSON.parse(
  readFileSync(resolve(evidenceDir, "image-e2e-evidence.json"), "utf8"),
);
test.describe.configure({ mode: "serial" });
let tokens: { access_token: string; refresh_token: string; token_type: string };
const results: Record<string, unknown> = {};
async function request(path: string, body?: unknown) {
  const response = await fetch(platformUrl + path, {
    headers: {
      authorization: `Bearer ${tokens.access_token}`,
      "x-project-id": saved.projectId,
      "content-type": "application/json",
    },
    method: body ? "POST" : "GET",
    body: body && JSON.stringify(body),
  });
  expect(response.ok, `${path}: ${response.status}`).toBe(true);
  return response.json();
}
const url = (threadId: string) =>
  `/workspace/projects/${saved.projectId}/chat/${threadId}`;
async function shot(page: Page, name: string) {
  await page.screenshot({
    path: resolve(evidenceDir, `screenshots/${name}.png`),
    fullPage: true,
  });
}
async function send(page: Page, text: string) {
  const input = page.getByRole("textbox", { name: "消息草稿" });
  await input.fill(text);
  const command = page.waitForResponse(
    (response) =>
      response.url().includes("/commands") &&
      response.request().method() === "POST",
    { timeout: 30000 },
  );
  await page.getByRole("button", { name: "发送", exact: true }).click();
  const accepted = await command;
  expect(
    accepted.ok(),
    `Command HTTP ${accepted.status()}: ${await accepted.text()}`,
  ).toBe(true);
  await expect(input).toHaveValue("", { timeout: 15000 });
}
async function success(threadId: string, previous: number) {
  await expect
    .poll(
      async () => {
        const runs = await request(`/api/langgraph/threads/${threadId}/runs`);
        return runs.length > previous && runs[0].status === "success";
      },
      { timeout: 120000 },
    )
    .toBe(true);
}
test.beforeEach(async ({ page }) => {
  test.setTimeout(240000);
  const response = await fetch(platformUrl + "/api/identity/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(testCredentials()),
  });
  expect(response.ok).toBe(true);
  ({ tokens } = await response.json());
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
    { tokens, projectId: saved.projectId },
  );
  await page.setViewportSize({ width: 1440, height: 1000 });
  page.on("pageerror", (error) => console.log("Page error:", error.message));
});
test.afterEach(async ({ page }, info) => {
  if (info.status !== info.expectedStatus) {
    await shot(
      page,
      `lifecycle-failure-${info.title.split(",")[0].slice(0, 30).replace(/\s/g, "-")}`,
    );
    console.log(
      "Failure UI:",
      (await page.locator("main").innerText()).slice(-3500),
    );
  }
});
test.afterAll(() =>
  writeFileSync(
    resolve(evidenceDir, "lifecycle-e2e-evidence.json"),
    JSON.stringify(results, null, 2),
  ),
);

test("restart persistence, running reload, stop and continue", async ({
  page,
}) => {
  const threadId = saved.threadId;
  await page.goto(url(threadId));
  await expect(
    page.locator(".pw-markdown:visible").filter({ hasText: "BLUE" }).last(),
  ).toBeVisible({ timeout: 30000 });
  const before = await request(`/api/langgraph/threads/${threadId}/runs`);
  await send(
    page,
    "直接撰写一篇不少于5000字的计算机历史文章，持续输出正文，不要调用工具。",
  );
  const stop = page.getByRole("button", { name: "停止生成", exact: true });
  await expect(stop).toBeVisible({ timeout: 30000 });
  await page.reload();
  await expect(stop).toBeVisible({ timeout: 30000 });
  await shot(page, "lifecycle-running-reload");
  const receiptResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/threads/${threadId}/cancel`) &&
      response.request().method() === "POST",
  );
  await stop.click();
  const response = await receiptResponse;
  const receipt = await response.json();
  results.stopReceipt = { status: response.status(), receipt };
  console.log("Stop receipt", JSON.stringify(results.stopReceipt));
  const banner = page.getByTestId("run-stop-report-banner");
  await expect(banner).toContainText("已停止", { timeout: 45000 });
  await shot(page, "lifecycle-stopped");
  const stopped = await request(`/api/langgraph/threads/${threadId}/runs`);
  expect(stopped.length).toBeGreaterThan(before.length);
  expect(["interrupted", "error"]).toContain(stopped[0].status);
  await send(page, "只回答 STOP_CONTINUE_OK，不要调用工具。");
  await success(threadId, stopped.length);
  await expect(
    page
      .locator(".pw-markdown:visible")
      .filter({ hasText: "STOP_CONTINUE_OK" })
      .last(),
  ).toBeVisible();
  await shot(page, "lifecycle-continued");
  results.stopContinue = {
    threadId,
    stoppedStatus: stopped[0].status,
    success: true,
  };
});

test("edit creates a new branch without cached old answers, then child details survive reload", async ({
  page,
}) => {
  await page.goto(url(saved.threadId));
  await expect(page.getByRole("textbox", { name: "消息草稿" })).toBeVisible({
    timeout: 30000,
  });
  await page.getByTitle("编辑", { exact: true }).last().click();
  const editor = page.locator('textarea:not([aria-label="消息草稿"])').first();
  await expect(editor).toBeVisible();
  await editor.fill("只回答 BRANCH_CURRENT_OK，不要调用工具。");
  const before = await request(`/api/langgraph/threads/${saved.threadId}/runs`);
  await page.getByRole("button", { name: "提交重发" }).click();
  const branchId = saved.threadId;
  await success(branchId, before.length);
  await expect(
    page
      .locator(".pw-markdown:visible")
      .filter({ hasText: "BRANCH_CURRENT_OK" })
      .last(),
  ).toBeVisible({ timeout: 30000 });
  await expect(
    page
      .locator(".pw-markdown:visible")
      .filter({ hasText: "STOP_CONTINUE_OK" }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page
      .locator(".pw-markdown:visible")
      .filter({ hasText: "BRANCH_CURRENT_OK" })
      .last(),
  ).toBeVisible({ timeout: 30000 });
  await shot(page, "lifecycle-edited-branch");
  await page.getByTitle("点击切换执行模式与参数").click();
  await page.getByRole("button").filter({ hasText: "Pro 深度模式" }).click();
  await page
    .getByRole("button", { name: "应用到当前会话", exact: true })
    .click();
  const runs = await request(`/api/langgraph/threads/${branchId}/runs`);
  await send(
    page,
    `调用 task 委派给 general-purpose 子智能体：用 read_file 读取 ${saved.toolReference.path}，识别图中的英文颜色词，同时计算7乘8，不联网。收到子任务结果后回答 CHILD_RESULT_56 和它识别到的颜色词。必须实际调用 task，不能自己替代子任务。`,
  );
  await success(branchId, runs.length);
  const state = await request(`/api/langgraph/threads/${branchId}/state`);
  expect(
    state.values.messages.some((m: any) =>
      m.tool_calls?.some((t: any) => t.name === "task"),
    ),
  ).toBe(true);
  expect(JSON.stringify(state.values)).not.toMatch(/data:image\/|"base64"/);
  await page.reload();
  await expect(
    page
      .locator(".pw-markdown:visible")
      .filter({ hasText: "CHILD_RESULT_56" })
      .last(),
  ).toBeVisible({ timeout: 30000 });
  await expect(
    page
      .locator(".pw-markdown:visible")
      .filter({ hasText: "CHILD_RESULT_56" })
      .last(),
  ).toContainText("BLUE");
  await page
    .getByRole("button")
    .filter({ hasText: /全能执行/ })
    .first()
    .click();
  await expect(page.getByText("子任务执行过程", { exact: true })).toBeVisible();
  await expect(page.getByText("分析结果汇报", { exact: true })).toBeVisible();
  await shot(page, "lifecycle-child-reloaded");
  results.branchAndChild = { branchId, success: true };
});

test("plan approval restores across reload and resumes to completion", async ({
  page,
}) => {
  const original = await request(`/api/langgraph/threads/${saved.threadId}`);
  await page.goto(
    `/workspace/projects/${saved.projectId}/chat?agentId=${original.metadata.agent_id}`,
  );
  await page
    .getByRole("button", { name: "新建会话", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "选择对话运行模型" }).click();
  await page
    .locator('[role="button"]')
    .filter({ hasText: "xiaok DeepSeek E2E" })
    .first()
    .click();
  await page.keyboard.press("Escape");
  await page.getByTestId("composer-feature-menu-btn").click();
  await page.getByTestId("feature-toggle-plan-mode").click();
  await send(
    page,
    "无需调研，先调用 save_plan 保存标题‘水合验收计划’，markdown 内容为‘# 水合验收\n\n1. 回答 APPROVAL_RESUMED_OK，不使用其他工具。’；下一轮单独调用 submit_plan 提交审批。审批通过后仅回复 APPROVAL_RESUMED_OK。不要合并两个工具调用。",
  );
  await expect(page.getByTestId("plan-review-card")).toBeVisible({
    timeout: 120000,
  });
  const threadId = page.url().match(/\/chat\/([0-9a-f-]{36})/)![1];
  await page.reload();
  await expect(page.getByTestId("plan-review-card")).toBeVisible({
    timeout: 30000,
  });
  await expect(
    page.getByRole("button", { name: "发送", exact: true }),
  ).toBeDisabled();
  await shot(page, "lifecycle-approval-reloaded");
  const runs = await request(`/api/langgraph/threads/${threadId}/runs`);
  await page.getByTestId("plan-review-approve-btn").click();
  await success(threadId, runs.length);
  await expect(
    page
      .locator(".pw-markdown:visible")
      .filter({ hasText: "APPROVAL_RESUMED_OK" })
      .last(),
  ).toBeVisible({ timeout: 30000 });
  await shot(page, "lifecycle-approval-resumed");
  results.approval = { threadId, success: true };
});
