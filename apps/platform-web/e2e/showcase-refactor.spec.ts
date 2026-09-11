import { expect, test } from "@playwright/test";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { createPlatformFixture } from "./support/platform";

test("Showcase browser approvals produce a real 43.50 workspace result", async ({ page }) => {
  test.skip(!process.env.SHOWCASE_TEST_WORKSPACES || process.env.PLATFORM_TEST_SEED_MODEL !== "1", "Requires isolated real-model Showcase runner");
  test.setTimeout(360000);
  const fixture = await createPlatformFixture("showcase_demo");
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  try {
    await page.addInitScript(({ tokens, projectId }) => {
      localStorage.setItem("pw:auth:token-set", JSON.stringify({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, tokenType: tokens.token_type }));
      localStorage.setItem("pw:workspace:project-id", projectId);
    }, { tokens: fixture.tokens, projectId: fixture.projectId });
    await page.goto(`/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`);
    const draft = page.getByRole("textbox", { name: "消息草稿" });
    await draft.fill("请读取 /workspace/report.py 和 /workspace/sales.csv，修复金额计算（单价乘数量），执行命令 python report.py | tee result.txt，让工具输出和 /workspace/result.txt 同时保留真实计算结果 43.50，然后 read_file 读取验证。不要委派子任务。必须真实执行、遵守审批，不要仅回复数字。");
    await expect(page.getByRole("button", { name: "发送", exact: true })).toBeEnabled();
    await draft.press("Enter");
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/);
    await expect(draft).toHaveValue("");
    await draft.fill("保留下一轮草稿");
    const reviews = page.getByRole("region", { name: "待审批操作" });
    const threadId = new URL(page.url()).pathname.split("/").pop();
    let approvals = 0;
    for (let attempt = 0; attempt < 12; attempt++) {
      let phase = "active";
      await expect.poll(async () => {
        if (await reviews.isVisible()) return phase = "review";
        const runs = await fixture.request<Array<{ status: string }>>(`/api/langgraph/threads/${threadId}/runs`);
        return phase = runs[0] && !["pending", "running", "interrupted"].includes(runs[0].status) ? runs[0].status : "active";
      }, { timeout: 90000 }).not.toBe("active");
      if (phase !== "review") { expect(phase).toBe("success"); break; }
      const selectors = reviews.getByRole("combobox");
      approvals += await selectors.count();
      for (const selector of await selectors.all()) await selector.selectOption("approve");
      await reviews.getByRole("button", { name: "提交所选决策" }).click();
      await expect(reviews).not.toBeVisible({ timeout: 30000 });
    }
    expect(approvals).toBeGreaterThanOrEqual(2);
    const state = await fixture.request<{ values: { messages: Array<{ type: string; name?: string; content: unknown }> } }>(`/api/langgraph/threads/${threadId}/state`);
    const tools = state.values.messages.filter(message => message.type === "tool");
    expect(tools.some(message => message.name === "execute" && JSON.stringify(message.content).includes("43.50"))).toBe(true);
    expect(tools.some(message => message.name === "read_file" && JSON.stringify(message.content).includes("43.50"))).toBe(true);
    const workspaces = process.env.SHOWCASE_TEST_WORKSPACES!;
    const results = await Promise.all((await readdir(workspaces)).map(async directory =>
      readFile(join(workspaces, directory, "workspace", "result.txt"), "utf8").catch(() => "")));
    expect(results.some(value => /^(?:Total sales:\s*)?43\.50$/.test(value.trim()))).toBe(true);
    await expect(draft).toHaveValue("保留下一轮草稿");
    await page.reload();
    await expect(page.getByTestId("transcript").first()).toContainText("43.50", { timeout: 30000 });
    await page.getByRole("button", { name: "会话详情", exact: true }).click();
    await page.getByRole("dialog", { name: "会话详情" }).getByRole("button", { name: "Files", exact: true }).click();
    await expect(page.getByRole("dialog")).toContainText("result.txt");
    expect(errors).toEqual([]);
    await page.screenshot({ path: test.info().outputPath("showcase-mobile.png"), fullPage: true, animations: "disabled" });
  } catch (error) {
    await page.screenshot({ path: test.info().outputPath("showcase-failure.png"), fullPage: true, animations: "disabled" });
    throw error;
  } finally { await page.close(); await fixture.cleanup(); }
});
