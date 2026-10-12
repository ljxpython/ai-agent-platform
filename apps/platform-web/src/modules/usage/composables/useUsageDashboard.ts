import {
  ref,
  shallowRef,
  watch,
  onScopeDispose,
  type Ref,
  type ComputedRef,
} from "vue";
import {
  getPlatformUsageDashboard,
  getProjectUsageDashboard,
} from "@/services/usage/usage.service";
import type { UsageDashboardV1, DashboardQueryParams } from "../types";

export interface UseUsageDashboardOptions {
  scope: ComputedRef<{
    kind: "platform" | "project";
    projectId?: string;
  }>;
  filters: Ref<DashboardQueryParams>;
  enabled?: ComputedRef<boolean>;
}

export function useUsageDashboard(options: UseUsageDashboardOptions) {
  const data = shallowRef<UsageDashboardV1 | null>(null);
  const loading = ref(false);
  const isRefreshing = ref(false);
  const error = shallowRef<Error | null>(null);

  let currentEpoch = 0;
  let activeAbortController: AbortController | null = null;

  function abortActiveRequest() {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
  }

  async function fetchDashboard(): Promise<void> {
    if (options.enabled && !options.enabled.value) {
      abortActiveRequest();
      data.value = null;
      loading.value = false;
      isRefreshing.value = false;
      return;
    }

    const currentScope = options.scope.value;
    // 如果是单项目但未提供有效 projectId，不发起请求
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
    error.value = null;

    try {
      let result: UsageDashboardV1;
      if (currentScope.kind === "platform") {
        result = await getPlatformUsageDashboard(options.filters.value, {
          signal: controller.signal,
        });
      } else {
        result = await getProjectUsageDashboard(
          currentScope.projectId!,
          options.filters.value,
          { signal: controller.signal },
        );
      }

      if (epoch !== currentEpoch) {
        return; // 丢弃过期竞态响应
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

  function refresh() {
    return fetchDashboard();
  }

  // 监听筛选和 scope 变化
  watch(
    [options.scope, options.filters],
    () => {
      fetchDashboard();
    },
    { deep: true, immediate: true },
  );

  onScopeDispose(() => {
    abortActiveRequest();
  });

  return {
    data,
    loading,
    isRefreshing,
    error,
    refresh,
  };
}
