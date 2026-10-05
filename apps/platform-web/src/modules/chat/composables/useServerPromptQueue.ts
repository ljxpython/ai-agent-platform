import { onScopeDispose, ref, watch, type Ref } from "vue";
import type { AgentContext } from "@/services/agents/types";
import type {
  createSessionService,
  QueuedRun,
} from "@/services/threads/session.service";
import type { QueuedPromptItem } from "./usePromptQueue";

type Service = ReturnType<typeof createSessionService>;
type Pending = { id: string; key: string; body: unknown; content: unknown };

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
  const pending = ref<Pending | null>(null);
  const error = ref("");
  let disposed = false;
  let epoch = 0;

  function remember(value: Pending | null) {
    pending.value = value;
    try {
      if (value)
        localStorage.setItem(options.storageKey.value, JSON.stringify(value));
      else localStorage.removeItem(options.storageKey.value);
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
      if (
        pending.value &&
        rows.some((run) => run.metadata?.client_queue_id === pending.value?.id)
      ) {
        remember(null);
      }
      error.value = "";
    } catch (cause) {
      if (!disposed)
        error.value = cause instanceof Error ? cause.message : String(cause);
    }
  }

  async function dispatch(value: Pending) {
    const threadId = options.threadId.value;
    if (!threadId) throw new Error("请先创建会话");
    try {
      const run = await options.service.enqueueRun(
        threadId,
        value.body,
        value.key,
      );
      if (!run.run_id) throw new Error("服务端未确认运行 ID");
      remember(null);
      await refresh();
      return true;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : String(cause);
      const status = (cause as { status?: number })?.status;
      if (status && status >= 400 && status < 500) {
        remember(null);
        return false;
      }
      return false;
    }
  }

  async function enqueue(content: unknown) {
    if (!options.threadId.value) throw new Error("请先创建会话");
    if (pending.value) throw new Error("请先确认上一条消息的提交结果");
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
    const value = { id, key: `run:${id}`, body, content };
    remember(value);
    return dispatch(value);
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
    () => {
      queue.value = [];
      pending.value = null;
      try {
        const raw = localStorage.getItem(options.storageKey.value);
        if (raw) pending.value = JSON.parse(raw) as Pending;
      } catch {
        /* Storage may be disabled. */
      }
      void refresh();
    },
    { immediate: true },
  );
  const timer = setInterval(() => {
    if (!document.hidden) void refresh();
  }, 2000);
  onScopeDispose(() => {
    disposed = true;
    clearInterval(timer);
  });
  return {
    queue,
    pending,
    error,
    enqueue,
    refresh,
    retry: () =>
      pending.value ? dispatch(pending.value) : Promise.resolve(false),
    remove,
    clear,
    moveUp,
    moveDown,
  };
}
