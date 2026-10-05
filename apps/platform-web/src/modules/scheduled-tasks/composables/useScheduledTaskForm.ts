import { computed, ref, watch } from "vue";
import {
  createScheduledTask,
  updateScheduledTask,
} from "../services/scheduled-tasks.service";
import type {
  ScheduleType,
  ScheduledTask,
  TaskCreatePayload,
  TaskUpdatePayload,
  ThreadMode,
} from "../types";

export function useScheduledTaskForm(
  projectId: () => string,
  initialTask: () => ScheduledTask | null | undefined,
  onSuccess: (task: ScheduledTask) => void,
) {
  const isEdit = computed(() => Boolean(initialTask()?.id));
  const taskId = computed(() => initialTask()?.id || "");

  const title = ref("");
  const prompt = ref("");
  const agentKey = ref("");
  const scheduleType = ref<ScheduleType>("cron");
  const cron = ref("0 9 * * *");
  const runAt = ref("");
  const timezone = ref("Asia/Shanghai");
  const endTime = ref<string | null>(null);
  const threadMode = ref<ThreadMode>("fresh");
  const threadId = ref("");
  const selectedModelId = ref<string>("");

  const submitting = ref(false);
  const submitError = ref("");

  function resetForm() {
    const t = initialTask();
    if (t) {
      title.value = t.title;
      prompt.value = t.prompt;
      agentKey.value = t.agent_key;
      scheduleType.value = t.schedule_type;
      cron.value = t.cron || "0 9 * * *";
      runAt.value = t.run_at || "";
      timezone.value = t.timezone || "Asia/Shanghai";
      endTime.value = t.end_time || null;
      threadMode.value = t.thread_mode;
      threadId.value = t.thread_id || "";
      selectedModelId.value = t.context?.model_id || "";
    } else {
      title.value = "";
      prompt.value = "";
      agentKey.value = "";
      scheduleType.value = "cron";
      cron.value = "0 9 * * *";
      runAt.value = "";
      timezone.value = "Asia/Shanghai";
      endTime.value = null;
      threadMode.value = "fresh";
      threadId.value = "";
      selectedModelId.value = "";
    }
    submitError.value = "";
  }

  watch(() => initialTask(), resetForm, { immediate: true });

  const previewPayload = computed(() => {
    return {
      schedule_type: scheduleType.value,
      cron: scheduleType.value === "cron" ? cron.value : null,
      run_at: scheduleType.value === "once" ? runAt.value : null,
      timezone: timezone.value,
      end_time: endTime.value,
    };
  });

  async function submit() {
    submitError.value = "";
    if (!title.value.trim()) {
      submitError.value = "请输入任务标题";
      return;
    }
    if (!prompt.value.trim()) {
      submitError.value = "请输入任务提示词";
      return;
    }
    if (!isEdit.value && !agentKey.value.trim()) {
      submitError.value = "请选择执行智能体";
      return;
    }
    if (threadMode.value === "reuse" && !threadId.value.trim()) {
      submitError.value = "复用模式下必须输入关联的 Thread ID";
      return;
    }

    submitting.value = true;
    try {
      const contextObj: Record<string, any> = {};
      if (selectedModelId.value) {
        contextObj.model_id = selectedModelId.value;
      }

      if (isEdit.value) {
        const patch: TaskUpdatePayload = {
          title: title.value.trim(),
          prompt: prompt.value.trim(),
          timezone: timezone.value,
          context: contextObj,
        };
        if (scheduleType.value === "cron") {
          patch.cron = cron.value;
          patch.end_time = endTime.value;
        } else {
          patch.run_at = runAt.value;
        }
        const updated = await updateScheduledTask(
          projectId(),
          taskId.value,
          patch,
        );
        onSuccess(updated);
      } else {
        const createPayload: TaskCreatePayload = {
          title: title.value.trim(),
          prompt: prompt.value.trim(),
          agent_key: agentKey.value.trim(),
          schedule_type: scheduleType.value,
          timezone: timezone.value,
          thread_mode: threadMode.value,
          thread_id:
            threadMode.value === "reuse" ? threadId.value.trim() : null,
          context: contextObj,
          enabled: true,
        };
        if (scheduleType.value === "cron") {
          createPayload.cron = cron.value;
          createPayload.end_time = endTime.value;
        } else {
          createPayload.run_at = runAt.value;
        }
        const created = await createScheduledTask(projectId(), createPayload);
        onSuccess(created);
      }
    } catch (err: any) {
      submitError.value = err?.message || "保存失败，请检查参数";
    } finally {
      submitting.value = false;
    }
  }

  return {
    isEdit,
    title,
    prompt,
    agentKey,
    scheduleType,
    cron,
    runAt,
    timezone,
    endTime,
    threadMode,
    threadId,
    selectedModelId,
    previewPayload,
    submitting,
    submitError,
    submit,
    resetForm,
  };
}
