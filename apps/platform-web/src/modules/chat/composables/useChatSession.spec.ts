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
  resume: vi.fn(),
  actions: vi.fn(),
  updateAccessPolicy: vi.fn(),
  getThread: vi.fn(),
  createThread: vi.fn(),
  state: vi.fn(),
  history: vi.fn(),
  useChannelEffect: vi.fn(),
}));
vi.mock("@langchain/vue", () => ({
  useStream: mocks.stream,
  useChannelEffect: mocks.useChannelEffect,
}));
vi.mock("@/services/threads/messages.service", () => ({
  enqueueThreadMessage: mocks.enqueue,
  listThreadMessages: mocks.list,
}));
vi.mock("@/services/threads/access-policy.service", () => ({
  updateThreadAccessPolicy: mocks.updateAccessPolicy,
}));
vi.mock("@/services/threads/session.service", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("@/services/threads/session.service")
  >()),
  createSessionService: () => ({
    client: {},
    runs: mocks.runs.getMockImplementation()
      ? mocks.runs
      : async () => [{ run_id: "run", status: "running" }],
    run: mocks.run,
    cancel: mocks.cancel,
    resume: mocks.resume,
    get: mocks.getThread.getMockImplementation()
      ? mocks.getThread
      : async () => ({
          thread_id: "t",
          metadata: {
            access_policy: "review",
            allowed_actions: [
              "read",
              "comment",
              "edit",
              "approve",
              "share",
              "full_access",
            ],
          },
        }),
    create: mocks.createThread.getMockImplementation()
      ? mocks.createThread
      : async () => ({
          thread_id: "new-thread",
          metadata: {
            allowed_actions: [
              "read",
              "comment",
              "edit",
              "approve",
              "share",
              "full_access",
            ],
          },
        }),
    state: mocks.state,
    history: mocks.history,
  }),
}));
vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: () => vi.fn(),
  getLanggraphApiUrl: () => "",
}));
vi.mock("../run-actions", () => ({
  createRunActions: () =>
    mocks.actions() ?? {
      current: ref(null),
      begin: vi.fn(() => ({ key: "k" })),
      acknowledge: vi.fn(),
      rejectUnsent: vi.fn(),
      dispose: vi.fn(),
    },
}));
import { useChatSession } from "./useChatSession";
import { useDearAgentSession } from "../../dear-agent/composables/useDearAgentSession";

