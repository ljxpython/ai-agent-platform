import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test.skip(
  process.env.RUN_SSE_CONTRACT_E2E !== "1",
  "Requires isolated sse_contract_server.py fixture",
);
test.setTimeout(60_000);

test("real SDK transport receives a redacted Protocol SSE event", async ({
  page,
  request,
}) => {
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string };
  const login = await request.post(
    "http://127.0.0.1:12144/api/identity/session",
    {
      data: {
        username: "sse-contract-owner",
        password: "Sse-contract-test-only-2026!",
      },
    },
  );
  expect(login.ok()).toBeTruthy();
  const accessToken = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${accessToken}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (
      await request.post("http://127.0.0.1:12144/__test/reset", { headers })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(
    "http://127.0.0.1:12144/api/langgraph/threads",
    { headers, data: { metadata: {} } },
  );
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  await page.goto("/");
  const result = await page.evaluate(
    async ({ accessToken, projectId, threadId }) => {
      const { ProtocolSseTransportAdapter } =
        await import("/src/services/langgraph/transport.ts");
      const transport = new ProtocolSseTransportAdapter({
        apiUrl: `${location.origin}/api/langgraph`,
        threadId,
        fetch: (input, init) => {
          const headers = new Headers(init?.headers);
          headers.set("authorization", `Bearer ${accessToken}`);
          headers.set("x-project-id", projectId);
          return fetch(input, { ...init, headers });
        },
        maxReconnectAttempts: 0,
        idleReconnect: false,
      });
      const handle = transport.openEventStream({ channels: ["values"] });
      try {
        await Promise.race([
          handle.ready,
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error("SSE handshake timeout")), 5000),
          ),
        ]);
        const next = await Promise.race([
          handle.events[Symbol.asyncIterator]().next(),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error("SSE event timeout")), 5000),
          ),
        ]);
        return next.value;
      } finally {
        handle.close();
        await transport.close();
      }
    },
    { accessToken, projectId: fixture.project_id, threadId },
  );
  expect(result.method).toBe("values");
  expect(result.params.thread_id).toBe(threadId);
});

