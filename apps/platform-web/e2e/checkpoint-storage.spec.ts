import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createPlatformFixture } from "./support/platform";

test("Delta reference conversation preserves full history after reload and fork", async ({
  page,
}) => {
  test.skip(
    process.env.RUN_STORAGE_STACK_TEST !== "1",
    "Requires registered stack and model",
  );
  test.setTimeout(240000);
  page.setDefaultTimeout(15000);
  const fixture = await createPlatformFixture("reference_agent");
  let threadId = "";
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
    const transcript = page.getByTestId("transcript");
    const send = page.getByRole("button", { name: "发送", exact: true });
    await expect(draft).toBeVisible({ timeout: 30000 });
    const prompts = [
      "请记住验收代号海港七号。不要调用工具，只回复：海港七号已记录。",
      "上一轮的验收代号是什么？不要调用工具，只回复代号。",
    ];
    for (const [index, prompt] of prompts.entries()) {
      await draft.fill(prompt);
      await expect(send).toBeEnabled();
      await draft.press("Enter");
      await expect(draft).toHaveValue("");
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/);
      threadId = new URL(page.url()).pathname.split("/").pop()!;
      await expect
        .poll(
          async () => {
            const runs = await fixture.request<Array<{ status: string }>>(
              `/api/langgraph/threads/${threadId}/runs`,
            );
            return (
              runs.length === index + 1 &&
              runs.every((run) => run.status === "success")
            );
          },
          { timeout: 90000 },
        )
        .toBe(true);
    }
    threadId = new URL(page.url()).pathname.split("/").pop()!;
    const path = `/api/langgraph/threads/${threadId}`;
    const state = await fixture.request<{
      values: {
        messages: Array<{ id: string; type: string; content: unknown }>;
      };
    }>(`${path}/state`);
    expect(
      state.values.messages.filter((m) => m.type === "human"),
    ).toHaveLength(2);
    expect(state.values.messages.filter((m) => m.type === "ai")).toHaveLength(
      2,
    );
    const ids = state.values.messages.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(JSON.stringify(state.values.messages.at(-1)?.content)).toContain(
      "海港七号",
    );
    await page.reload();
    for (const prompt of prompts)
      await expect(transcript).toContainText(prompt, { timeout: 30000 });
    const recovered = await fixture.request<{ values: unknown }>(
      `${path}/state`,
    );
    expect(recovered.values).toEqual(state.values);
    const originalHistory = await fixture.request<
      Array<{ checkpoint: { checkpoint_id: string } }>
    >(`${path}/history`, "POST", { limit: 50 });
    expect(originalHistory.length).toBeGreaterThan(3);
    await page
      .getByRole("button", { name: "编辑", exact: true })
      .first()
      .click();
    const edit = transcript.locator("textarea");
    await edit.fill("不要调用工具，只回复：分支验证通过。");
    await page.getByRole("button", { name: "提交重发", exact: true }).click();
    await expect(edit).not.toBeVisible({ timeout: 30000 });
    await expect
      .poll(
        async () => {
          const runs = await fixture.request<Array<{ status: string }>>(
            `${path}/runs`,
          );
          return (
            runs.length === 3 && runs.every((run) => run.status === "success")
          );
        },
        { timeout: 90000 },
      )
      .toBe(true);
    await expect(transcript).toContainText("分支验证通过", { timeout: 90000 });
    const branch = await fixture.request<{
      values: { messages: Array<{ type: string; content: unknown }> };
    }>(`${path}/state`);
    expect(
      branch.values.messages.filter((m) => m.type === "human"),
    ).toHaveLength(1);
    const history = await fixture.request<
      Array<{ checkpoint: { checkpoint_id: string } }>
    >(`${path}/history`, "POST", { limit: 100 });
    expect(
      history.some(
        (item) =>
          item.checkpoint.checkpoint_id ===
          originalHistory[0]!.checkpoint.checkpoint_id,
      ),
    ).toBe(true);
    await page.reload();
    await expect(transcript).toContainText("分支验证通过", { timeout: 30000 });
    const evidence = resolve(process.cwd(), "../../.local-stack/evidence");
    mkdirSync(evidence, { recursive: true });
    await page.screenshot({
      path: resolve(evidence, "checkpoint-storage-reference.png"),
      fullPage: true,
    });
    writeFileSync(
      resolve(evidence, "checkpoint-storage-reference.json"),
      JSON.stringify(
        {
          threadId,
          projectId: fixture.projectId,
          messageIds: ids,
          historyBefore: originalHistory.length,
          historyAfter: history.length,
          checks: [
            "real-model-two-turns",
            "stable-message-ids",
            "reload-full-history",
            "native-edit-fork",
            "old-checkpoint-retained",
          ],
        },
        null,
        2,
      ),
    );
  } finally {
    await page.close();
    if (threadId)
      await fixture.request(`/api/langgraph/threads/${threadId}`, "DELETE");
    await fixture.cleanup();
  }
});
