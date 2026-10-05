import {
  computed,
  getCurrentScope,
  onScopeDispose,
  ref,
  shallowRef,
  unref,
  watch,
  type ComputedRef,
  type Ref,
  type ShallowRef,
} from "vue";
import { useStream } from "@langchain/vue";
import type { Run } from "@langchain/langgraph-sdk";
import {
  hasThreadAction,
  type ChatThread,
  type ThreadAction,
  type AccessPolicy,
  type ChatState,
  type createSessionService,
} from "@/services/threads/session.service";
import { updateThreadAccessPolicy } from "@/services/threads/access-policy.service";
import type { createRunActions } from "../run-actions";
import { useChatSessionStore } from "../stores/useChatSessionStore";
import { accessDeniedDetail } from "@/services/auth/access-events";
import { extractPlatformHttpError } from "@/utils/http-error";

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

export interface UseSessionConnectionOptions {
  projectId: string;
  userId?: string;
  graphId: string;
  threadId: Ref<string | null>;
  canWrite: Ref<boolean>;
  visible?: Ref<boolean | undefined>;
  service: ReturnType<typeof createSessionService>;
  actions: ReturnType<typeof createRunActions>;
  initialThread?: ChatThread | Ref<ChatThread | undefined>;
  run: ShallowRef<Run | null>;
  busy: ComputedRef<boolean>;
  checking: Ref<boolean>;
  hasPendingReviews: ComputedRef<boolean>;
  hydrated: Ref<boolean>;
  error?: Ref<string>;
  getCheckEpoch: () => number;
  onVerify: (silent?: boolean) => Promise<unknown>;
  onFail: (err: unknown) => void;
  onAccessRevoked?: () => void;
  onClearReceipts?: () => void;
}

