import { effectScope, ref } from "vue";
import { flushPromises } from "@vue/test-utils";
import { afterEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  enqueue: vi.fn(),
  list: vi.fn(),
  stream: vi.fn(),
  run: vi.fn(),
  runs: vi.fn(),
  actions: vi.fn(),
  updateAccessPolicy: vi.fn(),
  getThread: vi.fn(),
  createThread: vi.fn(),
}));
vi.mock("@langchain/vue", () => ({ useStream: mocks.stream }));
vi.mock("@/services/threads/messages.service", () => ({
  enqueueThreadMessage: mocks.enqueue,
  listThreadMessages: mocks.list,
}));
vi.mock("@/services/threads/access-policy.service", () => ({
  updateThreadAccessPolicy: mocks.updateAccessPolicy,
}));
vi.mock("@/services/threads/session.service", () => ({
  createSessionService: () => ({
    client: {},
    runs: mocks.runs.getMockImplementation()
      ? mocks.runs
      : async () => [{ run_id: "run", status: "running" }],
    run: mocks.run,
    get: mocks.getThread.getMockImplementation()
      ? mocks.getThread
      : async () => ({ thread_id: "t", metadata: { access_policy: "review" } }),
    create: mocks.createThread.getMockImplementation()
      ? mocks.createThread
      : async () => ({ thread_id: "new-thread" }),
  }),
}));
vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: () => vi.fn(),
  getLanggraphApiUrl: () => "",
}));
vi.mock("../run-actions", () => ({
  createRunActions: () => mocks.actions() ?? ({ current: ref(null), begin: vi.fn(() => ({ key: "k" })), acknowledge: vi.fn(), rejectUnsent: vi.fn(), dispose: vi.fn() }),
}));
import { useChatSession } from "./useChatSession";
afterEach(() => { vi.restoreAllMocks(); mocks.actions.mockReset(); mocks.updateAccessPolicy.mockReset(); sessionStorage.clear(); });
it("unknown queue retry freezes original payload and key and clears draft only on ACK", async () => {
  mocks.stream.mockReturnValue({
    isLoading: ref(true),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  mocks.list.mockResolvedValue([]);
  mocks.enqueue.mockRejectedValueOnce(new Error("connection lost"));
  const accepted = vi.fn();
  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "p",
      graphId: "reference_agent",
      threadId: "t",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
      onAccepted: accepted,
    }),
  )!;
  try {
    await flushPromises();
    expect(await session.queueMessage("original")).toBe(false);
    expect(accepted).not.toHaveBeenCalled();
    expect(session.pendingMessage.value?.status).toBe("unknown");
    expect(session.canSend.value).toBe(false);
    const first = mocks.enqueue.mock.calls[0];
    mocks.enqueue.mockResolvedValue({
      message_id: first[2].client_message_id,
      status: "queued",
      sequence: 1,
    });
    expect(await session.queueMessage("changed draft")).toBe(true);
    expect(mocks.enqueue.mock.calls[1]).toEqual(first);
    expect(first[2].content).toBe("original");
    expect(accepted).toHaveBeenCalledTimes(1);
    expect(session.pendingMessage.value).toBeNull();
  } finally {
    scope.stop();
  }
});

it("late parent completion checks the new Run and cannot reopen sending", async () => {
  mocks.stream.mockReturnValue({ isLoading: ref(false), error: ref(null), interrupts: ref([]), hydrationPromise: ref(Promise.resolve()), disconnect: vi.fn() });
  const current = ref<{ key: string; kind: string; runId: string; status: string } | null>(null);
  mocks.actions.mockReturnValue({ current, dispose: vi.fn() });
  mocks.run.mockResolvedValue({ run_id: "new-run", status: "running" });
  const scope = effectScope();
  const session = scope.run(() => useChatSession({ projectId: "p", graphId: "workflow_demo", threadId: "t", context: ref({}), canWrite: ref(true), onThread: vi.fn(), onRefresh: vi.fn(), onReconnect: vi.fn() }))!;
  try {
    await flushPromises();
    current.value = { key: "new-action", kind: "send", runId: "new-run", status: "acknowledged" };
    mocks.stream.mock.lastCall![0].onCompleted();
    await flushPromises();
    expect(mocks.run).toHaveBeenCalledWith("t", "new-run");
    expect(session.run.value?.run_id).toBe("new-run");
    expect(session.busy.value).toBe(true);
    expect(session.canSend.value).toBe(false);
  } finally { scope.stop(); }
});

