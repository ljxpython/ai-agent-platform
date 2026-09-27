import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createPlatformFixture } from "./support/platform";

test.setTimeout(60_000);

const apiUrl = "http://127.0.0.1:12143";
const password = "Error-contract-test-only-2026!";

test("browser SDK keeps pending identity and platform HTTP errors stay safe", async ({
  page,
  request,
}) => {
  test.skip(
    process.env.RUN_ERROR_CONTRACT_E2E !== "1",
    "Requires isolated error_contract_server.py fixture",
  );
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-error-contract-e2e.json", "utf8"),
  ) as {
    project_id: string;
    users: Record<string, string>;
  };
  async function token(name: string) {
    const response = await request.post(`${apiUrl}/api/identity/session`, {
      data: { username: `error-contract-${name}`, password },
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()).tokens.access_token as string;
  }
  const owner = await token("owner");
  const peer = await token("peer");
  const headers = (accessToken: string) => ({
    authorization: `Bearer ${accessToken}`,
    "x-project-id": fixture.project_id,
  });
  const requests: string[] = [];
  page.on("request", (outgoing) => {
    if (outgoing.url().includes("/api/langgraph/threads"))
      requests.push(`${outgoing.method()} ${new URL(outgoing.url()).pathname}`);
  });
  await page.goto("/auth/login");
  const result = await page.evaluate(
    async ({ accessToken, projectId, userId }) => {
      const { createLanggraphAuthorizedFetch } =
        await import("/src/services/langgraph/client.ts");
      const { createSessionService } =
        await import("/src/services/threads/session.service.ts");
      sessionStorage.clear();
      const fetch = createLanggraphAuthorizedFetch({
        getAccessToken: () => accessToken,
        refreshAccessToken: async () => "",
      });
      const service = createSessionService(fetch, projectId, userId);
      let first:
        | { message: string; code?: string; extra?: Record<string, unknown> }
        | undefined;
      let second = "";
      try {
        await service.create("workflow_demo", undefined, "fixture");
      } catch (error) {
        const value = error as Error & {
          code?: string;
          extra?: Record<string, unknown>;
        };
        first = {
          message: value.message,
          code: value.code,
          extra: value.extra,
        };
      }
      try {
        await service.create("workflow_demo", undefined, "fixture");
      } catch (error) {
        second = (error as Error).message;
      }
      const ready = await service.create("workflow_demo", undefined, "fixture");
      return { first, second, ready };
    },
    {
      accessToken: owner,
      projectId: fixture.project_id,
      userId: fixture.users.owner,
    },
  );
  const threadId = result.first?.extra?.thread_id as string;
  expect(threadId).toMatch(/^[0-9a-f-]{36}$/);
  expect(result.first?.code).toBe("langgraph_upstream_request_failed");
  expect(result.first?.message).toContain(threadId);
  expect(result.second).toContain("请稍后重试");
  expect(result.ready.thread_id).toBe(threadId);
  expect(
    requests.filter((item) => item === "POST /api/langgraph/threads"),
  ).toHaveLength(1);
  expect(requests.filter((item) => item.endsWith("/reconcile"))).toHaveLength(
    2,
  );

  for (const [accessToken, path, expected] of [
    [peer, `/api/langgraph/threads/${threadId}`, 403],
    [
      owner,
      `/api/langgraph/threads/${threadId}/workspace/content?path=missing`,
      404,
    ],
    [
      owner,
      `/api/langgraph/threads/${threadId}/workspace/content?path=forced-502`,
      502,
    ],
  ] as const) {
    const response = await request.get(`${apiUrl}${path}`, {
      headers: headers(accessToken),
    });
    expect(response.status()).toBe(expected);
    const body = await response.json();
    expect(body.request_id).toBe(response.headers()["x-request-id"]);
    expect(JSON.stringify(body)).not.toContain("private-upstream-marker");
  }
  const invalid = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers: headers(owner),
  });
  expect(invalid.status()).toBe(422);
  expect((await invalid.json()).error.code).toBe("validation_failed");
});

test("live browser displays the request ID from a denied Thread response", async ({
  page,
}) => {
  test.skip(
    process.env.RUN_ERROR_CONTRACT_REAL_E2E !== "1",
    "Requires the existing local platform stack",
  );
  const fixture = await createPlatformFixture("reference_agent");
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
    const deniedThread = crypto.randomUUID();
    const responsePromise = page.waitForResponse((response) =>
      response.url().endsWith(`/api/langgraph/threads/${deniedThread}`),
    );
    await page.goto(
      `/workspace/projects/${fixture.projectId}/chat/${deniedThread}`,
    );
    const response = await responsePromise;
    expect(response.status()).toBe(403);
    const body = await response.json();
    const requestId = response.headers()["x-request-id"];
    expect(body.request_id).toBe(requestId);
    await expect(page.getByText(new RegExp(requestId))).toBeVisible();
  } finally {
    await fixture.cleanup();
  }
});
