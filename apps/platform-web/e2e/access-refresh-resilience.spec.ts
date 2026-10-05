import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";
import { readFileSync } from "node:fs";

test.skip(
  process.env.RUN_LOCAL_GOVERNANCE_E2E !== "1",
  "Requires isolated governance_server.py",
);
test.describe.configure({ mode: "serial" });
test.setTimeout(90_000);
const web = "http://127.0.0.1:13000";
const api = "http://127.0.0.1:12142";
const fixture = () =>
  JSON.parse(readFileSync("/tmp/platform-governance-e2e.json", "utf8")) as {
    project_id: string;
    users: Record<string, string>;
  };

async function token(request: APIRequestContext, name: string) {
  const response = await request.post(`${api}/api/identity/session`, {
    data: {
      username: `governance-${name}`,
      password: "Governance-test-only-2026!",
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).tokens;
}
async function open(page: Page, request: APIRequestContext) {
  await page.clock.install();
  const tokens = await token(request, "owner");
  const projectId = fixture().project_id;
  await page.addInitScript(
    ({ tokens, projectId }) => {
      localStorage.setItem(
        "pw:auth:token-set",
        JSON.stringify({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          tokenType: "bearer",
        }),
      );
      localStorage.setItem("pw:workspace:project-id", projectId);
    },
    { tokens, projectId },
  );
  await page.goto(`${web}/workspace/projects/${projectId}/members`);
  return projectId;
}
async function activate(page: Page) {
  await page.evaluate(() => {
    window.dispatchEvent(new Event("focus"));
    document.dispatchEvent(new Event("visibilitychange"));
  });
}

test("transient project refresh and unrelated thread denial never replace the page", async ({
  page,
  request,
}) => {
  const projectId = await open(page, request);
  await expect(
    page.getByText("成员管理", { exact: false }).first(),
  ).toBeVisible();
  let refreshes = 0;
  await page.route(`**/api/projects/${projectId}/access`, async (route) => {
    refreshes++;
    await route.fulfill({
      status: 503,
      json: { error: { code: "unavailable", message: "temporary" } },
    });
  });
  await page.clock.runFor(61_000);
  await expect.poll(() => refreshes).toBe(1);
  await activate(page);
  await page.evaluate((projectId) => {
    window.dispatchEvent(
      new CustomEvent("platform-access-denied", {
        detail: {
          scope: "thread",
          projectId,
          threadId: "other",
          method: "POST",
          code: "thread_action_denied",
        },
      }),
    );
  }, projectId);
  await page.clock.runFor(500);
  expect(refreshes).toBe(1);
  await expect(
    page.getByText("当前页面权限已失效", { exact: true }),
  ).toBeHidden();
  await expect(
    page.getByText("成员管理", { exact: false }).first(),
  ).toBeVisible();
  await page.screenshot({ path: "/tmp/access-refresh-retained.png" });
});

test("cold access failure offers retry and recovers without logging out", async ({
  page,
  request,
}) => {
  let unavailable = true;
  await page.route("**/api/projects/*/access", (route) =>
    unavailable
      ? route.fulfill({
          status: 503,
          json: { error: { code: "unavailable", message: "temporary" } },
        })
      : route.continue(),
  );
  await open(page, request);
  await expect(
    page.getByText("暂时无法确认访问权限", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("当前页面权限已失效", { exact: true }),
  ).toBeHidden();
  unavailable = false;
  await page.getByRole("button", { name: "重试", exact: true }).click();
  await expect(page).toHaveURL(/\/members$/);
  await expect(
    page.getByText("成员管理", { exact: false }).first(),
  ).toBeVisible();
});

test("REST and chat token renewal retain the login session through an authentication outage", async ({
  page,
  request,
}) => {
  await open(page, request);
  await expect(
    page.getByText("成员管理", { exact: false }).first(),
  ).toBeVisible();
  await page.route("**/api/identity/session/refresh", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { code: "unavailable", message: "temporary" } },
    }),
  );
  const result = await page.evaluate(async () => {
    const httpPath = "/src/services/http/client.ts";
    const chatPath = "/src/services/langgraph/client.ts";
    const { refreshAccessToken } = await import(httpPath);
    const { createLanggraphAuthorizedFetch } = await import(chatPath);
    const before = localStorage.getItem("pw:auth:token-set");
    const codes: string[] = [];
    try {
      await refreshAccessToken();
    } catch (error) {
      codes.push((error as { code: string }).code);
    }
    const chatFetch = createLanggraphAuthorizedFetch({
      fetchImpl: async () => new Response("", { status: 401 }),
    });
    try {
      await chatFetch(`${location.origin}/api/langgraph/threads/test`);
    } catch (error) {
      codes.push((error as { code: string }).code);
    }
    return {
      codes,
      retained:
        Boolean(before) && before === localStorage.getItem("pw:auth:token-set"),
    };
  });
  expect(result).toEqual({
    codes: ["auth_refresh_unavailable", "auth_refresh_unavailable"],
    retained: true,
  });
  await expect(page).toHaveURL(/\/members$/);
});

test("real project membership revocation still removes the page and is recoverable after restoration", async ({
  page,
  request,
}) => {
  const projectId = await open(page, request);
  await expect(
    page.getByText("成员管理", { exact: false }).first(),
  ).toBeVisible();
  const manager = await token(request, "manager");
  const path = `${api}/api/projects/${projectId}/members/${fixture().users.owner}`;
  const headers = { authorization: `Bearer ${manager.access_token}` };
  try {
    expect((await request.delete(path, { headers })).ok()).toBeTruthy();
    await page.clock.runFor(61_000);
    await expect(
      page.getByText("当前页面权限已失效", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("成员管理", { exact: false }).first(),
    ).toBeHidden();
    await page.screenshot({ path: "/tmp/access-refresh-revoked.png" });
  } finally {
    const restored = await request.put(path, {
      headers,
      data: { role: "project_executor" },
    });
    expect(restored.ok()).toBeTruthy();
  }
  await page.clock.runFor(61_000);
  await expect(
    page.getByText("当前页面权限已失效", { exact: true }),
  ).toBeHidden();
  await expect(
    page.getByText("成员管理", { exact: false }).first(),
  ).toBeVisible();
});
