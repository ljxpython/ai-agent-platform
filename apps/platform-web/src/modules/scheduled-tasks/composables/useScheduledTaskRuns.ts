import { ref, watch, type Ref } from "vue";
import { listScheduledTaskRuns } from "../services/scheduled-tasks.service";
import type { ScheduledTaskRun } from "../types";

export function useScheduledTaskRuns(
  projectId: Ref<string>,
  taskId: Ref<string>,
) {
  const items = ref<ScheduledTaskRun[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(10);
  const loading = ref(false);
  const error = ref("");
  let reqSeq = 0;

  async function loadRuns() {
    if (!projectId.value || !taskId.value) {
      items.value = [];
      total.value = 0;
      return;
    }

    const seq = ++reqSeq;
    loading.value = true;
    error.value = "";

    try {
      const res = await listScheduledTaskRuns(projectId.value, taskId.value, {
        limit: pageSize.value,
        offset: (page.value - 1) * pageSize.value,
      });
      if (seq === reqSeq) {
        items.value = res.items || [];
        total.value = res.total || 0;
      }
    } catch (err: any) {
      if (seq === reqSeq) {
        error.value = err?.message || "获取执行历史失败";
      }
    } finally {
      if (seq === reqSeq) {
        loading.value = false;
      }
    }
  }

  watch([projectId, taskId, page, pageSize], loadRuns, { immediate: true });

  return {
    items,
    total,
    page,
    pageSize,
    loading,
    error,
    refresh: loadRuns,
  };
}
