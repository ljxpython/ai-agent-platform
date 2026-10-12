import {
  ref,
  shallowRef,
  watch,
  onScopeDispose,
  type Ref,
  type ComputedRef,
} from "vue";
import { getProjectUsageRuns } from "@/services/usage/usage.service";
import type { UsageRun, RunsQueryParams } from "../types";

export interface UseUsageRunsOptions {
  projectId: ComputedRef<string | undefined>;
  filters: Ref<RunsQueryParams>;
  enabled?: ComputedRef<boolean>;
}

export function useUsageRuns(options: UseUsageRunsOptions) {
  const items = shallowRef<UsageRun[]>([]);
  const nextCursor = ref<string | null>(null);
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = shallowRef<Error | null>(null);
  const hasEmptyWithCursor = ref(false);

  let currentEpoch = 0;
  let activeAbortController: AbortController | null = null;

  function abortActive() {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
  }

  function reset() {
    abortActive();
    items.value = [];
    nextCursor.value = null;
    hasEmptyWithCursor.value = false;
    error.value = null;
    loading.value = false;
    loadingMore.value = false;
  }

  async function loadFirstPage(): Promise<void> {
    const pId = options.projectId.value;
    if (!pId || (options.enabled && !options.enabled.value)) {
      reset();
      return;
    }

    abortActive();
    const epoch = ++currentEpoch;
    const controller = new AbortController();
    activeAbortController = controller;

    loading.value = true;
    error.value = null;
    hasEmptyWithCursor.value = false;

    try {
      const result = await getProjectUsageRuns(
        pId,
        {
          ...options.filters.value,
          cursor: undefined,
        },
        { signal: controller.signal },
      );

      if (epoch !== currentEpoch) return;

      items.value = result.items;
      nextCursor.value = result.next_cursor;
      hasEmptyWithCursor.value =
        result.items.length === 0 && Boolean(result.next_cursor);
      error.value = null;
    } catch (err: unknown) {
      if (epoch !== currentEpoch || controller.signal.aborted) return;
      error.value = err instanceof Error ? err : new Error(String(err));
    } finally {
      if (epoch === currentEpoch) {
        loading.value = false;
      }
    }
  }

  async function loadNextPage(): Promise<void> {
    const pId = options.projectId.value;
    const cursor = nextCursor.value;
    if (!pId || !cursor || loadingMore.value) return;

    abortActive();
    const epoch = ++currentEpoch;
    const controller = new AbortController();
    activeAbortController = controller;

    loadingMore.value = true;
    hasEmptyWithCursor.value = false;

    try {
      const result = await getProjectUsageRuns(
        pId,
        {
          ...options.filters.value,
          cursor,
        },
        { signal: controller.signal },
      );

      if (epoch !== currentEpoch) return;

      // 按 (project_id, run_id) 去重合并追加
      const existingKeys = new Set(
        items.value.map((item) => `${item.project_id}_${item.run_id}`),
      );
      const newItems = result.items.filter(
        (item) => !existingKeys.has(`${item.project_id}_${item.run_id}`),
      );

      items.value = [...items.value, ...newItems];
      nextCursor.value = result.next_cursor;
      hasEmptyWithCursor.value =
        newItems.length === 0 && Boolean(result.next_cursor);
      error.value = null;
    } catch (err: unknown) {
      if (epoch !== currentEpoch || controller.signal.aborted) return;
      error.value = err instanceof Error ? err : new Error(String(err));
    } finally {
      if (epoch === currentEpoch) {
        loadingMore.value = false;
      }
    }
  }

  watch(
    [options.projectId, options.filters],
    () => {
      loadFirstPage();
    },
    { deep: true, immediate: true },
  );

  onScopeDispose(() => {
    abortActive();
  });

  return {
    items,
    nextCursor,
    loading,
    loadingMore,
    error,
    hasEmptyWithCursor,
    loadFirstPage,
    loadNextPage,
    reset,
  };
}