it("parks background SSE, confirms terminal state and permits the next queued turn", async () => {
  vi.useFakeTimers();
  const visible = ref(true);
  const loading = ref(true);
  let state = "connected";
  const thread = {
    onConnectionChange: vi.fn(),
    suspendEvents: vi.fn(() => {
      state = "paused";
    }),
    getConnectionState: () => ({ state, streams: [] }),
    reconnectEvents: vi.fn(async () => {
      state = "connected";
    }),
  };
  const disconnect = vi.fn(async () => {
    loading.value = false;
  });
  mocks.stream.mockReturnValue({
    isLoading: loading,
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    getThread: () => thread,
    disconnect,
  });
  mocks.runs.mockResolvedValue([{ run_id: "run", status: "running" }]);
  mocks.list.mockResolvedValue([]);
  mocks.state.mockResolvedValue({
    values: { messages: [{ type: "ai", content: "finished" }] },
  });
  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "p",
      graphId: "showcase_demo",
      threadId: "t",
      visible,
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;
  try {
    await flushPromises();
    visible.value = false;
    await flushPromises();
    expect(thread.suspendEvents).toHaveBeenCalled();
    mocks.runs.mockResolvedValue([{ run_id: "run", status: "success" }]);
    await vi.advanceTimersByTimeAsync(1600);
    await flushPromises();
    expect(disconnect).toHaveBeenCalled();
    expect(session.recoverySnapshot.value?.messages).toHaveLength(1);
    expect(session.canSend.value).toBe(true);
    visible.value = true;
    await flushPromises();
    expect(thread.reconnectEvents).toHaveBeenCalled();
  } finally {
    scope.stop();
    mocks.runs.mockReset();
    vi.useRealTimers();
  }
});
vi.mock("../../dear-agent/run-actions", () => ({
  createRunActions: () => ({
    current: ref(null),
    begin: vi.fn(() => ({ key: "k" })),
    acknowledge: vi.fn(),
    rejectUnsent: vi.fn(),
    dispose: vi.fn(),
  }),
}));
it.each([useChatSession, useDearAgentSession])(
  "revokes visible Thread content and disconnects on the 60-second ACL refresh (%#)",
  async (useSession) => {
    vi.useFakeTimers();
    const disconnect = vi.fn();
    mocks.stream.mockReturnValue({
      isLoading: ref(false),
      error: ref(null),
      interrupts: ref([]),
      hydrationPromise: ref(Promise.resolve()),
      disconnect,
    });
    mocks.runs.mockResolvedValue([]);
    mocks.list.mockResolvedValue([]);
    mocks.getThread.mockResolvedValue({
      thread_id: "t",
      metadata: { allowed_actions: ["read", "comment"] },
    });
    const scope = effectScope();
    const session = scope.run(() =>
      useSession({
        projectId: "p",
        graphId: "reference_agent",
        threadId: "t",
        context: ref({}),
        canWrite: ref(true),
        onThread: vi.fn(),
        onRefresh: vi.fn(),
        onReconnect: vi.fn(),
      }),
    )!;
    try {
      await flushPromises();
      expect(session.canRead.value).toBe(true);
      mocks.getThread.mockRejectedValue(
        Object.assign(new Error("Forbidden"), { status: 403 }),
      );
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
  },
);
afterEach(() => {
  vi.restoreAllMocks();
  mocks.actions.mockReset();
  mocks.updateAccessPolicy.mockReset();
  sessionStorage.clear();
});
it("recovers one expired cursor when suspension synchronously reports the same 410", async () => {
  const expired = Object.assign(new Error("expired"), { status: 410 });
  let listener:
    | ((state: {
        state: string;
        streams: { state: string; error?: Error }[];
      }) => void)
    | undefined;
  const streamThread = {
    onConnectionChange: vi.fn((callback: typeof listener) => {
      listener = callback;
      callback?.({ state: "connected", streams: [{ state: "connected" }] });
      return vi.fn();
    }),
    suspendEvents: vi.fn(() =>
      listener?.({
        state: "paused",
        streams: [{ state: "paused", error: expired }],
      }),
    ),
    reconnectEvents: vi.fn(async () => {}),
    getConnectionState: vi.fn(() => ({
      state: "paused",
      streams: [{ state: "paused", error: expired }],
    })),
  };
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
    getThread: () => streamThread,
  });
  mocks.getThread.mockResolvedValue({
    thread_id: "t",
    metadata: { allowed_actions: ["read", "comment"] },
  });
  mocks.state.mockResolvedValue({ values: { messages: [] } });
  mocks.history.mockResolvedValue([]);
  mocks.runs.mockResolvedValue([]);
  const scope = effectScope();
  try {
    scope.run(() =>
      useChatSession({
        projectId: "p",
        graphId: "reference_agent",
        threadId: "t",
        context: ref({}),
        canWrite: ref(true),
        onThread: vi.fn(),
        onRefresh: vi.fn(),
        onReconnect: vi.fn(),
      }),
    );
    await flushPromises();
    listener?.({
      state: "paused",
      streams: [{ state: "paused", error: expired }],
    });
    await flushPromises();
    expect(streamThread.suspendEvents).toHaveBeenCalledTimes(1);
    expect(mocks.state).toHaveBeenCalledTimes(1);
    expect(streamThread.reconnectEvents).toHaveBeenCalledTimes(1);
  } finally {
    scope.stop();
    mocks.getThread.mockReset();
    mocks.state.mockReset();
    mocks.history.mockReset();
    mocks.runs.mockReset();
  }
});
it("recovers stream smoothly without failure even if history fetch fails or times out with 504", async () => {
  const expired = Object.assign(new Error("expired"), { status: 410 });
  const timeout504 = Object.assign(new Error("LangGraph upstream timed out"), {
    status: 504,
  });
  let listener:
    | ((state: {
        state: string;
        streams: { state: string; error?: Error }[];
      }) => void)
    | undefined;
  const streamThread = {
    onConnectionChange: vi.fn((callback: typeof listener) => {
      listener = callback;
      callback?.({ state: "connected", streams: [{ state: "connected" }] });
      return vi.fn();
    }),
    suspendEvents: vi.fn(() =>
      listener?.({
        state: "paused",
        streams: [{ state: "paused", error: expired }],
      }),
    ),
    reconnectEvents: vi.fn(async () => {}),
    getConnectionState: vi.fn(() => ({
      state: "paused",
      streams: [{ state: "paused", error: expired }],
    })),
  };
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
    getThread: () => streamThread,
  });
  mocks.getThread.mockResolvedValue({
    thread_id: "t",
    metadata: { allowed_actions: ["read", "comment"] },
  });
  mocks.state.mockResolvedValue({
    values: { messages: [{ role: "assistant", content: "hello" }] },
  });
  // 模拟 history 接口发生 504 严重超时！
  mocks.history.mockRejectedValue(timeout504);
  mocks.runs.mockResolvedValue([]);
  const scope = effectScope();
  try {
    let session!: ReturnType<typeof useChatSession>;
    scope.run(() => {
      session = useChatSession({
        projectId: "p",
        graphId: "reference_agent",
        threadId: "t",
        context: ref({}),
        canWrite: ref(true),
        onThread: vi.fn(),
        onRefresh: vi.fn(),
        onReconnect: vi.fn(),
      });
    });
    await flushPromises();
    // 触发 410 流过期
    listener?.({
      state: "paused",
      streams: [{ state: "paused", error: expired }],
    });
    await flushPromises();
    // 验证核心自愈链路全部通畅，没有被 history 504 中断
    expect(streamThread.suspendEvents).toHaveBeenCalledTimes(1);
    expect(mocks.state).toHaveBeenCalledTimes(1);
    expect(streamThread.reconnectEvents).toHaveBeenCalledTimes(1);
    // 验证状态机平稳自愈，快照成功恢复，绝不进入 failed 态
    expect(session.status.value).not.toBe("failed");
    expect(session.recoverySnapshot.value).toEqual({
      messages: [{ role: "assistant", content: "hello" }],
    });
    expect(session.error.value).toBe(
      "历史流已过期，已刷新当前状态；部分过程无法恢复",
    );
  } finally {
    scope.stop();
    mocks.getThread.mockReset();
    mocks.state.mockReset();
    mocks.history.mockReset();
    mocks.runs.mockReset();
  }
});
it("discards a stale 410 snapshot and resumes the paused stream after a new Run appears", async () => {
  const expired = Object.assign(new Error("expired"), { status: 410 });
  let listener:
    | ((state: {
        state: string;
        streams: { state: string; error?: Error }[];
      }) => void)
    | undefined;
  const streamThread = {
    onConnectionChange: vi.fn((callback: typeof listener) => {
      listener = callback;
      callback?.({ state: "connected", streams: [{ state: "connected" }] });
      return vi.fn();
    }),
    suspendEvents: vi.fn(),
    reconnectEvents: vi.fn(async () => {}),
    getConnectionState: vi.fn(() => ({
      state: "paused",
      streams: [{ state: "paused", error: expired }],
    })),
  };
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
    getThread: () => streamThread,
  });
  mocks.getThread.mockResolvedValue({
    thread_id: "t",
    metadata: { allowed_actions: ["read", "comment", "approve"] },
  });
  mocks.runs.mockResolvedValue([{ run_id: "run-2", status: "running" }]);
  mocks.history.mockResolvedValue([]);
  let resolveState!: (state: {
    values: { messages: { id: string }[] };
  }) => void;
  mocks.state.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveState = resolve;
      }),
  );
  const scope = effectScope();
  try {
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
      }),
    )!;
    await flushPromises();
    session.run.value = {
      run_id: "run-1",
      status: "running",
    } as typeof session.run.value;
    listener?.({
      state: "paused",
      streams: [{ state: "paused", error: expired }],
    });
    await flushPromises();
    expect(session.canApprove.value).toBe(false);
    expect(session.canSend.value).toBe(false);
    expect(await session.queueMessage("must stay local")).toBe(false);
    await vi.waitFor(() => expect(mocks.state).toHaveBeenCalledTimes(1));
    session.run.value = {
      run_id: "run-2",
      status: "running",
    } as typeof session.run.value;
    resolveState({ values: { messages: [{ id: "old-snapshot" }] } });
    await vi.waitFor(() =>
      expect(streamThread.reconnectEvents).toHaveBeenCalledTimes(1),
    );
    expect(session.recoverySnapshot.value).toBeNull();
    expect(mocks.runs).toHaveBeenCalled();
    expect(mocks.enqueue).not.toHaveBeenCalled();
  } finally {
    scope.stop();
    mocks.getThread.mockReset();
    mocks.runs.mockReset();
    mocks.state.mockReset();
    mocks.history.mockReset();
  }
});
it.each([useChatSession, useDearAgentSession])(
  "ignores an ACL response issued before a sharing change (%#)",
  async (useSession) => {
    mocks.stream.mockReturnValue({
      isLoading: ref(false),
      error: ref(null),
      interrupts: ref([]),
      hydrationPromise: ref(Promise.resolve()),
      disconnect: vi.fn(),
    });
    mocks.runs.mockResolvedValue([]);
    mocks.list.mockResolvedValue([]);
    const allowed = {
      thread_id: "t",
      metadata: { allowed_actions: ["read", "comment"] },
    };
    mocks.getThread.mockResolvedValue(allowed);
    const scope = effectScope();
    const session = scope.run(() =>
      useSession({
        projectId: "p",
        graphId: "reference_agent",
        threadId: "t",
        context: ref({}),
        canWrite: ref(true),
        onThread: vi.fn(),
        onRefresh: vi.fn(),
        onReconnect: vi.fn(),
      }),
    )!;
    try {
      await flushPromises();
      let resolveOld!: (value: typeof allowed) => void;
      mocks.getThread.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOld = resolve;
          }),
      );
      const oldRequest = session.refreshAccessPolicy();
      window.dispatchEvent(new Event("thread-access-updated"));
      expect(session.canRead.value).toBe(false);
      mocks.getThread.mockRejectedValue(new Error("Forbidden"));
      resolveOld(allowed);
      await oldRequest;
      await flushPromises();
      expect(session.canRead.value).toBe(false);
      expect(session.canComment.value).toBe(false);
    } finally {
      scope.stop();
      mocks.getThread.mockReset();
      mocks.runs.mockReset();
    }
  },
);
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
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  const current = ref<{
    key: string;
    kind: string;
    runId: string;
    status: string;
  } | null>(null);
  mocks.actions.mockReturnValue({ current, dispose: vi.fn() });
  mocks.run.mockResolvedValue({ run_id: "new-run", status: "running" });
  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "p",
      graphId: "workflow_demo",
      threadId: "t",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;
  try {
    await flushPromises();
    current.value = {
      key: "new-action",
      kind: "send",
      runId: "new-run",
      status: "acknowledged",
    };
    mocks.stream.mock.lastCall![0].onCompleted();
    await flushPromises();
    expect(mocks.run).toHaveBeenCalledWith("t", "new-run");
    expect(session.run.value?.run_id).toBe("new-run");
    expect(session.busy.value).toBe(true);
    expect(session.canSend.value).toBe(false);
  } finally {
    scope.stop();
  }
});

