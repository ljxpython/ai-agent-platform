import { expect, test } from "@playwright/test";
import { createPlatformFixture, platformUrl } from "./support/platform";

test("failed first start reuses Thread and key; offline recovery and cancel allow a new action", async ({ page, context }) => {
  test.skip(process.env.Q5_QUEUE_FIXTURE !== "1", "Requires isolated slow-tool graph");
  test.setTimeout(120000);
  const fixture = await createPlatformFixture("reference_agent");
  const commands: Array<{ body: string | null; key: string | undefined }> = [];
  let creates = 0;
  let failFirst = true;
  page.on("request", request => {
    if (request.method() === "POST" && request.url().endsWith("/threads")) creates++;
    if (request.method() === "POST" && request.url().endsWith("/commands")) commands.push({ body: request.postData(), key: request.headers()["idempotency-key"] });
  });
  try {
    await page.addInitScript(({ tokens, projectId }) => {
      localStorage.setItem("pw:auth:token-set", JSON.stringify({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, tokenType: tokens.token_type }));
      localStorage.setItem("pw:workspace:project-id", projectId);
    }, { tokens: fixture.tokens, projectId: fixture.projectId });
    await page.route("**/commands", async route => {
      if (failFirst) { failFirst = false; return route.fulfill({ status: 503, json: { message: "acceptance transport failure before start" } }); }
      return route.continue();
    });
    await page.goto(`/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`);
    const draft = page.getByRole("textbox", { name: "消息草稿" });
    await draft.fill("start work");
    await expect(page.getByRole("button", { name: "发送", exact: true })).toBeEnabled();
    await draft.press("Enter");
    await expect(page.getByRole("button", { name: "核实原请求" })).toBeVisible();
    await expect(draft).toHaveValue("start work");
    const threadUrl = page.url();
    await page.getByRole("button", { name: "核实原请求" }).click();
    await expect(page.getByText("long_task", { exact: true }).first()).toBeVisible({ timeout: 30000 });
    expect(creates).toBe(1);
    expect(commands).toHaveLength(2);
    expect(commands[1]).toEqual(commands[0]);
    await draft.fill("next draft");
    await context.setOffline(true);
    await expect(draft).toHaveValue("next draft");
    await context.setOffline(false);
    await page.reload();
    await expect(page.getByText("long_task", { exact: true }).first()).toBeVisible({ timeout: 30000 });
    expect(page.url()).toBe(threadUrl);
    expect(commands).toHaveLength(2);
    await draft.fill("start work");
    const stop = page.getByRole("button", { name: "停止生成", exact: true });
    await expect(stop).toBeEnabled({ timeout: 15000 });
    await stop.click();
    await expect(page.getByRole("button", { name: "发送", exact: true })).toBeEnabled({ timeout: 45000 });
    await expect(draft).toHaveValue("start work");
    await draft.press("Enter");
    await expect(draft).toHaveValue("");
    expect(commands).toHaveLength(3);
    expect(commands[2].key).not.toBe(commands[0].key);
    expect(creates).toBe(1);
    await expect(stop).toBeEnabled({ timeout: 30000 });
    await stop.click();
    await draft.fill("done");
    await expect(page.getByRole("button", { name: "发送", exact: true })).toBeEnabled({ timeout: 45000 });
  } finally { await context.setOffline(false); await page.close(); await fixture.cleanup(); }
});

test("real gateway rejects competing Runs and changed idempotent payloads", async () => {
  test.skip(process.env.Q5_QUEUE_FIXTURE !== "1", "Requires isolated slow-tool graph");
  const fixture = await createPlatformFixture("reference_agent");
  try {
    const thread = await fixture.request<{ thread_id: string }>("/api/langgraph/threads", "POST", { graph_id: fixture.graphId, metadata: { agent_id: fixture.agent.id } });
    const body = { assistant_id: fixture.graphId, context: { model_id: fixture.modelId }, input: { messages: [{ role: "user", content: "start work" }] } };
    const start = (key: string, input = body) => fetch(`${platformUrl}/api/langgraph/threads/${thread.thread_id}/runs`, {
      method: "POST", headers: { authorization: `Bearer ${fixture.tokens.access_token}`, "x-project-id": fixture.projectId, "content-type": "application/json", "Idempotency-Key": key }, body: JSON.stringify(input),
    });
    const keys = [crypto.randomUUID(), crypto.randomUUID()];
    const results = await Promise.all(keys.map(key => start(key)));
    expect(results.map(result => result.status).sort()).toEqual([200, 409]);
    const accepted = results.findIndex(result => result.status === 200);
    const run = await results[accepted].json();
    const retry = await start(keys[accepted]);
    expect(retry.ok).toBe(true);
    expect((await retry.json()).run_id).toBe(run.run_id);
    const changed = await start(keys[accepted], { ...body, input: { messages: [{ role: "user", content: "changed" }] } });
    expect(changed.status).toBe(409);
    const runs = await fixture.request<Array<{ run_id: string }>>(`/api/langgraph/threads/${thread.thread_id}/runs`);
    expect(runs).toHaveLength(1);
    await fixture.request(`/api/langgraph/threads/${thread.thread_id}/runs/${run.run_id}/cancel`, "POST", { action: "interrupt" });
  } finally { await fixture.cleanup(); }
});
