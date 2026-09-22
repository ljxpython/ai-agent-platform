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
import {
  buildReviewResponses,
  parseReviews,
  type ReviewDraft,
} from "../approvals";
import {
  buildClarificationResponse,
  parseClarifications,
} from "../human-input";
import {
  calculateFileSha256 as calculateImageSha256,
  uploadThreadImage,
} from "@/services/threads/images.service";
import {
  calculateFileSha256,
  uploadThreadFile,
} from "@/services/threads/files.service";
import {
  createRuntimeFileTextBlock,
  createRuntimeImageTextBlock,
} from "@/utils/chat-content";

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
  const accessPolicy = ref<AccessPolicy>("review");
  const accessPolicyUpdating = ref(false);
  const accessThread = shallowRef<ChatThread>();
  const canRead = computed(() => !threadId.value || hasThreadAction(accessThread.value, "read"));
  let accessRefreshing = false;
  let accessEpoch = 0;
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
    try {
      const thread = await service.get(requestedThread);
      if (disposed || threadId.value !== requestedThread || accessEpoch !== requestedEpoch) return;
      if (!disposed) accessThread.value = thread;
      if (!disposed && thread?.metadata && typeof thread.metadata === "object") {
        const policy = (thread.metadata as Record<string, unknown>).access_policy;
        if (policy === "workspace_write" || policy === "full_access") {
          accessPolicy.value = policy;
        } else {
          accessPolicy.value = "review";
        }
      } else if (!disposed) {
        accessPolicy.value = "review";
      }
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

  watch(
    () => options.threadId,
    (next) => {
      if (next && next !== threadId.value) {
        threadId.value = next;
        void refreshAccessPolicy();
      } else if (!next) {
        threadId.value = null;
      }
    },
    { immediate: true },
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
      if (!disposed) {
        void verify(true);
      }
    },
  });
  const rawInterrupts = computed(() => stream.interrupts.value);
  const reviews = computed(() => parseReviews(rawInterrupts.value));
  const clarifications = computed(() =>
    parseClarifications(rawInterrupts.value),
  );
  const hasPendingInterrupts = computed(
    () => reviews.value.length > 0 || clarifications.value.length > 0,
  );
  const pendingAction = computed(() =>
    ["submitting", "unknown"].includes(actions.current.value?.status ?? ""),
  );
  const busy = computed(() => stream.isLoading.value || active(run.value));
  const canSend = computed(
    () =>
      canComment.value &&
      verified.value &&
      !stream.error.value &&
      !checking.value &&
      !cancelling.value &&
      !pendingAction.value &&
      !pendingMessage.value &&
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
    let deadline = Date.now() + 30000;
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
          // 流式通道活跃时持续顺延超时判定，避免长任务或多步图输出过程中误判
          if (stream.isLoading.value) {
            deadline = Date.now() + 30000;
          }
          // 仅在数据流已非传输状态且超时后，才提示未能确认运行结果；切标签页（document.hidden）不再误判
          if (!stream.isLoading.value && Date.now() >= deadline) {
            throw new Error("运行结果尚未确认，请恢复连接后核实");
          }
          const delay = document.hidden
            ? 3000
            : Math.min(500 * 2 ** attempt++, 4000);
          await new Promise<void>((resolve) => {
            releaseWait = resolve;
            timer = setTimeout(resolve, delay);
          });
        } while (!disposed && epoch === checkEpoch);
        if (!disposed && epoch === checkEpoch) {
          verified.value = true;
          error.value = "";
          options.onRefresh();
          await refreshAccessPolicy();
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

  function hasAttachmentsToUpload(rawContent: unknown): boolean {
    if (!Array.isArray(rawContent)) return false;
    return rawContent.some(
      (item) =>
        item &&
        typeof item === "object" &&
        ["image", "file"].includes((item as Record<string, unknown>).type as string) &&
        (item as Record<string, unknown>).file instanceof Blob,
    );
  }

  async function uploadAttachmentsAsync(
    targetThreadId: string,
    rawContent: unknown[],
  ): Promise<unknown> {
    const prepared = await Promise.all(
      rawContent.map(async (item) => {
        if (!item || typeof item !== "object") return item;
        const block = item as Record<string, unknown>;
        if (block.type === "image" && block.file instanceof Blob) {
          const file = block.file;
          const metadata = (block.metadata || {}) as Record<string, unknown>;
          const filename =
            typeof metadata.name === "string"
              ? metadata.name
              : typeof metadata.filename === "string"
                ? metadata.filename
                : "image.png";
          const sha256 = await calculateImageSha256(file);
          const ref = await uploadThreadImage(
            options.projectId,
            targetThreadId,
            sha256,
            file,
          );
          return createRuntimeImageTextBlock(filename, ref);
        }
        if (block.type === "file" && block.file instanceof Blob) {
          const file = block.file as File;
          const metadata = (block.metadata || {}) as Record<string, unknown>;
          const filename =
            typeof metadata.name === "string"
              ? metadata.name
              : typeof metadata.filename === "string"
                ? metadata.filename
                : file.name || "document";
          const sha256 = await calculateFileSha256(file);
          const ref = await uploadThreadFile(
            options.projectId,
            targetThreadId,
            sha256,
            file,
          );
          return createRuntimeFileTextBlock(filename, ref);
        }
        return item;
      }),
    );
    return prepared;
  }

  function prepareMessageAttachments(
    targetThreadId: string,
    rawContent: unknown,
  ): unknown | Promise<unknown> {
    if (!hasAttachmentsToUpload(rawContent)) {
      return rawContent;
    }
    return uploadAttachmentsAsync(targetThreadId, rawContent as unknown[]);
  }

  async function queueMessage(content?: unknown) {
    if (
      !supportsQueue ||
      !canComment.value ||
      !threadId.value ||
      cancelling.value ||
      reviews.value.length ||
      pendingMessage.value?.status === "sending"
    )
      return false;
    if (!pendingMessage.value) {
      const targetRunId = actions.current.value?.runId ?? run.value?.run_id;
      if (!busy.value || !targetRunId) return false;
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

  async function send(content: unknown, recursionLimit = 1000) {
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
      const messageContent = await prepareMessageAttachments(threadId.value, content);
      if (disposed || !canComment.value) return false;
      const input = {
        messages: [{ id: crypto.randomUUID(), type: "human", content: messageContent }],
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
      !canApprove.value ||
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
      if (disposed || !canApprove.value) return;
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

  async function answerClarification(
    interruptId: string,
    values: Record<string, unknown>,
  ) {
    if (
      !canApprove.value ||
      checking.value ||
      pendingAction.value ||
      !threadId.value
    )
      return;
    const targetClarification = clarifications.value.find(
      (c) => c.id === interruptId,
    );
    if (!targetClarification) return;
    checking.value = true;
    error.value = "";
    try {
      const response = buildClarificationResponse(
        targetClarification.id,
        values,
        targetClarification.request.schema_version,
        targetClarification.raw,
      );
      actions.begin(threadId.value, "resume", response);
      await stream.respondAll(response);
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
        await verify(true);
        if (!disposed && !active(run.value)) options.onReconnect();
        return;
      }
      if (!(await verify())) return;
      if (disposed || !canEdit.value) return;
      const runId = run.value?.run_id;
      // run 已终态说明 Agent 刚刚执行完，停止操作自然完成，静默刷新即可。
      if (!runId || !active(run.value)) {
        await verify(true);
        if (!disposed && !active(run.value)) options.onReconnect();
        return;
      }
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
    stop,
    retry,
    fork,
    verify,
  };
}
