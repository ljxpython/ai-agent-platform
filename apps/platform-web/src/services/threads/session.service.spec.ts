import { expect, it, vi } from "vitest";
import { createSessionService } from "./session.service";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";

it("uses SDK graphId and the public checkpoint wire contract", async () => {
  const requests: Array<{
    url: string;
    body?: Record<string, unknown>;
    headers: Headers;
  }> = [];
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({
      url: String(input),
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      headers: new Headers(init?.headers),
    });
    return new Response(JSON.stringify({ thread_id: "thread" }), {
      headers: { "content-type": "application/json" },
    });
  });
  const service = createSessionService(transport, "project");
  await service.create("workflow_demo", "agent", "标题");
  await service.state("thread", { checkpoint_id: "check", checkpoint_ns: "" });
  await service.history("thread", {
    checkpoint_id: "check",
    checkpoint_ns: "",
  });
  await service.fork("thread", "check", "分支标题");
  await service.resume("thread", {
    approval: { decisions: [{ type: "approve" }] },
  });
  expect(requests[0]?.body?.metadata).toEqual({
    graph_id: "workflow_demo",
    agent_id: "agent",
    title: "标题",
  });
  expect(requests[1]?.url).toMatch(
    /\/threads\/thread\/state\?checkpoint_id=check$/,
  );
  expect(requests[2]?.body?.before).toEqual({
    checkpoint_id: "check",
    checkpoint_ns: "",
  });
  expect(requests[3]?.url).toMatch(/\/threads\/thread\/fork$/);
  expect(requests[3]?.body).toEqual({
    checkpoint_id: "check",
    title: "分支标题",
  });
  expect(requests[4]?.url).toMatch(/\/threads\/thread\/runs$/);
  expect(requests[4]?.body).toEqual({
    command: { resume: { approval: { decisions: [{ type: "approve" }] } } },
  });
  expect(
    requests.every(
      (request) => request.headers.get("x-project-id") === "project",
    ),
  ).toBe(true);
});

it.each([503, 504])(
  "reconciles a pending thread after HTTP %i",
  async (status) => {
    const threadId = "11111111-1111-4111-8111-111111111111";
    let createCalls = 0;
    let reconcileCalls = 0;
    const transport = vi.fn<typeof fetch>(async (input) => {
      if (String(input).endsWith("/reconcile")) {
        reconcileCalls += 1;
        return new Response(
          JSON.stringify(
            reconcileCalls === 1
              ? { thread_id: threadId, status: "pending" }
              : {
                  thread_id: threadId,
                  status: "ready",
                  thread: { thread_id: threadId },
                },
          ),
          { headers: { "content-type": "application/json" } },
        );
      }
      createCalls += 1;
      return new Response(
        JSON.stringify({ error: { extra: { thread_id: threadId } } }),
        { status, headers: { "content-type": "application/json" } },
      );
    });
    const service = createSessionService(transport, "project", "user");
    await expect(
      service.create("workflow_demo", "agent", "标题"),
    ).rejects.toThrow(threadId);
    const rebuiltService = createSessionService(transport, "project", "user");
    await expect(
      rebuiltService.create("workflow_demo", "agent", "标题"),
    ).rejects.toThrow("请稍后重试");
    await expect(
      rebuiltService.create("workflow_demo", "agent", "标题"),
    ).resolves.toMatchObject({ thread_id: threadId });
    expect(createCalls).toBe(1);
    expect(reconcileCalls).toBe(2);
    expect(sessionStorage.getItem("pw:thread:create:user:project")).toBeNull();
  },
);

it("keeps pending identity through authorized fetch and the actual SDK", async () => {
  const threadId = "11111111-1111-4111-8111-111111111111";
  let creates = 0;
  const fetchImpl = vi.fn<typeof fetch>(async (input) => {
    if (String(input).endsWith("/reconcile")) {
      return new Response(
        JSON.stringify({ status: "ready", thread: { thread_id: threadId } }),
        { headers: { "content-type": "application/json" } },
      );
    }
    creates += 1;
    return new Response(
      JSON.stringify({
        error: {
          code: "thread_provisioning_unconfirmed",
          message: "Reconcile first",
          extra: { thread_id: threadId },
        },
        request_id: "req-1",
      }),
      { status: 503, headers: { "content-type": "application/json" } },
    );
  });
  const authorizedFetch = createLanggraphAuthorizedFetch({
    fetchImpl,
    getAccessToken: () => "token",
  });
  const service = createSessionService(authorizedFetch, "project", "owner");
  await expect(
    service.create("workflow_demo", "agent", "标题"),
  ).rejects.toThrow(threadId);
  await expect(
    service.create("workflow_demo", "agent", "标题"),
  ).resolves.toMatchObject({ thread_id: threadId });
  expect(creates).toBe(1);
  expect(fetchImpl).toHaveBeenCalledTimes(2);
});