export function useSessionConnection(options: UseSessionConnectionOptions) {
  const chatSessionStore = useChatSessionStore();
  const accessPolicy = ref<AccessPolicy>("review");
  const accessPolicyUpdating = ref(false);
  const accessThread = shallowRef<ChatThread>();
  const accessDenied = ref(false);
  const accessUncertain = ref(false);
  let accessRefreshing = false;
  let accessEpoch = 0;
  let disposed = false;
  let accessTimer: ReturnType<typeof setInterval> | undefined;
  let lastAccessRefresh = 0;

  const refreshVisibleAccess = () => {
    if (
      typeof document !== "undefined" &&
      !document.hidden &&
      options.visible?.value !== false &&
      (!lastAccessRefresh || Date.now() - lastAccessRefresh >= 10_000)
    ) {
      void refreshAccessPolicy();
    }
  };

  const handleAccessDenied = (event: Event) => {
    const detail = accessDeniedDetail(event);
    if (
      detail?.scope === "thread" &&
      detail.projectId === options.projectId &&
      detail.threadId === options.threadId.value
    ) {
      if (!lastAccessRefresh || Date.now() - lastAccessRefresh >= 10_000)
        void refreshAccessPolicy();
    }
  };

  const notifyAccessChanged = () => {
    ++accessEpoch;
    accessThread.value = undefined;
    refreshVisibleAccess();
  };

  if (typeof window !== "undefined") {
    // 保活的后台会话仍须周期性核对撤权；聚焦事件只唤醒当前可见会话。
    accessTimer = setInterval(() => {
      if (!document.hidden) void refreshAccessPolicy();
    }, 60_000);
    document.addEventListener("visibilitychange", refreshVisibleAccess);
    window.addEventListener("focus", refreshVisibleAccess);
    window.addEventListener("platform-access-denied", handleAccessDenied);
    window.addEventListener("thread-access-updated", notifyAccessChanged);
  }

  if (getCurrentScope()) {
    onScopeDispose(() => {
      disposed = true;
      connectionUnsubscribe?.();
      if (accessTimer) clearInterval(accessTimer);
      if (typeof window !== "undefined") {
        document.removeEventListener("visibilitychange", refreshVisibleAccess);
        window.removeEventListener("focus", refreshVisibleAccess);
        window.removeEventListener(
          "platform-access-denied",
          handleAccessDenied,
        );
        window.removeEventListener(
          "thread-access-updated",
          notifyAccessChanged,
        );
      }
    });
  }

  watch(
    () => options.visible?.value,
    (visible) => {
      if (visible !== false) refreshVisibleAccess();
    },
  );

  const normalizedThreadId = computed<string | null>(() => {
    const raw = options.threadId.value;
    return typeof raw === "string" && raw.trim().length > 0 ? raw.trim() : null;
  });

  function applyAccessThread(thread: ChatThread | undefined) {
    accessThread.value = thread;
    if (thread && normalizedThreadId.value) {
      chatSessionStore.setSessionThread(
        options.projectId,
        normalizedThreadId.value,
        thread,
      );
    }
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

  const cachedEntry = normalizedThreadId.value
    ? chatSessionStore.getSession(options.projectId, normalizedThreadId.value)
    : undefined;
  const initialSeeded = unref(options.initialThread) ?? cachedEntry?.thread;
  if (hasResolvedAccess(initialSeeded, normalizedThreadId.value)) {
    applyAccessThread(initialSeeded);
  }
  const hasCachedContent = Boolean(
    cachedEntry &&
    (cachedEntry.messages.length > 0 || cachedEntry.history.length > 0),
  );
  const accessLoading = ref(
    Boolean(
      normalizedThreadId.value && !accessThread.value && !hasCachedContent,
    ),
  );

  const canRead = computed(
    () =>
      !accessDenied.value &&
      (!normalizedThreadId.value ||
        hasThreadAction(accessThread.value, "read") ||
        hasCachedContent),
  );

  const canAct = (action: ThreadAction) =>
    accessDenied.value || accessUncertain.value
      ? false
      : normalizedThreadId.value
        ? hasThreadAction(accessThread.value, action)
        : options.canWrite.value;

  const canComment = computed(
    () => options.canWrite.value && canAct("comment"),
  );
  const canApprove = computed(
    () => canAct("approve") && connectionState.value !== "paused",
  );
  const canEdit = computed(() => options.canWrite.value && canAct("edit"));
  const canSetPolicy = computed(
    () => options.canWrite.value && canAct("share"),
  );
  const canFullAccess = computed(
    () => options.canWrite.value && canAct("full_access"),
  );

  async function refreshAccessPolicy() {
    if (!normalizedThreadId.value || disposed || accessRefreshing) return;
    const requestedThread = normalizedThreadId.value;
    const requestedEpoch = accessEpoch;
    accessRefreshing = true;
    lastAccessRefresh = Date.now();
    if (!accessThread.value) accessLoading.value = true;
    try {
      const thread = await options.service.get(requestedThread);
      if (
        disposed ||
        normalizedThreadId.value !== requestedThread ||
        accessEpoch !== requestedEpoch
      )
        return;
      if (!disposed) applyAccessThread(thread);
      if (!hasThreadAction(thread, "read")) {
        accessDenied.value = true;
        chatSessionStore.removeSession(options.projectId, requestedThread);
        void stream.disconnect();
        options.onAccessRevoked?.();
      } else {
        accessDenied.value = false;
        accessUncertain.value = false;
      }
    } catch (cause) {
      if (
        !disposed &&
        normalizedThreadId.value === requestedThread &&
        accessEpoch === requestedEpoch
      ) {
        const { status, code } = extractPlatformHttpError(cause);
        if (status === 403 || (status === 404 && code !== "route_not_found")) {
          accessDenied.value = true;
          accessThread.value = undefined;
          accessPolicy.value = "review";
          options.onClearReceipts?.();
          chatSessionStore.removeSession(options.projectId, requestedThread);
          void stream.disconnect();
          options.onAccessRevoked?.();
        } else {
          accessUncertain.value = true;
        }
      }
    } finally {
      accessRefreshing = false;
      if (!disposed && requestedEpoch === accessEpoch)
        accessLoading.value = false;
      if (
        !disposed &&
        (accessEpoch !== requestedEpoch ||
          normalizedThreadId.value !== requestedThread)
      )
        void refreshAccessPolicy();
    }
  }

  async function setAccessPolicy(policy: AccessPolicy) {
    if (policy === accessPolicy.value) return true;
    if (
      !canSetPolicy.value ||
      (policy === "full_access" && !canFullAccess.value)
    ) {
      options.onFail(
        new Error("没有此会话的策略管理权限；全权模式仅限私人会话所有者"),
      );
      return false;
    }
    if (
      options.busy.value ||
      options.hasPendingReviews.value ||
      options.checking.value
    ) {
      options.onFail(new Error("会话执行或待审批中，无法切换访问策略"));
      return false;
    }

    if (!normalizedThreadId.value) {
      accessPolicy.value = policy;
      return true;
    }

    accessPolicyUpdating.value = true;
    try {
      await updateThreadAccessPolicy(
        options.projectId,
        normalizedThreadId.value,
        policy,
      );
      if (!disposed) {
        accessPolicy.value = policy;
      }
      return true;
    } catch (cause) {
      if (!disposed) {
        options.onFail(cause);
      }
      return false;
    } finally {
      if (!disposed) {
        accessPolicyUpdating.value = false;
      }
    }
  }

  const stream = useStream<ChatState>({
    assistantId: options.graphId,
    threadId: normalizedThreadId,
    client: options.service.client,
    fetch: options.actions.fetch,
    optimistic: false,
    onCompleted: () => {
      if (!disposed) {
        void options.onVerify(true);
      }
    },
  });

  const connectionState = ref("connecting");
  const eventsParked = ref(false);
  const recoverySnapshot = shallowRef<ChatState | null>(null);
  let connectionUnsubscribe: (() => void) | undefined;
  let subscribedThread: ReturnType<typeof stream.getThread>;
  let recoveryPromise: Promise<void> | undefined;

  function parkEvents() {
    const thread = stream.getThread?.();
    if (!thread || typeof thread.suspendEvents !== "function") return;
    eventsParked.value = true;
    thread.suspendEvents();
  }

  function bindConnectionState() {
    const thread = stream.getThread?.();
    if (!thread || thread === subscribedThread) return;
    if (typeof thread.onConnectionChange !== "function") return;
    connectionUnsubscribe?.();
    subscribedThread = thread;
    connectionUnsubscribe = thread.onConnectionChange((state) => {
      if (disposed) return;
      connectionState.value = state.state;
      // SDK 在后台提交或投影变化时仍可能新建订阅；等握手完成再暂停，
      // 避免挂起 ready Promise，同时释放新连接占用的浏览器连接槽。
      if (
        options.visible?.value === false &&
        state.streams.some((item) => item.state === "connected") &&
        state.streams.every(
          (item) =>
            item.state !== "connecting" && item.state !== "reconnecting",
        )
      ) {
        parkEvents();
      }
      if (
        state.streams.some((item) =>
          [403, 404].includes(
            (item.error as Error & { status?: number })?.status ?? 0,
          ),
        )
      ) {
        // SSE 子资源错误先核对 Thread，不能把单个 Run 的 404 当成整个会话撤权。
        void refreshAccessPolicy();
        return;
      }
      if (
        state.streams.some(
          (item) =>
            (item.error as Error & { status?: number; code?: string })
              ?.status === 410 ||
            (item.error as Error & { code?: string })?.code ===
              "cursor_expired",
        )
      ) {
        void recoverExpiredStream();
      }
    });
  }

  async function recoverExpiredStream() {
    if (recoveryPromise) return recoveryPromise;
    const thread = stream.getThread?.();
    const id = normalizedThreadId.value;
    if (!thread || !id || disposed) return;
    const epoch = options.getCheckEpoch();
    const currentRunId = options.run.value?.run_id;
    recoveryPromise = Promise.resolve()
      .then(async () => {
        thread.suspendEvents();
        const access = await options.service.get(id);
        if (disposed || normalizedThreadId.value !== id) return;
        if (!hasThreadAction(access, "read")) {
          accessDenied.value = true;
          chatSessionStore.removeSession(options.projectId, id);
          void stream.disconnect();
          options.onAccessRevoked?.();
          return;
        }
        if (epoch !== options.getCheckEpoch()) {
          await options.onVerify(false);
          if (!disposed && normalizedThreadId.value === id && canRead.value)
            await thread.reconnectEvents();
          return;
        }
        const snapshot = await options.service.state(id);
        if (disposed || normalizedThreadId.value !== id) return;
        if (
          epoch !== options.getCheckEpoch() ||
          currentRunId !== options.run.value?.run_id
        ) {
          await options.onVerify(false);
          if (!disposed && normalizedThreadId.value === id && canRead.value)
            await thread.reconnectEvents();
          return;
        }
        applyAccessThread(access);
        recoverySnapshot.value = snapshot.values;
        if (options.error) {
          options.error.value =
            "历史流已过期，已刷新当前状态；部分过程无法恢复";
        }
        void options.service
          .history(id)
          .then((history) => {
            if (!disposed && normalizedThreadId.value === id && history) {
              chatSessionStore.setSessionHistory(
                options.projectId,
                id,
                history,
              );
            }
          })
          .catch((historyErr) => {
            console.warn(
              `[recoverExpiredStream] Non-blocking history preheat failed for thread ${id}:`,
              historyErr,
            );
          });
        await thread.reconnectEvents();
      })
      .catch((cause) => {
        if (
          !disposed &&
          [403, 404].includes((cause as { status?: number })?.status ?? 0)
        ) {
          void refreshAccessPolicy();
        } else if (!disposed) options.onFail(cause);
      })
      .finally(() => {
        recoveryPromise = undefined;
      });
    return recoveryPromise;
  }

  async function reconnectStream() {
    if (options.visible?.value === false) {
      parkEvents();
      return;
    }
    bindConnectionState();
    const thread = stream.getThread?.();
    if (!thread) return;
    eventsParked.value = false;
    const connState = thread.getConnectionState();
    if (
      connState.streams.some(
        (item) => (item.error as Error & { status?: number })?.status === 410,
      )
    ) {
      await recoverExpiredStream();
    } else if (
      connState.state === "paused" ||
      connState.streams.some((item) => item.state === "paused")
    ) {
      await thread.reconnectEvents();
    }
  }

  watch(
    [normalizedThreadId, stream.isLoading, options.hydrated],
    bindConnectionState,
    { immediate: true },
  );

  return {
    stream,
    connectionState,
    eventsParked,
    parkEvents,
    recoverySnapshot,
    accessPolicy,
    accessPolicyUpdating,
    accessThread,
    accessDenied,
    accessUncertain,
    accessLoading,
    canRead,
    canAct,
    canComment,
    canApprove,
    canEdit,
    canSetPolicy,
    canFullAccess,
    applyAccessThread,
    refreshAccessPolicy,
    refreshVisibleAccess,
    notifyAccessChanged,
    setAccessPolicy,
    bindConnectionState,
    recoverExpiredStream,
    reconnectStream,
  };
}
