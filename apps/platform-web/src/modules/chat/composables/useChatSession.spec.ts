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
}));
vi.mock("@langchain/vue", () => ({ useStream: mocks.stream }));
vi.mock("@/services/threads/messages.service", () => ({
  enqueueThreadMessage: mocks.enqueue,
  listThreadMessages: mocks.list,
}));
vi.mock("@/services/threads/session.service", () => ({
  createSessionService: () => ({
    client: {},
    runs: mocks.runs.getMockImplementation()
      ? mocks.runs
      : async () => [{ run_id: "run", status: "running" }],
    run: mocks.run,
  }),
}));
vi.mock("@/services/langgraph/client", () => ({
  createLanggraphAuthorizedFetch: () => vi.fn(),
  getLanggraphApiUrl: () => "",
}));
vi.mock("../run-actions", () => ({
  createRunActions: () => mocks.actions() ?? ({ current: ref(null), dispose: vi.fn() }),
}));
import { useChatSession } from "./useChatSession";
afterEach(() => { vi.restoreAllMocks(); mocks.actions.mockReset(); sessionStorage.clear(); });
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

