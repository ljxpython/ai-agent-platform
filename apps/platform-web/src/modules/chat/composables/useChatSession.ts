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
import { useStream } from "@langchain/vue";
import type { Checkpoint, Run } from "@langchain/langgraph-sdk";
import {
  createLanggraphAuthorizedFetch,
} from "@/services/langgraph/client";
import {
  createSessionService,
  hasThreadAction,
  type ChatThread,
  type ThreadAction,
  type AccessPolicy,
  type ChatState,
} from "@/services/threads/session.service";
import { updateThreadAccessPolicy } from "@/services/threads/access-policy.service";
import type { AgentContext } from "@/services/agents/types";
import { parseAgentContext } from "@/services/agents/context";
import {
  deriveMessagePreview,
  deriveThreadTitle,
} from "@/utils/thread-title";
import {
  enqueueThreadMessage,
  listThreadMessages,
  type MessageReceipt,
} from "@/services/threads/messages.service";
import { createRunActions } from "../run-actions";
import { createSessionAttachmentUploader } from "./useSessionAttachmentUpload";
import { useSessionInterrupts } from "./useSessionInterrupts";

const active = (run: Run | null) =>
  run != null && ["pending", "running"].includes(run.status);

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
  const accessPolicy = ref<AccessPolicy>("review");
  const accessPolicyUpdating = ref(false);
  const accessThread = shallowRef<ChatThread>();

  function applyAccessThread(thread: ChatThread | undefined) {
    accessThread.value = thread;
    if (thread?.metadata && typeof thread.metadata === "object") {
      const policy = (thread.metadata as Record<string, unknown>).access_policy;
      if (policy === "workspace_write" || policy === "full_access") {
        accessPolicy.value = policy;
      } else {
        accessPolicy.value = "review";
      }
    } else {
      accessPolicy.value = "review";
    }
  }

  const initialSeeded = unref(options.initialThread);
  if (hasResolvedAccess(initialSeeded, threadId.value)) {
    applyAccessThread(initialSeeded);
  }
  const accessLoading = ref(Boolean(threadId.value && !accessThread.value));
  const canRead = computed(() => !threadId.value || hasThreadAction(accessThread.value, "read"));
  let accessRefreshing = false;
  let accessEpoch = 0;
  const run = shallowRef<Run | null>(null);
  const checking = ref(true);
  const verified = ref(false);
  const cancelling = ref(false);
  const error = ref("");
  let disposed = false;
  let checkEpoch = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let releaseWait: (() => void) | undefined;

  const canAct = (action: ThreadAction) => threadId.value
    ? hasThreadAction(accessThread.value, action)
    : options.canWrite.value;
  const canComment = computed(() => options.canWrite.value && canAct("comment"));
  const canApprove = computed(() => canAct("approve"));
  const canEdit = computed(() => options.canWrite.value && canAct("edit"));
  const canSetPolicy = computed(() => options.canWrite.value && canAct("share"));
  const canFullAccess = computed(() => options.canWrite.value && canAct("full_access"));

  async function refreshAccessPolicy() {
    if (!threadId.value || disposed || accessRefreshing) return;
    const requestedThread = threadId.value;
    const requestedEpoch = accessEpoch;
    accessRefreshing = true;
    if (!accessThread.value) accessLoading.value = true;
    try {
      const thread = await service.get(requestedThread);
      if (disposed || threadId.value !== requestedThread || accessEpoch !== requestedEpoch) return;
      if (!disposed) applyAccessThread(thread);
    } catch {
      if (!disposed && threadId.value === requestedThread && accessEpoch === requestedEpoch) {
        accessThread.value = undefined;
        accessPolicy.value = "review";
        verified.value = false;
        receipts.value = [];
        pendingMessage.value = null;
        clearTimeout(receiptTimer);
        receiptController?.abort();
        receiptController = undefined;
        void stream.disconnect();
      }
    } finally {
      accessRefreshing = false;
      if (!disposed && requestedEpoch === accessEpoch) accessLoading.value = false;
      if (!disposed && (accessEpoch !== requestedEpoch || threadId.value !== requestedThread)) void refreshAccessPolicy();
    }
  }

  async function setAccessPolicy(policy: AccessPolicy) {
    if (policy === accessPolicy.value) return true;
    if (!canSetPolicy.value || (policy === "full_access" && !canFullAccess.value)) {
      fail(new Error("没有此会话的策略管理权限；全权模式仅限私人会话所有者"));
      return false;
    }
    if (busy.value || reviews.value.length || checking.value) {
      fail(new Error("会话执行或待审批中，无法切换访问策略"));
      return false;
    }

    if (!threadId.value) {
      accessPolicy.value = policy;
      return true;
    }

    accessPolicyUpdating.value = true;
    try {
      await updateThreadAccessPolicy(options.projectId, threadId.value, policy);
      if (!disposed) {
        accessPolicy.value = policy;
      }
      return true;
    } catch (cause) {
      if (!disposed) {
        fail(cause);
      }
      return false;
    } finally {
      if (!disposed) {
        accessPolicyUpdating.value = false;
      }
    }
  }

  const hydrated = ref(!threadId.value);
  watch(
    () => options.threadId,
    (next) => {
      if (next && next !== threadId.value) {
        threadId.value = next;
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
  const stream = useStream<ChatState>({
    assistantId: options.graphId,
    threadId: computed(() => threadId.value),
    client: service.client,
    fetch: actions.fetch,
    optimistic: false,
    onCompleted: () => {
      if (!disposed) {
        void verify(true);
      }
    },
  });
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
    stream,
    service,
    actions,
    verify: (force?: boolean) => verify(force),
    fail: (cause: unknown) => fail(cause),
  });
  const busy = computed(() => {
    if (
      run.value &&
      !active(run.value) &&
      !hasPendingInterrupts.value &&
      actions.current.value?.status !== "submitting"
    ) {
      return false;
    }
    return (
      stream.isLoading.value ||
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
      !checking.value &&
      !cancelling.value &&
      !pendingAction.value &&
      !(pendingMessage.value?.status === "sending") &&
      !busy.value &&
      !hasPendingInterrupts.value,
  );
  const status = computed(() =>
    cancelling.value
      ? "正在停止"
      : reviews.value.length
        ? "等待审批"
        : clarifications.value.length
          ? "等待补充信息"
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
                    : run.value?.status === "timeout"
                      ? "上一回合执行超时"
                      : "可以发送",
  );

  function fail(cause: unknown) {
    if (!disposed) {
      error.value = cause instanceof Error ? cause.message : "请求失败，请重试";
    }
  }
  let activeVerifyPromise: Promise<boolean> | undefined;
  let activeVerifyTerminal = false;
  let backgroundRunTimer: ReturnType<typeof setTimeout> | undefined;

  function scheduleBackgroundRunPoll(targetThreadId: string) {
    clearTimeout(backgroundRunTimer);
    if (disposed || threadId.value !== targetThreadId || !active(run.value)) return;
    backgroundRunTimer = setTimeout(async () => {
      if (disposed || threadId.value !== targetThreadId || stream.isLoading.value) return;
      try {
        const list = await service.runs(targetThreadId);
        if (disposed || threadId.value !== targetThreadId) return;
        const nextLatest = list.find((r) => active(r)) ?? list[0] ?? null;
        run.value = nextLatest;
        if (active(nextLatest)) {
          options.onRefresh();
          scheduleBackgroundRunPoll(targetThreadId);
        } else {
          options.onRefresh();
          await refreshAccessPolicy();
        }
      } catch {
        if (!disposed && threadId.value === targetThreadId && active(run.value)) {
          scheduleBackgroundRunPoll(targetThreadId);
        }
      }
    }, 1500);
  }

  async function verify(waitForTerminal = false): Promise<boolean> {
    if (disposed) return false;
    if (activeVerifyPromise && (!waitForTerminal || activeVerifyTerminal)) {
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
    verified.value = false;
    checking.value = true;
    activeVerifyTerminal = waitForTerminal;
    const id = threadId.value;
    let deadline = Date.now() + 30000;
    const p = (async () => {
      try {
        let attempt = 0;
        do {
          const actionRunId = actions.current.value?.runId;
          const activeKnownId = active(run.value) ? run.value?.run_id : undefined;
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
            if (
              !active(latest) &&
              stream.isLoading.value &&
              actions.current.value?.status !== "submitting" &&
              (!actionRunId || latest?.run_id === actionRunId)
            ) {
              void stream.disconnect();
            }
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
          if (waitForTerminal) {
            options.onRefresh();
          }
          if (!accessThread.value) {
            await refreshAccessPolicy();
          } else if (waitForTerminal) {
            void refreshAccessPolicy();
          }
          if (active(run.value) && !stream.isLoading.value) {
            scheduleBackgroundRunPoll(id);
          }
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
      if (disposed || controller !== receiptController || !canRead.value) return;
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
      !threadId.value ||
      cancelling.value ||
      reviews.value.length ||
      pendingMessage.value?.status === "sending"
    )
      return false;

    const allowFallbackSend = queueOptions?.allowFallbackSend ?? true;

    // 1. 严格检查活跃 run：只有明确处于 active 态的 run 才能作为追加目标
    let targetRunId = (run.value && active(run.value))
      ? run.value.run_id
      : (actions.current.value?.status === "submitting" ? actions.current.value.runId : undefined);

    // 2. 如果本地缓存未命中，始终向服务端查询最新的 running/pending 运行回合（即使本地 busy 因旧 verify 被误置为 false）
    if (!targetRunId) {
      try {
        const list = await service.client.runs.list(threadId.value, { limit: 5 });
        const runningItem = list?.find((r) => r.status === "running" || r.status === "pending");
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
      console.info("[session] 没有活跃中的运行回合，将排队消息自愈回退为直接发送");
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
        isAxiosError(cause) &&
        cause.response?.status === 409;

      if (is409RunEnded) {
        pendingMessage.value = null;
        error.value = "";
        await verify(true);
        if (!allowFallbackSend) {
          return false;
        }
        console.warn("[session] 目标回合已结束(409)，排队消息无感自愈转为新回合发送");
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
  const refreshVisibleAccess = () => {
    if (!document.hidden) void refreshAccessPolicy();
  };
  const accessChanged = () => {
    ++accessEpoch;
    accessThread.value = undefined;
    refreshVisibleAccess();
  };
  const accessTimer = setInterval(refreshVisibleAccess, 60_000);
  document.addEventListener("visibilitychange", refreshVisibleAccess);
  window.addEventListener("focus", refreshVisibleAccess);
  window.addEventListener("platform-access-denied", refreshVisibleAccess);
  window.addEventListener("thread-access-updated", accessChanged);
  watch(run, () => void refreshReceipts());

  async function send(
    content: unknown,
    recursionLimit = 1000,
    sendOptions?: { fromQueue?: boolean },
  ): Promise<boolean> {
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
      if (threadId.value && (busy.value || active(run.value) || actions.current.value?.status === "submitting")) {
        if (sendOptions?.fromQueue || supportsQueue) {
          return false;
        }
        throw new Error("当前回合正在执行中，请等待完成或停止后再发送");
      }
      const messageContent = await prepareMessageAttachments(threadId.value, content);
      if (disposed || !canComment.value) return false;
      const inputMessageId = crypto.randomUUID();
      const input = {
        messages: [{ id: inputMessageId, type: "human", content: messageContent }],
      };
      const removeUncommittedMessage = () => {
        const streamMessages = (stream as unknown as { messages?: { value?: Array<{ id?: string }> } }).messages;
        if (streamMessages && Array.isArray(streamMessages.value)) {
          streamMessages.value = streamMessages.value.filter((m) => m?.id !== inputMessageId);
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
          const raw = cause instanceof Error ? cause.message : String(cause);
          const is409 = raw.includes("409 Conflict") || raw.includes("pending or running run");
          if (is409 && attempts < maxAttempts) {
            actions.rejectUnsent();
            removeUncommittedMessage();
            console.warn(`[session] 遇到服务端短暂运行冲突 (409)，正在进行第 ${attempts} 次退避重试...`);
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
              actions.acknowledge(actions.current.value.key, actions.current.value?.runId ?? run.value?.run_id);
            }
            return true;
          }
          actions.rejectUnsent();
          removeUncommittedMessage();
          fail(cause);
          return false;
        }
      }
      return false;
    } finally {
      if (!disposed) checking.value = false;
    }
  }

  async function stop() {
    if (
      !canEdit.value ||
      cancelling.value ||
      pendingAction.value ||
      !threadId.value
    )
      return;
    cancelling.value = true;
    try {
      // stream 仍在传输时，服务端 run 可能已终态但前端尚未感知；
      // 优先复用已知 runId，跳过前置 verify 避免把终态覆写进 run.value。
      const knownRunId = actions.current.value?.runId ?? run.value?.run_id;
      if (knownRunId && stream.isLoading.value) {
        await service.cancel(threadId.value, knownRunId);
        void stream.disconnect();
        await verify(true);
        return;
      }
      if (!(await verify())) return;
      if (disposed || !canEdit.value) return;
      const runId = run.value?.run_id;
      // run 已终态说明 Agent 刚刚执行完，停止操作自然完成，静默刷新即可。
      if (!runId || !active(run.value)) {
        void stream.disconnect();
        await verify(true);
        return;
      }
      await service.cancel(threadId.value, runId);
      void stream.disconnect();
      await verify(true);
    } catch (cause) {
      fail(cause);
    } finally {
      if (!disposed) cancelling.value = false;
    }
  }

  async function retry() {
    if (actions.current.value?.kind === "resume" ? !canApprove.value : !canComment.value) return;
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
  ) {
    if (!canSend.value || !threadId.value || !checkpoint?.checkpoint_id) return false;
    const checkpointId = checkpoint.checkpoint_id;
    error.value = "";
    checking.value = true;
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
            messages: [{ id: crypto.randomUUID(), type: "human", content: messageContent }],
          }
        : null;

      const context = parseAgentContext(options.context.value);
      const action = actions.begin(threadId.value, "fork", {
        input,
        checkpoint_id: checkpointId,
      });

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
      if (!disposed) checking.value = false;
    }
  }

  watch(actions.current, (action, previous) => {
    if (disposed) return;
    if (
      action?.status === "acknowledged" &&
      (previous?.key !== action.key || previous.status !== "acknowledged")
    ) {
      if (action.kind === "send" || action.kind === "fork") options.onAccepted?.();
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
    clearTimeout(receiptTimer);
    clearTimeout(backgroundRunTimer);
    receiptController?.abort();
    document.removeEventListener("visibilitychange", receiptVisibility);
    clearInterval(accessTimer);
    document.removeEventListener("visibilitychange", refreshVisibleAccess);
    window.removeEventListener("focus", refreshVisibleAccess);
    window.removeEventListener("platform-access-denied", refreshVisibleAccess);
    window.removeEventListener("thread-access-updated", accessChanged);
    clearTimeout(timer);
    releaseWait?.();
    void stream.disconnect();
    actions.dispose();
  });
  return {
    canRead, canComment, canApprove, canEdit, canSetPolicy, canFullAccess,
    accessLoading,
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
    error,
    busy,
    canSend,
    status,
    send,
    approve,
    answerClarification,
    resumeClarification,
    stop,
    retry,
    fork,
    verify,
  };
}
