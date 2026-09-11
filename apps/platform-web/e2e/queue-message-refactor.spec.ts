import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

for (const mode of [
  "complete",
  "cancel-before",
  "cancel-after",
  "revoke",
  "unknown",
  "approval",
]) {
  test(`mobile queue through real gateway: ${mode}`, async ({ page }) => {
    test.skip(
      process.env.Q5_QUEUE_FIXTURE !== "1",
      "Requires isolated Q5 slow-tool graph",
    );
    test.setTimeout(120000);
    const fixture = await createPlatformFixture("reference_agent");
    await page.setViewportSize({ width: 390, height: 844 });
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
      const draft = page.getByRole("textbox", { name: "消息草稿" });
      await expect(draft).toBeVisible({ timeout: 30000 });
      await draft.fill(mode === "approval" ? "start approval work" : "start work");
      await expect(
        page.getByRole("button", { name: "发送", exact: true }),
      ).toBeEnabled({ timeout: 30000 });
      await draft.press("Enter");
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/);
      await expect(draft).toHaveValue("");
      await expect(
        page.getByText("long_task", { exact: true }).first(),
      ).toBeVisible({ timeout: 30000 });
      await draft.fill("extra verification Q5");
      let originalRequest:
        | { body: string | null; key: string | undefined }
        | undefined;
      let retrying = false;
      if (mode === "unknown") {
        await page.route("**/messages", async (route) => {
          if (!retrying && route.request().method() === "GET")
            return route.abort();
          if (!retrying && route.request().method() === "POST") {
            originalRequest = {
              body: route.request().postData(),
              key: route.request().headers()["idempotency-key"],
            };
            expect((await route.fetch()).status()).toBe(202);
            return route.abort(); // Server committed, client never received the ACK.
          }
          return route.continue();
        });
        await page.getByRole("button", { name: "排队发送当前草稿" }).click();
        await expect(
          page.getByRole("button", { name: "重试原消息" }),
        ).toBeVisible();
        await expect(draft).toHaveValue("extra verification Q5");
        await page.reload();
        await expect(
          page.getByRole("button", { name: "重试原消息" }),
        ).toBeVisible({ timeout: 30000 });
        retrying = true;
      }
      const responsePromise = page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname.endsWith("/messages") &&
          response.request().method() === "POST",
      );
      await page
        .getByRole("button", {
          name: mode === "unknown" ? "重试原消息" : "排队发送当前草稿",
        })
        .click();
      const response = await responsePromise;
      expect(response.status(), await response.text()).toBe(202);
      if (originalRequest) {
        expect(response.request().postData()).toBe(originalRequest.body);
        expect(response.request().headers()["idempotency-key"]).toBe(
          originalRequest.key,
        );
      }
      const receipt = await response.json();
      await expect(draft).toHaveValue("");
      const region = page.getByRole("region", { name: "消息投递状态" });
      if (mode === "revoke") {
        await fixture.request(`/api/agents/${fixture.agent.id}`, "PATCH", {
          status: "disabled",
        });
      }
      if (mode !== "cancel-before" && mode !== "revoke") {
        await expect(region).toContainText("已写入上下文", { timeout: 45000 });
      }
      if (mode.startsWith("cancel")) {
        await draft.fill("cancel preserves this draft");
        const cancelled = page.waitForResponse(
          (response) =>
            new URL(response.url()).pathname.endsWith("/cancel") &&
            response.request().method() === "POST",
        );
        await page
          .getByRole("button", { name: "停止生成", exact: true })
          .click();
        expect((await cancelled).ok()).toBe(true);
        await expect(
          page.getByRole("button", { name: "发送", exact: true }),
        ).toBeEnabled({ timeout: 45000 });
        await expect(draft).toHaveValue("cancel preserves this draft");
      }
      let secondId: string | undefined;
      if (mode === "complete" || mode === "approval") {
        await draft.fill("second batch Q5");
        const secondResponse = page.waitForResponse(
          (response) =>
            new URL(response.url()).pathname.endsWith("/messages") &&
            response.request().method() === "POST",
        );
        await page.getByRole("button", { name: "排队发送当前草稿" }).click();
        const second = await secondResponse;
        expect(second.status(), await second.text()).toBe(202);
        secondId = (await second.json()).message_id;
        if (mode === "complete") {
          await expect(region.getByText(/已写入上下文/)).toHaveCount(2, { timeout: 45000 });
        } else {
          const reviews = page.getByRole("region", { name: "待审批操作" });
          await expect(reviews).toBeVisible({ timeout: 45000 });
          await expect(region).toContainText("未消费", { timeout: 30000 });
          await reviews.getByRole("combobox").selectOption("approve");
          await reviews.getByRole("button", { name: "提交所选决策" }).click();
          await expect(reviews).not.toBeVisible({ timeout: 30000 });
          await draft.fill("next draft");
          await expect(page.getByRole("button", { name: "发送", exact: true })).toBeEnabled({ timeout: 45000 });
        }
      }
      const expected =
        mode === "revoke"
          ? "已拒绝"
          : mode === "cancel-before"
            ? "未消费"
            : "已写入上下文";
      await expect(region).toContainText(expected, { timeout: 45000 });
      const threadId = new URL(page.url()).pathname.split("/").pop();
      const state = await fixture.request<{
        values: { messages: Array<{ id: string; content: string }> };
      }>(`/api/langgraph/threads/${threadId}/state`);
      expect(
        state.values.messages.filter(
          (message) => message.id === receipt.message_id,
        ),
      ).toHaveLength(mode === "cancel-before" || mode === "revoke" ? 0 : 1);
      if (secondId)
        expect(
          state.values.messages.filter((message) => message.id === secondId),
        ).toHaveLength(mode === "approval" ? 0 : 1);
      expect(JSON.stringify(state)).not.toContain("runtime_message_claim");
      if (mode !== "cancel-before" && mode !== "revoke") {
        expect(
          state.values.messages.some(
            (message) =>
              message.content.includes("received:") &&
              message.content.includes("extra verification Q5"),
          ),
        ).toBe(true);
      }
      await page.reload();
      await expect(
        page.getByRole("region", { name: "消息投递状态" }),
      ).toContainText(expected, { timeout: 30000 });
      if (mode === "cancel-before" || mode === "revoke") {
        await draft.fill("existing draft");
        await page.getByRole("button", { name: "恢复到输入框" }).click();
        await expect(draft).toHaveValue("existing draft\nextra verification Q5");
      }
      if (mode === "revoke") {
        await expect(
          page.getByText("该 Agent 已停用，当前仅可查看历史消息和投递状态。"),
        ).toBeVisible();
        await expect(
          page.getByRole("button", { name: "发送", exact: true }),
        ).toBeDisabled({ timeout: 30000 });
      }
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    } finally {
      await page.close();
      await fixture.cleanup();
    }
  });
}
