/**
 * 后台非阻塞长任务核心状态机 Composable
 * 单一数据源 (Single Source of Truth)
 * 挂载于 ChatSession 顶层并通过 provide('backgroundTasks') 共享给 WorkspacePanel
 */

import {
  computed,
  getCurrentScope,
  onScopeDispose,
  ref,
  toValue,
  watch,
  type ComputedRef,
  type MaybeRefOrGetter,
  type Ref,
} from "vue";
import {
  cancelBackgroundTask,
  getBackgroundTaskOutput,
  listBackgroundTasks,
} from "@/services/threads/background-tasks.service";
import type { OutputV1, TaskV1 } from "@/modules/chat/background-tasks/types";
import type { WorkspaceCapabilities } from "@/types/workspace";

export interface UseBackgroundTasksOptions {
  capabilities?: MaybeRefOrGetter<WorkspaceCapabilities | null | undefined>;
  onRunDiscovered?: (runId: string) => void;
}

export function useBackgroundTasks(
  projectId: Ref<string> | ComputedRef<string>,
  threadId:
    | Ref<string | null | undefined>
    | ComputedRef<string | null | undefined>,
  options: UseBackgroundTasksOptions = {},
) {
  const queryEnabled = computed(() =>
    Boolean(toValue(options.capabilities)?.background_tasks),
  );
  const tasks = ref<TaskV1[]>([]);
  const loading = ref(false);
  const refreshing = ref(false);
  const error = ref<string | null>(null);
  const nextCursor = ref<string | null>(null);
  const hasUnresolved = ref(false);
  const latestDeliveryRunId = ref<string | null>(null);

  // 日志查看状态
  const activeLogTaskId = ref<string | null>(null);
  const logOutput = ref<OutputV1 | null>(null);
  const loadingLog = ref(false);
  const logError = ref<string | null>(null);

  // 取消操作单飞锁
  const cancellingTaskIds = ref<Set<string>>(new Set());

  // 已记录/发现的 Run ID 集合，避免重复通知
  const discoveredRunIds = new Set<string>();

  let probeTimer: ReturnType<typeof setTimeout> | null = null;
  let logPollTimer: ReturnType<typeof setTimeout> | null = null;
  let inFlightProbe: AbortController | null = null;
  let inFlightLog: AbortController | null = null;
  let isDisposed = false;

  const hasActiveBackgroundTasks = computed(() =>
    tasks.value.some(
      (t) =>
        t.status === "starting" ||
        t.status === "running" ||
        t.status === "cancel_requested",
    ),
  );

  const activeTaskCount = computed(
    () =>
      tasks.value.filter(
        (t) =>
          t.status === "starting" ||
          t.status === "running" ||
          t.status === "cancel_requested",
      ).length,
  );

  function clearTimers() {
    if (probeTimer) {
      clearTimeout(probeTimer);
      probeTimer = null;
    }
    if (logPollTimer) {
      clearTimeout(logPollTimer);
      logPollTimer = null;
    }
  }

  function resetScope() {
    clearTimers();
    if (inFlightProbe) {
      inFlightProbe.abort();
      inFlightProbe = null;
    }
    if (inFlightLog) {
      inFlightLog.abort();
      inFlightLog = null;
    }
    tasks.value = [];
    nextCursor.value = null;
    hasUnresolved.value = false;
    latestDeliveryRunId.value = null;
    activeLogTaskId.value = null;
    logOutput.value = null;
    loadingLog.value = false;
    logError.value = null;
    error.value = null;
    discoveredRunIds.clear();
  }

  function checkDiscoveredRuns(items: TaskV1[], latestRunId: string | null) {
    if (latestRunId && !discoveredRunIds.has(latestRunId)) {
      discoveredRunIds.add(latestRunId);
      options.onRunDiscovered?.(latestRunId);
    }
    for (const task of items) {
      const deliveryRunId = task.delivery.run_id;
      if (deliveryRunId && !discoveredRunIds.has(deliveryRunId)) {
        discoveredRunIds.add(deliveryRunId);
        options.onRunDiscovered?.(deliveryRunId);
      }
    }
  }

  function scheduleProbe(delay = 5000) {
    if (isDisposed || !queryEnabled.value) return;
    if (probeTimer) clearTimeout(probeTimer);

    // 仅在当前 Thread 存在、具备查询能力且有未收敛任务时维持低频探针
    if (!toValue(threadId) || !hasUnresolved.value) return;

    probeTimer = setTimeout(async () => {
      if (
        isDisposed ||
        !queryEnabled.value ||
        (typeof document !== "undefined" && document.hidden)
      ) {
        return;
      }
      await refresh(true);
      if (hasUnresolved.value && queryEnabled.value) {
        scheduleProbe();
      }
    }, delay);
  }

  async function loadTasks(silent = false) {
    if (isDisposed || !queryEnabled.value) return;
    const curPid = toValue(projectId);
    const curTid = toValue(threadId);
    if (!curPid || !curTid) {
      tasks.value = [];
      hasUnresolved.value = false;
      return;
    }

    if (!silent) {
      loading.value = true;
    } else {
      refreshing.value = true;
    }
    error.value = null;

    if (inFlightProbe) {
      inFlightProbe.abort();
    }
    inFlightProbe = new AbortController();

    try {
      const result = await listBackgroundTasks(
        curPid,
        curTid,
        { limit: 50 },
        inFlightProbe.signal,
      );
      if (
        isDisposed ||
        !queryEnabled.value ||
        toValue(projectId) !== curPid ||
        toValue(threadId) !== curTid
      ) {
        return;
      }

      tasks.value = result.items;
      nextCursor.value = result.next_cursor;
      hasUnresolved.value = result.has_unresolved;
      latestDeliveryRunId.value = result.latest_delivery_run_id;

      checkDiscoveredRuns(result.items, result.latest_delivery_run_id);

      // 若当前打开了详情且该任务在列表中存在，更新状态
      if (activeLogTaskId.value) {
        const found = result.items.find(
          (t) => t.task_id === activeLogTaskId.value,
        );
        if (
          found &&
          (found.status === "succeeded" ||
            found.status === "failed" ||
            found.status === "cancelled" ||
            found.status === "timed_out")
        ) {
          if (logPollTimer) {
            clearTimeout(logPollTimer);
            logPollTimer = null;
          }
        }
      }
    } catch (err: unknown) {
      if (
        isDisposed ||
        !queryEnabled.value ||
        toValue(projectId) !== curPid ||
        toValue(threadId) !== curTid
      ) {
        return;
      }
      if (err instanceof Error && err.name === "CanceledError") return;
      error.value = err instanceof Error ? err.message : "加载后台任务列表失败";
    } finally {
      loading.value = false;
      refreshing.value = false;
      inFlightProbe = null;
    }
  }

  async function refresh(silent = false) {
    if (isDisposed || !queryEnabled.value) {
      resetScope();
      return;
    }
    await loadTasks(silent);
    if (hasUnresolved.value && queryEnabled.value && !isDisposed) {
      scheduleProbe();
    }
  }

  async function openTaskLog(taskId: string) {
    if (isDisposed || !queryEnabled.value) return;
    activeLogTaskId.value = taskId;
    logOutput.value = null;
    logError.value = null;
    await fetchTaskLog(taskId);

    // 若该任务正在运行，开启按需有限轮询（3秒）
    const task = tasks.value.find((t) => t.task_id === taskId);
    if (task && (task.status === "starting" || task.status === "running")) {
      scheduleLogPoll(taskId);
    }
  }

  function closeTaskLog() {
    activeLogTaskId.value = null;
    logOutput.value = null;
    logError.value = null;
    if (logPollTimer) {
      clearTimeout(logPollTimer);
      logPollTimer = null;
    }
  }

  function scheduleLogPoll(taskId: string) {
    if (isDisposed || !queryEnabled.value || activeLogTaskId.value !== taskId)
      return;
    if (logPollTimer) clearTimeout(logPollTimer);

    logPollTimer = setTimeout(async () => {
      if (
        isDisposed ||
        !queryEnabled.value ||
        activeLogTaskId.value !== taskId ||
        (typeof document !== "undefined" && document.hidden)
      ) {
        return;
      }
      await fetchTaskLog(taskId, true);
      const curTask = tasks.value.find((t) => t.task_id === taskId);
      if (
        curTask &&
        (curTask.status === "starting" || curTask.status === "running")
      ) {
        scheduleLogPoll(taskId);
      }
    }, 3000);
  }

  async function fetchTaskLog(taskId: string, silent = false) {
    if (isDisposed || !queryEnabled.value) return;
    const curPid = toValue(projectId);
    const curTid = toValue(threadId);
    if (!curPid || !curTid) return;

    if (!silent) {
      loadingLog.value = true;
    }
    if (inFlightLog) {
      inFlightLog.abort();
    }
    inFlightLog = new AbortController();

    try {
      const out = await getBackgroundTaskOutput(
        curPid,
        curTid,
        taskId,
        inFlightLog.signal,
      );
      if (isDisposed || !queryEnabled.value || activeLogTaskId.value !== taskId)
        return;
      logOutput.value = out;
    } catch (err: unknown) {
      if (isDisposed || !queryEnabled.value || activeLogTaskId.value !== taskId)
        return;
      if (err instanceof Error && err.name === "CanceledError") return;
      logError.value = err instanceof Error ? err.message : "获取日志失败";
    } finally {
      loadingLog.value = false;
      inFlightLog = null;
    }
  }

  async function cancelTask(taskId: string) {
    if (isDisposed || !queryEnabled.value) return;
    const curPid = toValue(projectId);
    const curTid = toValue(threadId);
    if (!curPid || !curTid || cancellingTaskIds.value.has(taskId)) return;

    const nextSet = new Set(cancellingTaskIds.value);
    nextSet.add(taskId);
    cancellingTaskIds.value = nextSet;

    // 乐观单飞，生成确定性 Idempotency-Key
    const idemKey = `cancel-${taskId}-${Date.now()}`;
    try {
      const updated = await cancelBackgroundTask(
        curPid,
        curTid,
        taskId,
        idemKey,
      );
      // 更新本地快照
      const idx = tasks.value.findIndex((t) => t.task_id === taskId);
      if (idx !== -1) {
        tasks.value[idx] = updated;
      }
      // 触发一次整体刷新以确认对账
      void refresh(true);
    } catch (err) {
      // 失败后刷新单项对账
      void refresh(true);
      throw err;
    } finally {
      const clearSet = new Set(cancellingTaskIds.value);
      clearSet.delete(taskId);
      cancellingTaskIds.value = clearSet;
    }
  }

  function handleVisibilityChange() {
    if (typeof document === "undefined") return;
    if (!document.hidden && hasUnresolved.value && queryEnabled.value) {
      void refresh(true);
    }
  }

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", handleVisibilityChange);
  }

  // 监听 threadId 和 projectId 变化，重置作用域
  watch(
    [() => toValue(projectId), () => toValue(threadId)],
    ([newPid, newTid], oldValues) => {
      const oldPid = oldValues?.[0];
      const oldTid = oldValues?.[1];
      if (newPid !== oldPid || newTid !== oldTid) {
        resetScope();

        if (newPid && newTid && queryEnabled.value) {
          void loadTasks(false).then(() => {
            if (hasUnresolved.value) scheduleProbe();
          });
        }
      }
    },
    { immediate: true },
  );

  // 监听 queryEnabled 变化：关闭时清理作用域并停探针，开启时按需加载
  watch(queryEnabled, (enabled) => {
    if (!enabled) {
      resetScope();
    } else {
      const curPid = toValue(projectId);
      const curTid = toValue(threadId);
      if (curPid && curTid) {
        void loadTasks(false).then(() => {
          if (hasUnresolved.value) scheduleProbe();
        });
      }
    }
  });

  if (getCurrentScope()) {
    onScopeDispose(() => {
      isDisposed = true;
      resetScope();
      if (typeof document !== "undefined") {
        document.removeEventListener(
          "visibilitychange",
          handleVisibilityChange,
        );
      }
    });
  }

  return {
    queryEnabled,
    tasks,
    loading,
    refreshing,
    error,
    nextCursor,
    hasUnresolved,
    latestDeliveryRunId,
    hasActiveBackgroundTasks,
    activeTaskCount,
    // 日志
    activeLogTaskId,
    logOutput,
    loadingLog,
    logError,
    openTaskLog,
    closeTaskLog,
    fetchTaskLog,
    // 取消
    cancellingTaskIds,
    cancelTask,
    // 动作
    refresh,
  };
}

export type UseBackgroundTasksReturn = ReturnType<typeof useBackgroundTasks>;
