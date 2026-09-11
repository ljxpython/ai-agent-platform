import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

test("copied workbench keeps parameters, drafts, inline editing and responsive dialogs working", async ({ page }) => {
  test.setTimeout(240000);
  const fixture = await createPlatformFixture("workflow_demo");
  const failures: string[] = [];
  const runBodies: Record<string, unknown>[] = [];
  page.on("pageerror", error => failures.push(error.message));
  page.on("request", request => {
    if (request.method() === "POST" && (request.url().endsWith("/commands") || request.url().endsWith("/runs"))) runBodies.push(request.postDataJSON());
  });
  try {
    await page.addInitScript(({ tokens, projectId }) => {
      localStorage.setItem("pw:auth:token-set", JSON.stringify({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, tokenType: tokens.token_type }));
      localStorage.setItem("pw:workspace:project-id", projectId);
    }, { tokens: fixture.tokens, projectId: fixture.projectId });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/workspace/projects/${fixture.projectId}/chat?agentId=${fixture.agent.id}`);
    const draft = page.getByRole("textbox", { name: "消息草稿" });
    await draft.fill("请只回复：工作台还原验收正常。不要调用工具。");
    await page.reload();
    await expect(draft).toHaveValue("请只回复：工作台还原验收正常。不要调用工具。");
    await page.getByRole("button", { name: "运行参数", exact: true }).click();
    const options = page.getByRole("dialog", { name: "运行参数" });
    await options.getByLabel("Max Tokens").fill("-1");
    await options.getByRole("button", { name: "确认", exact: true }).click();
    await expect(options.getByRole("alert")).toBeVisible();
    await options.getByLabel("Max Tokens").fill("1024");
    await options.getByRole("button", { name: "确认", exact: true }).click();
    await page.getByRole("button", { name: "运行参数", exact: true }).click();
    await options.getByLabel("Max Tokens").fill("2048");
    await options.getByRole("button", { name: "取消", exact: true }).click();
    await page.getByRole("button", { name: "发送", exact: true }).click();
    await expect(page.getByTestId("transcript").first().locator('[data-author="agent"]')).toContainText(/工\s*作\s*台\s*还\s*原\s*验\s*收\s*正\s*常/, { timeout: 90000 });
    await expect(page.getByRole("button", { name: "编辑", exact: true })).toBeVisible({ timeout: 30000 });
    expect(JSON.stringify(runBodies)).toContain('"max_tokens":1024');
    expect(JSON.stringify(runBodies)).not.toContain('"max_tokens":2048');
    await page.getByRole("button", { name: "重试", exact: true }).click();
    await expect(page.getByRole("button", { name: "上一个分支", exact: true })).toBeEnabled({ timeout: 90000 });
    const beforeNavigation = runBodies.length;
    await page.getByRole("button", { name: "上一个分支", exact: true }).click();
    await expect(page.getByTestId("transcript").first().locator('[data-author="agent"]')).toContainText(/工\s*作\s*台\s*还\s*原\s*验\s*收\s*正\s*常/);
    expect(runBodies).toHaveLength(beforeNavigation);
    await page.getByRole("button", { name: "返回最新", exact: true }).click();
    await page.getByRole("button", { name: "编辑", exact: true }).click();
    const inlineEditor = page.getByTestId("transcript").getByRole("textbox");
    await inlineEditor.fill("请只回复：原位编辑正常。不要调用工具。");
    await page.getByRole("button", { name: "提交重发", exact: true }).click();
    await expect(inlineEditor).toHaveCount(0, { timeout: 30000 });
    await expect(page.getByTestId("transcript").first().locator('[data-author="agent"]')).toContainText(/原\s*位\s*编\s*辑\s*正\s*常/, { timeout: 90000 });
    await page.reload();
    await expect(page.getByTestId("transcript").first().locator('[data-author="agent"]')).toContainText(/原\s*位\s*编\s*辑\s*正\s*常/, { timeout: 30000 });
    const commandCount = runBodies.length;
    await page.getByRole("button", { name: "会话详情", exact: true }).click();
    const drawer = page.getByRole("dialog", { name: "会话详情" });
    await expect(drawer).toBeVisible();
    await expect.poll(() => drawer.evaluate(element => element.contains(document.activeElement))).toBe(true);
    await page.keyboard.press("Shift+Tab");
    expect(await drawer.evaluate(element => element.contains(document.activeElement))).toBe(true);
    await drawer.getByRole("button", { name: "历史", exact: true }).click();
    await drawer.locator("details").nth(1).locator("summary").click();
    await expect(drawer.getByRole("button", { name: /查看此/ }).first()).toBeVisible();
    await drawer.getByRole("button", { name: /查看此/ }).first().click();
    await expect(drawer).toContainText("当前正在查看历史分支");
    expect(runBodies).toHaveLength(commandCount);
    await drawer.getByRole("button", { name: "返回最新", exact: true }).click();
    await page.keyboard.press("Escape");
    await expect(drawer).toHaveCount(0);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      for (const dark of [false, true]) {
        await page.evaluate(value => document.documentElement.classList.toggle("dark", value), dark);
        await page.screenshot({ path: test.info().outputPath(`workbench-${width}-${dark ? "dark" : "light"}.png`), animations: "disabled", fullPage: true });
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      }
      await page.getByRole("button", { name: "选择对话运行模型" }).click();
      await expect(page.getByRole("dialog", { name: "切换对话模型" })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("button", { name: "选择对话运行模型" })).toBeFocused();
      await page.getByRole("button", { name: "会话详情", exact: true }).click();
      await drawer.getByRole("button", { name: "Files", exact: true }).click();
      await expect(drawer).toContainText("当前线程还没有文件状态");
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "专注模式", exact: true }).click();
      await expect(page.getByRole("complementary", { name: "对话列表" })).toHaveCount(0);
      await page.keyboard.press("Escape");
    }
    expect(failures).toEqual([]);
  } finally { await page.close(); await fixture.cleanup(); }
});