it("receipt before POST ACK confirms once, and disposed sessions ignore late receipts", async () => {
  mocks.stream.mockReturnValue({ isLoading: ref(true), error: ref(null), interrupts: ref([]), hydrationPromise: ref(Promise.resolve()), disconnect: vi.fn() });
  mocks.list.mockResolvedValue([]);
  let ack!: (value: unknown) => void;
  mocks.enqueue.mockImplementationOnce(() => new Promise(resolve => { ack = resolve; }));
  const accepted = vi.fn();
  const scope = effectScope();
  const session = scope.run(() => useChatSession({ projectId: "p", graphId: "reference_agent", threadId: "t", context: ref({}), canWrite: ref(true), onThread: vi.fn(), onRefresh: vi.fn(), onReconnect: vi.fn(), onAccepted: accepted }))!;
  await flushPromises();
  const request = session.queueMessage("ordered by ID");
  const id = session.pendingMessage.value!.payload.client_message_id;
  const consumed = { message_id: id, target_run_id: "run", thread_id: "t", sequence: 1, status: "consumed" };
  mocks.list.mockResolvedValueOnce([consumed]);
  await session.refreshReceipts();
  expect(accepted).toHaveBeenCalledTimes(1);
  ack({ ...consumed, status: "queued" });
  expect(await request).toBe(true);
  expect(accepted).toHaveBeenCalledTimes(1);
  expect(session.receipts.value[0]?.status).toBe("consumed");
  let late!: (value: unknown) => void;
  mocks.list.mockImplementationOnce(() => new Promise(resolve => { late = resolve; }));
  const refresh = session.refreshReceipts();
  scope.stop();
  late([]);
  await refresh;
  expect(session.receipts.value).toEqual([consumed]);
});

it("coalesces concurrent verify calls on completion so canSend resets to true", async () => {
  mocks.runs.mockResolvedValue([{ run_id: "run-0", status: "success" }]);
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  const current = ref<{ key: string; kind: string; runId: string; status: string } | null>(null);
  mocks.actions.mockReturnValue({ current, dispose: vi.fn() });
  mocks.run.mockResolvedValue({ run_id: "run-1", status: "success" });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "p",
      graphId: "workflow_demo",
      threadId: "t-1",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    expect(session.canSend.value).toBe(true);

    // 模拟并发调用：stream 的 onCompleted 与本地 verify(true) 同时触发
    current.value = { key: "send-1", kind: "send", runId: "run-1", status: "acknowledged" };
    const p1 = mocks.stream.mock.lastCall![0].onCompleted();
    const p2 = session.verify(true);

    await Promise.all([p1, p2]);
    await flushPromises();

    expect(session.verified.value).toBe(true);
    expect(session.checking.value).toBe(false);
    expect(session.canSend.value).toBe(true);
  } finally {
    scope.stop();
  }
});

