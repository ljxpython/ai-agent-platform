import { expect, test, type Request } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

test("three conversations keep progressing across rapid switches without starving access", async ({
  page,
}) => {
  test.skip(
    process.env.Q5_QUEUE_FIXTURE !== "1",
    "Requires isolated deterministic graph",
  );
  test.setTimeout(150_000);
  const fixture = await createPlatformFixture("reference_agent");
  const requests = new Set<Request>();
  const errors: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/stream/events")) requests.add(request);
  });
  page.on("requestfinished", (request) => requests.delete(request));
  page.on("requestfailed", (request) => requests.delete(request));
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
    await page.goto(
      `/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`,
    );
    const ids: string[] = [];
    const draft = page.getByRole("textbox", { name: "消息草稿" });
    for (const index of [1, 2, 3]) {
      if (index > 1)
        await page
          .getByRole("button", { name: "新建会话", exact: true })
          .click();
      await draft.fill(`resource conversation ${index}`);
      await expect(
        page.getByRole("button", { name: "发送", exact: true }),
      ).toBeEnabled();
      await draft.press("Enter");
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/);
      ids.push(new URL(page.url()).pathname.split("/").pop()!);
      await expect(draft).toHaveValue("");
      await draft.fill(`queued followup ${index}`);
      await page.getByRole("button", { name: "补充要求", exact: true }).click();
      await expect(
        page.getByText("待执行消息队列", { exact: true }),
      ).toBeVisible();
    }
    const sidebar = page.getByRole("complementary", { name: "对话列表" });
    for (const index of [1, 2, 3, 1, 3, 2]) {
      await sidebar.locator(`[data-thread-id="${ids[index - 1]}"]`).click();
      await expect
        .poll(() => requests.size, { timeout: 10_000 })
        .toBeLessThanOrEqual(2);
      await expect(
        page.getByText("权限同步暂时不可用，已保留当前页面。", { exact: true }),
      ).toBeHidden();
    }
    // This request shares the browser origin and must not wait behind parked SSE.
    expect(
      await page.evaluate(
        async ({ projectId, token }) => {
          const response = await fetch(`/api/projects/${projectId}/access`, {
            headers: { authorization: `Bearer ${token}` },
            signal: AbortSignal.timeout(10_000),
          });
          return response.status;
        },
        { projectId: fixture.projectId, token: fixture.tokens.access_token },
      ),
    ).toBe(200);
    for (const [index, id] of ids.entries()) {
      await expect
        .poll(
          async () => {
            const state = await fixture.request<{
              values: { messages?: Array<{ content: unknown }> };
            }>(`/api/langgraph/threads/${id}/state`);
            return JSON.stringify(state.values.messages);
          },
          { timeout: 90_000 },
        )
        .toContain(`queued followup ${index + 1}`);
      await sidebar.locator(`[data-thread-id="${id}"]`).click();
      await expect(page.getByTestId("transcript").first()).toContainText(
        `queued followup ${index + 1}`,
        { timeout: 20_000 },
      );
      await expect(
        page.getByText("待执行消息队列", { exact: true }),
      ).toBeHidden({ timeout: 20_000 });
      await expect
        .poll(
          async () => {
            const runs = await fixture.request<Array<{ status: string }>>(
              `/api/langgraph/threads/${id}/runs`,
            );
            return (
              runs.length >= 2 && runs.every((run) => run.status === "success")
            );
          },
          { timeout: 60_000 },
        )
        .toBe(true);
      const state = await fixture.request<{
        values: { messages: Array<{ type: string; content: unknown }> };
      }>(`/api/langgraph/threads/${id}/state`);
      expect(
        state.values.messages.filter(
          (message) =>
            message.type === "human" &&
            message.content === `queued followup ${index + 1}`,
        ),
      ).toHaveLength(1);
      expect(
        state.values.messages.some(
          (message) =>
            message.type === "ai" &&
            String(message.content).includes(`queued followup ${index + 1}`),
        ),
      ).toBe(true);
    }
    expect(errors).toEqual([]);
  } finally {
    await page.close();
    await fixture.cleanup();
  }
});
