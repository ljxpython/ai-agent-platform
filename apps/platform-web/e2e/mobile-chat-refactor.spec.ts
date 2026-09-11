import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

test("mobile Chat keeps composer reachable and hides desktop-only rail", async ({
  page,
}) => {
  test.setTimeout(90000);
  await page.setViewportSize({ width: 390, height: 844 });
  const fixture = await createPlatformFixture();
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
    await expect(page.getByRole("textbox", { name: "消息草稿" })).toBeVisible({
      timeout: 30000,
    });
    await expect(
      page.getByRole("complementary", { name: "对话列表" }),
    ).toBeHidden();
    await expect(
      page.getByRole("button", { name: "发送", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await expect(page.getByRole("heading", { name: "开始新的对话" })).toBeVisible();
    for (const dark of [false, true]) {
      await page.evaluate(value => document.documentElement.classList.toggle("dark", value), dark);
      await page.screenshot({ path: test.info().outputPath(`chat-mobile-${dark ? "dark" : "light"}.png`), animations: "disabled" });
    }
  } finally {
    await page.close();
    await fixture.cleanup();
  }
});

test("mobile cancel preserves next draft and does not submit a second Run", async ({
  page,
}) => {
  test.setTimeout(120000);
  await page.setViewportSize({ width: 390, height: 844 });
  const fixture = await createPlatformFixture();
  const starts: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname.endsWith("/commands")
    )
      starts.push(request.postDataJSON().method);
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
    const draft = page.getByRole("textbox", { name: "消息草稿" });
    await expect(draft).toBeVisible({ timeout: 30000 });
    await draft.fill(
      "请详细写一篇至少两千字的数据库事务与隔离级别介绍，不调用工具。",
    );
    await draft.press("Enter");
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/);
    await expect(draft).toHaveValue("");
    await draft.fill("停止后保留的草稿");
    const stop = page.getByRole("button", { name: "停止生成", exact: true });
    await expect(stop).toBeEnabled({ timeout: 30000 });
    const cancellation = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.endsWith("/cancel") &&
        response.request().method() === "POST",
    );
    await stop.click();
    expect((await cancellation).ok()).toBe(true);
    await expect(
      page.getByRole("button", { name: "发送", exact: true }),
    ).toBeEnabled({ timeout: 45000 });
    await expect(draft).toHaveValue("停止后保留的草稿");
    expect(starts).toEqual(["run.start"]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  } finally {
    await page.close();
    await fixture.cleanup();
  }
});
