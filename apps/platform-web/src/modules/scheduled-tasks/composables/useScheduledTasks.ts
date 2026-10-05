import { ref, watch, type Ref } from "vue";
import {
  deleteScheduledTask,
  listScheduledTasks,
  pauseScheduledTask,
  resumeScheduledTask,
  triggerScheduledTask,
} from "../services/scheduled-tasks.service";
import type { ScheduledTask } from "../types";

export function useScheduledTasks(projectId: Ref<string>) {
  const items = ref<ScheduledTask[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(12);
  const filterEnabled = ref<boolean | undefined>(undefined);
  const searchQuery = ref("");

  const loading = ref(false);
  const error = ref("");
  const triggeringTaskId = ref<string | null>(null);
  let requestEpoch = 0;

  async function loadTasks() {
    if (!projectId.value) {
      items.value = [];
      total.value = 0;
      return;
    }

    const epoch = ++requestEpoch;
    loading.value = true;
    error.value = "";

    try {
      const res = await listScheduledTasks(projectId.value, {
        limit: pageSize.value,
        offset: (page.value - 1) * pageSize.value,
        enabled: filterEnabled.value,
      });

      if (epoch === requestEpoch) {
        items.value = res.items || [];
        total.value = res.total || 0;
      }
    } catch (err: any) {
      if (epoch === requestEpoch) {
        error.value = err?.message || "获取定时任务列表失败";
      }
    } finally {
      if (epoch === requestEpoch) {
        loading.value = false;
      }
    }
  }

  watch([projectId, page, pageSize, filterEnabled], loadTasks, {
    immediate: true,
  });

  async function togglePause(task: ScheduledTask) {
    if (!projectId.value) return;
    try {
      const updated = task.enabled
        ? await pauseScheduledTask(projectId.value, task.id)
        : await resumeScheduledTask(projectId.value, task.id);

      const idx = items.value.findIndex((t) => t.id === task.id);
      if (idx !== -1) {
        items.value[idx] = updated;
      }
    } catch (err: any) {
      const code = err?.response?.data?.error?.code;
      const msg = err?.response?.data?.error?.message;
      if (code === "invalid_run_at") {
        error.value =
          "单次任务执行时间已过，无法恢复。请点击「编辑」修改为未来时间，或直接点击「立即运行」再次触发。";
      } else {
        error.value = msg || err?.message || "操作失败";
      }
    }
  }

  async function remove(task: ScheduledTask) {
    if (!projectId.value) return;
    try {
      await deleteScheduledTask(projectId.value, task.id);
      items.value = items.value.filter((t) => t.id !== task.id);
      total.value = Math.max(0, total.value - 1);
    } catch (err: any) {
      error.value =
        err?.response?.data?.error?.message || err?.message || "删除任务失败";
    }
  }

  async function trigger(
    task: ScheduledTask,
    onTriggerSuccess?: (runId: string, threadId: string) => void,
  ) {
    if (!projectId.value || triggeringTaskId.value) return;
    triggeringTaskId.value = task.id;
    try {
      const res = await triggerScheduledTask(projectId.value, task.id);
      if (onTriggerSuccess) {
        onTriggerSuccess(res.run_id, res.thread_id);
      }
    } catch (err: any) {
      error.value =
        err?.response?.data?.error?.message ||
        err?.message ||
        "手动触发任务失败";
    } finally {
      triggeringTaskId.value = null;
    }
  }

  function handleTaskSaved(saved: ScheduledTask) {
    const idx = items.value.findIndex((t) => t.id === saved.id);
    if (idx !== -1) {
      items.value[idx] = saved;
    } else {
      items.value = [saved, ...items.value];
      total.value += 1;
    }
  }

  return {
    items,
    total,
    page,
    pageSize,
    filterEnabled,
    searchQuery,
    loading,
    error,
    triggeringTaskId,
    loadTasks,
    togglePause,
    remove,
    trigger,
    handleTaskSaved,
  };
}
