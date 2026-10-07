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
import { getRunDiagnostics } from "@/services/threads/diagnostics.service";
import type { RunDiagnosticsV1 } from "../diagnostics/types";
import type { PlatformHttpError } from "@/utils/http-error";

export interface UseRunDiagnosticsOptions {
  projectId?:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  threadId:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  runId:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  canRead?: Ref<boolean> | ComputedRef<boolean>;
  enabled?: Ref<boolean> | ComputedRef<boolean>;
}

export function useRunDiagnostics(options: UseRunDiagnosticsOptions) {
  const data = shallowRef<RunDiagnosticsV1 | null>(null);
  const loading = ref(false);
  const isRefreshing = ref(false);
  const error = shallowRef<PlatformHttpError | Error | null>(null);

  let currentEpoch = 0;
  let activeAbortController: AbortController | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let hasRetriedTarget = false;

  const isEnabled = computed(() => options.enabled?.value ?? true);
  const canAccess = computed(() => options.canRead?.value ?? true);
  const availability = computed(() => data.value?.availability ?? null);
  const unavailableReason = computed(
    () => data.value?.unavailable_reason ?? null,
  );

  function clearRetryTimer() {
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
  }

  function abortPendingRequest() {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
    clearRetryTimer();
  }

  /**
   * 执行诊断查询
   * @param isManualRefresh 是否为用户主动点击刷新（主动刷新保留现有数据呈现刷新态）
   */
  async function fetchDiagnostics(isManualRefresh = false): Promise<void> {
    const pId = options.projectId?.value ?? undefined;
    const tId = options.threadId.value;
    const rId = options.runId.value;

    if (!tId || !rId || !canAccess.value || !isEnabled.value) {
      abortPendingRequest();
      if (!isManualRefresh) {
        data.value = null;
        error.value = null;
      }
      loading.value = false;
      isRefreshing.value = false;
      return;
    }

    abortPendingRequest();
    const epoch = ++currentEpoch;
    const controller = new AbortController();
    activeAbortController = controller;

    if (isManualRefresh && data.value) {
      isRefreshing.value = true;
    } else {
      loading.value = true;
    }
    error.value = null;

    try {
      const result = await getRunDiagnostics(tId, rId, {
        projectId: pId ?? undefined,
        signal: controller.signal,
      });

      // 竞态防御：校验代数与目标是否仍然匹配
      if (
        epoch !== currentEpoch ||
        options.threadId.value !== tId ||
        options.runId.value !== rId
      ) {
        return;
      }

      data.value = result;
      error.value = null;

      // 有限延迟重试规则：收到 unavailable 且 not_recorded 时，若非 running 原生状态，延迟 2 秒最多单次重查
      if (
        result.availability === "unavailable" &&
        result.unavailable_reason === "not_recorded" &&
        result.run_status !== "running" &&
        !hasRetriedTarget
      ) {
        hasRetriedTarget = true;
        clearRetryTimer();
        retryTimer = setTimeout(() => {
          if (
            currentEpoch === epoch &&
            options.threadId.value === tId &&
            options.runId.value === rId &&
            isEnabled.value
          ) {
            void fetchDiagnostics(false);
          }
        }, 2000);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted || epoch !== currentEpoch) {
        return;
      }

      const e = err as PlatformHttpError & Error;
      error.value = e;

      // 403 真实权限拒绝时立即清空数据
      if (e.status === 403) {
        data.value = null;
      }
    } finally {
      if (epoch === currentEpoch) {
        loading.value = false;
        isRefreshing.value = false;
        if (activeAbortController === controller) {
          activeAbortController = null;
        }
      }
    }
  }

  // 监听 Thread 或 Project 变更：同步物理清空旧数据，重置重试状态
  watch(
    [() => options.projectId?.value, () => options.threadId.value],
    () => {
      abortPendingRequest();
      currentEpoch++;
      hasRetriedTarget = false;
      data.value = null;
      error.value = null;
      loading.value = false;
      isRefreshing.value = false;

      if (options.runId.value && isEnabled.value) {
        void fetchDiagnostics(false);
      }
    },
    { flush: "sync" },
  );

  // 监听 Run 变更：同步物理清空旧数据并按需拉取
  watch(
    () => options.runId.value,
    (newRunId, oldRunId) => {
      if (newRunId === oldRunId) return;
      abortPendingRequest();
      currentEpoch++;
      hasRetriedTarget = false;
      data.value = null;
      error.value = null;

      if (newRunId && isEnabled.value) {
        void fetchDiagnostics(false);
      }
    },
    { flush: "sync" },
  );

  // 监听 isEnabled 开关（如打开/关闭面板）：打开时按需触发
  watch(
    isEnabled,
    (enabled) => {
      if (enabled && options.runId.value && !data.value && !loading.value) {
        void fetchDiagnostics(false);
      } else if (!enabled) {
        clearRetryTimer();
      }
    },
    { immediate: true },
  );

  if (getCurrentScope()) {
    onScopeDispose(() => {
      abortPendingRequest();
    });
  }

  return {
    data,
    loading,
    isRefreshing,
    error,
    availability,
    unavailableReason,
    refresh: () => fetchDiagnostics(true),
    reset: () => {
      abortPendingRequest();
      currentEpoch++;
      data.value = null;
      error.value = null;
      loading.value = false;
      isRefreshing.value = false;
      hasRetriedTarget = false;
    },
  };
}
