import { ref, watch, type Ref } from "vue";
import { previewSchedule } from "../services/scheduled-tasks.service";
import type { SchedulePreviewPayload } from "../types";

export function useSchedulePreview(
  projectId: Ref<string>,
  payload: Ref<SchedulePreviewPayload | null>,
) {
  const times = ref<string[]>([]);
  const loading = ref(false);
  const error = ref<string>("");
  let timer: ReturnType<typeof setTimeout> | null = null;
  let requestSeq = 0;

  async function fetchPreview() {
    if (!projectId.value || !payload.value) {
      times.value = [];
      error.value = "";
      return;
    }

    const current = payload.value;
    if (current.schedule_type === "cron") {
      if (!current.cron || current.cron.trim().split(/\s+/).length !== 5) {
        times.value = [];
        return;
      }
    } else if (current.schedule_type === "once") {
      if (!current.run_at) {
        times.value = [];
        return;
      }
    }

    const seq = ++requestSeq;
    loading.value = true;
    error.value = "";

    try {
      const result = await previewSchedule(projectId.value, current);
      if (seq === requestSeq) {
        times.value = result.times || [];
      }
    } catch (err: any) {
      if (seq === requestSeq) {
        times.value = [];
        error.value = err?.message || "时间预测失败";
      }
    } finally {
      if (seq === requestSeq) {
        loading.value = false;
      }
    }
  }

  watch(
    [projectId, payload],
    () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(fetchPreview, 300);
    },
    { deep: true, immediate: true },
  );

  return {
    times,
    loading,
    error,
    refresh: fetchPreview,
  };
}