it("passes metadata and pagination options to search and count", async () => {
  const requests: Array<{ url: string; body?: Record<string, unknown> }> = [];
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({
      url: String(input),
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
    });
    return new Response(JSON.stringify([{ thread_id: "t-1" }]), {
      headers: { "content-type": "application/json" },
    });
  });
  const service = createSessionService(transport, "project");
  await service.list({ offset: 20, metadata: { agent_id: "agent-1" } });
  await service.count({ metadata: { agent_id: "agent-1" } });

  expect(requests[0]?.url).toMatch(/\/threads\/search$/);
  expect(requests[0]?.body?.offset).toBe(20);
  expect(requests[0]?.body?.metadata).toEqual({ agent_id: "agent-1" });

  expect(requests[1]?.url).toMatch(/\/threads\/count$/);
  expect(requests[1]?.body?.metadata).toEqual({ agent_id: "agent-1" });
});

it("unwraps object response into integer count", async () => {
  const transport = vi.fn<typeof fetch>(async () => {
    return new Response(JSON.stringify({ count: 42 }), {
      headers: { "content-type": "application/json" },
    });
  });
  const service = createSessionService(transport, "project");
  const count = await service.count({ metadata: { agent_id: "agent-1" } });
  expect(count).toBe(42);
});

it("updates thread metadata with PATCH request", async () => {
  const requests: Array<{
    url: string;
    method?: string;
    body?: Record<string, unknown>;
  }> = [];
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({
      url: String(input),
      method: init?.method,
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
    });
    return new Response(
      JSON.stringify({ thread_id: "thread-1", metadata: { title: "新标题" } }),
      {
        headers: { "content-type": "application/json" },
      },
    );
  });
  const service = createSessionService(transport, "project");
  await service.update("thread-1", { title: "新标题", preview: "消息摘要" });

  expect(requests[0]?.url).toMatch(/\/threads\/thread-1$/);
  expect(requests[0]?.method).toBe("PATCH");
  expect(requests[0]?.body).toEqual({ title: "新标题", preview: "消息摘要" });
});

it("summarizes thread title with POST request", async () => {
  const requests: Array<{
    url: string;
    method?: string;
    body?: Record<string, unknown>;
  }> = [];
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({
      url: String(input),
      method: init?.method,
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
    });
    return new Response(
      JSON.stringify({ thread_id: "thread-1", title: "智能标题" }),
      {
        headers: { "content-type": "application/json" },
      },
    );
  });
  const service = createSessionService(transport, "project");
  const res = await service.summarizeTitle("thread-1", [
    { role: "user", content: "测试消息" },
  ]);

  expect(requests[0]?.url).toMatch(/\/threads\/thread-1\/title\/summarize$/);
  expect(requests[0]?.method).toBe("POST");
  expect(requests[0]?.body).toEqual({
    messages: [{ role: "user", content: "测试消息" }],
  });
  expect(res.title).toBe("智能标题");
});

it("rejects empty or whitespace-only threadId to prevent invalid path requests", async () => {
  const service = createSessionService(vi.fn(), "project");
  for (const empty of ["", "   ", "\t\n"]) {
    expect(() => service.state(empty)).toThrow("Invalid threadId");
    expect(() => service.history(empty)).toThrow("Invalid threadId");
    expect(() => service.resume(empty, {})).toThrow("Invalid threadId");
    expect(() => service.fork(empty, "cp")).toThrow("Invalid threadId");
    expect(() => service.update(empty, {})).toThrow("Invalid threadId");
    expect(() => service.summarizeTitle(empty)).toThrow("Invalid threadId");
    await expect(service.stopThread(empty, "key-1")).rejects.toThrow(
      "Invalid threadId",
    );
    await expect(service.getStopRequest(empty, "stop-1")).rejects.toThrow(
      "Invalid threadId",
    );
    await expect(service.listStopRequests(empty)).rejects.toThrow(
      "Invalid threadId",
    );
  }
});