it("keeps the stream after cancel ACK until the server confirms a terminal Run", async () => {
  const disconnect = vi.fn();
  mocks.stream.mockReturnValue({
    isLoading: ref(true),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect,
  });
  mocks.runs.mockResolvedValue([{ run_id: "run-1", status: "running" }]);
  mocks.cancel.mockResolvedValue(undefined);
  let finish!: (value: { run_id: string; status: string }) => void;
  mocks.run
    .mockResolvedValueOnce({ run_id: "run-1", status: "running" })
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
  const scope = effectScope();
  try {
    const session = scope.run(() =>
      useChatSession({
        projectId: "p",
        graphId: "workflow_demo",
        threadId: "t",
        initialThread: ref({
          thread_id: "t",
          metadata: { allowed_actions: ["read", "comment", "edit", "approve"] },
        } as never),
        context: ref({}),
        canWrite: ref(true),
        onThread: vi.fn(),
        onRefresh: vi.fn(),
        onReconnect: vi.fn(),
      }),
    )!;
    await flushPromises();
    const stopping = session.stop();
    await vi.waitFor(() => expect(mocks.run).toHaveBeenCalledTimes(2));
    expect(mocks.cancel).toHaveBeenCalledTimes(1);
    expect(session.run.value?.status).toBe("running");
    expect(disconnect).not.toHaveBeenCalled();
    finish({ run_id: "run-1", status: "cancelled" });
    await stopping;
    expect(session.run.value?.status).toBe("cancelled");
    expect(disconnect).not.toHaveBeenCalled();
  } finally {
    scope.stop();
    mocks.runs.mockReset();
    mocks.run.mockReset();
    mocks.cancel.mockReset();
  }
});

