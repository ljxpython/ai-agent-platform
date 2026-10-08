import {
  computed,
  ref,
  shallowRef,
  watch,
  getCurrentScope,
  onScopeDispose,
  type Ref,
  type ComputedRef,
} from "vue";
import { getRunUsage, getThreadUsage } from "@/services/threads/usage.service";
import type { RunUsageV1, ThreadUsageV1, UsageCallV1 } from "../usage/types";
import type { PlatformHttpError } from "@/utils/http-error";

export interface UseRunUsageOptions {
  projectId?:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  threadId:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  runId:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  runStatus?:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  canRead?: Ref<boolean> | ComputedRef<boolean>;
  enabled?: Ref<boolean> | ComputedRef<boolean>;
}

export function useRunUsage(options: UseRunUsageOptions) {
  // Run 维度状态
  const runData = shallowRef<RunUsageV1 | null>(null);
  const runLoading = ref(false);
  const isRunRefreshing = ref(false);
  const runError = shallowRef<PlatformHttpError | Error | null>(null);

  // Calls 分页状态
  const calls = ref<UsageCallV1[]>([]);
  const nextCursor = ref<string | null>(null);
  const loadingMore = ref(false);
  const loadMoreError = shallowRef<Error | null>(null);

  // Thread 维度状态
  const threadData = shallowRef<ThreadUsageV1 | null>(null);
  const threadLoading = ref(false);
  const isThreadRefreshing = ref(false);
  const threadError = shallowRef<PlatformHttpError | Error | null>(null);

  // 竞态与控制变量
  let currentRunEpoch = 0;
  let currentThreadEpoch = 0;
  let activeRunAbortController: AbortController | null = null;
  let activeThreadAbortController: AbortController | null = null;
  let delayedRetryTimer: ReturnType<typeof setTimeout> | null = null;
  const hasDelayedRetried = ref(false);

  const isEnabled = computed(() => options.enabled?.value ?? true);
  const canAccess = computed(() => options.canRead?.value ?? true);

  function clearDelayedTimer() {
    if (delayedRetryTimer) {
      clearTimeout(delayedRetryTimer);
      delayedRetryTimer = null;
    }
  }

  function abortRunRequest() {
    if (activeRunAbortController) {
      activeRunAbortController.abort();
      activeRunAbortController = null;
    }
    clearDelayedTimer();
  }

  function abortThreadRequest() {
    if (activeThreadAbortController) {
      activeThreadAbortController.abort();
      activeThreadAbortController = null;
    }
  }

  function abortAll() {
    abortRunRequest();
    abortThreadRequest();
  }

  /**
   * 拉取指定 Run 用量
   */
  async function fetchRun(isManualRefresh = false): Promise<void> {
    const pId = options.projectId?.value ?? undefined;
    const tId = options.threadId.value;
    const rId = options.runId.value;

    if (!tId || !rId || !canAccess.value || !isEnabled.value) {
      abortRunRequest();
      if (!isManualRefresh) {
        runData.value = null;
        calls.value = [];
        nextCursor.value = null;
        runError.value = null;
      }
      runLoading.value = false;
      isRunRefreshing.value = false;
      return;
    }

    abortRunRequest();
    const epoch = ++currentRunEpoch;
    const controller = new AbortController();
    activeRunAbortController = controller;

    if (isManualRefresh && runData.value) {
      isRunRefreshing.value = true;
    } else {
      runLoading.value = true;
    }
    runError.value = null;

    try {
      const result = await getRunUsage(tId, rId, {
        projectId: pId ?? undefined,
        limit: 50,
        signal: controller.signal,
      });

      if (
        epoch !== currentRunEpoch ||
        options.threadId.value !== tId ||
        options.runId.value !== rId
      ) {
        return;
      }

      runData.value = result;
      calls.value = result.calls.items;
      nextCursor.value = result.calls.next_cursor;
      runError.value = null;
    } catch (err: any) {
      if (controller.signal.aborted) return;
      if (
        epoch !== currentRunEpoch ||
        options.threadId.value !== tId ||
        options.runId.value !== rId
      ) {
        return;
      }

      const status = Number(err?.status);
      if (status === 401 || status === 403 || status === 404) {
        runData.value = null;
        calls.value = [];
        nextCursor.value = null;
      }
      runError.value = err instanceof Error ? err : new Error(String(err));
    } finally {
      if (epoch === currentRunEpoch) {
        runLoading.value = false;
        isRunRefreshing.value = false;
        if (activeRunAbortController === controller) {
          activeRunAbortController = null;
        }
      }
    }
  }

  /**
   * 加载更多调用明细 (基于 keyset cursor 分页)
   */
  async function loadMoreCalls(): Promise<void> {
    if (loadingMore.value || !nextCursor.value) return;

    const pId = options.projectId?.value ?? undefined;
    const tId = options.threadId.value;
    const rId = options.runId.value;

    if (!tId || !rId || !canAccess.value || !isEnabled.value) return;

    loadingMore.value = true;
    loadMoreError.value = null;
    const epoch = currentRunEpoch;

    try {
      const result = await getRunUsage(tId, rId, {
        projectId: pId ?? undefined,
        limit: 50,
        cursor: nextCursor.value,
      });

      if (
        epoch !== currentRunEpoch ||
        options.threadId.value !== tId ||
        options.runId.value !== rId
      ) {
        return;
      }

      // 按 model_call_id 去重合并追加
      const existingIds = new Set(calls.value.map((c) => c.model_call_id));
      const newItems = result.calls.items.filter(
        (c) => !existingIds.has(c.model_call_id),
      );
      calls.value = [...calls.value, ...newItems];
      nextCursor.value = result.calls.next_cursor;
      loadMoreError.value = null;
    } catch (err: unknown) {
      loadMoreError.value = err instanceof Error ? err : new Error(String(err));
    } finally {
      loadingMore.value = false;
    }
  }

  /**
   * 拉取 Thread 累计摘要
   */
  async function fetchThread(isManualRefresh = false): Promise<void> {
    const pId = options.projectId?.value ?? undefined;
    const tId = options.threadId.value;

    if (!tId || !canAccess.value || !isEnabled.value) {
      abortThreadRequest();
      if (!isManualRefresh) {
        threadData.value = null;
        threadError.value = null;
      }
      threadLoading.value = false;
      isThreadRefreshing.value = false;
      return;
    }

    abortThreadRequest();
    const epoch = ++currentThreadEpoch;
    const controller = new AbortController();
    activeThreadAbortController = controller;

    if (isManualRefresh && threadData.value) {
      isThreadRefreshing.value = true;
    } else {
      threadLoading.value = true;
    }
    threadError.value = null;

    try {
      const result = await getThreadUsage(tId, {
        projectId: pId ?? undefined,
        signal: controller.signal,
      });

      if (epoch !== currentThreadEpoch || options.threadId.value !== tId) {
        return;
      }

      threadData.value = result;
      threadError.value = null;
    } catch (err: any) {
      if (controller.signal.aborted) return;
      if (epoch !== currentThreadEpoch || options.threadId.value !== tId) {
        return;
      }

      const status = Number(err?.status);
      if (status === 401 || status === 403 || status === 404) {
        threadData.value = null;
      }
      threadError.value = err instanceof Error ? err : new Error(String(err));
    } finally {
      if (epoch === currentThreadEpoch) {
        threadLoading.value = false;
        isThreadRefreshing.value = false;
        if (activeThreadAbortController === controller) {
          activeThreadAbortController = null;
        }
      }
    }
  }

  /**
   * 刷新全部 (Run + Thread)
   */
  async function refresh(): Promise<void> {
    await Promise.allSettled([fetchRun(true), fetchThread(true)]);
  }

  // 1. 监听 threadId 变动：清空全部，重新拉取二者
  watch(
    () => options.threadId.value,
    (newThreadId) => {
      hasDelayedRetried.value = false;
      clearDelayedTimer();
      if (!newThreadId) {
        abortAll();
        runData.value = null;
        calls.value = [];
        nextCursor.value = null;
        threadData.value = null;
        return;
      }
      void fetchRun(false);
      void fetchThread(false);
    },
    { immediate: true },
  );

  // 2. 监听 runId 变动：切 Run 时重置 Run 数据并拉取新 Run，保留同 Thread 摘要
  watch(
    () => options.runId.value,
    (newRunId, oldRunId) => {
      if (newRunId === oldRunId) return;
      hasDelayedRetried.value = false;
      clearDelayedTimer();
      abortRunRequest();
      runData.value = null;
      calls.value = [];
      nextCursor.value = null;
      runError.value = null;
      loadMoreError.value = null;
      void fetchRun(false);
    },
  );

  // 3. 监听 projectId 变动：切换项目时清空所有数据并重新拉取
  watch(
    () => options.projectId?.value,
    (newProjectId, oldProjectId) => {
      if (newProjectId === oldProjectId) return;
      hasDelayedRetried.value = false;
      clearDelayedTimer();
      abortAll();
      runData.value = null;
      calls.value = [];
      nextCursor.value = null;
      runError.value = null;
      loadMoreError.value = null;
      threadData.value = null;
      threadError.value = null;
      void fetchRun(false);
      void fetchThread(false);
    },
  );

  // 4. 监听权限与启用状态
  watch([canAccess, isEnabled], ([can, en]) => {
    if (!can || !en) {
      abortAll();
      runData.value = null;
      calls.value = [];
      nextCursor.value = null;
      threadData.value = null;
    } else {
      void fetchRun(false);
      void fetchThread(false);
    }
  });

  // 5. 监听 Run 状态转为结束态时的单次 2 秒延迟重查 (死循环防护锁)
  watch(
    () => options.runStatus?.value,
    (newStatus, oldStatus) => {
      const isTerminal =
        newStatus === "completed" ||
        newStatus === "failed" ||
        newStatus === "cancelled" ||
        newStatus === "interrupted" ||
        newStatus === "success" ||
        newStatus === "error";
      const wasRunning =
        oldStatus === "running" || oldStatus === "pending" || !oldStatus;

      if (
        isTerminal &&
        wasRunning &&
        !hasDelayedRetried.value &&
        runData.value &&
        !runData.value.finalized
      ) {
        hasDelayedRetried.value = true;
        clearDelayedTimer();
        delayedRetryTimer = setTimeout(() => {
          void refresh();
        }, 2000);
      }
    },
  );

  if (getCurrentScope()) {
    onScopeDispose(() => {
      abortAll();
    });
  }

  return {
    // Run
    runData,
    runLoading,
    isRunRefreshing,
    runError,
    calls,
    nextCursor,
    loadingMore,
    loadMoreError,
    loadMoreCalls,
    fetchRun,
    // Thread
    threadData,
    threadLoading,
    isThreadRefreshing,
    threadError,
    fetchThread,
    // 整体操作
    refresh,
  };
}
