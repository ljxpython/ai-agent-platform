import { effectScope, ref } from "vue";
import { flushPromises } from "@vue/test-utils";
import { afterEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  enqueue: vi.fn(),
  list: vi.fn(),
  stream: vi.fn(),
  run: vi.fn(),
  runs: vi.fn(),
  cancel: vi.fn(),
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
vi.mock("@/services/threads/session.service", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/services/threads/session.service")>(),
  createSessionService: () => ({
    client: {},
    runs: mocks.runs.getMockImplementation()
      ? mocks.runs
      : async () => [{ run_id: "run", status: "running" }],
    run: mocks.run,
    cancel: mocks.cancel,
    get: mocks.getThread.getMockImplementation()
      ? mocks.getThread
      : async () => ({ thread_id: "t", metadata: { access_policy: "review", allowed_actions: ["read", "comment", "edit", "approve", "share", "full_access"] } }),
    create: mocks.createThread.getMockImplementation()
      ? mocks.createThread
      : async () => ({ thread_id: "new-thread", metadata: { allowed_actions: ["read", "comment", "edit", "approve", "share", "full_access"] } }),
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
import { useDearAgentSession } from "../../dear-agent/composables/useDearAgentSession";
vi.mock("../../dear-agent/run-actions", () => ({
  createRunActions: () => ({ current: ref(null), begin: vi.fn(() => ({ key: "k" })), acknowledge: vi.fn(), rejectUnsent: vi.fn(), dispose: vi.fn() }),
}));
it.each([useChatSession, useDearAgentSession])("revokes visible Thread content and disconnects on the 60-second ACL refresh (%#)", async (useSession) => {
  vi.useFakeTimers();
  const disconnect = vi.fn();
  mocks.stream.mockReturnValue({ isLoading: ref(false), error: ref(null), interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()), disconnect });
  mocks.runs.mockResolvedValue([]);
  mocks.list.mockResolvedValue([]);
  mocks.getThread.mockResolvedValue({ thread_id: "t", metadata: { allowed_actions: ["read", "comment"] } });
  const scope = effectScope();
  const session = scope.run(() => useSession({ projectId: "p", graphId: "reference_agent", threadId: "t",
    context: ref({}), canWrite: ref(true), onThread: vi.fn(), onRefresh: vi.fn(), onReconnect: vi.fn() }))!;
  try {
    await flushPromises();
    expect(session.canRead.value).toBe(true);
    mocks.getThread.mockRejectedValue(new Error("Forbidden"));
    await vi.advanceTimersByTimeAsync(60_000);
    await flushPromises();
    expect(session.canRead.value).toBe(false);
    expect(session.canComment.value).toBe(false);
    expect(disconnect).toHaveBeenCalled();
  } finally {
    scope.stop();
    mocks.getThread.mockReset();
    mocks.runs.mockReset();
    vi.useRealTimers();
  }
});
afterEach(() => { vi.restoreAllMocks(); mocks.actions.mockReset(); mocks.updateAccessPolicy.mockReset(); sessionStorage.clear(); });
it.each([useChatSession, useDearAgentSession])("ignores an ACL response issued before a sharing change (%#)", async useSession => {
  mocks.stream.mockReturnValue({ isLoading: ref(false), error: ref(null), interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()), disconnect: vi.fn() });
  mocks.runs.mockResolvedValue([]);
  mocks.list.mockResolvedValue([]);
  const allowed = { thread_id: "t", metadata: { allowed_actions: ["read", "comment"] } };
  mocks.getThread.mockResolvedValue(allowed);
  const scope = effectScope();
  const session = scope.run(() => useSession({ projectId: "p", graphId: "reference_agent", threadId: "t",
    context: ref({}), canWrite: ref(true), onThread: vi.fn(), onRefresh: vi.fn(), onReconnect: vi.fn() }))!;
  try {
    await flushPromises();
    let resolveOld!: (value: typeof allowed) => void;
    mocks.getThread.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    const oldRequest = session.refreshAccessPolicy();
    window.dispatchEvent(new Event('thread-access-updated'));
    expect(session.canRead.value).toBe(false);
    mocks.getThread.mockRejectedValue(new Error('Forbidden'));
    resolveOld(allowed);
    await oldRequest;
    await flushPromises();
    expect(session.canRead.value).toBe(false);
    expect(session.canComment.value).toBe(false);
  } finally { scope.stop(); mocks.getThread.mockReset(); mocks.runs.mockReset(); }
});
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
  mocks.createThread.mockResolvedValue({ thread_id: "created-thread-1", metadata: { allowed_actions: ["read", "comment", "edit", "approve", "share", "full_access"] } });

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
    metadata: { access_policy: "review", allowed_actions: ["read", "comment", "edit", "approve", "share", "full_access"] },
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
  mocks.createThread.mockResolvedValue({ thread_id: "created-thread-full", metadata: { allowed_actions: ["read", "comment", "edit", "approve", "share", "full_access"] } });
  mocks.getThread.mockResolvedValue({
    thread_id: "created-thread-full",
    metadata: { access_policy: "full_access", allowed_actions: ["read", "comment", "edit", "approve", "share", "full_access"] },
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

it.each([useChatSession, useDearAgentSession])("self-heals and fallbacks to direct send when queueMessage encounters 409 run_changed (%#)", async (useSession) => {
  const submitFn = vi.fn().mockResolvedValue({});
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
    submit: submitFn,
  });
  mocks.runs.mockResolvedValue([{ run_id: "run-ended-1", status: "success" }]);
  mocks.list.mockResolvedValue([]);
  mocks.getThread.mockResolvedValue({
    thread_id: "t-heal",
    metadata: { allowed_actions: ["read", "comment", "edit", "approve", "share", "full_access"] },
  });

  const scope = effectScope();
  const session = scope.run(() =>
    useSession({
      projectId: "proj-heal",
      graphId: "reference_agent",
      threadId: "t-heal",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();

    // 1. 无 active run 时调用 queueMessage，直接自愈回退到 direct send，不抛错
    await session.queueMessage("hello when idle");
    expect(submitFn).toHaveBeenCalledTimes(1);
    expect(session.error.value).toBe("");

    // 2. 模拟运行中有 active run，但向后端排队时后端判定 run 已结束返回 409 run_changed
    mocks.enqueue.mockRejectedValueOnce(
      Object.assign(new Error("Request failed with status code 409"), {
        isAxiosError: true,
        response: { status: 409, data: { detail: "run_changed" } },
      }),
    );

    await session.queueMessage("second message after run ended");
    // 验证无感自愈转为发起新回合 send()，因此 submit 被再次调用
    expect(submitFn).toHaveBeenCalledTimes(2);
    // 验证绝不将 409 冒泡为顶部大红框报错
    expect(session.error.value).toBe("");
  } finally {
    scope.stop();
    mocks.enqueue.mockReset();
    mocks.runs.mockReset();
  }
});

it.each([useChatSession, useDearAgentSession])(
  "suppresses historical clarification flash during hydration/completed run and keeps queued item when send fromQueue hits 409 (%#)",
  async (useSession) => {
    let resolveHydration!: () => void;
  const hydrationDeferred = new Promise<void>((resolve) => {
    resolveHydration = resolve;
  });

  const submitFn = vi.fn(async () => {
    throw new Error("409 Conflict: Cannot start a new run while thread has a pending or running run.");
  });

  mocks.stream.mockReturnValue({
    values: ref({ messages: [] }),
    messages: ref([]),
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([
      {
        id: "hist-clarification-1",
        value: {
          action_requests: [
            {
              name: "ask_user_question",
              args: {
                schema_version: 1,
                title: "历史需求澄清",
                questions: [{ id: "q1", label: "选择方向", type: "text" }],
              },
            },
          ],
        },
      },
    ]),
    hydrationPromise: ref(hydrationDeferred),
    disconnect: vi.fn(),
    submit: submitFn,
  });

  // 初始 hydrate 完成时后端返回最新已完结 run（success）
  mocks.runs.mockResolvedValue([{ run_id: "run-completed-old", status: "success" }]);
  mocks.list.mockResolvedValue([]);
  mocks.getThread.mockResolvedValue({
    thread_id: "t-switch-back",
    metadata: { allowed_actions: ["read", "comment", "edit", "approve", "share", "full_access"] },
  });

  const scope = effectScope();
  const session = scope.run(() =>
    useSession({
      projectId: "proj-switch",
      graphId: "reference_agent",
      threadId: "t-switch-back",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    // 1. Hydration 尚未完成、messages 为空时，历史中断绝不可闪现为澄清卡片
    expect(session.clarifications.value).toHaveLength(0);

    resolveHydration();
    await flushPromises();

    // 2. Hydration 完成后，当前最新 run 为 success 终态（非 interrupted），历史中断同样绝不可闪现
    expect(session.clarifications.value).toHaveLength(0);

    // 3. 模拟后台其实有一个新启动的 active run 正在执行，前端队列尝试弹出第一条消息发送（fromQueue: true）遇到 409
    mocks.runs.mockResolvedValue([{ run_id: "run-active-bg", status: "running" }]);
    const ok = await session.send("queued message 1", 1000, { fromQueue: true });

    // 必须返回 false 以便前端队列将消息放回队首等待，且只尝试 1 次不产生递归重复气泡
    expect(ok).toBe(false);
    expect(submitFn).toHaveBeenCalledTimes(1);
    expect(session.error.value).toBe("");
    // 并且 verify(true) 已将后台 running 状态同步回前端，busy 恢复为 true 阻止后续队列继续抢跑
    expect(session.busy.value).toBe(true);
  } finally {
    scope.stop();
    mocks.runs.mockReset();
  }
});

it("seeds accessThread from initialThread with zero accessLoading and stops in-place without calling onReconnect", async () => {
  const disconnect = vi.fn();
  const onReconnect = vi.fn();
  const isLoading = ref(true);
  mocks.stream.mockReturnValue({
    isLoading,
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect,
  });
  mocks.runs.mockResolvedValue([{ run_id: "run-active-1", status: "running" }]);
  mocks.run.mockResolvedValue({ run_id: "run-active-1", status: "interrupted" });
  mocks.cancel.mockResolvedValue(undefined);
  mocks.list.mockResolvedValue([]);
  mocks.getThread.mockClear();

  const preloadedThread = {
    thread_id: "t-seeded",
    created_at: "2026-09-23T00:00:00Z",
    updated_at: "2026-09-23T00:00:00Z",
    status: "busy" as const,
    values: { messages: [] },
    metadata: {
      access_policy: "workspace_write",
      allowed_actions: ["read", "comment", "edit", "approve", "share"],
    },
  };

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t-seeded",
      initialThread: ref(preloadedThread),
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect,
    }),
  )!;

  try {
    // 1. 挂载第 0 帧即完成权限水合，绝不触发 accessLoading 遮罩，也不重复请求 getThread
    expect(session.accessLoading.value).toBe(false);
    expect(session.canRead.value).toBe(true);
    expect(session.accessPolicy.value).toBe("workspace_write");
    expect(mocks.getThread).not.toHaveBeenCalled();

    await flushPromises();
    expect(session.accessLoading.value).toBe(false);
    expect(mocks.getThread).not.toHaveBeenCalled();

    // 2. 点击停止时，原地取消 run 并断开流，绝不触发 onReconnect 重建组件或开启 accessLoading
    await session.stop();
    expect(mocks.cancel).toHaveBeenCalledWith("t-seeded", "run-active-1");
    expect(disconnect).toHaveBeenCalled();
    expect(onReconnect).not.toHaveBeenCalled();
    expect(session.accessLoading.value).toBe(false);
  } finally {
    scope.stop();
    mocks.runs.mockReset();
    mocks.run.mockReset();
    mocks.cancel.mockReset();
  }
});

it("removes uncommitted HumanMessage from stream.messages on 409 and extends verify deadline while backend run is active", async () => {
  vi.useFakeTimers();
  const streamMessages = ref<Array<{ id?: string; type?: string; content?: unknown }>>([]);
  const submitFn = vi.fn().mockImplementation(async (input: { messages: Array<{ id?: string; type?: string; content?: unknown }> }) => {
    streamMessages.value = [...streamMessages.value, ...input.messages];
    throw new Error("409 Conflict: pending or running run");
  });

  mocks.runs.mockResolvedValue([{ run_id: "run-active-44s", status: "running" }]);
  mocks.run.mockResolvedValue({ run_id: "run-active-44s", status: "running" });
  mocks.stream.mockReturnValue({
    messages: streamMessages,
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    submit: submitFn,
    disconnect: vi.fn(),
  });
  const current = ref<{ key: string; kind: string; runId?: string; status: string } | null>(null);
  mocks.actions.mockReturnValue({
    current,
    begin: vi.fn((_tid: string, kind: string) => {
      const action = { key: "act-409", kind, status: "submitting" };
      current.value = action;
      return action;
    }),
    rejectUnsent: vi.fn(() => {
      current.value = null;
    }),
    acknowledge: vi.fn(),
    dispose: vi.fn(),
  });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "showcase_demo",
      threadId: "t-409",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    const sendPromise = session.send("你再换另一个人物给我讲一下", 1000, { fromQueue: true });
    await flushPromises();
    const ok = await sendPromise;

    // 1. 遇到 409 返回 false 交由队列等待，且 stream.messages 中注入的未提交消息必须被清除，不留假气泡
    expect(ok).toBe(false);
    expect(streamMessages.value).toEqual([]);

    // 2. 即使 stream.isLoading=false，只要服务端轮询返回 status="running"，超过 30 秒也绝不能报错“运行结果尚未确认”
    void session.verify(true);
    for (let i = 0; i < 10; i++) {
      await vi.advanceTimersByTimeAsync(4000);
      await flushPromises();
    }
    expect(session.error.value).toBe("");

    mocks.run.mockResolvedValueOnce({ run_id: "run-active-44s", status: "success" });
    await vi.advanceTimersByTimeAsync(4000);
    await flushPromises();
    expect(session.verified.value).toBe(true);
    expect(session.error.value).toBe("");
  } finally {
    scope.stop();
    vi.useRealTimers();
    mocks.runs.mockReset();
    mocks.run.mockReset();
  }
});