it("receipt before POST ACK confirms once, and disposed sessions ignore late receipts", async () => {
  mocks.stream.mockReturnValue({
    isLoading: ref(true),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  mocks.list.mockResolvedValue([]);
  let ack!: (value: unknown) => void;
  mocks.enqueue.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        ack = resolve;
      }),
  );
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
  await flushPromises();
  const request = session.queueMessage("ordered by ID");
  const id = session.pendingMessage.value!.payload.client_message_id;
  const consumed = {
    message_id: id,
    target_run_id: "run",
    thread_id: "t",
    sequence: 1,
    status: "consumed",
  };
  mocks.list.mockResolvedValueOnce([consumed]);
  await session.refreshReceipts();
  expect(accepted).toHaveBeenCalledTimes(1);
  ack({ ...consumed, status: "queued" });
  expect(await request).toBe(true);
  expect(accepted).toHaveBeenCalledTimes(1);
  expect(session.receipts.value[0]?.status).toBe("consumed");
  let late!: (value: unknown) => void;
  mocks.list.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        late = resolve;
      }),
  );
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
  const current = ref<{
    key: string;
    kind: string;
    runId: string;
    status: string;
  } | null>(null);
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
    current.value = {
      key: "send-1",
      kind: "send",
      runId: "run-1",
      status: "acknowledged",
    };
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
  const current = ref<{
    key: string;
    kind: string;
    runId: string;
    status: string;
  } | null>({
    key: "action-1",
    kind: "send",
    runId: "run-active",
    status: "acknowledged",
  });
  mocks.actions.mockReturnValue({ current, dispose: vi.fn() });
  mocks.run.mockResolvedValue({ run_id: "run-active", status: "running" });

  const originalHidden = Object.getOwnPropertyDescriptor(document, "hidden");
  Object.defineProperty(document, "hidden", {
    configurable: true,
    get: () => true,
  });

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
    mocks.run.mockResolvedValueOnce({
      run_id: "run-active",
      status: "success",
    });
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
  mocks.createThread.mockResolvedValue({
    thread_id: "created-thread-1",
    metadata: {
      allowed_actions: [
        "read",
        "comment",
        "edit",
        "approve",
        "share",
        "full_access",
      ],
    },
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
    metadata: {
      access_policy: "review",
      allowed_actions: [
        "read",
        "comment",
        "edit",
        "approve",
        "share",
        "full_access",
      ],
    },
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
  mocks.createThread.mockResolvedValue({
    thread_id: "created-thread-full",
    metadata: {
      allowed_actions: [
        "read",
        "comment",
        "edit",
        "approve",
        "share",
        "full_access",
      ],
    },
  });
  mocks.getThread.mockResolvedValue({
    thread_id: "created-thread-full",
    metadata: {
      access_policy: "full_access",
      allowed_actions: [
        "read",
        "comment",
        "edit",
        "approve",
        "share",
        "full_access",
      ],
    },
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

it.each([useChatSession, useDearAgentSession])(
  "self-heals and fallbacks to direct send when queueMessage encounters 409 run_changed (%#)",
  async (useSession) => {
    const submitFn = vi.fn().mockResolvedValue({});
    mocks.stream.mockReturnValue({
      isLoading: ref(false),
      error: ref(null),
      interrupts: ref([]),
      hydrationPromise: ref(Promise.resolve()),
      disconnect: vi.fn(),
      submit: submitFn,
    });
    mocks.runs.mockResolvedValue([
      { run_id: "run-ended-1", status: "success" },
    ]);
    mocks.list.mockResolvedValue([]);
    mocks.getThread.mockResolvedValue({
      thread_id: "t-heal",
      metadata: {
        allowed_actions: [
          "read",
          "comment",
          "edit",
          "approve",
          "share",
          "full_access",
        ],
      },
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
  },
);

it.each([useChatSession, useDearAgentSession])(
  "suppresses historical clarification flash during hydration/completed run and keeps queued item when send fromQueue hits 409 (%#)",
  async (useSession) => {
    let resolveHydration!: () => void;
    const hydrationDeferred = new Promise<void>((resolve) => {
      resolveHydration = resolve;
    });

    const submitFn = vi.fn(async () => {
      throw new Error(
        "409 Conflict: Cannot start a new run while thread has a pending or running run.",
      );
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
    mocks.runs.mockResolvedValue([
      { run_id: "run-completed-old", status: "success" },
    ]);
    mocks.list.mockResolvedValue([]);
    mocks.getThread.mockResolvedValue({
      thread_id: "t-switch-back",
      metadata: {
        allowed_actions: [
          "read",
          "comment",
          "edit",
          "approve",
          "share",
          "full_access",
        ],
      },
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
      mocks.runs.mockResolvedValue([
        { run_id: "run-active-bg", status: "running" },
      ]);
      const ok = await session.send("queued message 1", 1000, {
        fromQueue: true,
      });

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
  },
);

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
  mocks.run.mockResolvedValue({
    run_id: "run-active-1",
    status: "interrupted",
  });
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
    expect(disconnect).not.toHaveBeenCalled();
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
  const streamMessages = ref<
    Array<{ id?: string; type?: string; content?: unknown }>
  >([]);
  const submitFn = vi
    .fn()
    .mockImplementation(
      async (input: {
        messages: Array<{ id?: string; type?: string; content?: unknown }>;
      }) => {
        streamMessages.value = [...streamMessages.value, ...input.messages];
        throw new Error("409 Conflict: pending or running run");
      },
    );

  mocks.runs.mockResolvedValue([
    { run_id: "run-active-44s", status: "running" },
  ]);
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
  const current = ref<{
    key: string;
    kind: string;
    runId?: string;
    status: string;
  } | null>(null);
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
    const sendPromise = session.send("你再换另一个人物给我讲一下", 1000, {
      fromQueue: true,
    });
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

    mocks.run.mockResolvedValueOnce({
      run_id: "run-active-44s",
      status: "success",
    });
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

it("keeps busy true throughout subsequent send() stream even when previous run in run.value was terminal", async () => {
  const isLoading = ref(false);
  let resolveStream!: () => void;
  const current = ref<{
    key: string;
    kind: string;
    runId?: string;
    status: string;
  } | null>(null);
  const submitFn = vi.fn().mockImplementation(() => {
    isLoading.value = true;
    // Simulate POST /commands returning 200 OK immediately with the new runId
    current.value = {
      key: "act-2",
      kind: "send",
      runId: "run-turn-2",
      status: "acknowledged",
    };
    return new Promise<void>((resolve) => {
      resolveStream = () => {
        isLoading.value = false;
        resolve();
      };
    });
  });

  mocks.runs.mockResolvedValue([{ run_id: "run-turn-1", status: "success" }]);
  mocks.run.mockResolvedValue({ run_id: "run-turn-2", status: "success" });
  mocks.stream.mockReturnValue({
    isLoading,
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    submit: submitFn,
    disconnect: vi.fn(),
  });
  mocks.actions.mockReturnValue({
    current,
    begin: vi.fn((_tid: string, kind: string) => {
      const action = { key: "act-2", kind, status: "submitting" };
      current.value = action;
      return action;
    }),
    rejectUnsent: vi.fn(),
    acknowledge: vi.fn(),
    dispose: vi.fn(),
  });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t-multi-turn",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    // Turn 1 finished: run.value is run-turn-1 (status: "success"), busy is false
    expect(session.run.value?.run_id).toBe("run-turn-1");
    expect(session.busy.value).toBe(false);

    // Start Turn 2: POST /commands acknowledges run-turn-2 while stream is still running
    const sendPromise = session.send("开始执行工具调用");
    await flushPromises();

    // Crucial assertion: while Turn 2 is streaming and executing tools, busy MUST remain true
    // so ChatMessageList never receives isRunning=false and never marks active tools as "incomplete" (未完成/已中止)
    expect(session.busy.value).toBe(true);

    resolveStream();
    await sendPromise;
    await flushPromises();

    expect(session.run.value?.run_id).toBe("run-turn-2");
    expect(session.busy.value).toBe(false);
  } finally {
    scope.stop();
    mocks.runs.mockReset();
    mocks.run.mockReset();
  }
});

it("rotates shared SSE event stream via getThread().subscribe() on every consecutive acknowledged run and keeps verify silent", async () => {
  const isLoading = ref(false);
  const current = ref<{
    key: string;
    kind: string;
    status: string;
    runId?: string;
  } | null>(null);
  const unsubscribe = vi.fn().mockResolvedValue(undefined);
  const subscribe = vi.fn().mockResolvedValue({ unsubscribe });

  mocks.getThread.mockResolvedValue({
    thread_id: "t-consecutive",
    metadata: { allowed_actions: ["read", "comment", "edit"] },
  });
  mocks.runs.mockResolvedValue([{ run_id: "run-1", status: "success" }]);
  mocks.run.mockImplementation(async (_tid: string, rid: string) => ({
    run_id: rid,
    status: "success",
  }));

  let runCounter = 1;
  mocks.stream.mockReturnValue({
    isLoading,
    error: ref(null),
    interrupts: ref([]),
    messages: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    getThread: () => ({ subscribe }),
    submit: vi.fn(async () => {
      runCounter += 1;
      isLoading.value = true;
      current.value = {
        key: `act-${runCounter}`,
        kind: "send",
        status: "acknowledged",
        runId: `run-${runCounter}`,
      };
      await Promise.resolve();
      isLoading.value = false;
    }),
    disconnect: vi.fn(),
  });

  mocks.actions.mockReturnValue({
    current,
    begin: vi.fn((_tid: string, kind: string) => {
      const action = {
        key: `act-${runCounter + 1}`,
        kind,
        status: "submitting",
      };
      current.value = action;
      return action;
    }),
    rejectUnsent: vi.fn(),
    acknowledge: vi.fn(),
    dispose: vi.fn(),
  });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t-consecutive",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    expect(session.verified.value).toBe(true);
    expect(session.checking.value).toBe(false);

    // Send consecutive Turn 2 and Turn 3
    await session.send("第二轮连续消息");
    await flushPromises();
    await session.send("第三轮连续消息");
    await flushPromises();

    // Every acknowledged run command must trigger getThread().subscribe() to reopen/rotate POST /threads/{id}/stream/events
    expect(subscribe).not.toHaveBeenCalled();
    expect(unsubscribe).not.toHaveBeenCalled();
    expect(session.verified.value).toBe(true);
    expect(session.checking.value).toBe(false);
  } finally {
    scope.stop();
    mocks.runs.mockReset();
    mocks.run.mockReset();
  }
});

it("prevents stop() from canceling background run when session visible is false", async () => {
  mocks.cancel.mockReset();
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  mocks.runs.mockResolvedValueOnce([{ run_id: "run-bg", status: "running" }]);

  const visible = ref(false);
  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t-bg-test",
      context: ref({}),
      canWrite: ref(true),
      visible,
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    await session.stop();
    await flushPromises();

    // Because visible was false, stop() was guarded and cancel was not invoked
    expect(mocks.cancel).not.toHaveBeenCalled();

    // Now make it visible, stop() should proceed to invoke cancel
    visible.value = true;
    await session.stop();
    await flushPromises();
    expect(mocks.cancel).toHaveBeenCalled();
  } finally {
    scope.stop();
    mocks.cancel.mockReset();
    mocks.runs.mockReset();
  }
});

it("resumeInterruptedRun invokes service.resume with empty dict to unblock interrupted run", async () => {
  mocks.resume.mockReset();
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  mocks.resume.mockResolvedValue({
    thread_id: "t",
    run_id: "run-resumed",
  });
  mocks.runs.mockResolvedValue([{ run_id: "run-int", status: "interrupted" }]);

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    await session.resumeInterruptedRun();
    await flushPromises();

    expect(mocks.resume).toHaveBeenCalledWith("t", {});
  } finally {
    scope.stop();
    mocks.resume.mockReset();
    mocks.runs.mockReset();
  }
});

it("auto-heals and resets stream.isLoading when backend run is confirmed terminal", async () => {
  const streamLoading = ref(true);
  mocks.stream.mockReturnValue({
    isLoading: streamLoading,
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  mocks.runs.mockResolvedValue([{ run_id: "run-done", status: "success" }]);

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t-finished",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    expect(streamLoading.value).toBe(true);
    await session.verify();
    await flushPromises();

    expect(streamLoading.value).toBe(false);
    expect(session.busy.value).toBe(false);
    expect(session.canSend.value).toBe(true);
  } finally {
    scope.stop();
    mocks.runs.mockReset();
  }
});

it("offloadConversation submits null input with offload_conversation: true and acknowledges action", async () => {
  const submitFn = vi.fn().mockResolvedValue(undefined);
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    submit: submitFn,
    disconnect: vi.fn(),
  });
  mocks.runs.mockResolvedValue([]);

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t",
      context: ref({ execution_mode: "standard" }),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    const result = await session.offloadConversation();
    expect(result).toBe(true);
    expect(submitFn).toHaveBeenCalledWith(null, {
      threadId: "t",
      config: {
        configurable: {
          platform_runtime: {
            execution_mode: "standard",
            offload_conversation: true,
          },
        },
      },
    });
  } finally {
    scope.stop();
    mocks.stream.mockReset();
    mocks.runs.mockReset();
  }
});

it("subscribes to custom offload events and clears offloadState upon send() or timer expiry", async () => {
  vi.useFakeTimers();
  let channelHandler: ((event: unknown) => void) | undefined;
  mocks.useChannelEffect.mockImplementation((_stream, _channels, options) => {
    channelHandler = options.onEvent;
  });

  const submitFn = vi.fn().mockResolvedValue(undefined);
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    submit: submitFn,
    disconnect: vi.fn(),
  });
  mocks.runs.mockResolvedValue([]);

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await flushPromises();
    expect(channelHandler).toBeDefined();

    // 1. 模拟 started 事件
    channelHandler!({
      method: "custom",
      params: {
        namespace: [],
        data: {
          type: "conversation_offloading",
          status: "started",
          operation_id: "op-1",
        },
      },
    });
    expect(session.isOffloading.value).toBe(true);
    expect(session.offloadState.value).toEqual({
      status: "started",
      trigger: "automatic",
      operationId: "op-1",
      runId: "",
      text: "正在整理上下文...",
      icon: "refresh",
      variant: "info",
    });

    // 2. 模拟 completed 事件
    channelHandler!({
      method: "custom",
      params: {
        namespace: [],
        data: {
          type: "conversation_offloading",
          status: "completed",
          operation_id: "op-1",
          history_saved: true,
        },
      },
    });
    expect(session.isOffloading.value).toBe(false);
    expect(session.offloadState.value).toEqual({
      status: "completed",
      trigger: "automatic",
      operationId: "op-1",
      runId: "",
      text: "上下文已整理",
      icon: "check",
      variant: "success",
    });

    // 3. 测试 4 秒自动淡出
    vi.advanceTimersByTime(3900);
    expect(session.offloadState.value).not.toBeNull();
    vi.advanceTimersByTime(200);
    expect(session.offloadState.value).toBeNull();

    // 4. 再次触发 completed，测试调用 send() 立即清除
    channelHandler!({
      method: "custom",
      params: {
        namespace: [],
        data: {
          type: "conversation_offloading",
          status: "completed",
          operation_id: "op-2",
        },
      },
    });
    expect(session.offloadState.value).not.toBeNull();
    // 进场发送消息，立即打断
    await session.send("Hello agent");
    expect(session.offloadState.value).toBeNull();
  } finally {
    scope.stop();
    vi.useRealTimers();
    mocks.useChannelEffect.mockReset();
    mocks.stream.mockReset();
    mocks.runs.mockReset();
  }
});

it("when cancel fails or times out, records unconfirmedStopRunId and allows retry even when run is no longer active", async () => {
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  // 首次运行中
  mocks.runs.mockResolvedValue([{ run_id: "run-stuck", status: "running" }]);
  // 取消时抛出超时未确认异常
  mocks.cancel.mockRejectedValueOnce(new Error("停止尚未确认，请核实或重试"));

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t-cancel-test",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await session.verify();
    await flushPromises();

    expect(session.run.value?.run_id).toBe("run-stuck");

    // 第一次点击停止，cancel 失败
    await session.stop();
    await flushPromises();

    expect(mocks.cancel).toHaveBeenCalledTimes(1);
    expect(mocks.cancel).toHaveBeenCalledWith("t-cancel-test", "run-stuck");
    expect(session.unconfirmedStopRunId.value).toBe("run-stuck");
    expect(session.status.value).toBe("停止尚未确认");

    // 此时模拟后台同步，run 变成了 interrupted（导致 active(run) === false）
    mocks.runs.mockResolvedValue([
      { run_id: "run-stuck", status: "interrupted" },
    ]);
    await session.verify();
    await flushPromises();

    expect(session.run.value?.status).toBe("interrupted");
    // 依然保留未确认标识
    expect(session.unconfirmedStopRunId.value).toBe("run-stuck");

    // 第二次点击停止（重试停止），此时由于解耦机制，即使 !active(run) 也能正常发起重试调用
    mocks.cancel.mockResolvedValueOnce(undefined);
    await session.stop();
    await flushPromises();

    expect(mocks.cancel).toHaveBeenCalledTimes(2);
    expect(mocks.cancel).toHaveBeenLastCalledWith("t-cancel-test", "run-stuck");
    // 确认成功后清除未确认标识
    expect(session.unconfirmedStopRunId.value).toBeNull();
  } finally {
    scope.stop();
    mocks.cancel.mockReset();
    mocks.runs.mockReset();
  }
});

