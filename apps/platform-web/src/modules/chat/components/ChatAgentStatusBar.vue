<script setup lang="ts">
import { computed } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { formatThreadTime } from "@/utils/threads";
import type { SessionTurnState } from "../composables/useChatSession";

const props = defineProps<{
  isRunning: boolean;
  isInterrupted: boolean;
  error?: string;
  lastEventAt?: string;
  disabled?: boolean;
  turnState?: SessionTurnState;
}>();

const emit = defineEmits<{
  resume: [];
  cancel: [];
  verifyStop: [];
}>();

function formatError(raw: string): string {
  if (raw.includes("runtime.tool.not_allowed")) {
    const match = raw.match(
      /runtime\.tool\.not_allowed(?::\s*([a-zA-Z0-9_.-]+))?/,
    );
    const toolName = match?.[1]?.trim();
    return toolName
      ? `工具「${toolName}」已被项目策略禁用，无法执行`
      : "工具调用受限，已被项目策略禁用";
  }
  return raw;
}

const resolvedState = computed<SessionTurnState>(() => {
  if (props.turnState) {
    return props.turnState;
  }
  if (props.error) return "error";
  if (props.isInterrupted) return "awaiting_review";
  if (props.isRunning) return "running";
  return "idle";
});

const shouldRender = computed(() => {
  if (props.turnState) {
    return (
      props.turnState === "stopping" ||
      props.turnState === "stop_unconfirmed" ||
      props.turnState === "timeout" ||
      props.turnState === "awaiting_review" ||
      props.turnState === "stopped" ||
      props.turnState === "error" ||
      Boolean(props.error)
    );
  }
  return props.isInterrupted || Boolean(props.error);
});

const statusText = computed(() => {
  switch (resolvedState.value) {
    case "timeout":
      return "上一回合执行超时，已完成的内容已保留";
    case "stopping":
      return "正在停止...";
    case "stop_unconfirmed":
      return "停止结果待确认";
    case "stopped":
      return "已停止";
    case "awaiting_review":
      return "等待人工确认";
    case "error":
      return props.error ? `执行出错: ${formatError(props.error)}` : "执行出错";
    case "running":
      return "Agent 正在执行...";
    default:
      return props.lastEventAt
        ? `最后活跃于 ${formatThreadTime(props.lastEventAt)}`
        : "就绪";
  }
});

const statusIcon = computed(() => {
  switch (resolvedState.value) {
    case "timeout":
    case "stop_unconfirmed":
    case "awaiting_review":
      return "alert";
    case "stopping":
    case "running":
      return "refresh";
    case "error":
      return "x";
    case "stopped":
    default:
      return "check";
  }
});

const isSpinning = computed(() => {
  return (
    resolvedState.value === "stopping" ||
    (resolvedState.value === "running" && props.isRunning)
  );
});

const isAmber = computed(() => {
  return (
    resolvedState.value === "timeout" ||
    resolvedState.value === "stop_unconfirmed" ||
    resolvedState.value === "awaiting_review"
  );
});

const isError = computed(() => resolvedState.value === "error");
const isBlue = computed(
  () => resolvedState.value === "stopping" || resolvedState.value === "running",
);
</script>

<template>
  <div
    v-if="shouldRender"
    class="flex flex-wrap sm:flex-nowrap items-center justify-between p-3 rounded-lg border shadow-sm transition-all gap-2"
    :class="{
      'bg-blue-50 border-blue-200': isBlue,
      'bg-amber-50 border-amber-200': isAmber,
      'bg-red-50 border-red-200': isError,
      'bg-gray-50 border-gray-200': resolvedState === 'stopped',
    }"
  >
    <div class="flex items-center gap-3 min-w-0 flex-1">
      <BaseIcon
        :name="statusIcon"
        class="shrink-0"
        :class="{
          'animate-spin text-blue-500': isSpinning,
          'text-amber-500': isAmber,
          'text-red-500': isError,
          'text-gray-500': resolvedState === 'stopped',
        }"
      />
      <span
        class="text-sm font-medium break-words"
        :class="{
          'text-blue-800': isBlue,
          'text-amber-800': isAmber,
          'text-red-800': isError,
          'text-gray-700': resolvedState === 'stopped',
        }"
        :title="statusText"
        >{{ statusText }}</span
      >
    </div>

    <!-- 停止待确认：核实停止按钮 -->
    <div
      v-if="resolvedState === 'stop_unconfirmed'"
      class="flex items-center gap-2 mt-2 sm:mt-0 shrink-0"
    >
      <button
        type="button"
        :disabled="disabled"
        class="px-3 py-1.5 text-xs font-medium text-amber-900 bg-white border border-amber-300 rounded hover:bg-amber-50 focus:outline-none focus:ring-2 focus:ring-amber-500 transition-colors disabled:opacity-50"
        @click="emit('verifyStop')"
      >
        核实停止
      </button>
    </div>

    <!-- 人工审批：查看审批按钮（严禁在 stopping/stop_unconfirmed 下显示） -->
    <div
      v-else-if="resolvedState === 'awaiting_review'"
      class="flex items-center gap-2 mt-2 sm:mt-0 shrink-0"
    >
      <button
        v-if="isRunning"
        :disabled="disabled"
        class="px-3 py-1.5 text-xs text-gray-600 bg-white border border-gray-300 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200 transition-colors"
        @click="emit('cancel')"
      >
        取消
      </button>
      <button
        class="px-3 py-1.5 text-xs font-medium text-white bg-amber-600 rounded hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500 transition-colors"
        @click="emit('resume')"
      >
        查看审批
      </button>
    </div>
  </div>
</template>
