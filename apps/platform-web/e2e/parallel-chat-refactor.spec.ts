import { expect, test, type Request } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 390, height: 844 }]) {
  test(`parallel approvals and nested scoped streams ${viewport.width}`, async ({ page }) => {
    test.skip(process.env.Q5_QUEUE_FIXTURE !== "1", "Requires isolated contract graph");
    test.setTimeout(120000);
    const fixture = await createPlatformFixture("workflow_demo");
    if (viewport.width === 1440) {
      await fixture.request("/api/langgraph/threads", "POST", { graph_id: "workflow_demo", metadata: { agent_id: fixture.agent.id, title: "空白切换验证" } });
    }
    const failures: string[] = [];
    const activeStreams = new Set<Request>();
    let commands = 0;
    page.on("request", request => {
      if (request.url().endsWith("/stream/events")) activeStreams.add(request);
      if (request.method() === "POST" && request.url().endsWith("/commands")) commands++;
    });
    page.on("requestfinished", request => activeStreams.delete(request));
    page.on("requestfailed", request => activeStreams.delete(request));
    page.on("pageerror", error => failures.push(error.message));
    await page.setViewportSize(viewport);
    try {
      await page.addInitScript(({ tokens, projectId }) => {
        localStorage.setItem("pw:auth:token-set", JSON.stringify({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, tokenType: tokens.token_type }));
        localStorage.setItem("pw:workspace:project-id", projectId);
      }, { tokens: fixture.tokens, projectId: fixture.projectId });
      await page.goto(`/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`);
      const draft = page.getByRole("textbox", { name: "消息草稿" });
      await draft.fill("parallel task");
      await expect(page.getByRole("button", { name: "发送", exact: true })).toBeEnabled();
      await draft.press("Enter");
      const reviews = page.getByRole("region", { name: "待审批操作" });
      await expect(reviews).toContainText("2 项请求", { timeout: 45000 });
      const tasks = page.locator('[aria-label="子任务"]');
      await expect(tasks).toBeVisible();
      // Scoped replay discovers nested nodes asynchronously and can reorder rows.
      // Expand only currently closed nodes, never retain positional locators.
      await expect.poll(async () => {
        const closed = tasks.locator('section > button[aria-expanded="false"]');
        while (await closed.count()) await closed.first().click();
        return tasks.textContent();
      }, { timeout: 30000 }).toContain("NESTED_PRIVATE");
      await expect(tasks).toContainText("LEFT_PRIVATE");
      await expect(tasks).toContainText("RIGHT_PRIVATE");
      await expect(page.getByTestId("transcript").first()).not.toContainText("_PRIVATE");
      // Decisions deliberately chosen in reverse display order; IDs own the mapping.
      const right = reviews.locator("article").filter({ hasText: "/right.txt" });
      await right.getByRole("combobox").selectOption("reject");
      await right.getByRole("textbox", { name: "拒绝原因" }).fill("Do not change right file");
      const left = reviews.locator("article").filter({ hasText: "/left.txt" });
      await left.getByRole("combobox").nth(1).selectOption("approve");
      await left.getByRole("combobox").first().selectOption("edit");
      await left.getByRole("textbox").fill(JSON.stringify({ path: "/left.txt", count: 4, enabled: false }));
      await expect(left).toContainText("变更字段：count、enabled");
      const resumed = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/commands"));
      await reviews.getByRole("button", { name: "提交所选决策" }).click();
      expect((await resumed).ok()).toBe(true);
      await expect(page.getByTestId("transcript").first()).toContainText("并行审批完成", { timeout: 45000 });
      const thread = new URL(page.url()).pathname.split("/").pop();
      const state = await fixture.request<{ values: { outcomes: Array<{ branch: string; executed: boolean; args: { count: number; enabled?: boolean } }>; files: Record<string, unknown> } }>(`/api/langgraph/threads/${thread}/state`);
      expect(state.values.outcomes).toHaveLength(3);
      expect(state.values.outcomes.find(item => item.branch === "RIGHT")?.executed).toBe(false);
      expect(state.values.outcomes.find(item => item.args.enabled === false)?.args.count).toBe(4);
      expect(Object.keys(state.values.files)).toEqual(["/left.txt"]);
      await page.getByRole("button", { name: "会话详情", exact: true }).click();
      const drawer = page.getByRole("dialog", { name: "会话详情" });
      await drawer.locator("summary").filter({ hasText: "运行详情" }).click();
      await expect(drawer).toContainText("success");
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      await expect(page.getByRole("button", { name: "会话详情", exact: true })).toBeFocused();
      if (viewport.width < 1024) {
        await page.getByRole("button", { name: "打开导航" }).click();
        await expect(page.getByRole("navigation", { name: "移动端导航" })).toContainText("Agents");
        await page.keyboard.press("Escape");
        await expect(page.getByRole("combobox", { name: "历史对话" })).toBeVisible();
      }
      await page.getByRole("button", { name: "会话详情", exact: true }).click();
      await drawer.getByRole("button", { name: "Files", exact: true }).click();
      await expect(drawer).toContainText("/left.txt");
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
      const expandedTasks = tasks.locator('section > button[aria-expanded="true"]');
      while (await expandedTasks.count()) await expandedTasks.first().click();
      await page.locator(".pw-chat-stream").evaluate(element => { element.scrollTop = 0; });
      for (const dark of [false, true]) {
        await page.evaluate(value => document.documentElement.classList.toggle("dark", value), dark);
        await page.screenshot({ path: test.info().outputPath(`parallel-${viewport.width}-${dark ? 'dark' : 'light'}.png`), fullPage: true, animations: "disabled" });
      }
      // A full navigation destroys the document; measure SPA disposal within
      // the new document, without retaining Playwright's old request objects.
      activeStreams.clear();
      await page.reload();
      await expect(page.getByTestId("transcript").first()).toContainText("并行审批完成", { timeout: 30000 });
      await expect(page.getByRole("region", { name: "待审批操作" })).toHaveCount(0);
      if (viewport.width === 1440) {
        const submitted = commands;
        for (let index = 0; index < 20; index++) {
          const previous = [...activeStreams];
          await page.getByRole("complementary", { name: "对话列表" }).getByRole("button", { name: "空白切换验证", exact: true }).click();
          await expect.poll(() => previous.filter(request => activeStreams.has(request)).map(request => ({ url: request.url(), body: request.postData() }))).toEqual([]);
          await expect(page.getByTestId("transcript").first()).not.toContainText("并行审批完成");
          await page.getByRole("complementary", { name: "对话列表" }).getByRole("button", { name: "parallel task", exact: true }).click();
          await expect(page.getByTestId("transcript").first()).toContainText("并行审批完成", { timeout: 15000 });
        }
        expect(commands).toBe(submitted);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      expect(failures).toEqual([]);
    } finally { await page.close(); await fixture.cleanup(); }
  });
}
