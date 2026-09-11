import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

for (const viewport of [
  { width: 1280, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`Chat ${viewport.width} sends once, clears only accepted draft, hydrates and resumes approval`, async ({
    page,
  }) => {
    test.setTimeout(240000);
    await page.setViewportSize(viewport);
    const fixture = await createPlatformFixture();
    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    const commands: string[] = [];
    page.on("request", (request) => {
      if (
        new URL(request.url()).pathname.endsWith("/commands") &&
        request.method() === "POST"
      ) {
        const body = request.postDataJSON() as { method: string };
        commands.push(body.method);
      }
    });
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
      const composer = page.getByRole("textbox", { name: "消息草稿" });
      await expect(composer).toBeVisible({ timeout: 30000 });
      await composer.fill("请只回复：前端页面正常。不要调用工具。");
      await expect(
        page.getByRole("button", { name: "发送", exact: true }),
      ).toBeEnabled();
      await composer.press("Enter");
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/);
      await expect(composer).toHaveValue("");
      await composer.fill("保留下一条草稿");
      await expect(page.getByTestId("transcript")).toContainText(
        "前端页面正常",
        { timeout: 90000 },
      );
      await expect(
        page.getByRole("button", { name: "发送", exact: true }),
      ).toBeEnabled({ timeout: 90000 });
      await expect(composer).toHaveValue("保留下一条草稿");
      expect(commands).toEqual(["run.start"]);
      const threadUrl = page.url();
      await page.reload();
      await expect(page.getByTestId("transcript")).toContainText(
        "前端页面正常",
        { timeout: 30000 },
      );
      await composer.fill("需要人工确认：请回复审批完成，不要调用工具。");
      await expect(
        page.getByRole("button", { name: "发送", exact: true }),
      ).toBeEnabled();
      await composer.press("Enter");
      const reviews = page.getByRole("region", { name: "待审批操作" });
      await expect(reviews).toBeVisible({ timeout: 90000 });
      await expect(
        reviews.getByRole("button", { name: "提交所选决策" }),
      ).toBeDisabled();
      await reviews.getByLabel("处理方式").selectOption("approve");
      await reviews.getByRole("button", { name: "提交所选决策" }).click();
      await expect(reviews).not.toBeVisible({ timeout: 90000 });
      await expect(
        page.getByRole("button", { name: "发送", exact: true }).and(page.locator(":enabled")),
      ).toHaveCount(0);
      await composer.fill("下一轮");
      await expect(
        page.getByRole("button", { name: "发送", exact: true }),
      ).toBeEnabled({ timeout: 90000 });
      expect(commands).toEqual(["run.start", "run.start", "input.respond"]);
      expect(page.url()).toBe(threadUrl);
      const threadId = new URL(threadUrl).pathname.split("/").pop();
      const originalHistory = await fixture.request<Array<{ checkpoint: { checkpoint_id: string } }>>(
        `/api/langgraph/threads/${threadId}/history`, "POST", { limit: 50 });
      await page.getByRole("button", { name: "编辑", exact: true }).first().click();
      const edit = page.getByTestId("transcript").locator("textarea");
      await expect(edit).toBeVisible();
      await edit.fill("请只回复：编辑分支正常。不要调用工具。");
      await page.getByRole("button", { name: "提交重发", exact: true }).click();
      await expect(edit).not.toBeVisible({ timeout: 30000 });
      await expect(page.getByTestId("transcript")).toContainText("编辑分支正常", { timeout: 90000 });
      await expect(page.getByRole("button", { name: "发送", exact: true })).toBeEnabled({ timeout: 90000 });
      const branchState = await fixture.request<{ values: { messages: Array<{ type: string; content: unknown }> } }>(`/api/langgraph/threads/${threadId}/state`);
      expect(branchState.values.messages.filter(message => message.type === "human")).toHaveLength(1);
      expect(JSON.stringify(branchState.values.messages)).not.toContain("需要人工确认");
      const branchHistory = await fixture.request<Array<{ checkpoint: { checkpoint_id: string } }>>(
        `/api/langgraph/threads/${threadId}/history`, "POST", { limit: 100 });
      expect(branchHistory.some(item => item.checkpoint.checkpoint_id === originalHistory[0]?.checkpoint.checkpoint_id)).toBe(true);
      await page.reload();
      await expect(page.getByTestId("transcript")).toContainText("编辑分支正常", { timeout: 30000 });
      expect(browserErrors).toEqual([]);
      await page.screenshot({
        path: "/tmp/platform-web-chat-refactor.png",
        fullPage: true,
      });
    } catch (error) {
      await page.screenshot({
        path: "/tmp/platform-web-chat-failure.png",
        fullPage: true,
      });
      expect(browserErrors).toEqual([]);
      throw error;
    } finally {
      await page.close();
      await fixture.cleanup();
    }
  });
}
