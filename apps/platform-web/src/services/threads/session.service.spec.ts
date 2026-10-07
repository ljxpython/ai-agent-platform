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

it("rejects empty or whitespace-only threadId to prevent invalid path requests", () => {
  const service = createSessionService(vi.fn(), "project");
  for (const empty of ["", "   ", "\t\n"]) {
    expect(() => service.state(empty)).toThrow("Invalid threadId");
    expect(() => service.history(empty)).toThrow("Invalid threadId");
    expect(() => service.resume(empty, {})).toThrow("Invalid threadId");
    expect(() => service.fork(empty, "cp")).toThrow("Invalid threadId");
    expect(() => service.update(empty, {})).toThrow("Invalid threadId");
    expect(() => service.summarizeTitle(empty)).toThrow("Invalid threadId");
    expect(() => service.cancelAndWait(empty, "run-1")).toThrow(
      "Invalid threadId",
    );
    expect(() => service.cancelAndWait("thread-1", empty)).toThrow(
      "Invalid runId",
    );
  }
});

it("cancelAndWait sends POST with JSON body wait=true and x-project-id", async () => {
  const requests: Array<{
    url: string;
    method?: string;
    body?: Record<string, unknown>;
    headers: Headers;
  }> = [];
  const transport = vi.fn<typeof fetch>(async (input, init) => {
    requests.push({
      url: String(input),
      method: init?.method,
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      headers: new Headers(init?.headers),
    });
    return new Response(JSON.stringify({ ok: true }), {
      headers: { "content-type": "application/json" },
    });
  });
  const service = createSessionService(transport, "project-123");
  const res = await service.cancelAndWait("thread-abc", "run-xyz");

  expect(res).toEqual({ ok: true });
  expect(requests[0]?.url).toMatch(
    /\/threads\/thread-abc\/runs\/run-xyz\/cancel$/,
  );
  expect(requests[0]?.method).toBe("POST");
  expect(requests[0]?.body).toEqual({ wait: true, action: "interrupt" });
  expect(requests[0]?.headers.get("x-project-id")).toBe("project-123");
  expect(requests[0]?.headers.get("content-type")).toBe("application/json");
});

it("cancelAndWait handles platform error envelopes on failure", async () => {
  const transport = vi.fn<typeof fetch>(async () => {
    return new Response(
      JSON.stringify({
        error: {
          code: "gateway_timeout",
          message: "Wait timeout on cancel",
        },
        request_id: "req-cancel-504",
      }),
      { status: 504, headers: { "content-type": "application/json" } },
    );
  });
  const service = createSessionService(transport, "project-123");
  await expect(
    service.cancelAndWait("thread-1", "run-1"),
  ).rejects.toMatchObject({
    status: 504,
    code: "gateway_timeout",
    requestId: "req-cancel-504",
  });
});
