import {
  computed,
  onScopeDispose,
  ref,
  shallowRef,
  unref,
  watch,
  type Ref,
} from "vue";
import { isAxiosError } from "axios";
import type { Checkpoint, Run } from "@langchain/langgraph-sdk";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import {
  createSessionService,
  type ChatThread,
} from "@/services/threads/session.service";
import { updateThreadAccessPolicy } from "@/services/threads/access-policy.service";
import type { AgentContext } from "@/services/agents/types";
import { parseAgentContext } from "@/services/agents/context";
import { deriveMessagePreview, deriveThreadTitle } from "@/utils/thread-title";
import { unwrapPlatformHttpError } from "@/utils/http-error";
import {
  enqueueThreadMessage,
  listThreadMessages,
  type MessageReceipt,
} from "@/services/threads/messages.service";
import { createRunActions } from "../run-actions";
import { createSessionAttachmentUploader } from "./useSessionAttachmentUpload";
import { useSessionInterrupts } from "./useSessionInterrupts";
import { useChatSessionStore } from "../stores/useChatSessionStore";
import { useSessionConnection } from "./useSessionConnection";
import { useChannelEffect } from "@langchain/vue";
import {
  parseOffloadCustomEvent,
  toOffloadDisplayState,
  type OffloadDisplayState,
} from "../offload-status";
import { safeExtractBudgetSafetyError } from "../budget/view-model";
import { useThreadStopControl } from "./useThreadStopControl";

export type SessionTurnState =
  | "idle"
  | "running"
  | "stopping"
  | "stop_unconfirmed"
  | "stopped"
  | "timeout"
  | "awaiting_review"
  | "error";

export type SessionStopState = "idle" | "stopping" | "unconfirmed" | "stopped";

const active = (run: Run | null) =>
  run != null && ["pending", "running"].includes(run.status);

export const RUNTIME_MODEL_ERROR_MESSAGES: Record<string, string> = {
  "runtime.model.retry_exhausted": "模型服务暂不可用，本次运行未完成。",
  "runtime.model.retry_budget_exceeded": "模型调用等待超时，本次运行未完成。",
  "runtime.model.stream_interrupted": "本次回答中断，已保留部分内容。",
  "runtime.model.provider_rejected": "模型配置或额度不可用，请联系项目管理员。",
  "runtime.model.fallback_incompatible": "备用模型不支持当前请求，请调整配置。",
};

export function extractRuntimeModelErrorMessage(cause: unknown): string | null {
  if (!cause) return null;
  if (typeof cause === "object" && cause !== null) {
    const raw = cause as Record<string, unknown>;
    const errorObj =
      raw.error && typeof raw.error === "object"
        ? (raw.error as Record<string, unknown>)
        : raw;
    const msg =
      typeof errorObj.message === "string"
        ? errorObj.message
        : typeof raw.message === "string"
          ? raw.message
          : "";
    if (msg && RUNTIME_MODEL_ERROR_MESSAGES[msg]) {
      return RUNTIME_MODEL_ERROR_MESSAGES[msg];
    }
  }
  if (typeof cause === "string" && RUNTIME_MODEL_ERROR_MESSAGES[cause]) {
    return RUNTIME_MODEL_ERROR_MESSAGES[cause];
  }
  return null;
}

function hasResolvedAccess(
  thread: ChatThread | undefined,
  expectedThreadId: string | null,
): thread is ChatThread {
  return Boolean(
    expectedThreadId &&
    thread &&
    thread.thread_id === expectedThreadId &&
    Array.isArray(thread.metadata?.allowed_actions),
  );
}

