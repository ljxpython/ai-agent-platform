<script setup lang="ts">
import { computed } from "vue";
import type { useThreadStopControl } from "../composables/useThreadStopControl";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  stopControl: ReturnType<typeof useThreadStopControl>;
}>();

const emit = defineEmits<{
  "open-report": [];
}>();

const isStopping = computed(() => props.stopControl.isStopping.value);
const isConfirmed = computed(() => props.stopControl.isConfirmed.value);
const isUnavailable = computed(
  () => props.stopControl.isConfirmationUnavailable.value,
);
const isRejected = computed(() => props.stopControl.phase.value === "rejected");
const hasError = computed(() => Boolean(props.stopControl.stopError.value));

const isVisible = computed(
  () =>
    isStopping.value ||
    isConfirmed.value ||
    isUnavailable.value ||
    isRejected.value ||
    hasError.value,
);

const statusText = computed(() => {
  if (isStopping.value) {
    return "正在停止会话...";
  }
  if (isConfirmed.value) {
    const count = props.stopControl.targetCount.value;
    if (count != null && count > 0) {
      return `已停止（取消 ${count} 个任务）`;
    }
    return "任务已停止";
  }
  if (isUnavailable.value) {
    return (
      props.stopControl.stopError.value || "运行已停止，部分资源清理结果待确认"
    );
  }
  if (isRejected.value || hasError.value) {
    return props.stopControl.stopError.value || "停止请求已被拒绝";
  }
  return "";
});

function handleClose() {
  props.stopControl.clearFeedback();
}

function handleVerify() {
  void props.stopControl.verifyLatest(true);
}

function handleRetry() {
  void props.stopControl.retry();
}
</script>

<template>
  <div
    v-if="isVisible"
    data-testid="run-stop-report-banner"
    role="status"
    aria-live="polite"
    class="mb-2 flex w-full flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-1.5 text-xs shadow-2xs transition-all duration-200"
    :class="{
      'border-blue-200 bg-blue-50/90 text-blue-800 dark:border-blue-900/60 dark:bg-blue-950/40 dark:text-blue-300':
        isStopping,
      'border-emerald-200 bg-emerald-50/90 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300':
        isConfirmed,
      'border-amber-200 bg-amber-50/90 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300':
        isUnavailable,
      'border-red-200 bg-red-50/90 text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300':
        isRejected || hasError,
    }"
  >
    <div class="flex min-w-0 items-center gap-2">
      <!-- 状态图标 -->
      <span
        v-if="isStopping"
        class="inline-block h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
        aria-hidden="true"
      />
      <BaseIcon
        v-else-if="isConfirmed"
        name="check"
        class="h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400"
      />
      <BaseIcon
        v-else-if="isUnavailable"
        name="alert"
        class="h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-400"
      />
      <BaseIcon
        v-else
        name="x"
        class="h-3.5 w-3.5 shrink-0 text-red-600 dark:text-red-400"
      />

      <span class="truncate font-medium">{{ statusText }}</span>
    </div>

    <!-- 动作按钮区 -->
    <div class="flex items-center gap-2">
      <button
        v-if="isUnavailable"
        type="button"
        class="cursor-pointer rounded px-2 py-0.5 text-xs font-semibold underline underline-offset-2 hover:bg-amber-200/50 dark:hover:bg-amber-900/40"
        @click="handleVerify"
      >
        重新核实
      </button>

      <button
        v-if="isRejected"
        type="button"
        class="cursor-pointer rounded px-2 py-0.5 text-xs font-semibold underline underline-offset-2 hover:bg-red-200/50 dark:hover:bg-red-900/40"
        @click="handleRetry"
      >
        重试
      </button>

      <button
        v-if="props.stopControl.report.value"
        type="button"
        class="cursor-pointer rounded px-2 py-0.5 text-xs font-semibold underline underline-offset-2 hover:opacity-80"
        @click="emit('open-report')"
      >
        查看报告
      </button>

      <button
        v-if="!isStopping"
        type="button"
        class="cursor-pointer rounded p-0.5 opacity-70 hover:opacity-100"
        aria-label="关闭停止反馈提示"
        @click="handleClose"
      >
        <BaseIcon name="x" class="h-3.5 w-3.5" />
      </button>
    </div>
  </div>
</template>