it("supports stopThread, getStopRequest and listStopRequests with contract verification", async () => {
  const validStopRequest = {
    version: 1,
    stop_id: "33333333-3333-4333-8333-333333333333",
    thread_id: "11111111-1111-4111-8111-111111111111",
    phase: "stopped",
    requested_at: "2026-10-07T06:00:00Z",
    accepted_at: "2026-10-07T06:00:00.100Z",
    confirmed_at: "2026-10-07T06:00:01Z",
    target_count: 2,
    execution_stopped: true,
    resource_cleanup: "confirmed",
    has_pending_interrupts: false,
    queue: {
      pending_cancelled_count: 1,
      inbox_consumed_count: 1,
      inbox_not_consumed_count: 0,
    },
    report: {
      version: 1,
      source: "checkpoint_and_receipts",
      checkpoint_id: "cp-1",
      checkpoints: [
        {
          run_id: "22222222-2222-4222-8222-222222222222",
          checkpoint_id: "cp-1",
        },
      ],
      progress: [
        {
          kind: "tool_receipt",
          label: "search",
          observed_status: "recorded",
          source_run_id: "22222222-2222-4222-8222-222222222222",
        },
      ],
      artifacts: [
        {
          artifact_id:
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          path: "/workspace/outputs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.txt",
          source_run_id: "22222222-2222-4222-8222-222222222222",
        },
      ],
      uncertainties: [],
      truncated: false,
    },
    reason_code: null,
    request_id: "req-123",
  };

  const requests: Array<{
    url: string;
    method?: string;
    body?: unknown;
    headers: Headers;
  }> = [];

  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({
      url: String(input),
      method: init?.method,
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      headers: new Headers(init?.headers),
    });

    const url = String(input);
    if (url.includes("/stop-requests?")) {
      return new Response(
        JSON.stringify({
          items: [validStopRequest],
          next_cursor: "cursor-token-2",
        }),
        { headers: { "content-type": "application/json" } },
      );
    }

    return new Response(JSON.stringify(validStopRequest), {
      headers: { "content-type": "application/json" },
    });
  });

  const service = createSessionService(transport, "project-123");

  // 1. 测试 stopThread
  const stopRes = await service.stopThread("thread-1", "stop:uuid-123");
  expect(stopRes.stop_id).toBe("33333333-3333-4333-8333-333333333333");
  expect(requests[0]?.url).toMatch(/\/threads\/thread-1\/cancel$/);
  expect(requests[0]?.method).toBe("POST");
  expect(requests[0]?.headers.get("Idempotency-Key")).toBe("stop:uuid-123");
  expect(requests[0]?.headers.get("x-project-id")).toBe("project-123");
  expect(requests[0]?.body).toEqual({});

  // 2. 测试 getStopRequest
  const getRes = await service.getStopRequest(
    "thread-1",
    "33333333-3333-4333-8333-333333333333",
  );
  expect(getRes.phase).toBe("stopped");
  expect(requests[1]?.url).toMatch(
    /\/threads\/thread-1\/stop-requests\/33333333-3333-4333-8333-333333333333$/,
  );

  // 3. 测试 listStopRequests 无 cursor 时
  const listResNoCursor = await service.listStopRequests("thread-1", {
    limit: 10,
  });
  expect(listResNoCursor.items).toHaveLength(1);
  expect(listResNoCursor.next_cursor).toBe("cursor-token-2");
  expect(requests[2]?.url).toMatch(
    /\/threads\/thread-1\/stop-requests\?limit=10$/,
  );
  expect(requests[2]?.url).not.toContain("cursor=");

  // 4. 测试 listStopRequests 带 cursor 时（参数必须是 cursor）
  await service.listStopRequests("thread-1", {
    limit: 10,
    cursor: "my-cursor",
  });
  expect(requests[3]?.url).toMatch(
    /\/threads\/thread-1\/stop-requests\?limit=10&cursor=my-cursor$/,
  );

  // 5. 校验非法响应报错
  const badTransport = vi.fn<typeof fetch>(async () => {
    return new Response(JSON.stringify({ version: 999, invalid: true }), {
      headers: { "content-type": "application/json" },
    });
  });
  const badService = createSessionService(badTransport, "project-123");
  await expect(badService.stopThread("thread-1", "key")).rejects.toThrow(
    "停止请求回执校验失败",
  );
});