export function useChatSession(options: {
  projectId: string;
  userId?: string;
  graphId: string;
  agentId?: string;
  threadId?: string;
  initialThread?: ChatThread | Ref<ChatThread | undefined>;
  context: Ref<AgentContext>;
  canWrite: Ref<boolean>;
  visible?: Ref<boolean | undefined>;
  onThread: (id: string) => void;
  onRefresh: () => void;
  onReconnect: () => void;
  onAccepted?: () => void;
  onAccessRevoked?: () => void;
  onStopConfirmed?: () => void;
}) {
  const chatSessionStore = useChatSessionStore();
  const actions = createRunActions(
    options.projectId,
    createLanggraphAuthorizedFetch(),
  );
  const service = createSessionService(
    actions.fetch,
    options.projectId,
    options.userId,
  );
  const normalizeThreadId = (id: unknown): string | null =>
    typeof id === "string" && id.trim().length > 0 ? id.trim() : null;
  const threadId = ref<string | null>(normalizeThreadId(options.threadId));
  const run = shallowRef<Run | null>(null);
  const cachedEntry = threadId.value
    ? chatSessionStore.getSession(options.projectId, threadId.value)
    : undefined;
  const hasCachedContent = Boolean(
    cachedEntry &&
    (cachedEntry.messages.length > 0 || cachedEntry.history.length > 0),
  );
  const checking = ref(!hasCachedContent);
  const verified = ref(hasCachedContent);
  const stopState = ref<SessionStopState>("idle");
  const unconfirmedStopRunId = ref<string | null>(null);
  const error = ref("");
  let disposed = false;
  let checkEpoch = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let releaseWait: (() => void) | undefined;
  const hydrated = ref(!threadId.value);
  const streamInFlight = ref(false);

  const connection = useSessionConnection({
    projectId: options.projectId,
    userId: options.userId,
    graphId: options.graphId,
    threadId,
    canWrite: options.canWrite,
    visible: options.visible,
    service,
    actions,
    initialThread: options.initialThread,
    run,
    busy: computed(
      () =>
        stream.isLoading.value ||
        streamInFlight.value ||
        active(run.value) ||
        actions.current.value?.status === "submitting",
    ),
    checking,
    hasPendingReviews: computed(() => reviews.value.length > 0),
    hydrated,
    error,
    getCheckEpoch: () => checkEpoch,
    onVerify: (silent) => verify(silent),
    onFail: (cause) => fail(cause),
    onAccessRevoked: options.onAccessRevoked,
    onClearReceipts: () => {
      receipts.value = [];
      pendingMessage.value = null;
      clearTimeout(receiptTimer);
      receiptController?.abort();
      receiptController = undefined;
    },
  });

  const {
    stream,
    connectionState,
    eventsParked,
    parkEvents,
    recoverySnapshot,
    accessPolicy,
    accessPolicyUpdating,
    accessThread,
    accessLoading,
    canRead,
    canComment,
    canApprove,
    canEdit,
    canSetPolicy,
    canFullAccess,
    applyAccessThread,
    refreshAccessPolicy,
    setAccessPolicy,
    reconnectStream,
    bindConnectionState,
  } = connection;

  const offloadState = ref<OffloadDisplayState | null>(null);
  let offloadDismissTimer: ReturnType<typeof setTimeout> | undefined;

  const isOffloading = computed(() => {
    return (
      offloadState.value?.status === "started" ||
      actions.current.value?.kind === "offload"
    );
  });

  function clearOffloadState() {
    if (offloadDismissTimer) {
      clearTimeout(offloadDismissTimer);
      offloadDismissTimer = undefined;
    }
    offloadState.value = null;
  }

  function scheduleOffloadDismiss() {
    if (offloadDismissTimer) clearTimeout(offloadDismissTimer);
    offloadDismissTimer = setTimeout(() => {
      offloadState.value = null;
      offloadDismissTimer = undefined;
    }, 4000);
  }

  useChannelEffect(stream, ["custom"], {
    onEvent(event) {
      const parsed = parseOffloadCustomEvent(event);
      if (!parsed || disposed) return;
      if (parsed.status === "started") {
        if (offloadDismissTimer) clearTimeout(offloadDismissTimer);
        offloadState.value = toOffloadDisplayState(parsed);
      } else if (parsed.status === "completed" || parsed.status === "skipped") {
        offloadState.value = toOffloadDisplayState(parsed);
        scheduleOffloadDismiss();
      } else if (parsed.status === "failed") {
        if (offloadDismissTimer) clearTimeout(offloadDismissTimer);
        offloadState.value = toOffloadDisplayState(parsed);
      }
    },
    onError() {
      if (!disposed && offloadState.value?.status === "started") {
        clearOffloadState();
      }
    },
  });

  const stopControl = useThreadStopControl({
    projectId: computed(() => options.projectId),
    threadId,
    userId: computed(() => options.userId),
    service,
    canWrite: canEdit,
    onStopConfirmed: () => {
      void verify(true);
      options.onStopConfirmed?.();
    },
  });
  const cancelling = computed(
    () => stopControl.isStopping.value || stopState.value === "stopping",
  );

  watch(
    () => options.threadId,
    (rawNext) => {
      const next = normalizeThreadId(rawNext);
      if (next && next !== threadId.value) {
        clearOffloadState();
        threadId.value = next;
        unconfirmedStopRunId.value = null;
        hydrated.value = false;
        const seeded = unref(options.initialThread);
        if (hasResolvedAccess(seeded, next)) {
          applyAccessThread(seeded);
          accessLoading.value = false;
        } else {
          accessThread.value = undefined;
          accessLoading.value = true;
          void refreshAccessPolicy();
        }
      } else if (next && !accessThread.value) {
        const seeded = unref(options.initialThread);
        if (hasResolvedAccess(seeded, next)) {
          applyAccessThread(seeded);
          accessLoading.value = false;
        } else {
          void refreshAccessPolicy();
        }
      } else if (!next) {
        threadId.value = null;
        hydrated.value = true;
        accessThread.value = undefined;
        accessLoading.value = false;
      }
    },
    { immediate: true },
  );
  const pendingAction = computed(() =>
    ["submitting", "unknown"].includes(actions.current.value?.status ?? ""),
  );
  const {
    reviews,
    clarifications,
    hasPendingInterrupts,
    approve,
    answerClarification,
    resumeClarification,
  } = useSessionInterrupts({
    threadId,
    hydrated,
    verified,
    checking,
    error,
    run,
    canApprove,
    pendingAction,
    isDisposed: () => disposed,
    streamInFlight,
    stream,
    service,
    actions,
    verify: (force?: boolean) => verify(force),
    fail: (cause: unknown) => fail(cause),
  });
  const busy = computed(() => {
    const isStaleRun = Boolean(
      actions.current.value?.runId &&
      run.value &&
      run.value.run_id !== actions.current.value.runId,
    );
    const isSameConfirmedTerminalRun = Boolean(
      run.value &&
      !active(run.value) &&
      (!stream.isLoading.value ||
        (actions.current.value?.runId &&
          run.value.run_id === actions.current.value.runId) ||
        ["timeout", "error", "cancelled", "canceled"].includes(
          String(run.value.status),
        )),
    );
    if (
      !streamInFlight.value &&
      isSameConfirmedTerminalRun &&
      !isStaleRun &&
      !hasPendingInterrupts.value &&
      actions.current.value?.status !== "submitting"
    ) {
      return false;
    }
    return (
      stream.isLoading.value ||
      streamInFlight.value ||
      active(run.value) ||
      actions.current.value?.status === "submitting"
    );
  });
  const isNonFatalStreamError = (err: unknown): boolean => {
    if (!err) return true;
    const raw = err instanceof Error ? err.message : String(err);
    return (
      raw.includes("409 Conflict") ||
      raw.includes("pending or running run") ||
      raw.includes("multitaskStrategy is 'reject'") ||
      raw.includes("already in flight") ||
      raw.includes("Upstream stream ended before terminal chunk") ||
      raw.includes("AbortError") ||
      raw.includes("BodyStreamBuffer")
    );
  };
  watch(
    () => stream.error.value,
    (err) => {
      if (err && isNonFatalStreamError(err)) {
        try {
          (stream.error as unknown as { value: unknown }).value = null;
        } catch {
          // ignore
        }
        if (!disposed && threadId.value && !checking.value) {
          void verify(false);
        }
      }
    },
  );
  const hasFatalStreamError = computed(() => {
    if (!stream.error.value) return false;
    if (!stream.isLoading.value && !active(run.value)) return false;
    return !isNonFatalStreamError(stream.error.value);
  });

  const canSend = computed(
    () =>
      canComment.value &&
      hydrated.value &&
      verified.value &&
      !hasFatalStreamError.value &&
      (eventsParked.value || connectionState.value !== "paused") &&
      !checking.value &&
      stopState.value !== "stopping" &&
      stopState.value !== "unconfirmed" &&
      !pendingAction.value &&
      !(pendingMessage.value?.status === "sending") &&
      !busy.value &&
      !hasPendingInterrupts.value,
  );

  const turnState = computed<SessionTurnState>(() => {
    if (stopState.value === "stopping") return "stopping";
    if (stopState.value === "unconfirmed") return "stop_unconfirmed";
    if (reviews.value.length > 0 || hasPendingInterrupts.value) {
      return "awaiting_review";
    }
    if (busy.value || active(run.value) || stream.isLoading.value) {
      return "running";
    }
    if (stopState.value === "stopped") return "stopped";
    const currentRun = run.value;
    const runReason = (currentRun as { reason?: string } | null)?.reason;
    if (currentRun?.status === "timeout" || runReason === "timeout") {
      return "timeout";
    }
    if (
      currentRun?.status === "interrupted" &&
      runReason === "cancel_requested"
    ) {
      return "stopped";
    }
    if (error.value || stream.error.value || currentRun?.status === "error") {
      return "error";
    }
    return "idle";
  });

  const status = computed(() => {
    if (stopControl.isStopping.value || turnState.value === "stopping") {
      return "正在停止";
    }
    if (
      stopControl.isConfirmationUnavailable.value ||
      turnState.value === "stop_unconfirmed"
    ) {
      return error.value.includes("停止尚未确认")
        ? "停止尚未确认"
        : "停止结果待确认";
    }
    if (unconfirmedStopRunId.value) {
      return "停止尚未确认";
    }
    if (!threadId.value) {
      return "新会话";
    }
    if (actions.current.value?.status === "unknown") {
      return "提交结果待确认";
    }
    if (checking.value) {
      return "正在核实会话";
    }
    if (actions.current.value?.status === "submitting") {
      return "正在发送";
    }
    if (reviews.value.length) {
      return "等待审批";
    }
    if (clarifications.value.length) {
      return "等待补充信息";
    }
    if (turnState.value === "stopped") {
      return "已停止";
    }
    if (busy.value) {
      return "正在执行";
    }
    if (error.value || stream.error.value || turnState.value === "error") {
      return "连接或执行异常";
    }
    if (run.value?.status === "timeout" || turnState.value === "timeout") {
      return "上一回合执行超时";
    }
    return "可以发送";
  });

  function fail(cause: unknown) {
    if (!disposed) {
      if (
        safeExtractBudgetSafetyError(cause) ||
        safeExtractBudgetSafetyError((run.value as any)?.error) ||
        safeExtractBudgetSafetyError(run.value) ||
        safeExtractBudgetSafetyError((accessThread.value as any)?.error) ||
        safeExtractBudgetSafetyError(accessThread.value)
      ) {
        // 预算安全受限由 runBudget 机制统一处理，不污染通用 error
        return;
      }
      const runtimeMsg = extractRuntimeModelErrorMessage(cause);
      if (runtimeMsg) {
        error.value = runtimeMsg;
        return;
      }
      if (cause instanceof Error) {
        if (cause.message === "[object Object]") {
          const nestedMsg =
            (cause as any)?.error?.message ||
            (cause as any)?.cause?.message ||
            (cause as any)?.code ||
            (run.value as any)?.error?.message ||
            (accessThread.value as any)?.error?.message ||
            "";
          error.value = nestedMsg
            ? `执行异常: ${nestedMsg}`
            : "执行服务响应异常，请点击右侧恢复连接重试";
        } else {
          error.value = cause.message;
        }
      } else if (typeof cause === "object" && cause !== null) {
        const msg = (cause as any).message || (cause as any).error?.message;
        error.value = msg ? String(msg) : "请求失败，请重试";
      } else {
        error.value = typeof cause === "string" ? cause : "请求失败，请重试";
      }
    }
  }
  let activeVerifyPromise: Promise<boolean> | undefined;
  let activeVerifyTerminal = false;
  let activeVerifyRunId: string | undefined;
  let backgroundRunTimer: ReturnType<typeof setTimeout> | undefined;

  function scheduleBackgroundRunPoll(targetThreadId: string) {
    clearTimeout(backgroundRunTimer);
    if (disposed || threadId.value !== targetThreadId || !active(run.value))
      return;
    backgroundRunTimer = setTimeout(async () => {
      if (
        disposed ||
        threadId.value !== targetThreadId ||
        (stream.isLoading.value && !eventsParked.value)
      )
        return;
      try {
        const list = await service.runs(targetThreadId);
        if (disposed || threadId.value !== targetThreadId) return;
        const nextLatest = list.find((r) => active(r)) ?? list[0] ?? null;
        if (active(nextLatest)) {
          run.value = nextLatest;
          options.onRefresh();
          scheduleBackgroundRunPoll(targetThreadId);
        } else {
          if (eventsParked.value) {
            const snapshot = await service.state(targetThreadId);
            if (disposed || threadId.value !== targetThreadId) return;
            recoverySnapshot.value = snapshot.values;
            run.value = nextLatest;
            await stream.disconnect();
            streamInFlight.value = false;
          }
          run.value = nextLatest;
          options.onRefresh();
          await refreshAccessPolicy();
        }
      } catch {
        if (
          !disposed &&
          threadId.value === targetThreadId &&
          active(run.value)
        ) {
          scheduleBackgroundRunPoll(targetThreadId);
        }
      }
    }, 1500);
  }

  async function verify(waitForTerminal = false): Promise<boolean> {
    if (disposed) return false;
    const targetRunId =
      actions.current.value?.runId ??
      (active(run.value) ? run.value?.run_id : undefined);
    if (
      activeVerifyPromise &&
      (!waitForTerminal || activeVerifyTerminal) &&
      activeVerifyRunId === targetRunId
    ) {
      return activeVerifyPromise;
    }
    const epoch = ++checkEpoch;
    clearTimeout(timer);
    clearTimeout(backgroundRunTimer);
    releaseWait?.();
    releaseWait = undefined;
    if (!threadId.value) {
      checking.value = false;
      verified.value = true;
      return true;
    }
    const isSilentRevalidate =
      verified.value ||
      Boolean(
        chatSessionStore.getSession(options.projectId, threadId.value)?.messages
          .length,
      );
    if (!isSilentRevalidate) {
      verified.value = false;
      checking.value = true;
    }
    activeVerifyTerminal = waitForTerminal;
    activeVerifyRunId = targetRunId;
    const id = threadId.value;
    let deadline = Date.now() + 30000;
    const p = (async () => {
      try {
        let attempt = 0;
        do {
          const actionRunId = actions.current.value?.runId;
          const activeKnownId = active(run.value)
            ? run.value?.run_id
            : undefined;
          const knownId = waitForTerminal
            ? (actionRunId ?? activeKnownId)
            : undefined;
          let latest: Run | null = null;
          if (knownId) {
            latest = await service.run(id, knownId);
          } else {
            const list = await service.runs(id);
            latest = list.find((r) => active(r)) ?? list[0] ?? null;
          }
          if (disposed || epoch !== checkEpoch) return false;
          run.value = latest;
          if (!active(latest) || !waitForTerminal) {
            break;
          }
          // 流式通道活跃或服务端明确返回 run 仍处于 active (running/pending) 状态时，持续顺延超时判定，避免长任务或后台轮询过程中误判
          if (stream.isLoading.value || active(latest)) {
            deadline = Date.now() + 30000;
          }
          // 仅在数据流已非传输状态且超时后，才提示未能确认运行结果；切标签页（document.hidden）不再误判
          if (!stream.isLoading.value && Date.now() >= deadline) {
            throw new Error("运行结果尚未确认，请恢复连接后核实");
          }
          const delay = document.hidden
            ? 3000
            : attempt++ === 0
              ? 150
              : Math.min(500 * 2 ** (attempt - 2), 4000);
          await new Promise<void>((resolve) => {
            releaseWait = resolve;
            timer = setTimeout(resolve, delay);
          });
        } while (!disposed && epoch === checkEpoch);
        if (!disposed && epoch === checkEpoch) {
          verified.value = true;
          error.value = "";
          // 自愈状态机：若当前 run 已经处于非 active 终态，强制收敛流式与动作状态
          if (!active(run.value)) {
            if (stream.isLoading.value) {
              (stream.isLoading as unknown as { value: boolean }).value = false;
            }
            streamInFlight.value = false;
            if (actions.current.value?.status === "submitting") {
              actions.acknowledge();
            }
          }
          if (waitForTerminal) {
            options.onRefresh();
          }
          if (!accessThread.value) {
            await refreshAccessPolicy();
          } else if (waitForTerminal) {
            void refreshAccessPolicy();
          }
          if (
            active(run.value) &&
            (!stream.isLoading.value || eventsParked.value)
          ) {
            scheduleBackgroundRunPoll(id);
          }
          return true;
        }
        return false;
      } catch (cause) {
        if (epoch === checkEpoch) fail(cause);
        return false;
      } finally {
        if (!disposed && epoch === checkEpoch) {
          checking.value = false;
          activeVerifyPromise = undefined;
          activeVerifyTerminal = false;
          activeVerifyRunId = undefined;
        }
      }
    })();
    activeVerifyPromise = p;
    return p;
  }

  const supportsQueue = [
    "dearflow_agent",
    "dear_agent",
    "reference_agent",
    "showcase_demo",
  ].includes(options.graphId);
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
      if (disposed || controller !== receiptController || !canRead.value)
        return;
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
    } catch (cause) {
      const isCanceled =
        controller.signal.aborted ||
        (isAxiosError(cause) && cause.code === "ERR_CANCELED") ||
        (cause as { name?: string })?.name === "CanceledError" ||
        (cause as { name?: string })?.name === "AbortError";
      if (!disposed && !isCanceled) {
        // 仅在存在待投递的 pendingMessage 或已有未清空 receipts 时才显示投递状态警告，避免后台静默轮询失败干扰空队列界面
        if (pendingMessage.value || receipts.value.length > 0) {
          receiptError.value = "投递状态读取失败，请刷新";
        }
      }
    }
    if (!disposed && !document.hidden && Date.now() < receiptDeadline)
      receiptTimer = setTimeout(() => void refreshReceipts(false), 3000);
  }

  const prepareMessageAttachments = createSessionAttachmentUploader(
    options.projectId,
  );

  async function queueMessage(
    content?: unknown,
    queueOptions?: { allowFallbackSend?: boolean },
  ): Promise<boolean> {
    if (
      !supportsQueue ||
      !canComment.value ||
      connectionState.value === "paused" ||
      !threadId.value ||
      stopState.value === "stopping" ||
      stopState.value === "unconfirmed" ||
      reviews.value.length ||
      pendingMessage.value?.status === "sending"
    )
      return false;

    const allowFallbackSend = queueOptions?.allowFallbackSend ?? true;

    // 1. 严格检查活跃 run：只有明确处于 active 态的 run 才能作为追加目标
    let targetRunId =
      run.value && active(run.value)
        ? run.value.run_id
        : actions.current.value?.status === "submitting"
          ? actions.current.value.runId
          : undefined;

    // 2. 如果本地缓存未命中，始终向服务端查询最新的 running/pending 运行回合（即使本地 busy 因旧 verify 被误置为 false）
    if (!targetRunId) {
      try {
        const list = await service.client.runs.list(threadId.value, {
          limit: 5,
        });
        const runningItem = list?.find(
          (r) => r.status === "running" || r.status === "pending",
        );
        if (runningItem) {
          targetRunId = runningItem.run_id;
          run.value = runningItem;
          scheduleBackgroundRunPoll(threadId.value);
        }
      } catch {
        // ignore
      }
    }

    // 3. 若根本无 active/running 的运行回合：
    //    - 若是从 send(409) 退避过来的，禁止再次递归调用 send() 造成重复生成乐观气泡与死循环，直接返回 false 让前端队列保留等待！
    //    - 若是用户主动调用 queueMessage 且确实无活跃回合，才回退为直接发送。
    if (!targetRunId) {
      if (!allowFallbackSend) {
        await verify(true);
        return false;
      }
      console.info(
        "[session] 没有活跃中的运行回合，将排队消息自愈回退为直接发送",
      );
      return await send(content);
    }

    if (!pendingMessage.value) {
      const messageContent = prepareMessageAttachments(threadId.value, content);
      if (messageContent instanceof Promise) {
        const resolved = await messageContent;
        if (disposed) return false;
        const id = crypto.randomUUID();
        pendingMessage.value = {
          payload: {
            client_message_id: id,
            target_run_id: targetRunId,
            content: JSON.parse(JSON.stringify(resolved)),
          },
          key: `message:${id}`,
          status: "sending",
        };
      } else {
        const id = crypto.randomUUID();
        pendingMessage.value = {
          payload: {
            client_message_id: id,
            target_run_id: targetRunId,
            content: JSON.parse(JSON.stringify(messageContent)),
          },
          key: `message:${id}`,
          status: "sending",
        };
      }
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

      // 4. 关键自愈机制（对齐 open-swe）：
      // 若后端返回 409（run_changed 或 thread 不在 running 态），说明上一回合在发送间隙恰好完结！
      const is409RunEnded =
        isAxiosError(cause) && cause.response?.status === 409;

      if (is409RunEnded) {
        pendingMessage.value = null;
        error.value = "";
        await verify(true);
        if (!allowFallbackSend) {
          return false;
        }
        console.warn(
          "[session] 目标回合已结束(409)，排队消息无感自愈转为新回合发送",
        );
        const fallbackContent = pending.payload.content ?? content;
        return await send(fallbackContent);
      }

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
    if (document.hidden) {
      receiptController?.abort();
    } else {
      void refreshReceipts();
      if (releaseWait) {
        clearTimeout(timer);
        releaseWait();
        releaseWait = undefined;
      }
    }
  }
  document.addEventListener("visibilitychange", receiptVisibility);
  watch(run, () => void refreshReceipts());

  async function send(
    content: unknown,
    recursionLimit = 1000,
    sendOptions?: { fromQueue?: boolean; messageId?: string },
  ): Promise<boolean> {
    clearOffloadState();
    if (!canSend.value) return false;
    error.value = "";
    unconfirmedStopRunId.value = null;
    if (!verified.value) checking.value = true;
    streamInFlight.value = true;
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
        const title = deriveThreadTitle(content);
        const preview = deriveMessagePreview(content);
        const thread = await service.create(
          options.graphId,
          options.agentId,
          title,
          accessPolicy.value,
          preview,
        );
        if (disposed) return false;
        threadId.value = thread.thread_id;
        accessThread.value = thread;
        options.onThread(thread.thread_id);

        if (accessPolicy.value !== "review") {
          try {
            await updateThreadAccessPolicy(
              options.projectId,
              thread.thread_id,
              accessPolicy.value,
            );
          } catch (cause) {
            accessPolicy.value = "review";
            fail(cause);
            return false;
          }
        }
      }
      if (disposed || !canComment.value) return false;
      if (stopState.value === "stopping" || stopState.value === "unconfirmed") {
        throw new Error("停止结果尚未确认，请核实停止后再发送");
      }
      if (
        threadId.value &&
        (stream.isLoading.value ||
          active(run.value) ||
          actions.current.value?.status === "submitting")
      ) {
        if (sendOptions?.fromQueue || supportsQueue) {
          return false;
        }
        throw new Error("当前回合正在执行中，请等待完成或停止后再发送");
      }
      const messageContent = await prepareMessageAttachments(
        threadId.value,
        content,
      );
      if (disposed || !canComment.value) return false;
      const inputMessageId = sendOptions?.messageId || crypto.randomUUID();
      const input = {
        messages: [
          { id: inputMessageId, type: "human", content: messageContent },
        ],
      };
      const removeUncommittedMessage = () => {
        const streamMessages = (
          stream as unknown as { messages?: { value?: Array<{ id?: string }> } }
        ).messages;
        if (streamMessages && Array.isArray(streamMessages.value)) {
          streamMessages.value = streamMessages.value.filter(
            (m) => m?.id !== inputMessageId,
          );
        }
      };
      const isFromQueue = Boolean(sendOptions?.fromQueue);
      let attempts = 0;
      const maxAttempts = isFromQueue ? 1 : 3;
      while (attempts < maxAttempts) {
        attempts++;
        try {
          if (stream.error.value) {
            try {
              (stream.error as unknown as { value: unknown }).value = null;
            } catch {
              // ignore
            }
          }
          const action = actions.begin(threadId.value, "send", input);
          stopState.value = "idle";
          streamInFlight.value = true;
          if (run.value && !active(run.value)) {
            run.value = null;
          }
          const completion = stream.submit(input, {
            threadId: threadId.value,
            config: {
              recursion_limit: recursionLimit,
              configurable: { platform_runtime: context },
            },
          });
          checking.value = false;
          await completion;
          if (disposed) {
            return true;
          }
          if (stream.error.value) throw stream.error.value;
          actions.acknowledge(action.key, actions.current.value?.runId);
          await verify(true);
          if (disposed) {
            return true;
          }
          return actions.current.value?.status === "acknowledged";
        } catch (cause) {
          streamInFlight.value = false;
          const raw = cause instanceof Error ? cause.message : String(cause);
          const is409 =
            raw.includes("409 Conflict") ||
            raw.includes("pending or running run") ||
            raw.includes("multitaskStrategy is 'reject'") ||
            raw.includes("already in flight");
          if (is409 && attempts < maxAttempts) {
            actions.rejectUnsent();
            removeUncommittedMessage();
            console.warn(
              `[session] 遇到服务端短暂运行冲突 (409)，正在进行第 ${attempts} 次退避重试...`,
            );
            error.value = "";
            try {
              (stream.error as unknown as { value: unknown }).value = null;
            } catch {
              // ignore
            }
            await new Promise((r) => setTimeout(r, attempts * 350));
            continue;
          }
          if (is409) {
            actions.rejectUnsent();
            removeUncommittedMessage();
            error.value = "";
            try {
              (stream.error as unknown as { value: unknown }).value = null;
            } catch {
              // ignore
            }
            // 同步服务端真实 active run 状态并开启后台轮询，直接返回 false 交由前端待执行消息队列（promptQueue）统一排队，避免写入 runtime_message_inbox 造成消息在回合结束后丢失或提前滞留气泡
            await verify(false);
            return false;
          }
          const isMidStreamDisconnect =
            raw.includes("Upstream stream ended before terminal chunk") ||
            raw.includes("AbortError") ||
            raw.includes("BodyStreamBuffer") ||
            disposed;
          if (isMidStreamDisconnect) {
            error.value = "";
            try {
              (stream.error as unknown as { value: unknown }).value = null;
            } catch {
              // ignore
            }
            if (!disposed) {
              await verify(true);
            }
            if (actions.current.value?.key) {
              actions.acknowledge(
                actions.current.value.key,
                actions.current.value?.runId ?? run.value?.run_id,
              );
            }
            return true;
          }
          actions.rejectUnsent();
          removeUncommittedMessage();
          if (threadId.value) {
            try {
              await refreshAccessPolicy();
              await verify(true);
            } catch {
              // ignore
            }
          }
          fail(cause);
          return false;
        }
      }
      return false;
    } finally {
      streamInFlight.value = false;
      if (!disposed) checking.value = false;
    }
  }

  async function performCancel(targetThreadId: string, targetRunId: string) {
    if (typeof service.cancelAndWait === "function") {
      await service.cancelAndWait(targetThreadId, targetRunId);
    } else {
      await service.cancel(targetThreadId, targetRunId);
    }
  }

  async function stop() {
    if (
      !canEdit.value ||
      stopControl.isStopping.value ||
      stopState.value === "stopping" ||
      pendingAction.value ||
      !threadId.value ||
      options.visible?.value === false
    )
      return;

    let stopControlPromise: Promise<void> | undefined;
    if (typeof (service as any).stopThread === "function") {
      stopControlPromise = stopControl
        .stop()
        .then(() => {})
        .catch(() => {});
    }

    const knownRunId =
      actions.current.value?.runId ??
      run.value?.run_id ??
      unconfirmedStopRunId.value;
    let targetRunId = knownRunId;
    if (!targetRunId) {
      if (!(await verify())) return;
      targetRunId = run.value?.run_id ?? unconfirmedStopRunId.value;
    }
    if (disposed || !canEdit.value) return;
    const isRetryingUnconfirmed = Boolean(
      targetRunId &&
      (targetRunId === unconfirmedStopRunId.value ||
        stopState.value === "unconfirmed"),
    );
    if (!targetRunId || (!active(run.value) && !isRetryingUnconfirmed)) {
      await verify(true);
      if (!disposed && !active(run.value)) {
        stopState.value = "stopped";
        unconfirmedStopRunId.value = null;
      }
      return;
    }

    stopState.value = "stopping";
    try {
      await performCancel(threadId.value, targetRunId);
      unconfirmedStopRunId.value = null;
      await verify(true);
      if (!disposed) {
        if (!active(run.value)) {
          stopState.value = "stopped";
        } else {
          stopState.value = "unconfirmed";
          unconfirmedStopRunId.value = targetRunId;
        }
      }
      if (stopControlPromise) {
        await stopControlPromise;
      }
    } catch (cause) {
      if (!disposed) {
        stopState.value = "unconfirmed";
        unconfirmedStopRunId.value = targetRunId;
        fail(cause);
      }
    }
  }

  async function verifyStop(): Promise<boolean> {
    if (
      !canEdit.value ||
      !threadId.value ||
      disposed ||
      options.visible?.value === false
    )
      return false;
    const targetRunId =
      actions.current.value?.runId ??
      run.value?.run_id ??
      unconfirmedStopRunId.value;
    if (!targetRunId) {
      stopState.value = "idle";
      unconfirmedStopRunId.value = null;
      return true;
    }
    stopState.value = "stopping";
    try {
      void stopControl.verifyLatest?.().catch(() => {});
      // 1. 双通道容错：先查服务端 Run 当前状态，若已是非 active 终态直接收敛，彻底杜绝对已终态 Run 重复 cancel 触发 400/409 死锁
      const current = await service.run(threadId.value, targetRunId);
      if (!disposed && current) {
        run.value = current;
        if (!active(current)) {
          stopState.value = "stopped";
          unconfirmedStopRunId.value = null;
          await verify(false);
          return true;
        }
      }
      // 2. 依然处于 active 状态时，才再次发起 cancelAndWait
      await performCancel(threadId.value, targetRunId);
      await verify(true);
      if (!disposed) {
        if (!active(run.value)) {
          stopState.value = "stopped";
          unconfirmedStopRunId.value = null;
        } else {
          stopState.value = "unconfirmed";
        }
      }
      return true;
    } catch (cause) {
      if (!disposed) {
        stopState.value = "unconfirmed";
        fail(cause);
      }
      return false;
    }
  }

  async function resumeInterruptedRun() {
    if (
      !canEdit.value ||
      !threadId.value ||
      checking.value ||
      stopState.value === "stopping" ||
      stopState.value === "unconfirmed" ||
      pendingAction.value ||
      options.visible?.value === false
    )
      return;
    const currentRun = run.value;
    if (!currentRun || currentRun.status !== "interrupted") return;
    const runReason = (currentRun as { reason?: string }).reason;
    if (runReason === "cancel_requested") {
      return;
    }
    checking.value = true;
    error.value = "";
    try {
      await service.resume(threadId.value, {});
      await verify(false);
      void reconnectStream();
      options.onRefresh();
    } catch (cause) {
      fail(cause);
    } finally {
      if (!disposed) checking.value = false;
    }
  }

  async function retry() {
    if (connectionState.value === "paused") {
      try {
        await reconnectStream();
      } catch (cause) {
        fail(cause);
      }
      return;
    }
    if (
      actions.current.value?.kind === "resume"
        ? !canApprove.value
        : !canComment.value
    )
      return;
    try {
      const response = await actions.retry();
      if (!response.ok || actions.current.value?.status !== "acknowledged")
        throw new Error("原请求结果尚未确认");
      if (!disposed) options.onReconnect();
    } catch (cause) {
      fail(cause);
    }
  }

  async function fork(
    checkpoint: Checkpoint,
    content?: unknown,
    recursionLimit = 1000,
    forkOptions?: { messageId?: string },
  ) {
    if (!canSend.value || !threadId.value || !checkpoint?.checkpoint_id)
      return false;
    const checkpointId = checkpoint.checkpoint_id;
    error.value = "";
    if (!verified.value) checking.value = true;
    try {
      if (
        !Number.isInteger(recursionLimit) ||
        recursionLimit < 1 ||
        recursionLimit > 1000
      )
        throw new Error("执行步数须为 1–1000 的整数");

      const hasContent =
        content !== undefined &&
        (typeof content === "string"
          ? Boolean(content.trim())
          : Array.isArray(content) && Boolean(content.length));

      const messageContent = hasContent
        ? await prepareMessageAttachments(threadId.value, content)
        : null;

      const input = hasContent
        ? {
            messages: [
              {
                id: forkOptions?.messageId || crypto.randomUUID(),
                type: "human",
                content: messageContent,
              },
            ],
          }
        : null;

      const context = parseAgentContext(options.context.value);
      const action = actions.begin(threadId.value, "fork", {
        input,
        checkpoint_id: checkpointId,
      });
      streamInFlight.value = true;
      if (run.value && !active(run.value)) {
        run.value = null;
      }

      const completion = stream.submit(input, {
        threadId: threadId.value,
        forkFrom: checkpointId,
        config: {
          recursion_limit: recursionLimit,
          configurable: {
            platform_runtime: context,
            checkpoint_id: checkpointId,
          },
        },
      });
      checking.value = false;
      await completion;
      if (stream.error.value) throw stream.error.value;
      actions.acknowledge(action.key, actions.current.value?.runId);
      await verify(true);
      return actions.current.value?.status === "acknowledged";
    } catch (cause) {
      actions.rejectUnsent();
      fail(cause);
      return false;
    } finally {
      streamInFlight.value = false;
      if (!disposed) checking.value = false;
    }
  }

  async function offloadConversation(): Promise<boolean> {
    if (
      !threadId.value ||
      busy.value ||
      hasPendingInterrupts.value ||
      !canEdit.value ||
      disposed
    ) {
      return false;
    }
    clearOffloadState();
    error.value = "";
    if (!verified.value) checking.value = true;
    streamInFlight.value = true;
    try {
      const context = parseAgentContext(options.context.value);
      const action = actions.begin(threadId.value, "offload", {});
      if (run.value && !active(run.value)) {
        run.value = null;
      }
      const completion = stream.submit(null, {
        threadId: threadId.value,
        config: {
          configurable: {
            platform_runtime: {
              ...(context || {}),
              offload_conversation: true,
            },
          },
        },
      });
      checking.value = false;
      await completion;
      if (disposed) return true;
      if (stream.error.value) throw stream.error.value;
      actions.acknowledge(action.key, actions.current.value?.runId);
      await verify(true);
      return true;
    } catch (cause) {
      actions.rejectUnsent();
      const unwrapped = await unwrapPlatformHttpError(cause);
      let errMsg = unwrapped.message;
      if (unwrapped.code === "context_offload_not_supported") {
        errMsg = "当前智能体不支持上下文手动整理";
      } else if (unwrapped.code === "context_offload_empty_thread") {
        errMsg = "当前会话尚无历史消息，无需整理";
      } else if (unwrapped.code === "context_offload_input_invalid") {
        errMsg = "整理请求参数非法，请重试";
      } else if (unwrapped.code === "context_offload_pending_input") {
        errMsg = "当前存在排队或待发送消息，请完成后再试";
      } else if (unwrapped.code === "context_offload_interrupt_pending") {
        errMsg = "当前会话存在等待审批的动作，请先处理";
      } else if (unwrapped.code === "thread_active_run_conflict") {
        errMsg = "当前会话正在执行中，请等待其结束";
      } else if (unwrapped.code === "runtime.context.capacity_unknown") {
        errMsg = "当前模型未配置上下文容量，请联系管理员配置";
      }
      fail(new Error(errMsg));
      return false;
    } finally {
      streamInFlight.value = false;
      if (!disposed) checking.value = false;
    }
  }

  function ensureLiveEventStream() {
    if (disposed) return;
    bindConnectionState();
    if (options.visible?.value === false) {
      parkEvents();
      if (threadId.value) scheduleBackgroundRunPoll(threadId.value);
      return;
    }
    if (connectionState.value === "paused") void reconnectStream();
  }

  watch(
    [() => options.visible?.value, () => stream.isLoading.value, hydrated],
    ([visible, loading, ready]) => {
      if (!ready || disposed) return;
      if (visible === false) {
        parkEvents();
        if (threadId.value) {
          if (active(run.value)) scheduleBackgroundRunPoll(threadId.value);
          else if (loading) void verify(false);
        }
      } else if (eventsParked.value) {
        void reconnectStream().catch(fail);
      }
    },
    { flush: "post" },
  );

  watch(actions.current, (action, previous) => {
    if (disposed) return;
    if (
      action?.status === "acknowledged" &&
      (previous?.key !== action.key || previous.status !== "acknowledged")
    ) {
      if (action.runId && (!run.value || run.value.run_id !== action.runId)) {
        run.value = {
          ...(run.value ?? {}),
          run_id: action.runId,
          thread_id: action.threadId,
          status: "running",
        } as Run;
      }
      ensureLiveEventStream();
      if (action.kind === "send" || action.kind === "fork")
        options.onAccepted?.();
      options.onRefresh();
    }
  });
  watch(stream.error, (cause) => {
    if (cause && !disposed && !isNonFatalStreamError(cause)) {
      fail(cause);
      void verify(true);
    }
  });
  void stream.hydrationPromise.value
    .then(async () => {
      if (!disposed) hydrated.value = true;
      await verify();
    })
    .catch((cause) => {
      if (!disposed) hydrated.value = true;
      fail(cause);
    });
  onScopeDispose(() => {
    disposed = true;
    ++checkEpoch;
    clearOffloadState();
    clearTimeout(receiptTimer);
    clearTimeout(backgroundRunTimer);
    receiptController?.abort();
    document.removeEventListener("visibilitychange", receiptVisibility);
    clearTimeout(timer);
    releaseWait?.();
    if (
      !active(run.value) &&
      !streamInFlight.value &&
      !stream.isLoading.value
    ) {
      void stream.disconnect();
    }
    actions.dispose();
  });
  return {
    canRead,
    canComment,
    canApprove,
    canEdit,
    canSetPolicy,
    canFullAccess,
    accessLoading,
    supportsQueue,
    receipts,
    pendingMessage,
    receiptError,
    refreshReceipts,
    queueMessage,
    stream,
    connectionState,
    recoverySnapshot,
    reconnectStream,
    service,
    actions,
    threadId,
    accessThread,
    accessPolicy,
    accessPolicyUpdating,
    setAccessPolicy,
    refreshAccessPolicy,
    run,
    reviews,
    clarifications,
    hasPendingInterrupts,
    checking,
    verified,
    cancelling,
    stopControl,
    unconfirmedStopRunId,
    stopState,
    turnState,
    verifyStop,
    error,
    busy,
    canSend,
    status,
    send,
    prepareQueueContent: (content: unknown) =>
      prepareMessageAttachments(threadId.value!, content),
    approve,
    answerClarification,
    resumeClarification,
    stop,
    resumeInterruptedRun,
    retry,
    fork,
    verify,
    offloadState,
    clearOffloadState,
    offloadConversation,
    isOffloading,
  };
}
