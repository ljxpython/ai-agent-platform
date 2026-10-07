import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import type { AgentContext } from "@/services/agents/types";
import { useServerPromptQueue } from "./useServerPromptQueue";

function createMockService() {
  return {
    queuedRuns: vi.fn().mockResolvedValue([]),
    runs: vi.fn().mockResolvedValue([]),
    enqueueRun: vi.fn().mockResolvedValue({ run_id: "run-1" }),
    manageQueue: vi.fn().mockResolvedValue([]),
  };
}

describe("useServerPromptQueue", () => {
  const defaultContext = ref<AgentContext>({
    model_id: "test-model",
    mode: "chat",
  });
  const recursionLimit = ref(25);

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("enqueues message without flashing unconfirmed status during normal in-flight submission", async () => {
    const threadId = ref<string | null>("thread-1");
    const storageKey = ref("queue:user1:proj1:thread-1");
    const service = createMockService();

    let resolveEnqueue: ((val: { run_id: string }) => void) | undefined;
    service.enqueueRun.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveEnqueue = resolve;
        }),
    );

    const { pending, submitting, unconfirmed, enqueue } = useServerPromptQueue({
      threadId,
      service: service as unknown as Parameters<
        typeof useServerPromptQueue
      >[0]["service"],
      graphId: "graph-1",
      context: defaultContext,
      recursionLimit,
      storageKey,
    });

    const enqueuePromise = enqueue("你好呀");
    await nextTick();

    // 关键断言：正在提交中，但绝不是 unconfirmed（绝不能弹黄色待确认警告横幅！）
    expect(pending.value).not.toBeNull();
    expect(submitting.value).toBe(true);
    expect(unconfirmed.value).toBe(false);

    expect(pending.value?.content).toBe("你好呀");
    expect(pending.value?.threadId).toBe("thread-1");
    expect(pending.value?.storageKey).toBe("queue:user1:proj1:thread-1");
    expect(pending.value?.createdAt).toBeTypeOf("number");

    // 服务端响应成功
    resolveEnqueue!({ run_id: "run-1" });
    const success = await enqueuePromise;
    expect(success).toBe(true);
    expect(submitting.value).toBe(false);
    expect(unconfirmed.value).toBe(false);
    expect(pending.value).toBeNull();
    expect(localStorage.getItem("queue:user1:proj1:thread-1")).toBeNull();
  });

  it("enters unconfirmed status only when network fails with unknown error", async () => {
    const threadId = ref<string | null>("thread-1");
    const storageKey = ref("queue:user1:proj1:thread-1");
    const service = createMockService();

    service.enqueueRun.mockRejectedValue(
      new Error("网络中断 / Gateway Timeout"),
    );

    const { pending, submitting, unconfirmed, enqueue } = useServerPromptQueue({
      threadId,
      service: service as unknown as Parameters<
        typeof useServerPromptQueue
      >[0]["service"],
      graphId: "graph-1",
      context: defaultContext,
      recursionLimit,
      storageKey,
    });

    const success = await enqueue("失败消息");
    expect(success).toBe(false);

    // 只有在此刻失败后，才真正进入 unconfirmed 待确认警告状态！
    expect(submitting.value).toBe(false);
    expect(unconfirmed.value).toBe(true);
    expect(pending.value?.status).toBe("unconfirmed");
    expect(localStorage.getItem(storageKey.value)).not.toBeNull();
  });

  it("accurately cleans up the original thread's storageKey even if threadId changes before completion", async () => {
    const threadId = ref<string | null>("thread-1");
    const storageKey = ref("queue:user1:proj1:thread-1");
    const service = createMockService();

    let resolveEnqueue: ((val: { run_id: string }) => void) | undefined;
    service.enqueueRun.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveEnqueue = resolve;
        }),
    );

    const queue1 = useServerPromptQueue({
      threadId,
      service: service as unknown as Parameters<
        typeof useServerPromptQueue
      >[0]["service"],
      graphId: "graph-1",
      context: defaultContext,
      recursionLimit,
      storageKey,
    });

    const enqueuePromise = queue1.enqueue("异步消息");
    await nextTick();

    // 此时 thread-1 的 key 已存入 localStorage
    expect(localStorage.getItem("queue:user1:proj1:thread-1")).not.toBeNull();

    // 用户切换会话到 thread-2
    threadId.value = "thread-2";
    storageKey.value = "queue:user1:proj1:thread-2";
    await nextTick();

    // 此时原请求才姗姗来迟完成
    resolveEnqueue!({ run_id: "run-delayed" });
    await enqueuePromise;

    // 核心验证：thread-1 的 key 必须被精确清除，不能残留为幽灵锁！
    expect(localStorage.getItem("queue:user1:proj1:thread-1")).toBeNull();
  });

  it("auto-heals pending lock when run appears in queuedRuns", async () => {
    const threadId = ref<string | null>("thread-1");
    const storageKey = ref("queue:user1:proj1:thread-1");
    const service = createMockService();

    const testPendingId = "client-uuid-123";
    localStorage.setItem(
      storageKey.value,
      JSON.stringify({
        id: testPendingId,
        key: `run:${testPendingId}`,
        body: {},
        content: "待确认消息",
        threadId: "thread-1",
        storageKey: storageKey.value,
        createdAt: Date.now(),
        status: "unconfirmed",
      }),
    );

    service.queuedRuns.mockResolvedValue([
      {
        run_id: "server-run-1",
        status: "pending",
        metadata: { client_queue_id: testPendingId },
        kwargs: { input: { messages: [{ content: "待确认消息" }] } },
      },
    ]);

    const { pending, unconfirmed, refresh } = useServerPromptQueue({
      threadId,
      service: service as unknown as Parameters<
        typeof useServerPromptQueue
      >[0]["service"],
      graphId: "graph-1",
      context: defaultContext,
      recursionLimit,
      storageKey,
    });

    await refresh();

    // 应该自愈清除
    expect(pending.value).toBeNull();
    expect(unconfirmed.value).toBe(false);
    expect(localStorage.getItem(storageKey.value)).toBeNull();
  });

  it("auto-heals pending lock when run is not in queuedRuns but found in historical runs", async () => {
    const threadId = ref<string | null>("thread-1");
    const storageKey = ref("queue:user1:proj1:thread-1");
    const service = createMockService();

    const testPendingId = "client-uuid-456";
    localStorage.setItem(
      storageKey.value,
      JSON.stringify({
        id: testPendingId,
        key: `run:${testPendingId}`,
        body: {},
        content: "已执行消息",
        threadId: "thread-1",
        storageKey: storageKey.value,
        createdAt: Date.now(),
        status: "unconfirmed",
      }),
    );

    service.queuedRuns.mockResolvedValue([]);
    service.runs.mockResolvedValue([
      {
        run_id: "server-run-2",
        status: "success",
        metadata: { client_queue_id: testPendingId },
      },
    ]);

    const { pending, unconfirmed, refresh } = useServerPromptQueue({
      threadId,
      service: service as unknown as Parameters<
        typeof useServerPromptQueue
      >[0]["service"],
      graphId: "graph-1",
      context: defaultContext,
      recursionLimit,
      storageKey,
    });

    await nextTick();
    expect(unconfirmed.value).toBe(true);

    await refresh();

    // 应该识别到该任务已在服务端落地执行，自愈清除 pending
    expect(pending.value).toBeNull();
    expect(unconfirmed.value).toBe(false);
    expect(localStorage.getItem(storageKey.value)).toBeNull();
  });

  it("dismisses pending lock immediately and returns discarded content", async () => {
    const threadId = ref<string | null>("thread-1");
    const storageKey = ref("queue:user1:proj1:thread-1");
    const service = createMockService();

    localStorage.setItem(
      storageKey.value,
      JSON.stringify({
        id: "discard-id",
        key: "run:discard-id",
        body: {},
        content: "用户想丢弃的草稿",
        threadId: "thread-1",
        storageKey: storageKey.value,
        createdAt: Date.now(),
        status: "unconfirmed",
      }),
    );

    const { pending, unconfirmed, dismiss } = useServerPromptQueue({
      threadId,
      service: service as unknown as Parameters<
        typeof useServerPromptQueue
      >[0]["service"],
      graphId: "graph-1",
      context: defaultContext,
      recursionLimit,
      storageKey,
    });

    await nextTick();
    expect(pending.value).not.toBeNull();
    expect(unconfirmed.value).toBe(true);

    const dismissed = dismiss();
    expect(dismissed).not.toBeNull();
    expect(dismissed?.content).toBe("用户想丢弃的草稿");
    expect(pending.value).toBeNull();
    expect(unconfirmed.value).toBe(false);
    expect(localStorage.getItem(storageKey.value)).toBeNull();
  });

  it("automatically discards stale pending records older than 30 minutes on mount", async () => {
    const threadId = ref<string | null>("thread-1");
    const storageKey = ref("queue:user1:proj1:thread-1");
    const service = createMockService();

    // 40 分钟前的远古记录
    localStorage.setItem(
      storageKey.value,
      JSON.stringify({
        id: "stale-id",
        key: "run:stale-id",
        body: {},
        content: "远古死锁",
        threadId: "thread-1",
        storageKey: storageKey.value,
        createdAt: Date.now() - 40 * 60 * 1000,
        status: "unconfirmed",
      }),
    );

    const { pending, unconfirmed } = useServerPromptQueue({
      threadId,
      service: service as unknown as Parameters<
        typeof useServerPromptQueue
      >[0]["service"],
      graphId: "graph-1",
      context: defaultContext,
      recursionLimit,
      storageKey,
    });

    await nextTick();
    // 应该被直接判定为过期垃圾，不挂载给用户
    expect(pending.value).toBeNull();
    expect(unconfirmed.value).toBe(false);
    expect(localStorage.getItem(storageKey.value)).toBeNull();
  });
});
