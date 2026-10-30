import { expect, test } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createPlatformFixture } from "./support/platform";

test("view and send renew retention; background reads do not", async ({
  page,
}) => {
  test.skip(
    process.env.RUN_RETENTION_STACK_TEST !== "1",
    "Requires registered stack and model",
  );
  test.setTimeout(180000);
  const fixture = await createPlatformFixture("dearflow_agent");
  const thread = await fixture.request<{ thread_id: string }>(
    "/api/langgraph/threads",
    "POST",
    {
      graph_id: fixture.graphId,
      metadata: {
        agent_id: fixture.agent.id,
        graph_id: fixture.graphId,
        title: "保留治理验收",
      },
    },
  );
  const path = `/api/langgraph/threads/${thread.thread_id}`;
  const snapshot = async () =>
    (await fixture.request<{ retention: { last_activity_at: string } }>(path))
      .retention;
  const activity: number[] = [];
  page.on("response", (response) => {
    if (response.url().endsWith(`${path}/activity`) && response.ok())
      activity.push(Date.now());
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
    const base = `/workspace/projects/${fixture.projectId}`;
    const chat = `${base}/chat/${thread.thread_id}?agentId=${fixture.agent.id}`;
    const initial = await snapshot();
    await page.goto(chat);
    const draft = page.getByRole("textbox", { name: "消息草稿" });
    await expect(draft).toBeVisible();
    await expect.poll(() => activity.length).toBe(1);
    const viewed = await snapshot();
    expect(viewed.last_activity_at > initial.last_activity_at).toBe(true);
    for (let i = 0; i < 3; i++) {
      await fixture.request("/api/langgraph/threads/search", "POST", {
        limit: 10,
      });
      await fixture.request(`${path}/state`);
    }
    await page.waitForTimeout(2000);
    expect(activity).toHaveLength(1);
    expect(await snapshot()).toEqual(viewed);
    await page.locator(`a[href="${base}/agents"]`).first().click();
    await expect(page).toHaveURL(new RegExp(`${base}/agents$`));
    await page.goBack();
    await expect(draft).toBeVisible();
    await expect.poll(() => activity.length).toBe(2);
    const returned = await snapshot();
    expect(returned.last_activity_at > viewed.last_activity_at).toBe(true);
    await draft.fill("不要调用任何工具，只回复四个汉字：验证通过");
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await expect
      .poll(async () => (await snapshot()).last_activity_at, { timeout: 30000 })
      .not.toBe(returned.last_activity_at);
    await expect
      .poll(
        async () => {
          const runs = await fixture.request<Array<{ status: string }>>(
            `${path}/runs`,
          );
          return (
            runs.length > 0 &&
            runs.every((run) =>
              ["success", "error", "timeout", "interrupted"].includes(
                run.status,
              ),
            )
          );
        },
        { timeout: 120000 },
      )
      .toBe(true);
    const runs = await fixture.request<Array<{ status: string }>>(
      `${path}/runs`,
    );
    expect(runs.some((run) => run.status === "success")).toBe(true);
    await expect(
      page.getByText("验证通过", { exact: true }).first(),
    ).toBeVisible();
    const evidence = resolve(process.cwd(), "../../.local-stack/evidence");
    mkdirSync(evidence, { recursive: true });
    await page.screenshot({
      path: resolve(evidence, "retention-browser.png"),
      fullPage: true,
    });
    writeFileSync(
      resolve(evidence, "retention-browser.json"),
      JSON.stringify(
        {
          project: fixture.projectId,
          thread: thread.thread_id,
          activityReports: activity.length,
          checks: [
            "view-renews",
            "background-reads-do-not-renew",
            "return-renews",
            "send-renews",
            "real-model-success",
          ],
        },
        null,
        2,
      ),
    );
  } finally {
    await page.close();
    await fixture.request(path, "DELETE");
    await fixture.cleanup();
  }
});
