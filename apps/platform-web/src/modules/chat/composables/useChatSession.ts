import {
  computed,
  onScopeDispose,
  ref,
  shallowRef,
  watch,
  type Ref,
} from "vue";
import { isAxiosError } from "axios";
import { useStream } from "@langchain/vue";
import type { Checkpoint, Run } from "@langchain/langgraph-sdk";
import {
  createLanggraphAuthorizedFetch,
  getLanggraphApiUrl,
} from "@/services/langgraph/client";
import {
  createSessionService,
  type ChatState,
} from "@/services/threads/session.service";
import type { AgentContext } from "@/services/agents/types";
import { parseAgentContext } from "@/services/agents/context";
import {
  enqueueThreadMessage,
  listThreadMessages,
  type MessageReceipt,
} from "@/services/threads/messages.service";
import { createRunActions } from "../run-actions";
import {
  buildReviewResponses,
  parseReviews,
  type ReviewDraft,
} from "../approvals";

const active = (run: Run | null) =>
  run != null && ["pending", "running"].includes(run.status);

export function useChatSession(options: {
  projectId: string;
  userId?: string;
  graphId: string;
  agentId?: string;
  threadId?: string;
  context: Ref<AgentContext>;
  canWrite: Ref<boolean>;
  onThread: (id: string) => void;
  onRefresh: () => void;
  onReconnect: () => void;
  onAccepted?: () => void;
}) {
  const actions = createRunActions(
    options.projectId,
    createLanggraphAuthorizedFetch(),
  );
  const service = createSessionService(actions.fetch);
  const threadId = ref(options.threadId ?? null);
  watch(
    () => options.threadId,
    (next) => {
      if (next && next !== threadId.value) {
        threadId.value = next;
      }
    },
  );
  const run = shallowRef<Run | null>(null);
  const checking = ref(true);
  const verified = ref(false);
  const cancelling = ref(false);
  const error = ref("");
  let disposed = false;
  let checkEpoch = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let releaseWait: (() => void) | undefined;
  const stream = useStream<ChatState>({
    assistantId: options.graphId,
    threadId: computed(() => threadId.value),
    client: service.client,
    fetch: actions.fetch,
    onCompleted: () => {
      if (!disposed) void verify(true);
    },
  });
  const reviews = computed(() => parseReviews(stream.interrupts.value));
  const pendingAction = computed(() =>
    ["submitting", "unknown"].includes(actions.current.value?.status ?? ""),
  );
  const busy = computed(() => stream.isLoading.value || active(run.value));
  const canSend = computed(
    () =>
      options.canWrite.value &&
      verified.value &&
      !stream.error.value &&
      !checking.value &&
      !cancelling.value &&
      !pendingAction.value &&
      !pendingMessage.value &&
      !busy.value &&
      !reviews.value.length,
  );
  const status = computed(() =>
    cancelling.value
      ? "正在停止"
      : reviews.value.length
        ? "等待审批"
        : actions.current.value?.status === "unknown"
          ? "提交结果待确认"
          : checking.value
            ? "正在核实会话"
            : actions.current.value?.status === "submitting"
              ? "正在发送"
              : busy.value
                ? "正在执行"
                : error.value || stream.error.value
                  ? "连接或执行异常"
                  : "可以发送",
  );

  function fail(cause: unknown) {
    if (!disposed)
      error.value = cause instanceof Error ? cause.message : "请求失败，请重试";
  }
  let activeVerifyPromise: Promise<boolean> | undefined;
  let activeVerifyTerminal = false;
  async function verify(waitForTerminal = false): Promise<boolean> {
    if (disposed) return false;
    if (activeVerifyPromise && (!waitForTerminal || activeVerifyTerminal)) {
      return activeVerifyPromise;
    }
    const epoch = ++checkEpoch;
    clearTimeout(timer);
    releaseWait?.();
    releaseWait = undefined;
    if (!threadId.value) {
      checking.value = false;
      verified.value = true;
      return true;
    }
    verified.value = false;
    checking.value = true;
    activeVerifyTerminal = waitForTerminal;
    const id = threadId.value;
    const deadline = Date.now() + 30000;
    const p = (async () => {
      try {
        let attempt = 0;
        do {
          const knownId = waitForTerminal
            ? (actions.current.value?.runId ?? run.value?.run_id)
            : undefined;
          const latest = knownId
            ? await service.run(id, knownId)
            : ((await service.runs(id))[0] ?? null);
          if (disposed || epoch !== checkEpoch) return false;
          run.value = latest;
          if (!active(latest) || !waitForTerminal) break;
          if (document.hidden || Date.now() >= deadline)
            throw new Error("运行结果尚未确认，请恢复连接后核实");
          await new Promise<void>((resolve) => {
            releaseWait = resolve;
            timer = setTimeout(resolve, Math.min(500 * 2 ** attempt++, 4000));
          });
        } while (!disposed && epoch === checkEpoch);
        if (!disposed && epoch === checkEpoch) {
          verified.value = true;
          error.value = "";
          options.onRefresh();
          return true;
        }
        return false;
      } catch (cause) {
        if (epoch === checkEpoch) fail(cause);
        return false;
      } finally {
        if (!disposed && epoch === checkEpoch) checking.value = false;
        activeVerifyPromise = undefined;
        activeVerifyTerminal = false;
      }
    })();
    activeVerifyPromise = p;
    return p;
  }

  const supportsQueue = ["reference_agent", "showcase_demo"].includes(
    options.graphId,
  );
  const receipts = ref<MessageReceipt[]>([]);
  const pendingMessage = ref<{
    payload: {
      client_message_id: string;
      target_run_id: string;
      content: unknown;
    };
    key: string;
    status: "sending" | "unknown" | "rejected";
  } | null>(null);
  const pendingStorageKey = computed(() =>
    options.userId && threadId.value
      ? `pw:queued-message:${options.userId}:${options.projectId}:${threadId.value}`
      : null,
  );
  if (pendingStorageKey.value) {
    try {
      const saved = JSON.parse(
        sessionStorage.getItem(pendingStorageKey.value) ?? "null",
      );
      if (
        saved?.payload?.client_message_id &&
        saved?.payload?.target_run_id &&
        saved?.key
      )
        pendingMessage.value = { ...saved, status: "unknown" };
    } catch {
      /* In-memory retry remains available when browser storage is disabled. */
    }
  }
  watch(
    pendingMessage,
    (pending) => {
      if (!pendingStorageKey.value) return;
      try {
        if (pending)
          sessionStorage.setItem(
            pendingStorageKey.value,
            JSON.stringify(pending),
          );
        else sessionStorage.removeItem(pendingStorageKey.value);
      } catch {
        /* Do not turn a storage failure into a second network submission. */
      }
    },
    { deep: true, flush: "sync" },
  );
  const receiptError = ref("");
  let receiptTimer: ReturnType<typeof setTimeout> | undefined;
  let receiptController: AbortController | undefined;
  let receiptDeadline = 0;
  async function refreshReceipts(restart = true) {
    clearTimeout(receiptTimer);
    if (!supportsQueue || disposed || document.hidden || !threadId.value)
      return;
    if (restart) receiptDeadline = Date.now() + 30000;
    receiptController?.abort();
    const controller = new AbortController();
    receiptController = controller;
    try {
      const rows = await listThreadMessages(
        options.projectId,
        threadId.value,
        controller.signal,
      );
      if (disposed || controller !== receiptController) return;
      receipts.value = rows;
      receiptError.value = "";
      const pending = pendingMessage.value;
      if (
        pending &&
        rows.some((row) => row.message_id === pending.payload.client_message_id)
      ) {
        pendingMessage.value = null;
        options.onAccepted?.();
      }
    } catch {
      if (!disposed && !controller.signal.aborted)
        receiptError.value = "投递状态读取失败，请刷新";
    }
    if (!disposed && !document.hidden && Date.now() < receiptDeadline)
      receiptTimer = setTimeout(() => void refreshReceipts(false), 3000);
  }
  async function queueMessage(content?: unknown) {
    if (
      !supportsQueue ||
      !options.canWrite.value ||
      !threadId.value ||
      cancelling.value ||
      reviews.value.length ||
      pendingMessage.value?.status === "sending"
    )
      return false;
    if (!pendingMessage.value) {
      const targetRunId = actions.current.value?.runId ?? run.value?.run_id;
      if (!busy.value || !targetRunId) return false;
      const id = crypto.randomUUID();
      pendingMessage.value = {
        payload: {
          client_message_id: id,
          target_run_id: targetRunId,
          content: JSON.parse(JSON.stringify(content)),
        },
        key: `message:${id}`,
        status: "sending",
      };
    }
    const pending = pendingMessage.value;
    pending.status = "sending";
    try {
      const row = await enqueueThreadMessage(
        options.projectId,
        threadId.value,
        pending.payload,
        pending.key,
      );
      if (disposed) return false;
      // A receipt query may confirm this exact message before the POST ACK.
      if (pendingMessage.value !== pending) return true;
      receipts.value = [
        ...receipts.value.filter((item) => item.message_id !== row.message_id),
        row,
      ];
      pendingMessage.value = null;
      options.onAccepted?.();
      void refreshReceipts();
      return true;
    } catch (cause) {
      if (disposed) return false;
      if (pendingMessage.value !== pending) return true;
      pending.status =
        isAxiosError(cause) &&
        cause.response &&
        cause.response.status >= 400 &&
        cause.response.status < 500
          ? "rejected"
          : "unknown";
      fail(cause);
      return false;
    }
  }
  function receiptVisibility() {
    clearTimeout(receiptTimer);
    if (document.hidden) receiptController?.abort();
    else void refreshReceipts();
  }
  document.addEventListener("visibilitychange", receiptVisibility);
  watch(run, () => void refreshReceipts());

  async function send(content: unknown, recursionLimit = 25) {
    if (!canSend.value) return false;
    error.value = "";
    checking.value = true;
    try {
      if (
        !Number.isInteger(recursionLimit) ||
        recursionLimit < 1 ||
        recursionLimit > 1000
      )
        throw new Error("执行步数须为 1–1000 的整数");
      if (
        typeof content === "string"
          ? !content.trim()
          : !Array.isArray(content) || !content.length
      )
        throw new Error("请输入消息");
      const context = parseAgentContext(options.context.value);
      if (!threadId.value) {
        const title =
          typeof content === "string" ? content.slice(0, 80) : "新对话";
        const thread = await service.create(
          options.graphId,
          options.agentId,
          title,
        );
        if (disposed) return false;
        threadId.value = thread.thread_id;
        options.onThread(thread.thread_id);
      }
      if (disposed || !options.canWrite.value) return false;
      const input = {
        messages: [{ id: crypto.randomUUID(), type: "human", content }],
      };
      const action = actions.begin(threadId.value, "send", input);
      // The public submit override binds a newly created thread without remounting.
      const completion = stream.submit(input, {
        threadId: threadId.value,
        config: {
          recursion_limit: recursionLimit,
          configurable: { platform_runtime: context },
        },
      });
      checking.value = false;
      await completion;
      if (stream.error.value) throw stream.error.value;
      actions.acknowledge(action.key, run.value?.run_id);
      await verify(true);
      return actions.current.value?.status === "acknowledged";
    } catch (cause) {
      actions.rejectUnsent();
      fail(cause);
      return false;
    } finally {
      if (!disposed) checking.value = false;
    }
  }

  async function approve(drafts: Record<string, ReviewDraft[]>) {
    if (
      !options.canWrite.value ||
      checking.value ||
      pendingAction.value ||
      !threadId.value
    )
      return;
    const before = reviews.value;
    checking.value = true;
    error.value = "";
    try {
      const state = await service.state(threadId.value);
      if (disposed || !options.canWrite.value) return;
      const current = parseReviews(state.interrupts ?? []);
      if (
        current.length !== before.length ||
        before.some(
          (review) =>
            !current.some(
              (item) =>
                item.id === review.id &&
                item.fingerprint === review.fingerprint,
            ),
        )
      ) {
        throw new Error("审批请求已变化，请恢复连接后重新确认");
      }
      const responses = buildReviewResponses(current, drafts);
      actions.begin(threadId.value, "resume", responses);
      await stream.respondAll(responses);
      await verify(true);
    } catch (cause) {
      actions.rejectUnsent();
      fail(cause);
    } finally {
      if (!disposed) checking.value = false;
    }
  }

  async function stop() {
    if (
      !options.canWrite.value ||
      cancelling.value ||
      pendingAction.value ||
      !threadId.value
    )
      return;
    cancelling.value = true;
    try {
      if (!(await verify())) return;
      if (disposed || !options.canWrite.value) return;
      const runId = run.value?.run_id;
      if (!runId || !active(run.value))
        throw new Error("未找到可停止的当前运行");
      await service.cancel(threadId.value, runId);
      await verify(true);
      if (!disposed && !active(run.value)) options.onReconnect();
    } catch (cause) {
      fail(cause);
    } finally {
      if (!disposed) cancelling.value = false;
    }
  }

  async function retry() {
    if (!options.canWrite.value) return;
    try {
      const response = await actions.retry();
      if (!response.ok || actions.current.value?.status !== "acknowledged")
        throw new Error("原请求结果尚未确认");
      if (!disposed) options.onReconnect();
    } catch (cause) {
      fail(cause);
    }
  }

  async function fork(checkpoint: Checkpoint, content?: string) {
    if (!canSend.value || !threadId.value) return;
    try {
      const response = await actions.fork(
        getLanggraphApiUrl(),
        threadId.value,
        {
          assistant_id: options.graphId,
          checkpoint_id: checkpoint.checkpoint_id,
          context: parseAgentContext(options.context.value),
          ...(content === undefined
            ? {}
            : {
                input: {
                  messages: [
                    { id: crypto.randomUUID(), role: "user", content },
                  ],
                },
              }),
        },
      );
      if (!response.ok || actions.current.value?.status !== "acknowledged")
        throw new Error("创建历史分支结果尚未确认，请核实原请求");
      if (!disposed) options.onReconnect();
    } catch (cause) {
      fail(cause);
    }
  }

  watch(actions.current, (action, previous) => {
    if (disposed) return;
    if (
      action?.status === "acknowledged" &&
      (previous?.key !== action.key || previous.status !== "acknowledged")
    ) {
      if (action.kind === "send") options.onAccepted?.();
      options.onRefresh();
    }
  });
  watch(stream.error, (cause) => {
    if (cause && !disposed) {
      fail(cause);
      void verify(true);
    }
  });
  void stream.hydrationPromise.value.then(() => verify()).catch(fail);
  onScopeDispose(() => {
    disposed = true;
    ++checkEpoch;
    clearTimeout(receiptTimer);
    receiptController?.abort();
    document.removeEventListener("visibilitychange", receiptVisibility);
    clearTimeout(timer);
    releaseWait?.();
    void stream.disconnect();
    actions.dispose();
  });
  return {
    supportsQueue,
    receipts,
    pendingMessage,
    receiptError,
    refreshReceipts,
    queueMessage,
    stream,
    service,
    actions,
    threadId,
    run,
    reviews,
    checking,
    verified,
    cancelling,
    error,
    busy,
    canSend,
    status,
    send,
    approve,
    stop,
    retry,
    fork,
    verify,
  };
}
