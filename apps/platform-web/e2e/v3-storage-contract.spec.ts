import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createPlatformFixture } from "./support/platform";

test.beforeEach(() => {
  test.skip(
    process.env.RUN_V3_STORAGE_FIXTURE !== "1",
    "Requires the registered deterministic v3 graph",
  );
  test.setTimeout(120000);
});

async function open(page: Page) {
  const config = JSON.parse(
    readFileSync(
      resolve(process.cwd(), "../runtime-service/langgraph.json"),
      "utf8",
    ),
  );
  expect(config.graphs.reference_agent.path).toBe(
    "./tests/fixtures/v3_browser.py:get_agent",
  );
  const fixture = await createPlatformFixture("reference_agent");
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
  const thread = () => new URL(page.url()).pathname.split("/").pop()!;
  const path = () => `/api/langgraph/threads/${thread()}`;
  return {
    ...fixture,
    thread,
    path,
    async send(prompt: string) {
      await draft.fill(prompt);
      await expect(
        page.getByRole("button", { name: "发送", exact: true }),
      ).toBeEnabled();
      await draft.press("Enter");
      await expect(draft).toHaveValue("", { timeout: 30000 });
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/, { timeout: 30000 });
    },
    async completed() {
      await expect
        .poll(
          async () => {
            const runs = await fixture.request<Array<{ status: string }>>(
              `${path()}/runs`,
            );
            return (
              runs.some((run) => run.status === "success") &&
              runs.every((run) =>
                ["success", "interrupted"].includes(run.status),
              )
            );
          },
          { timeout: 45000 },
        )
        .toBe(true);
    },
    async dispose() {
      await page.close();
      if (/^[0-9a-f-]{36}$/.test(thread()))
        await fixture.request(path(), "DELETE");
      await fixture.cleanup();
    },
  };
}