it("does NOT throw unconfirmed error while stream is loading even if document is hidden", async () => {
  const isLoading = ref(true);
  mocks.stream.mockReturnValue({
    isLoading,
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  const current = ref<{ key: string; kind: string; runId: string; status: string } | null>({
    key: "action-1",
    kind: "send",
    runId: "run-active",
    status: "acknowledged",
  });
  mocks.actions.mockReturnValue({ current, dispose: vi.fn() });
  mocks.run.mockResolvedValue({ run_id: "run-active", status: "running" });

  const originalHidden = Object.getOwnPropertyDescriptor(document, "hidden");
  Object.defineProperty(document, "hidden", { configurable: true, get: () => true });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "p",
      graphId: "workflow_demo",
      threadId: "t-hidden",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    // 触发 verify(true)，在后台运行且 stream 仍在 loading
    void session.verify(true);
    await flushPromises();

    // 绝不能报错为“运行结果尚未确认”
    expect(session.error.value).toBe("");
    expect(session.busy.value).toBe(true);

    // 随后后端 run 完成且流式结束
    mocks.run.mockResolvedValueOnce({ run_id: "run-active", status: "success" });
    isLoading.value = false;
    await session.verify(true);
    await flushPromises();

    expect(session.error.value).toBe("");
    expect(session.verified.value).toBe(true);
  } finally {
    if (originalHidden) {
      Object.defineProperty(document, "hidden", originalHidden);
    }
    scope.stop();
  }
});

it("supports draft state policy staging and sends PATCH before starting run on new thread", async () => {
  const submitFn = vi.fn().mockResolvedValue(undefined);
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
    submit: submitFn,
  });
  mocks.runs.mockResolvedValue([]);
  mocks.updateAccessPolicy.mockResolvedValue({
    thread_id: "created-thread-1",
    access_policy: "workspace_write",
  });
  mocks.createThread.mockResolvedValue({ thread_id: "created-thread-1" });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "reference_agent",
      threadId: undefined, // 草稿态
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    expect(session.accessPolicy.value).toBe("review");

    // 1. 草稿态预选 workspace_write
    const switched = await session.setAccessPolicy("workspace_write");
    expect(switched).toBe(true);
    expect(session.accessPolicy.value).toBe("workspace_write");
    // 此时尚未创建线程，不应调用 API
    expect(mocks.updateAccessPolicy).not.toHaveBeenCalled();

    // 2. 发送首条消息，触发创建线程并补发 PATCH
    await session.send("Hello agent");
    await flushPromises();

    expect(mocks.createThread).toHaveBeenCalled();
    expect(mocks.updateAccessPolicy).toHaveBeenCalledWith(
      "proj-1",
      "created-thread-1",
      "workspace_write",
    );
    expect(submitFn).toHaveBeenCalled();
  } finally {
    scope.stop();
  }
});

it("updates access policy for existing thread via API and handles failure gracefully", async () => {
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  mocks.runs.mockResolvedValue([]);
  mocks.getThread.mockResolvedValue({
    thread_id: "thread-existing",
    metadata: { access_policy: "review" },
  });
  mocks.updateAccessPolicy.mockResolvedValue({
    thread_id: "thread-existing",
    access_policy: "workspace_write",
  });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "reference_agent",
      threadId: "thread-existing",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    expect(session.accessPolicy.value).toBe("review");

    // 成功切换
    const success = await session.setAccessPolicy("workspace_write");
    expect(success).toBe(true);
    expect(session.accessPolicy.value).toBe("workspace_write");
    expect(mocks.updateAccessPolicy).toHaveBeenCalledWith(
      "proj-1",
      "thread-existing",
      "workspace_write",
    );

    // 切换失败时保留原值
    mocks.updateAccessPolicy.mockRejectedValueOnce(new Error("409 Conflict"));
    const failed = await session.setAccessPolicy("review");
    expect(failed).toBe(false);
    expect(session.accessPolicy.value).toBe("workspace_write"); // 保持原值，不乐观伪造
    expect(session.error.value).toContain("409 Conflict");
  } finally {
    scope.stop();
  }
});

it("supports draft state full_access staging and keeps full_access after refresh", async () => {
  const submitFn = vi.fn();
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
    submit: submitFn,
  });
  mocks.runs.mockResolvedValue([]);
  mocks.createThread.mockResolvedValue({ thread_id: "created-thread-full" });
  mocks.getThread.mockResolvedValue({
    thread_id: "created-thread-full",
    metadata: { access_policy: "full_access" },
  });
  mocks.updateAccessPolicy.mockResolvedValue({
    thread_id: "created-thread-full",
    access_policy: "full_access",
  });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "reference_agent",
      threadId: undefined, // 草稿态
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    expect(session.accessPolicy.value).toBe("review");

    // 1. 草稿态预选 full_access
    const switched = await session.setAccessPolicy("full_access");
    expect(switched).toBe(true);
    expect(session.accessPolicy.value).toBe("full_access");
    expect(mocks.updateAccessPolicy).not.toHaveBeenCalled();

    // 2. 发送首条消息，触发创建线程并补发 PATCH "full_access"
    await session.send("Build architecture design");
    await flushPromises();

    expect(mocks.createThread).toHaveBeenCalled();
    expect(mocks.updateAccessPolicy).toHaveBeenCalledWith(
      "proj-1",
      "created-thread-full",
      "full_access",
    );
    expect(submitFn).toHaveBeenCalled();

    // 3. 模拟工具调用中断后触发 refreshAccessPolicy，验证策略坚定常驻为 full_access，绝不退化为 review
    await session.refreshAccessPolicy();
    expect(session.accessPolicy.value).toBe("full_access");
  } finally {
    scope.stop();
  }
});


