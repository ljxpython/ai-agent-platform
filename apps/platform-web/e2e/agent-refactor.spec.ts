import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

test("Authorized Graph automatically appears as Agent and preserves edited configuration", async ({
  page,
}) => {
  test.setTimeout(90000);
  const fixture = await createPlatformFixture();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
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
    const base = `/workspace/projects/${fixture.projectId}`;
    await page.goto(`${base}/agents`);
    await expect(page.getByRole("button", { name: "新建 Agent", exact: true })).toHaveCount(0);
    await expect(page.getByText("Web refactor test", { exact: true })).toBeVisible();
    await page.goto(`${base}/agents/${fixture.agent.id}`);
    await page.getByLabel("名称", { exact: true }).fill("Browser-edited Agent");
    await page.getByRole("combobox", { name: "模型", exact: true }).selectOption(fixture.modelId);
    await page.getByLabel("工具范围").selectOption("select");
    const id = fixture.agent.id;
    await expect(page.getByLabel("名称", { exact: true })).toBeEnabled();
    await page.getByLabel("描述", { exact: true }).fill("Edited in browser");
    await page.getByRole("button", { name: "保存", exact: true }).click();
    await expect(page.getByText("已保存", { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByLabel("描述", { exact: true })).toHaveValue(
      "Edited in browser",
    );
    await expect(page.getByLabel("工具范围")).toHaveValue("select");
    const stored = await fixture.request<{
      context: Record<string, unknown>;
      description: string;
    }>(`/api/agents/${id}`);
    expect(stored.context.tools).toEqual([]);
    expect(stored.context.model_id).toBe(fixture.modelId);
    expect(stored.description).toBe("Edited in browser");
    await expect(page.getByRole("button", { name: "删除", exact: true })).toHaveCount(0);
    await page.goto(`${base}/agents`);
    await expect(page.getByText("Browser-edited Agent", { exact: true })).toBeVisible();
    await page.goto(`${base}/chat?graphId=${fixture.graphId}`);
    await expect(page.getByRole("textbox", { name: "消息草稿" })).toBeVisible();
    await expect(page.getByLabel("对话目标")).toHaveValue(id);
    await expect(page.locator('select[aria-label="对话目标"] optgroup')).toHaveCount(0);
    const catalog = await fixture.request<{ graphs: Array<{ id: string; graph_id: string }> }>("/api/runtime/graphs");
    const graph = catalog.graphs.find(item => item.graph_id === fixture.graphId)!;
    const thread = await fixture.request<{ thread_id: string }>("/api/langgraph/threads", "POST", {
      graph_id: fixture.graphId, metadata: { agent_id: id, title: "授权撤销后保留历史" }
    });
    const policy = `/api/projects/${fixture.projectId}/runtime-policies/graphs/${graph.id}`;
    await fixture.request(policy, "PUT", { is_enabled: false });
    const revoked = await fixture.request<{ items: Array<{ id: string }> }>(`/api/projects/${fixture.projectId}/agents`);
    expect(revoked.items.some(item => item.id === id)).toBe(false);
    await page.goto(`${base}/chat/${thread.thread_id}`);
    await expect(page.getByText("该智能体已停用或未授权，当前仅可查看历史消息和投递状态。")).toBeVisible();
    await expect(page.getByRole("button", { name: "发送", exact: true })).toBeDisabled();
    await fixture.request(policy, "PUT", { is_enabled: true });
    const restored = await fixture.request<{ items: Array<{ id: string; name: string }> }>(`/api/projects/${fixture.projectId}/agents`);
    expect(restored.items.find(item => item.id === id)?.name).toBe("Browser-edited Agent");
    expect(errors).toEqual([]);
  } finally {
    await page.close();
    await fixture.cleanup();
  }
});
