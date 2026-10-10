<script setup lang="ts">
import { computed } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import type { TaskV1 } from "@/modules/chat/background-tasks/types";

const props = defineProps<{
  task: TaskV1;
  isCancelling?: boolean;
  isSelected?: boolean;
}>();

const emit = defineEmits<{
  viewLogs: [taskId: string];
  cancel: [taskId: string];
}>();

const statusBadge = computed(() => {
  switch (props.task.status) {
    case "starting":
      return {
        text: "启动中",
        bg: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200",
      };
    case "running":
      return {
        text: "运行中",
        bg: "bg-primary-50 text-primary-700 dark:bg-primary-950/40 dark:text-primary-300 border-primary-200 animate-pulse",
      };
    case "succeeded":
      return {
        text: "已完成",
        bg: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200",
      };
    case "failed":
      return {
        text: "失败",
        bg: "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border-rose-200",
      };
    case "timed_out":
      return {
        text: "超时",
        bg: "bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300 border-orange-200",
      };
    case "cancel_requested":
      return {
        text: "正在取消...",
        bg: "bg-gray-100 text-gray-700 dark:bg-dark-800 dark:text-dark-300 border-gray-300",
      };
    case "cancelled":
      return {
        text: "已取消",
        bg: "bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-dark-400 border-gray-200",
      };
    default:
      return {
        text: "未知状态",
        bg: "bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300 border-purple-200",
      };
  }
});

const canViewLogs = computed(() => props.task.allowed_actions.includes("logs"));
const canCancel = computed(
  () =>
    props.task.allowed_actions.includes("cancel") &&
    (props.task.status === "starting" || props.task.status === "running"),
);

function formatTime(isoStr: string | null): string {
  if (!isoStr) return "-";
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoStr;
  }
}
</script>

<template>
  <div
    data-testid="background-task-item"
    class="rounded-lg border p-3 transition-colors"
    :class="[
      isSelected
        ? 'border-primary-500 bg-primary-50/20 dark:border-primary-500/80 dark:bg-primary-950/20'
        : 'border-gray-200 bg-white hover:border-gray-300 dark:border-dark-800 dark:bg-dark-900 dark:hover:border-dark-700',
    ]"
  >
    <!-- 卡片头部：ID 与状态 Badge -->
    <div class="flex items-center justify-between gap-2">
      <div
        class="flex items-center gap-1.5 font-mono text-xs font-semibold text-gray-800 dark:text-dark-200"
      >
        <BaseIcon name="runtime" class="h-3.5 w-3.5 text-gray-400" />
        <span>{{ task.task_id.slice(0, 8) }}</span>
        <span
          v-if="task.exit_code !== null"
          class="text-[11px] text-gray-400 font-normal"
        >
          (exit {{ task.exit_code }})
        </span>
      </div>
      <span
        class="inline-flex items-center rounded-md border px-1.5 py-0.5 text-[11px] font-medium"
        :class="statusBadge.bg"
      >
        {{ statusBadge.text }}
      </span>
    </div>

    <!-- 卡片元信息区 -->
    <div
      class="mt-2 grid grid-cols-2 gap-1 text-[11px] text-gray-500 dark:text-dark-400"
    >
      <div>开始: {{ formatTime(task.started_at || task.created_at) }}</div>
      <div>期限: {{ formatTime(task.deadline_at) }}</div>
    </div>

    <!-- 附属状态提示条（清理/交付） -->
    <div class="mt-2 flex flex-wrap items-center gap-1.5 text-[10px]">
      <span
        v-if="task.cleanup_state === 'pending'"
        class="rounded bg-amber-100 px-1.5 py-0.2 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
      >
        资源回收中
      </span>
      <span
        v-else-if="task.cleanup_state === 'unconfirmed'"
        class="rounded bg-rose-100 px-1.5 py-0.2 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300"
      >
        清理未确认
      </span>
      <span
        v-if="task.delivery.state === 'accepted' && task.delivery.run_id"
        class="rounded bg-purple-100 px-1.5 py-0.2 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300"
        :title="`关联完成通知 Run: ${task.delivery.run_id}`"
      >
        已送达通知
      </span>
      <span
        v-else-if="task.delivery.state === 'suppressed'"
        class="rounded bg-gray-100 px-1.5 py-0.2 text-gray-600 dark:bg-dark-800 dark:text-dark-400"
      >
        通知已抑制
      </span>
    </div>

    <!-- 操作按钮区 -->
    <div
      class="mt-2.5 flex items-center justify-end gap-2 border-t border-gray-100 pt-2 dark:border-dark-800/80"
    >
      <button
        v-if="canViewLogs"
        type="button"
        data-testid="task-view-logs-btn"
        class="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-dark-100"
        @click="emit('viewLogs', task.task_id)"
      >
        <BaseIcon name="file" class="h-3 w-3" />
        <span>日志</span>
      </button>

      <button
        v-if="canCancel"
        type="button"
        data-testid="task-cancel-btn"
        class="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:text-rose-400 dark:hover:bg-rose-950/30"
        :disabled="isCancelling || task.status === 'cancel_requested'"
        @click="emit('cancel', task.task_id)"
      >
        <BaseIcon
          :name="isCancelling ? 'refresh' : 'x'"
          class="h-3 w-3"
          :class="{ 'animate-spin': isCancelling }"
        />
        <span>取消</span>
      </button>
    </div>
  </div>
</template>