test("controlled advance reaches the installed SDK and closes the subscription", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const accessToken = (await login.json()).tokens.access_token as string;
  const controlHeaders = {
    authorization: `Bearer ${accessToken}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (
      await request.post(`${apiUrl}/__test/reset`, { headers: controlHeaders })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers: controlHeaders,
        data: { id: "V07" },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers: {
      authorization: `Bearer ${accessToken}`,
      "x-project-id": fixture.project_id,
    },
    data: { metadata: {} },
  });
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  await page.goto("/");
  const received = page.evaluate(
    async ({ accessToken, projectId, threadId }) => {
      const { ProtocolSseTransportAdapter } =
        await import("/src/services/langgraph/transport.ts");
      const transport = new ProtocolSseTransportAdapter({
        apiUrl: `${location.origin}/api/langgraph`,
        threadId,
        fetch: (input, init) => {
          const headers = new Headers(init?.headers);
          headers.set("authorization", `Bearer ${accessToken}`);
          headers.set("x-project-id", projectId);
          return fetch(input, { ...init, headers });
        },
        maxReconnectAttempts: 0,
        idleReconnect: false,
      });
      const handle = transport.openEventStream({ channels: ["values"] });
      try {
        await handle.ready;
        const result = await handle.events[Symbol.asyncIterator]().next();
        return result.value;
      } finally {
        handle.close();
        await transport.close();
      }
    },
    { accessToken, projectId: fixture.project_id, threadId },
  );
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, {
              headers: controlHeaders,
            })
          ).json()
        ).open,
    )
    .toBe(1);
  const event = {
    type: "event",
    seq: 2,
    event_id: "advanced-2",
    method: "values",
    params: {
      thread_id: threadId,
      run_id: "run-2",
      namespace: [],
      data: {
        messages: [
          { id: "advanced-message", type: "ai", content: "advanced token" },
        ],
      },
    },
  };
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers: controlHeaders,
        data: {
          thread_id: threadId,
          chunks: [
            "event: event\r",
            `\ndata: ${JSON.stringify(event)}\r`,
            "\n\r\n",
          ],
        },
      })
    ).ok(),
  ).toBeTruthy();
  expect((await received).params.data.messages[0].content).toBe(
    "advanced token",
  );
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, {
              headers: controlHeaders,
            })
          ).json()
        ).closed,
    )
    .toBe(1);
});

test("the API preserves out-of-order events with equal IDs in separate namespaces", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V11" },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers,
    data: { metadata: {} },
  });
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  await page.goto("/");
  const received = page.evaluate(
    async ({ token, projectId, threadId }) => {
      const { ProtocolSseTransportAdapter } =
        await import("/src/services/langgraph/transport.ts");
      const transport = new ProtocolSseTransportAdapter({
        apiUrl: `${location.origin}/api/langgraph`,
        threadId,
        maxReconnectAttempts: 0,
        idleReconnect: false,
        fetch: (input, init) => {
          const headers = new Headers(init?.headers);
          headers.set("authorization", `Bearer ${token}`);
          headers.set("x-project-id", projectId);
          return fetch(input, { ...init, headers });
        },
      });
      const handle = transport.openEventStream({
        channels: ["values"],
        namespaces: [["task:a"], ["task:b"]],
      });
      try {
        await handle.ready;
        const reader = handle.events[Symbol.asyncIterator]();
        return [(await reader.next()).value, (await reader.next()).value];
      } finally {
        handle.close();
        await transport.close();
      }
    },
    { token, projectId: fixture.project_id, threadId },
  );
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBe(1);
  const frame = (seq: number, namespace: string) => {
    const event = {
      type: "event",
      seq,
      event_id: "same-id",
      method: "values",
      params: {
        thread_id: threadId,
        run_id: "run-1",
        namespace: [namespace],
        data: { messages: [{ id: namespace, type: "ai", content: namespace }] },
      },
    };
    return `event: event\ndata: ${JSON.stringify(event)}\n\n`;
  };
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers,
        data: {
          thread_id: threadId,
          chunks: [frame(2, "task:b"), frame(1, "task:a")],
        },
      })
    ).ok(),
  ).toBeTruthy();
  expect((await received).map((event) => event.params.namespace)).toEqual([
    ["task:b"],
    ["task:a"],
  ]);
  expect(
    (await (await request.get(`${apiUrl}/__test/counters`, { headers })).json())
      .commands,
  ).toBe(0);
});

test("EOF reconnects the installed SDK without replaying a command", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V09" },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers,
    data: { metadata: {} },
  });
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  await page.goto("/");
  const received = page.evaluate(
    async ({ token, projectId, threadId }) => {
      const { ProtocolSseTransportAdapter } =
        await import("/src/services/langgraph/transport.ts");
      const transport = new ProtocolSseTransportAdapter({
        apiUrl: `${location.origin}/api/langgraph`,
        threadId,
        maxReconnectAttempts: 1,
        idleReconnect: false,
        fetch: (input, init) => {
          const headers = new Headers(init?.headers);
          headers.set("authorization", `Bearer ${token}`);
          headers.set("x-project-id", projectId);
          return fetch(input, { ...init, headers });
        },
      });
      const handle = transport.openEventStream({ channels: ["values"] });
      try {
        await handle.ready;
        return (await handle.events[Symbol.asyncIterator]().next()).value;
      } finally {
        handle.close();
        await transport.close();
      }
    },
    { token, projectId: fixture.project_id, threadId },
  );
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBe(1);
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers,
        data: { thread_id: threadId },
      })
    ).ok(),
  ).toBeTruthy();
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).subscriptions,
    )
    .toBe(2);
  const event = {
    type: "event",
    seq: 2,
    event_id: "after-eof",
    method: "values",
    params: {
      thread_id: threadId,
      run_id: "run-2",
      namespace: [],
      data: {
        messages: [{ id: "after-eof", type: "ai", content: "recovered" }],
      },
    },
  };
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers,
        data: { thread_id: threadId, event },
      })
    ).ok(),
  ).toBeTruthy();
  expect((await received).params.data.messages[0].content).toBe("recovered");
  const counters = await (
    await request.get(`${apiUrl}/__test/counters`, { headers })
  ).json();
  expect(counters.commands).toBe(0);
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBe(0);
});

test("malformed upstream frame closes safely without exposing its bytes", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V16" },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers,
    data: { metadata: {} },
  });
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  await page.goto("/");
  const stopped = page.evaluate(
    async ({ token, projectId, threadId }) => {
      const { ProtocolSseTransportAdapter } =
        await import("/src/services/langgraph/transport.ts");
      const transport = new ProtocolSseTransportAdapter({
        apiUrl: `${location.origin}/api/langgraph`,
        threadId,
        maxReconnectAttempts: 0,
        idleReconnect: false,
        fetch: (input, init) => {
          const headers = new Headers(init?.headers);
          headers.set("authorization", `Bearer ${token}`);
          headers.set("x-project-id", projectId);
          return fetch(input, { ...init, headers });
        },
      });
      const handle = transport.openEventStream({ channels: ["values"] });
      try {
        await handle.ready;
        return await new Promise<string>((resolve) => {
          const unsubscribe = transport.onConnectionChange((state) => {
            if (state.state !== "paused") return;
            unsubscribe();
            resolve(
              state.streams.map((item) => item.error?.message ?? "").join(" "),
            );
          });
        });
      } finally {
        handle.close();
        await transport.close();
      }
    },
    { token, projectId: fixture.project_id, threadId },
  );
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBe(1);
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers,
        data: {
          thread_id: threadId,
          chunks: ["data: fixture-secret\r", "\n\r\n"],
        },
      })
    ).ok(),
  ).toBeTruthy();
  expect(await stopped).not.toContain("fixture-secret");
  const counters = await (
    await request.get(`${apiUrl}/__test/counters`, { headers })
  ).json();
  expect(counters.commands).toBe(0);
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBe(0);
});

test("expired cursor pauses the installed SDK without sending a command", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const accessToken = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${accessToken}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V13" },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers,
    data: { metadata: {} },
  });
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  await page.goto("/");
  const status = await page.evaluate(
    async ({ accessToken, projectId, threadId }) => {
      const { ProtocolSseTransportAdapter } =
        await import("/src/services/langgraph/transport.ts");
      const transport = new ProtocolSseTransportAdapter({
        apiUrl: `${location.origin}/api/langgraph`,
        threadId,
        maxReconnectAttempts: 0,
        fetch: (input, init) => {
          const headers = new Headers(init?.headers);
          headers.set("authorization", `Bearer ${accessToken}`);
          headers.set("x-project-id", projectId);
          return fetch(input, { ...init, headers });
        },
      });
      const handle = transport.openEventStream({
        channels: ["values"],
        since: 9,
      });
      void handle.ready.catch(() => {});
      try {
        return await Promise.race([
          new Promise<number>((resolve) => {
            const unsubscribe = transport.onConnectionChange((state) => {
              if (state.state === "paused") {
                unsubscribe();
                resolve(
                  (state.streams[0]?.error as { status?: number })?.status ?? 0,
                );
              }
            });
          }),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error("410 timeout")), 5000),
          ),
        ]);
      } finally {
        handle.close();
        await transport.close();
      }
    },
    { accessToken, projectId: fixture.project_id, threadId },
  );
  expect(status).toBe(410);
  const counters = await (
    await request.get(`${apiUrl}/__test/counters`, { headers })
  ).json();
  expect(counters.subscriptions).toBe(1);
  expect(counters.commands).toBe(0);
});

for (const status of [403, 404, 429, 502]) {
  test(`stream handshake ${status} pauses without a command`, async ({
    page,
    request,
  }) => {
    const apiUrl = "http://127.0.0.1:12144";
    const fixture = JSON.parse(
      readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
    ) as { project_id: string };
    const login = await request.post(`${apiUrl}/api/identity/session`, {
      data: {
        username: "sse-contract-owner",
        password: "Sse-contract-test-only-2026!",
      },
    });
    expect(login.ok()).toBeTruthy();
    const token = (await login.json()).tokens.access_token as string;
    const headers = {
      authorization: `Bearer ${token}`,
      "x-project-id": fixture.project_id,
    };
    expect(
      (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
    ).toBeTruthy();
    expect(
      (
        await request.post(`${apiUrl}/__test/scenario`, {
          headers,
          data: { id: `V12-${status}` },
        })
      ).ok(),
    ).toBeTruthy();
    const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
      headers,
      data: { metadata: {} },
    });
    expect(created.ok()).toBeTruthy();
    const threadId = (await created.json()).thread_id as string;
    await page.goto("/");
    const pausedStatus = await page.evaluate(
      async ({ token, projectId, threadId }) => {
        const { ProtocolSseTransportAdapter } =
          await import("/src/services/langgraph/transport.ts");
        const transport = new ProtocolSseTransportAdapter({
          apiUrl: `${location.origin}/api/langgraph`,
          threadId,
          maxReconnectAttempts: 0,
          idleReconnect: false,
          fetch: (input, init) => {
            const headers = new Headers(init?.headers);
            headers.set("authorization", `Bearer ${token}`);
            headers.set("x-project-id", projectId);
            return fetch(input, { ...init, headers });
          },
        });
        const handle = transport.openEventStream({ channels: ["values"] });
        void handle.ready.catch(() => {});
        try {
          return await new Promise<number>((resolve) => {
            const unsubscribe = transport.onConnectionChange((state) => {
              if (state.state !== "paused") return;
              unsubscribe();
              resolve(
                (state.streams[0]?.error as Error & { status?: number })
                  ?.status ?? 0,
              );
            });
          });
        } finally {
          handle.close();
          await transport.close();
        }
      },
      { token, projectId: fixture.project_id, threadId },
    );
    expect(pausedStatus).toBe(status);
    const counters = await (
      await request.get(`${apiUrl}/__test/counters`, { headers })
    ).json();
    expect(counters.subscriptions).toBe(1);
    expect(counters.commands).toBe(0);
  });
}

test("real ChatPage recovers one expired stream without replaying a command", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string; agent_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V13UI" },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers,
    data: {
      metadata: {
        graph_id: "reference_agent",
        agent_id: fixture.agent_id,
        title: "Expired Thread",
      },
    },
  });
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  await page.goto("/auth/login");
  await page
    .locator('input[autocomplete="username"]')
    .fill("sse-contract-owner");
  await page
    .locator('input[autocomplete="current-password"]')
    .fill("Sse-contract-test-only-2026!");
  await page.locator('button[type="submit"]').click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 20_000 });
  await page.goto(
    `/workspace/projects/${fixture.project_id}/chat/${threadId}?agentId=${fixture.agent_id}`,
  );
  await expect(
    page.getByRole("alert").filter({ hasText: "历史流已过期" }),
  ).toBeVisible();
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).state,
    )
    .toBeGreaterThan(0);
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).subscriptions,
    )
    .toBeGreaterThan(1);
  expect(
    (await (await request.get(`${apiUrl}/__test/counters`, { headers })).json())
      .commands,
  ).toBe(0);
});

test("real ChatPage keeps Thread A subscribed while viewing Thread B", async ({
  page,
  request,
}, testInfo) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string; agent_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V07" },
      })
    ).ok(),
  ).toBeTruthy();
  const create = async (title: string) => {
    const response = await request.post(`${apiUrl}/api/langgraph/threads`, {
      headers,
      data: {
        metadata: {
          graph_id: "reference_agent",
          agent_id: fixture.agent_id,
          title,
        },
      },
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()).thread_id as string;
  };
  const a = await create("Thread A");
  const b = await create("Thread B");
  await page.goto("/auth/login");
  await page
    .locator('input[autocomplete="username"]')
    .fill("sse-contract-owner");
  await page
    .locator('input[autocomplete="current-password"]')
    .fill("Sse-contract-test-only-2026!");
  await page.locator('button[type="submit"]').click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 20_000 });
  const chat = (thread: string) =>
    `/workspace/projects/${fixture.project_id}/chat/${thread}?agentId=${fixture.agent_id}`;
  await page.goto(chat(a));
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBeGreaterThan(0);
  await page.locator('input[type="file"]').setInputFiles({
    name: "a-only.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("A attachment"),
  });
  await expect(page.getByText("a-only.txt")).toBeVisible();
  const before = await (
    await request.get(`${apiUrl}/__test/counters`, { headers })
  ).json();
  await page.getByRole("button", { name: "Thread B", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/chat/${b}`));
  await expect(page.getByText("a-only.txt")).toBeHidden();
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBeGreaterThan(before.open);
  await page
    .getByRole("textbox", { name: "消息草稿" })
    .fill("B draft stays here");
  const during = await (
    await request.get(`${apiUrl}/__test/counters`, { headers })
  ).json();
  const event = {
    type: "event",
    seq: 1,
    event_id: "background-a",
    method: "values",
    params: {
      thread_id: a,
      run_id: "run-a",
      namespace: [],
      data: {
        messages: [
          {
            id: "background-a-step",
            type: "ai",
            content: "background A step",
            additional_kwargs: { reasoning_content: "background reasoning" },
            tool_calls: [
              {
                id: "call-a",
                name: "read_file",
                args: { path: "/missing.txt" },
              },
              {
                id: "call-b",
                name: "read_file",
                args: { path: "/fixture.txt" },
              },
            ],
          },
          {
            id: "background-a-tool-error",
            type: "tool",
            tool_call_id: "call-a",
            content: "fixture missing file",
            status: "error",
          },
          {
            id: "background-a-tool",
            type: "tool",
            tool_call_id: "call-b",
            content: "fixture tool result",
          },
          { id: "background-a", type: "ai", content: "background A token" },
        ],
      },
    },
  };
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers,
        data: { thread_id: a, event },
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers,
        data: { thread_id: a, event },
      })
    ).ok(),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Thread A", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/chat/${a}`));
  await expect(page.getByText("a-only.txt")).toBeVisible();
  await expect(page.getByText("background A step")).toBeVisible();
  await expect(page.getByText("background A token")).toBeVisible();
  await expect(page.getByText("read_file").first()).toBeVisible();
  const reasoning = page
    .locator('details[class*="group/reasoning"]')
    .filter({ hasText: "background reasoning" });
  await expect(reasoning).toHaveAttribute("open", "");
  await reasoning.locator("summary").click();
  await expect(reasoning).not.toHaveAttribute("open", "");
  expect(await page.getByText("read_file").count()).toBe(2);
  await page.getByText("read_file").last().click();
  await expect(page.getByText("fixture tool result")).toBeVisible();
  await page.getByText("read_file").first().click();
  await expect(page.getByText("fixture missing file")).toBeVisible();
  expect(await page.getByText("background A token").count()).toBe(1);
  await page.screenshot({
    path: testInfo.outputPath("sse-chat-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("sse-chat-mobile.png"),
    fullPage: true,
  });
  await page
    .getByRole("complementary", { name: "对话列表" })
    .getByRole("button", { name: "收起历史会话" })
    .click();
  await expect(page.getByText("background A token")).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("sse-chat-mobile-content.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.getByRole("button", { name: "历史", exact: true }).click();
  const after = await (
    await request.get(`${apiUrl}/__test/counters`, { headers })
  ).json();
  expect(after.commands).toBe(0);
  expect(after.closed).toBe(0);
  expect(after.subscriptions).toBe(during.subscriptions);
  await page.getByRole("button", { name: "Thread B", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "消息草稿" })).toHaveValue(
    "B draft stays here",
  );
  await page.getByRole("button", { name: "Thread A", exact: true }).click();
  await expect(
    page
      .locator('details[class*="group/reasoning"]')
      .filter({ hasText: "background reasoning" }),
  ).not.toHaveAttribute("open", "");
  const longEvent = {
    type: "event",
    seq: 2,
    event_id: "scroll-a",
    method: "values",
    params: {
      thread_id: a,
      run_id: "run-a",
      namespace: [],
      data: {
        messages: Array.from({ length: 40 }, (_, index) => ({
          id: `scroll-${index}`,
          type: "ai",
          content: `scroll line ${index}: ${"content ".repeat(20)}`,
        })),
      },
    },
  };
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers,
        data: { thread_id: a, event: longEvent },
      })
    ).ok(),
  ).toBeTruthy();
  await expect(page.getByText(/scroll line 39:/)).toBeVisible();
  const viewport = page.locator(".pw-chat-stream:visible");
  await expect
    .poll(() =>
      viewport.evaluate(
        (element) => element.scrollHeight > element.clientHeight,
      ),
    )
    .toBe(true);
  const scrollTop = await viewport.evaluate((element) => {
    element.scrollTop = 180;
    element.dispatchEvent(new WheelEvent("wheel", { deltaY: -300 }));
    return element.scrollTop;
  });
  expect(scrollTop).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Thread B", exact: true }).click();
  await page.getByRole("button", { name: "Thread A", exact: true }).click();
  await expect
    .poll(() => viewport.evaluate((element) => element.scrollTop))
    .toBeGreaterThanOrEqual(scrollTop - 5);
  expect(
    (
      await request.post(`${apiUrl}/__test/run`, {
        headers,
        data: { thread_id: a, status: "running" },
      })
    ).ok(),
  ).toBeTruthy();
  await page.reload();
  await expect(page.getByRole("button", { name: "停止生成" })).toBeVisible();
  await page.getByRole("button", { name: /sse-contract-owner/ }).click();
  await page.getByRole("button", { name: /退出登录|Log out/ }).click();
  await expect(page).toHaveURL(/\/auth\/login/);
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBe(0);
  expect(
    (await (await request.get(`${apiUrl}/__test/counters`, { headers })).json())
      .commands,
  ).toBe(0);
  expect(
    (await (await request.get(`${apiUrl}/__test/counters`, { headers })).json())
      .cancels,
  ).toBe(0);
});