for (const scenario of ["V3_TEXT", "V3_REASONING", "V3_USAGE"]) {
  test(`real v3 browser renders ${scenario} without duplicate content`, async ({
    page,
  }) => {
    const fixture = await open(page);
    try {
      await fixture.send(scenario);
      await fixture.completed();
      const transcript = page.getByTestId("transcript");
      await expect(
        transcript.locator(".pw-markdown").filter({ hasText: "正文验收完成" }),
      ).toHaveCount(1);
      if (scenario === "V3_REASONING") {
        const reasoning = transcript
          .locator("details")
          .filter({ hasText: "公开思考验收" });
        await expect(reasoning).toHaveCount(1);
        await reasoning.locator("summary").click();
        const expanded = await reasoning.evaluate(
          (node) => (node as HTMLDetailsElement).open,
        );
        await expect(
          transcript
            .locator(".pw-markdown")
            .filter({ hasText: "正文验收完成" }),
        ).not.toContainText("公开思考验收");
        await expect
          .poll(() =>
            reasoning.evaluate((node) => (node as HTMLDetailsElement).open),
          )
          .toBe(expanded);
      }
      if (scenario === "V3_USAGE")
        await expect(
          page.getByText("输入 7 · 输出 11 tok", { exact: false }),
        ).toBeVisible();
      else await expect(page.getByText(/输入 0.*输出 0/)).toHaveCount(0);
      await page.reload();
      await expect(
        transcript.locator(".pw-markdown").filter({ hasText: "正文验收完成" }),
      ).toHaveCount(1, { timeout: 30000 });
      await test.info().attach("browser.png", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    } finally {
      await fixture.dispose();
    }
  });
}

test("streamed tool arguments, failures and retry retain call/result identity", async ({
  page,
}) => {
  const fixture = await open(page);
  try {
    await fixture.send("V3_TOOLS");
    await fixture.completed();
    await expect(page.getByTestId("transcript")).toContainText("验收完成");
    const state = await fixture.request<{
      values: {
        messages: Array<{
          type: string;
          tool_calls?: Array<{ id: string; args: { value: string } }>;
          tool_call_id?: string;
          status?: string;
          content: unknown;
        }>;
      };
    }>(`${fixture.path()}/state`);
    const calls = state.values.messages.flatMap(
      (message) => message.tool_calls ?? [],
    );
    const results = state.values.messages.filter(
      (message) => message.type === "tool",
    );
    expect(calls.map((call) => call.args.value)).toEqual([
      "first",
      "fail",
      "retry",
    ]);
    expect(results.map((message) => message.tool_call_id)).toEqual(
      calls.map((call) => call.id),
    );
    expect(results.map((message) => message.status)).toEqual([
      "success",
      "error",
      "success",
    ]);
    await expect(
      page.getByTestId("transcript").getByRole("button", { name: /lookup/ }),
    ).toHaveCount(3);
    await test.info().attach("tools.json", {
      body: JSON.stringify({ calls, results }),
      contentType: "application/json",
    });
  } finally {
    await fixture.dispose();
  }
});

test("a child graph failure stays scoped while the parent completes", async ({
  page,
}) => {
  const fixture = await open(page);
  try {
    await fixture.send("V3_CHILD");
    await fixture.completed();
    await expect(page.getByTestId("transcript")).toContainText(
      "父任务继续完成",
    );
    const card = page.getByRole("button", { name: /fixture.*子智能体/ });
    await expect(card).toBeVisible();
    await card.click();
    await expect(page.getByTestId("transcript")).toContainText(
      "fixture child failed",
    );
    await expect(page.getByTestId("transcript")).toContainText(
      "子任务执行过程",
    );
    await test.info().attach("child.png", {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    });
  } finally {
    await fixture.dispose();
  }
});

test("approval resumes by interrupt ID without starting a second conversation", async ({
  page,
}) => {
  const fixture = await open(page);
  try {
    await fixture.send("V3_APPROVAL");
    const url = page.url();
    const reviews = page.getByRole("region", { name: "待审批操作" });
    await expect(reviews).toBeVisible({ timeout: 45000 });
    await reviews.getByRole("button", { name: "批准 (Approve)" }).click();
    await reviews.getByRole("button", { name: "确认批准所选操作" }).click();
    await fixture.completed();
    await expect(reviews).not.toBeVisible();
    await expect(page.getByTestId("transcript")).toContainText("验收完成");
    expect(page.url()).toBe(url);
  } finally {
    await fixture.dispose();
  }
});

test("expired cursor and offline recovery hydrate without replaying a command", async ({
  page,
  context,
}) => {
  const fixture = await open(page);
  let expired = 0,
    reconnected = 0,
    commands = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/commands"))
      commands++;
  });
  try {
    await fixture.send("V3_TEXT");
    await fixture.completed();
    await page.route("**/stream/events**", async (route) => {
      if (expired++ === 0)
        return route.fulfill({
          status: 410,
          json: {
            error: {
              code: "cursor_expired",
              message: "Cursor expired",
              request_id: "v3-storage-expired",
            },
          },
        });
      reconnected++;
      await route.continue();
    });
    await page.reload();
    await expect.poll(() => reconnected, { timeout: 30000 }).toBeGreaterThan(0);
    await expect(page.getByTestId("transcript")).toContainText("正文验收完成");
    await context.setOffline(true);
    await context.setOffline(false);
    await page.reload();
    await expect(page.getByTestId("transcript")).toContainText("正文验收完成");
    expect(commands).toBe(1);
  } finally {
    await context.setOffline(false);
    await fixture.dispose();
  }
});

test("an explicit v2 run renders through the real thread protocol", async ({
  page,
}) => {
  const fixture = await open(page);
  try {
    await page.route("**/commands", async (route) => {
      const body = route.request().postDataJSON();
      if (body.method === "run.start") body.params.version = "v2";
      await route.continue({ postData: JSON.stringify(body) });
    });
    await fixture.send("V3_TEXT");
    await fixture.completed();
    await expect(page.getByTestId("transcript")).toContainText("正文验收完成");
    const runs = await fixture.request<Array<{ kwargs: { version: string } }>>(
      `${fixture.path()}/runs`,
    );
    expect(runs).toHaveLength(1);
    expect(runs[0]?.kwargs.version).toBe("v2");
  } finally {
    await fixture.dispose();
  }
});
