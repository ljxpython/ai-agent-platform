import { expect, test } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { createPlatformFixture } from "./support/platform";

test("local：真实前台执行成功，启动能力关闭，已有任务查询入口保留", async ({
  page,
}) => {
  test.setTimeout(360000);
  const fixture = await createPlatformFixture("showcase_demo");
  const errors: string[] = [];
  const responses: Array<{ method: string; path: string; status: number }> = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    const path = new URL(response.url()).pathname;
    if (path.startsWith("/api/"))
      responses.push({
        method: response.request().method(),
        path,
        status: response.status(),
      });
  });

  try {
    // 显式选取 deepseek-v4-flash 模型，避开 qwen-plus 空工具 ID 的已知 Runtime 适配问题
    const platformModels = await fixture.request<{
      models: Array<{
        id: string;
        model?: string;
        display_name?: string;
        enabled: boolean;
        credential_configured: boolean;
      }>;
    }>("/api/runtime/platform-models");

    const preferredModel = platformModels.models.find(
      (item) =>
        item.enabled &&
        item.credential_configured &&
        (item.model?.toLowerCase().includes("deepseek") ||
          item.display_name?.toLowerCase().includes("deepseek")),
    );

    if (preferredModel && preferredModel.id !== fixture.modelId) {
      await fixture.request(
        `/api/projects/${fixture.projectId}/runtime-policies/models/${preferredModel.id}`,
        "PUT",
        { is_enabled: true, is_default_for_project: true },
      );
      await fixture.request(`/api/agents/${fixture.agent.id}`, "PATCH", {
        context: { model_id: preferredModel.id },
      });
      fixture.modelId = preferredModel.id;
    }

    const models = await fixture.request<{
      models: Array<{ id: string; display_name: string }>;
    }>("/api/runtime/models");
    const model = models.models.find((item) => item.id === fixture.modelId);
    expect(model).toBeDefined();

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

    await page.goto(
      `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
    );

    const composer = page.getByRole("textbox", { name: "消息草稿" });
    await expect(composer).toBeVisible({ timeout: 90000 });
    await expect(
      page.getByRole("button", { name: "选择对话运行模型" }),
    ).toContainText(model!.display_name, { timeout: 90000 });

    await composer.fill(
      "请真实执行短命令 printf AB_LOCAL_OK，然后报告工具的输出。不要委派子任务，遵守审批，不要仅凭文字猜测结果。",
    );
    const send = page.getByRole("button", { name: "发送", exact: true });
    await expect(send).toBeEnabled({ timeout: 90000 });

    const [submitted] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          /\/api\/langgraph\/threads\/[^/]+\/commands$/.test(response.url()),
        { timeout: 60000 },
      ),
      send.click(),
    ]);
    expect(submitted.status()).toBe(200);

    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });
    const threadId = new URL(page.url()).pathname.split("/").pop();

    const capabilities = await fixture.request<{
      background_tasks: boolean;
      background_tasks_start_enabled: boolean;
    }>(`/api/langgraph/threads/${threadId}/capabilities`);
    expect(capabilities.background_tasks).toBe(true);
    expect(capabilities.background_tasks_start_enabled).toBe(false);

    const reviews = page.getByRole("region", { name: "待审批操作" });
    let approvals = 0;
    let finalStatus = "active";
    for (let attempt = 0; attempt < 5; attempt++) {
      let phase = "active";
      await expect
        .poll(
          async () => {
            if (await reviews.isVisible()) return (phase = "review");
            const runs = await fixture.request<Array<{ status: string }>>(
              `/api/langgraph/threads/${threadId}/runs`,
            );
            return (phase =
              runs[0] &&
              !["pending", "running", "interrupted"].includes(runs[0].status)
                ? runs[0].status
                : "active");
          },
          { timeout: 180000, intervals: [1000, 2000, 5000] },
        )
        .not.toBe("active");
      if (phase !== "review") {
        expect(phase).toBe("success");
        finalStatus = phase;
        break;
      }
      const approveButtons = reviews.getByRole("button", {
        name: "批准 (Approve)",
      });
      approvals += await approveButtons.count();
      for (const button of await approveButtons.all()) await button.click();
      await reviews.getByRole("button", { name: "确认批准所选操作" }).click();
      await expect(reviews).not.toBeVisible({ timeout: 30000 });
    }

    expect(finalStatus).toBe("success");
    expect(approvals).toBeGreaterThanOrEqual(1);

    const state = await fixture.request<{
      values: {
        messages: Array<{ type: string; name?: string; content: unknown }>;
      };
    }>(`/api/langgraph/threads/${threadId}/state`);
    const tools = state.values.messages.filter(
      (message) => message.type === "tool",
    );
    expect(
      tools.some(
        (message) =>
          message.name === "execute" &&
          JSON.stringify(message.content).includes("AB_LOCAL_OK"),
      ),
    ).toBe(true);
    expect(tools.some((message) => message.name === "background_execute")).toBe(
      false,
    );

    // 验证工作区与后台任务入口：query=true/start=false 时任务 Tab 正常存在
    await page.getByTestId("toggle-workspace-button").click();
    await page.getByTestId("workspace-tab-tasks").click();
    await expect(page.getByTestId("background-tasks-empty-state")).toBeVisible({
      timeout: 15000,
    });
    const tasks = await fixture.request<{ items: unknown[] }>(
      `/api/langgraph/threads/${threadId}/background-tasks`,
    );
    expect(tasks.items).toEqual([]);
    expect(errors).toEqual([]);

    await page.screenshot({
      path: test.info().outputPath("local-background-compatibility.png"),
      fullPage: true,
    });
  } catch (error) {
    await page.screenshot({
      path: test.info().outputPath("local-background-failure.png"),
      fullPage: true,
    });
    throw error;
  } finally {
    const responsePath = test.info().outputPath("api-responses.json");
    await writeFile(responsePath, JSON.stringify(responses, null, 2));
    await test.info().attach("api-responses.json", {
      path: responsePath,
      contentType: "application/json",
    });
    await page.close();
    await fixture.cleanup();
  }
});
