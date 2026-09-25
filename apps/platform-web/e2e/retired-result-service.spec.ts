import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

test("Dear Agent delivers an artifact without the retired result service", async ({
  page,
}) => {
  test.setTimeout(300000);
  const fixture = await createPlatformFixture("dearflow_agent");
  const fileName = "retirement-check.md";
  const threadResponses: string[] = [];
  const requestFailures: string[] = [];
  let threadId: string | undefined;
  page.on("response", async (response) => {
    if (
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.includes("/threads")
    ) {
      const body = (await response.json().catch(() => ({}))) as {
        thread_id?: string;
        error?: { code?: string };
      };
      if (
        new URL(response.url()).pathname.endsWith("/api/langgraph/threads") &&
        response.ok()
      ) {
        threadId = body.thread_id;
      }
      threadResponses.push(
        `${new URL(response.url()).pathname} ${response.status()} ${body.error?.code ?? ""}`,
      );
    }
  });
  page.on("requestfailed", (request) =>
    requestFailures.push(
      `${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`,
    ),
  );
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
      `/workspace/projects/${fixture.projectId}/dear-agent?agentId=${fixture.agent.id}`,
    );
    const draft = page.getByRole("textbox", { name: "消息草稿" });
    await draft.fill(
      `仅用 write_file 在 /workspace/work/${fileName} 写入“退役验收成功”，再用 present_artifacts 发布该文件。不要执行命令、搜索或委派任务。`,
    );
    const send = page.getByRole("button", { name: "发送", exact: true });
    await expect(page.getByRole("status")).toContainText("可以发送");
    await expect(send).toBeEnabled();
    await send.click();
    await expect(
      page,
      `thread responses: ${threadResponses.join(", ")}; failures: ${requestFailures.join(", ")}`,
    ).toHaveURL(/\/dear-agent\/[0-9a-f-]+/, { timeout: 30000 });
    threadId = new URL(page.url()).pathname.split("/").pop()!;
    const artifactPath = `/api/langgraph/threads/${threadId}/artifacts`;
    let artifact: { file_name: string; path: string } | undefined;

    for (let attempt = 0; attempt < 50 && !artifact; attempt++) {
      const review = page.getByRole("region", { name: "待审批操作" });
      if (await review.isVisible()) {
        for (const button of await review
          .getByRole("button", { name: "批准 (Approve)" })
          .all()) {
          await button.click();
        }
        await review.getByRole("button", { name: "确认批准所选操作" }).click();
      }
      const result = await fixture.request<{
        items: Array<{ file_name: string; path: string }>;
      }>(artifactPath);
      artifact = result.items.find((item) => item.file_name.endsWith(".md"));
      if (!artifact) await page.waitForTimeout(4000);
    }
    expect(artifact).toBeDefined();

    await page.goto(
      `/workspace/projects/${fixture.projectId}/dear-agent-artifacts?threadId=${threadId}`,
    );
    const card = page
      .locator("article")
      .filter({ hasText: artifact!.file_name })
      .first();
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: "在线预览" }).click();
    await expect(page.getByText("退役验收成功")).toBeVisible();
    await page.getByTitle("关闭预览 (Esc)").click();
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      card.getByRole("button", { name: "安全下载" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe(artifact!.file_name);
  } finally {
    await page.close();
    try {
      if (threadId)
        await fixture.request(`/api/langgraph/threads/${threadId}`, "DELETE");
    } finally {
      await fixture.cleanup();
    }
  }
});