test("a hidden Thread keeps its queued prompt local after its Run ends", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string; agent_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V08" },
      })
    ).ok(),
  ).toBeTruthy();
  const create = async (title: string) => {
    const response = await request.post(`${apiUrl}/api/langgraph/threads`, {
      headers,
      data: {
        metadata: {
          graph_id: "reference_agent",
          agent_id: fixture.agent_id,
          title,
        },
      },
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()).thread_id as string;
  };
  const a = await create("Queued A");
  const b = await create("Queued B");
  expect(
    (
      await request.post(`${apiUrl}/__test/run`, {
        headers,
        data: { thread_id: a, status: "running" },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto("/auth/login");
  await page
    .locator('input[autocomplete="username"]')
    .fill("sse-contract-owner");
  await page
    .locator('input[autocomplete="current-password"]')
    .fill("Sse-contract-test-only-2026!");
  await page.locator('button[type="submit"]').click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 20_000 });
  await page.goto(
    `/workspace/projects/${fixture.project_id}/chat/${a}?agentId=${fixture.agent_id}`,
  );
  await page.getByRole("textbox", { name: "消息草稿" }).fill("A queued prompt");
  await page.getByRole("button", { name: "补充要求" }).click();
  await expect(page.getByRole("region", { name: "消息队列" })).toContainText(
    "A queued prompt",
  );
  await page.evaluate(() => {
    const target = window as typeof window & {
      queueDelay?: () => void;
      restoreQueueTimer?: () => void;
    };
    const original = window.setTimeout;
    window.setTimeout = ((
      handler: TimerHandler,
      timeout?: number,
      ...args: unknown[]
    ) => {
      if (timeout === 350) {
        target.queueDelay = handler as () => void;
        return 0;
      }
      return original(handler, timeout, ...args);
    }) as typeof window.setTimeout;
    target.restoreQueueTimer = () => {
      window.setTimeout = original;
    };
  });
  expect(
    (
      await request.post(`${apiUrl}/__test/run`, {
        headers,
        data: { thread_id: a, status: "success" },
      })
    ).ok(),
  ).toBeTruthy();
  await expect
    .poll(() =>
      page.evaluate(() =>
        Boolean(
          (window as typeof window & { queueDelay?: () => void }).queueDelay,
        ),
      ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "Queued B", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/chat/${b}`));
  await page.getByRole("textbox", { name: "消息草稿" }).fill("B private draft");
  await page.evaluate(() => {
    const target = window as typeof window & {
      queueDelay?: () => void;
      restoreQueueTimer?: () => void;
    };
    target.restoreQueueTimer?.();
    target.queueDelay?.();
  });
  await page.waitForTimeout(500);
  expect(
    (await (await request.get(`${apiUrl}/__test/counters`, { headers })).json())
      .commands,
  ).toBe(0);
  await expect(page.getByRole("textbox", { name: "消息草稿" })).toHaveValue(
    "B private draft",
  );
  await page.getByRole("button", { name: "Queued A", exact: true }).click();
  await expect(page.getByRole("region", { name: "消息队列" })).toContainText(
    "A queued prompt",
  );
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).commands,
    )
    .toBe(1);
});

test("cancel ACK leaves the Run active until the server reports its terminal state", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string; agent_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V21" },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers,
    data: {
      metadata: {
        graph_id: "reference_agent",
        agent_id: fixture.agent_id,
        title: "Cancel pending",
      },
    },
  });
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  expect(
    (
      await request.post(`${apiUrl}/__test/run`, {
        headers,
        data: { thread_id: threadId, status: "running" },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto("/auth/login");
  await page
    .locator('input[autocomplete="username"]')
    .fill("sse-contract-owner");
  await page
    .locator('input[autocomplete="current-password"]')
    .fill("Sse-contract-test-only-2026!");
  await page.locator('button[type="submit"]').click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 20_000 });
  await page.goto(
    `/workspace/projects/${fixture.project_id}/chat/${threadId}?agentId=${fixture.agent_id}`,
  );
  await page.getByRole("button", { name: "停止生成" }).click();
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).cancels,
    )
    .toBe(1);
  expect(
    (
      await (
        await request.get(
          `${apiUrl}/api/langgraph/threads/${threadId}/runs/fixture-run`,
          { headers },
        )
      ).json()
    ).status,
  ).toBe("running");
  expect(
    (await (await request.get(`${apiUrl}/__test/counters`, { headers })).json())
      .commands,
  ).toBe(0);
  expect(
    (
      await request.post(`${apiUrl}/__test/run`, {
        headers,
        data: { thread_id: threadId, status: "success" },
      })
    ).ok(),
  ).toBeTruthy();
  await expect(page.getByRole("button", { name: "停止生成" })).toHaveCount(0);
  expect(
    (await (await request.get(`${apiUrl}/__test/counters`, { headers })).json())
      .cancels,
  ).toBe(1);
});

test("revoking a Thread closes its live ChatSession and hides cached content", async ({
  page,
  request,
}) => {
  const apiUrl = "http://127.0.0.1:12144";
  const fixture = JSON.parse(
    readFileSync("/tmp/platform-sse-contract-e2e.json", "utf8"),
  ) as { project_id: string; agent_id: string };
  const login = await request.post(`${apiUrl}/api/identity/session`, {
    data: {
      username: "sse-contract-owner",
      password: "Sse-contract-test-only-2026!",
    },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).tokens.access_token as string;
  const headers = {
    authorization: `Bearer ${token}`,
    "x-project-id": fixture.project_id,
  };
  expect(
    (await request.post(`${apiUrl}/__test/reset`, { headers })).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiUrl}/__test/scenario`, {
        headers,
        data: { id: "V08" },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers,
    data: {
      metadata: {
        graph_id: "reference_agent",
        agent_id: fixture.agent_id,
        title: "Revoked Thread",
      },
    },
  });
  expect(created.ok()).toBeTruthy();
  const threadId = (await created.json()).thread_id as string;
  await page.goto("/auth/login");
  await page
    .locator('input[autocomplete="username"]')
    .fill("sse-contract-owner");
  await page
    .locator('input[autocomplete="current-password"]')
    .fill("Sse-contract-test-only-2026!");
  await page.locator('button[type="submit"]').click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 20_000 });
  await page.goto(
    `/workspace/projects/${fixture.project_id}/chat/${threadId}?agentId=${fixture.agent_id}`,
  );
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBeGreaterThan(0);
  const event = {
    type: "event",
    seq: 1,
    event_id: "before-revoke",
    method: "values",
    params: {
      thread_id: threadId,
      run_id: "run-a",
      namespace: [],
      data: {
        messages: [
          {
            id: "private-message",
            type: "ai",
            content: "must disappear on revoke",
          },
        ],
      },
    },
  };
  expect(
    (
      await request.post(`${apiUrl}/__test/advance`, {
        headers,
        data: { thread_id: threadId, event },
      })
    ).ok(),
  ).toBeTruthy();
  await expect(page.getByText("must disappear on revoke")).toBeVisible();
  expect(
    (
      await request.post(`${apiUrl}/__test/revoke`, {
        headers,
        data: { thread_id: threadId },
      })
    ).ok(),
  ).toBeTruthy();
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByText("must disappear on revoke")).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (
          await (
            await request.get(`${apiUrl}/__test/counters`, { headers })
          ).json()
        ).open,
    )
    .toBe(0);
  expect(
    (await (await request.get(`${apiUrl}/__test/counters`, { headers })).json())
      .commands,
  ).toBe(0);
});
