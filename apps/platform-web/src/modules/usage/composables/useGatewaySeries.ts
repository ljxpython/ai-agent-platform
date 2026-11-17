import {
  ref,
  shallowRef,
  watch,
  onScopeDispose,
  type Ref,
  type ComputedRef,
} from "vue";
import {
  getPlatformGatewaySeries,
  getProjectGatewaySeries,
} from "@/services/usage/usage.service";
import type { GatewaySeriesV1, GatewaySeriesQueryParams } from "../types";

export interface UseGatewaySeriesOptions {
  scope: ComputedRef<{
    kind: "platform" | "project";
    projectId?: string;
  }>;
  filters: Ref<GatewaySeriesQueryParams>;
  enabled?: ComputedRef<boolean>;
  refreshIntervalMs?: Ref<number>; // 0 表示关闭，如 30000 表示 30s 自动刷新
}

export function useGatewaySeries(options: UseGatewaySeriesOptions) {
  const data = shallowRef<GatewaySeriesV1 | null>(null);
  const loading = ref(false);
  const isRefreshing = ref(false);
  const error = shallowRef<Error | null>(null);

  let currentEpoch = 0;
  let activeAbortController: AbortController | null = null;
  let refreshTimer: ReturnType<typeof setInterval> | null = null;

  function abortActiveRequest() {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
  }

  async function fetchSeries(silent = false): Promise<void> {
    if (options.enabled && !options.enabled.value) {
      abortActiveRequest();
      data.value = null;
      loading.value = false;
      isRefreshing.value = false;
      return;
    }

    const currentScope = options.scope.value;
    if (currentScope.kind === "project" && !currentScope.projectId) {
      abortActiveRequest();
      data.value = null;
      loading.value = false;
      return;
    }

    abortActiveRequest();
    const epoch = ++currentEpoch;
    const controller = new AbortController();
    activeAbortController = controller;

    if (data.value) {
      isRefreshing.value = true;
    } else {
      loading.value = true;
    }
    if (!silent) {
      error.value = null;
    }

    try {
      let result: GatewaySeriesV1;
      if (currentScope.kind === "platform") {
        result = await getPlatformGatewaySeries(options.filters.value, {
          signal: controller.signal,
        });
      } else {
        result = await getProjectGatewaySeries(
          currentScope.projectId!,
          options.filters.value,
          { signal: controller.signal },
        );
      }

      if (epoch !== currentEpoch) {
        return;
      }

      data.value = result;
      error.value = null;
    } catch (err: unknown) {
      if (epoch !== currentEpoch || controller.signal.aborted) {
        return;
      }
      error.value = err instanceof Error ? err : new Error(String(err));
    } finally {
      if (epoch === currentEpoch) {
        loading.value = false;
        isRefreshing.value = false;
      }
    }
  }

  function setupRefreshTimer() {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
    const interval = options.refreshIntervalMs?.value ?? 0;
    if (interval > 0) {
      refreshTimer = setInterval(() => {
        if (!loading.value && !isRefreshing.value) {
          fetchSeries(true);
        }
      }, interval);
    }
  }

  // 监听过滤条件或作用域改变
  watch(
    [options.scope, options.filters],
    () => {
      fetchSeries();
    },
    { deep: true, immediate: true },
  );

  // 监听刷新频率配置改变
  if (options.refreshIntervalMs) {
    watch(options.refreshIntervalMs, () => {
      setupRefreshTimer();
    });
  }

  onScopeDispose(() => {
    abortActiveRequest();
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  });

  return {
    data,
    loading,
    isRefreshing,
    error,
    refresh: () => fetchSeries(false),
  };
}
