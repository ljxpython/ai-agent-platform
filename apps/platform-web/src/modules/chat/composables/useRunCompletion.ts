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
import { getRunCompletion } from "@/services/threads/completion.service";
import type { CompletionResponse, SafeCompletion } from "../completion/types";
import {
  resolveFailurePresentation,
  type FailurePresentation,
} from "../completion/presentation";
import type { PlatformHttpError } from "@/utils/http-error";

export interface UseRunCompletionOptions {
  projectId?:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  threadId:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  runId:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  isRunning?: Ref<boolean> | ComputedRef<boolean>;
  canRead?: Ref<boolean> | ComputedRef<boolean>;
  enabled?: Ref<boolean> | ComputedRef<boolean>;
}

export function useRunCompletion(options: UseRunCompletionOptions) {
  const data = shallowRef<CompletionResponse | null>(null);
  const loading = ref(false);
  const isRefreshing = ref(false);
  const error = shallowRef<PlatformHttpError | Error | null>(null);

  let currentEpoch = 0;
  let activeAbortController: AbortController | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let hasRetriedPending = false;

  const isEnabled = computed(() => options.enabled?.value ?? true);
  const canAccess = computed(() => options.canRead?.value ?? true);
  const running = computed(() => options.isRunning?.value ?? false);

  const availability = computed(() => data.value?.availability ?? null);
  const completion = computed<SafeCompletion | null>(() => {
    if (data.value && data.value.availability === "available") {
      return data.value.completion;
    }
    return null;
  });

  const failurePresentation = computed<FailurePresentation | null>(() => {
    if (!completion.value) return null;
    if (
      completion.value.status === "error" ||
      completion.value.status === "timeout"
    ) {
      return resolveFailurePresentation(completion.value);
    }
    return null;
  });

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
   * 执行 completion 查询
   * @param isManualRefresh 是否为用户主动点击刷新
   */
  async function fetchCompletion(isManualRefresh = false): Promise<void> {
    const pId = options.projectId?.value ?? undefined;
    const tId = options.threadId.value;
    const rId = options.runId.value;

    // 运行中绝不查询 completion；未选中目标或无权限时直接重置并中止
    if (!tId || !rId || !canAccess.value || !isEnabled.value || running.value) {
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
      const result = await getRunCompletion(tId, rId, {
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

      // 有限延迟重试：若后端返回 pending，且尚未重试过，等待 2 秒单次自动复查
      if (result.availability === "pending" && !hasRetriedPending) {
        hasRetriedPending = true;
        clearRetryTimer();
        retryTimer = setTimeout(() => {
          if (
            currentEpoch === epoch &&
            options.threadId.value === tId &&
            options.runId.value === rId &&
            isEnabled.value &&
            !running.value
          ) {
            void fetchCompletion(false);
          }
        }, 2000);
      }
    } catch (err: unknown) {
      if (controller.signal.aborted || epoch !== currentEpoch) {
        return;
      }

      const e = err as PlatformHttpError & Error;
      error.value = e;

      // 403 权限拒绝立即清空数据
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

  // 监听目标变更（threadId, runId, isRunning, canAccess, isEnabled）
  watch(
    [
      () => options.threadId.value,
      () => options.runId.value,
      () => running.value,
      () => canAccess.value,
      () => isEnabled.value,
    ],
    ([newThread, newRun, isRun, canA, isEn], [oldThread, oldRun]) => {
      // 切换了目标时，重置 pending 单次重试状态
      if (newThread !== oldThread || newRun !== oldRun) {
        hasRetriedPending = false;
      }

      if (newThread && newRun && canA && isEn && !isRun) {
        void fetchCompletion(false);
      } else {
        abortPendingRequest();
        data.value = null;
        error.value = null;
        loading.value = false;
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
    completion,
    failurePresentation,
    refresh: () => fetchCompletion(true),
  };
}
