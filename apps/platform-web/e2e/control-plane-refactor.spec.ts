import { expect, test } from "@playwright/test";
import { createPlatformFixture } from "./support/platform";

test("retained control-plane routes load through real APIs without retired requests", async ({ page }) => {
  test.setTimeout(180000);
  const fixture = await createPlatformFixture();
  const pageErrors: string[] = [];
  const retired: string[] = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const path = new URL(request.url()).pathname;
    if (/\/api\/(operations|knowledge|testcases)|\/resync/.test(path)) retired.push(path);
  });
  try {
    await page.addInitScript(({ tokens, projectId }) => {
      localStorage.setItem("pw:auth:token-set", JSON.stringify({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, tokenType: tokens.token_type }));
      localStorage.setItem("pw:workspace:project-id", projectId);
      localStorage.setItem("pw:locale", "zh-CN");
    }, { tokens: fixture.tokens, projectId: fixture.projectId });
    const paths = ["overview", "projects", `projects/${fixture.projectId}`, `projects/${fixture.projectId}/members`,
      `projects/${fixture.projectId}/agents`, `projects/${fixture.projectId}/models`, `projects/${fixture.projectId}/graphs`,
      "users", "control-plane", "announcements", "me", "security", "audit", "platform-config", "service-accounts", "system-governance"];
    const responses: Array<{ path: string; status: number }> = [];
    page.on("response", response => {
      const path = new URL(response.url()).pathname;
      if (path.startsWith("/api/") || path.startsWith("/_system/")) responses.push({ path, status: response.status() });
    });
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const path of paths) {
        const before = responses.length;
        await page.goto(`/workspace/${path}`);
        await expect(page.locator("main")).toBeVisible();
        await expect(page.locator("main h1").first()).toBeVisible({ timeout: 15000 });
        await expect.poll(() => responses.length).toBeGreaterThan(before);
        const overflow = await page.evaluate(() => [...document.querySelectorAll("main *")]
          .filter(element => element.getBoundingClientRect().right > innerWidth + 1)
          .slice(0, 8).map(element => ({ tag: element.tagName, class: element.className })));
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width} ${path}: ${JSON.stringify(overflow)}`).toBe(true);
      }
    }
    await page.goto("/workspace/no-such-page");
    await expect(page.getByText("页面不存在", { exact: true }).last()).toBeVisible();
    expect(retired).toEqual([]);
    expect(pageErrors).toEqual([]);
    expect(responses.filter(response => response.status >= 500)).toEqual([]);
    await test.info().attach("route-responses", { body: JSON.stringify(responses), contentType: "application/json" });
  } finally { await page.close(); await fixture.cleanup(); }
});

test("list loading, empty, failure and forbidden are distinct", async ({ page }) => {
  test.setTimeout(120000);
  const fixture = await createPlatformFixture();
  try {
    await page.addInitScript(({ tokens, projectId }) => {
      localStorage.setItem("pw:auth:token-set", JSON.stringify({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, tokenType: tokens.token_type }));
      localStorage.setItem("pw:workspace:project-id", projectId);
    }, { tokens: fixture.tokens, projectId: fixture.projectId });
    for (const resource of ["users", "audit", "announcements"]) {
      for (const status of [200, 503, 403]) {
        let release!: () => void;
        const gate = new Promise<void>(resolve => { release = resolve; });
        const matcher = (url: URL) => url.pathname === `/api/${resource}`;
        await page.route(matcher, async route => {
          await gate;
          await route.fulfill({ status, json: status === 200 ? { items: [], total: 0 } : { error: { code: status === 403 ? "permission_denied" : "acceptance_unavailable", message: "验收：读取不可用" } } });
        });
        await page.goto(`/workspace/${resource}`);
        await expect(page.locator('[aria-busy="true"]')).toBeVisible();
        release();
        if (status === 200) {
          await expect(page.locator('[aria-busy="false"]')).toBeVisible();
          await expect(page.locator(".pw-data-table-root")).toContainText(/暂无|没有/);
        } else {
          await expect(page.locator(".pw-data-table-root").getByRole("alert")).toContainText("列表读取失败");
          await expect(page.locator(".pw-data-table-root")).not.toContainText("暂无数据");
        }
        await page.unroute(matcher);
      }
    }
  } finally { await page.close(); await fixture.cleanup(); }
});
