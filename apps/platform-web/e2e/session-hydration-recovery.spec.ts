import { expect, test, type Page } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { platformUrl, testCredentials } from "./support/platform";

const evidence = resolve(
  import.meta.dirname,
  "../../../docs/projects/20261107-session-hydration-and-artifact-offloading",
);
const saved = JSON.parse(
  readFileSync(resolve(evidence, "image-e2e-evidence.json"), "utf8"),
);

test("late snapshot, expired cursor and background run converge without resubmission", async ({
  context,
  page,
}) => {
  test.setTimeout(240000);
  const login = await fetch(platformUrl + "/api/identity/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(testCredentials()),
  });
  expect(login.ok).toBe(true);
  const { tokens } = await login.json();
  const headers = {
    authorization: `Bearer ${tokens.access_token}`,
    "x-project-id": saved.projectId,
    "content-type": "application/json",
  };
  async function request(path: string, body?: unknown) {
    const response = await fetch(platformUrl + path, {
      headers,
      method: body ? "POST" : "GET",
      body: body && JSON.stringify(body),
    });
    expect(response.ok, `${path}: ${response.status}`).toBe(true);
    return response.json();
  }
  await context.addInitScript(
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
  const original = await request(`/api/langgraph/threads/${saved.threadId}`);
  const title = `Hydration race ${crypto.randomUUID().slice(0, 8)}`;
  const { thread_id: threadId } = await request("/api/langgraph/threads", {
    graph_id: "dearflow_agent",
    metadata: {
      graph_id: "dearflow_agent",
      agent_id: original.metadata.agent_id,
      title,
    },
  });
  const url = `/workspace/projects/${saved.projectId}/chat/${threadId}`;
  await page.setViewportSize({ width: 1440, height: 1000 });
  let release!: () => void;
  let captured!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const snapshotCaptured = new Promise<void>((resolve) => {
    captured = resolve;
  });
  let snapshotIntercepted = false;
  await page.route(`**/threads/${threadId}/state`, async (route) => {
    if (snapshotIntercepted) return route.continue();
    snapshotIntercepted = true;
    const response = await route.fetch();
    captured();
    await held;
    await route.fulfill({ response });
  });
  let observerCommands = 0;
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/commands"))
      observerCommands++;
  });
  await page.goto(url);
  await snapshotCaptured;
  const producer = await context.newPage();
  await producer.goto(url);
  await producer.getByRole("button", { name: "选择对话运行模型" }).click();
  await producer
    .getByRole("button")
    .filter({ hasText: "xiaok DeepSeek E2E" })
    .first()
    .click();
  await producer.keyboard.press("Escape");
  async function send(marker: string, previousRuns: number) {
    await producer
      .getByRole("textbox", { name: "消息草稿" })
      .fill(`只回答 ${marker}，不要调用工具。`);
    await producer.getByRole("button", { name: "发送", exact: true }).click();
    await expect
      .poll(
        async () => {
          const runs = await request(`/api/langgraph/threads/${threadId}/runs`);
          return runs.length > previousRuns && runs[0].status === "success";
        },
        { timeout: 90000 },
      )
      .toBe(true);
  }
  const answer = (target: Page, marker: string) =>
    target.locator(".pw-markdown:visible").filter({ hasText: marker });
  await send("LATE_SNAPSHOT_OK", 0);
  release();
  await expect(answer(page, "LATE_SNAPSHOT_OK")).toHaveCount(1, {
    timeout: 30000,
  });
  await page.screenshot({
    path: resolve(evidence, "screenshots/recovery-late-snapshot.png"),
    fullPage: true,
  });

  let expired = 0;
  let reconnected = 0;
  await page.route(`**/threads/${threadId}/stream/events**`, async (route) => {
    if (expired === 0) {
      expired++;
      await route.fulfill({
        status: 410,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "cursor_expired",
            message: "Cursor expired",
            request_id: "hydration-expired-test",
          },
        }),
      });
    } else {
      reconnected++;
      await route.continue();
    }
  });
  await page.reload();
  await expect.poll(() => expired).toBe(1);
  await expect.poll(() => reconnected, { timeout: 30000 }).toBeGreaterThan(0);
  await expect(answer(page, "LATE_SNAPSHOT_OK")).toHaveCount(1);
  await page.screenshot({
    path: resolve(evidence, "screenshots/recovery-expired-cursor.png"),
    fullPage: true,
  });

  await page
    .getByRole("button", { name: "新建会话", exact: true })
    .first()
    .click();
  const runs = await request(`/api/langgraph/threads/${threadId}/runs`);
  await send("BACKGROUND_DISCOVERY_OK", runs.length);
  await page.getByRole("button", { name: title, exact: true }).click();
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(answer(page, "BACKGROUND_DISCOVERY_OK")).toHaveCount(1, {
    timeout: 30000,
  });
  expect(observerCommands).toBe(0);
  const finalRuns = await request(`/api/langgraph/threads/${threadId}/runs`);
  expect(finalRuns).toHaveLength(2);
  await page.screenshot({
    path: resolve(evidence, "screenshots/recovery-background-run.png"),
    fullPage: true,
  });
  writeFileSync(
    resolve(evidence, "recovery-e2e-evidence.json"),
    JSON.stringify(
      {
        threadId,
        delayedSnapshot: true,
        expired,
        reconnected,
        observerCommands,
        successfulRuns: finalRuns.length,
        provider: "xiaok DeepSeek",
      },
      null,
      2,
    ),
  );
});
