import { computed, onScopeDispose, ref, watch, type Ref } from "vue";
import type { AgentContext } from "@/services/agents/types";
import type {
  createSessionService,
  QueuedRun,
} from "@/services/threads/session.service";
import type { QueuedPromptItem } from "./usePromptQueue";

type Service = ReturnType<typeof createSessionService>;

export type PendingPromptSubmission = {
  id: string;
  key: string;
  body: unknown;
  content: unknown;
  threadId?: string;
  storageKey?: string;
  createdAt?: number;
  status?: "submitting" | "unconfirmed";
};

function items(rows: QueuedRun[]): QueuedPromptItem[] {
  return rows
    .filter((run) => !run.kwargs?.command)
    .sort((a, b) => (a.queue_position ?? 0) - (b.queue_position ?? 0))
    .map((run) => ({
      id: run.run_id,
      content: run.kwargs?.input?.messages?.[0]?.content,
      createdAt: Date.parse(run.created_at),
    }));
}

export function useServerPromptQueue(options: {
  threadId: Ref<string | null>;
  service: Service;
  graphId: string;
  context: Ref<AgentContext>;
  recursionLimit: Ref<number>;
  storageKey: Ref<string>;
}) {
  const queue = ref<QueuedPromptItem[]>([]);
  const pending = ref<PendingPromptSubmission | null>(null);
  const submitting = ref(false);
  const unconfirmed = computed(() =>
    Boolean(pending.value && pending.value.status === "unconfirmed"),
  );
  const error = ref("");
  let disposed = false;
  let epoch = 0;

  function clearPending(item?: PendingPromptSubmission | null) {
    const target = item || pending.value;
    if (pending.value && (!item || pending.value.id === item.id)) {
      pending.value = null;
    }
    try {
      if (options.storageKey.value) {
        localStorage.removeItem(options.storageKey.value);
      }
      if (target?.storageKey) {
        localStorage.removeItem(target.storageKey);
      }
    } catch {
      /* Storage may be disabled. */
    }
  }

  function remember(value: PendingPromptSubmission | null) {
    if (!value) {
      clearPending();
      return;
    }
    pending.value = value;
    try {
      const key = value.storageKey || options.storageKey.value;
      if (key) {
        localStorage.setItem(key, JSON.stringify(value));
      }
    } catch {
      /* Storage may be disabled. */
    }
  }

  async function refresh() {
    const threadId = options.threadId.value;
    if (!threadId) return;
    const generation = ++epoch;
    try {
      const rows = await options.service.queuedRuns(threadId);
      if (
        disposed ||
        generation !== epoch ||
        options.threadId.value !== threadId
      )
        return;
      queue.value = items(rows);

      if (pending.value) {
        const pendingItem = pending.value;
        const pendingId = pendingItem.id;
        // 场景 1: 排队队列中已确认存在该 client_queue_id
        if (rows.some((run) => run.metadata?.client_queue_id === pendingId)) {
          clearPending(pendingItem);
        } else if (typeof options.service.runs === "function") {
          // 场景 2: 排队队列中未找到，检查最近已执行/执行中的运行记录
          try {
            const recentRuns = await options.service.runs(threadId);
            if (
              !disposed &&
              generation === epoch &&
              options.threadId.value === threadId &&
              recentRuns.some(
                (run) => run.metadata?.client_queue_id === pendingId,
              )
            ) {
              clearPending(pendingItem);
            }
          } catch {
            /* Ignore optional run detection errors. */
          }
        }
      }
      error.value = "";
    } catch (cause) {
      if (!disposed)
        error.value = cause instanceof Error ? cause.message : String(cause);
    }
  }

  async function dispatch(value: PendingPromptSubmission) {
    const targetThreadId = value.threadId || options.threadId.value;
    if (!targetThreadId) throw new Error("请先创建会话");
    submitting.value = true;
    try {
      const run = await options.service.enqueueRun(
        targetThreadId,
        value.body,
        value.key,
      );
      if (!run.run_id) throw new Error("服务端未确认运行 ID");
      clearPending(value);
      await refresh();
      return true;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause);
      const status = (cause as { status?: number })?.status;
      if (status && status >= 400 && status < 500) {
        clearPending(value);
        return false;
      }
      // 非 4xx（网络中断、超时、500/504 等未决状态）：将状态转为 unconfirmed！
      value.status = "unconfirmed";
      remember(value);
      return false;
    } finally {
      submitting.value = false;
    }
  }

  async function enqueue(content: unknown) {
    const currentThreadId = options.threadId.value;
    if (!currentThreadId) throw new Error("请先创建会话");
    if (unconfirmed.value) {
      throw new Error("上一条消息排队结果待确认，请先核实或恢复草稿");
    }

    // 若有上一个请求正在提交中（用户快速连击），平滑等待最多 3 秒
    if (submitting.value) {
      let waited = 0;
      while (submitting.value && waited < 3000) {
        await new Promise((resolve) => setTimeout(resolve, 50));
        waited += 50;
      }
      if (unconfirmed.value) {
        throw new Error("上一条消息排队结果待确认，请先核实或恢复草稿");
      }
    }

    const id = crypto.randomUUID();
    const body = {
      assistant_id: options.graphId,
      input: { messages: [{ id, type: "human", content }] },
      config: {
        recursion_limit: options.recursionLimit.value,
        configurable: { platform_runtime: { ...options.context.value } },
      },
      multitask_strategy: "enqueue",
      metadata: { client_queue_id: id },
    };
    const value: PendingPromptSubmission = {
      id,
      key: `run:${id}`,
      body,
      content,
      threadId: currentThreadId,
      storageKey: options.storageKey.value,
      createdAt: Date.now(),
      status: "submitting",
    };
    remember(value);
    return dispatch(value);
  }

  function dismiss(): PendingPromptSubmission | null {
    const current = pending.value;
    if (current) {
      clearPending(current);
    }
    return current;
  }

  async function operate(operation: "cancel" | "reorder", runIds: string[]) {
    const threadId = options.threadId.value;
    if (!threadId) return false;
    try {
      const expected = queue.value.map((item) => item.id);
      const rows = await options.service.manageQueue(
        threadId,
        operation,
        expected,
        runIds,
      );
      queue.value = items(rows);
      error.value = "";
      return true;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause);
      await refresh();
      return false;
    }
  }

  const remove = (id: string) => operate("cancel", [id]);
  const clear = () =>
    operate(
      "cancel",
      queue.value.map((item) => item.id),
    );
  const moveUp = (index: number) => {
    const ids = queue.value.map((item) => item.id);
    if (index <= 0 || index >= ids.length) return Promise.resolve(false);
    [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
    return operate("reorder", ids);
  };
  const moveDown = (index: number) => moveUp(index + 1);

  watch(
    options.threadId,
    (newThreadId) => {
      queue.value = [];
      pending.value = null;
      if (!newThreadId) return;

      try {
        const raw = localStorage.getItem(options.storageKey.value);
        if (raw) {
          const item = JSON.parse(raw) as PendingPromptSubmission;
          const isMatchingThread =
            !item.threadId || item.threadId === newThreadId;
          const isNotStale =
            !item.createdAt || Date.now() - item.createdAt < 30 * 60 * 1000;
          if (isMatchingThread && isNotStale) {
            // 切回读取到的遗留记录，直接标记为 unconfirmed
            item.status = "unconfirmed";
            pending.value = item;
          } else {
            localStorage.removeItem(options.storageKey.value);
            if (
              item.storageKey &&
              item.storageKey !== options.storageKey.value
            ) {
              localStorage.removeItem(item.storageKey);
            }
          }
        }
      } catch {
        /* Storage may be disabled. */
      }
      void refresh();
    },
    { immediate: true },
  );

  let timer: ReturnType<typeof setInterval> | null = null;
  if (typeof window !== "undefined") {
    timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 2000);
  }

  try {
    onScopeDispose(() => {
      disposed = true;
      if (timer) clearInterval(timer);
    });
  } catch {
    /* Safe fallback when outside effect scope. */
  }

  return {
    queue,
    pending,
    unconfirmed,
    submitting,
    error,
    enqueue,
    refresh,
    retry: () =>
      pending.value ? dispatch(pending.value) : Promise.resolve(false),
    dismiss,
    remove,
    clear,
    moveUp,
    moveDown,
  };
}