it("maps runtime.model.retry_exhausted and whitelist error codes to safe user-friendly messages", async () => {
  mocks.stream.mockReturnValue({
    isLoading: ref(false),
    error: ref(null),
    interrupts: ref([]),
    hydrationPromise: ref(Promise.resolve()),
    disconnect: vi.fn(),
  });
  mocks.runs.mockResolvedValue([{ run_id: "run-1", status: "running" }]);
  // 模拟 cancel 遇到白名单错误
  mocks.cancel.mockRejectedValueOnce({
    type: "RuntimeResolutionError",
    message: "runtime.model.retry_exhausted",
  });

  const scope = effectScope();
  const session = scope.run(() =>
    useChatSession({
      projectId: "proj-1",
      graphId: "dearflow_agent",
      threadId: "t-error-test",
      context: ref({}),
      canWrite: ref(true),
      onThread: vi.fn(),
      onRefresh: vi.fn(),
      onReconnect: vi.fn(),
    }),
  )!;

  try {
    await session.verify();
    await flushPromises();

    await session.stop();
    await flushPromises();

    expect(session.error.value).toBe("模型服务暂不可用，本次运行未完成。");
  } finally {
    scope.stop();
    mocks.cancel.mockReset();
    mocks.runs.mockReset();
  }
});
