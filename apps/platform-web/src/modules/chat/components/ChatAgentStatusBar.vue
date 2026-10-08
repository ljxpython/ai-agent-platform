<script setup lang="ts">
import { computed } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { formatThreadTime } from "@/utils/threads";
import type { SessionTurnState } from "../composables/useChatSession";
import type { BudgetViewModel } from "../budget/view-model";

const props = defineProps<{
  isRunning: boolean;
  isInterrupted: boolean;
  error?: string;
  lastEventAt?: string;
  disabled?: boolean;
  turnState?: SessionTurnState;
  budget?: BudgetViewModel | null;
}>();

const emit = defineEmits<{
  resume: [];
  cancel: [];
  verifyStop: [];
  action: [type: "adjust_draft" | "new_thread"];
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
      Boolean(props.error) ||
      Boolean(props.budget)
    );
  }
  if (props.isInterrupted) return true;
  if (props.isRunning) {
    return Boolean(props.budget && !props.budget.isTerminal);
  }
  return Boolean(props.error || props.budget);
});

const statusText = computed(() => {
  // 1. 人工审批最高优先级
  if (props.isInterrupted || resolvedState.value === "awaiting_review") {
    return "等待人工确认";
  }
  // 2. 超时治理专用状态
  if (resolvedState.value === "timeout") {
    return "上一回合执行超时，已完成的内容已保留";
  }
  if (resolvedState.value === "stopping") {
    return "正在停止...";
  }
  if (resolvedState.value === "stop_unconfirmed") {
    return "停止结果待确认";
  }
  if (resolvedState.value === "stopped") {
    return "已停止";
  }
  // 3. 运行态
  if (props.isRunning) {
    if (props.budget && !props.budget.isTerminal) {
      return `${props.budget.title}（${props.budget.description}）`;
    }
    return "Agent 正在执行...";
  }
  // 4. 终态预算限制
  if (props.budget?.isTerminal) {
    return `${props.budget.title}：${props.budget.description}`;
  }
  // 5. 原生错误
  if (props.error) {
    return `执行出错: ${formatError(props.error)}`;
  }
  // 6. 默认就绪或活跃时间
  return props.lastEventAt
    ? `最后活跃于 ${formatThreadTime(props.lastEventAt)}`
    : "就绪";
});

const statusIcon = computed(() => {
  if (
    resolvedState.value === "timeout" ||
    resolvedState.value === "stop_unconfirmed"
  ) {
    return "alert";
  }
  if (props.isInterrupted || resolvedState.value === "awaiting_review") {
    return "alert";
  }
  if (props.budget && !props.budget.isTerminal) {
    return "alert";
  }
  if (resolvedState.value === "stopping" || props.isRunning) {
    return "refresh";
  }
  if (
    props.budget?.isTerminal ||
    props.error ||
    resolvedState.value === "error"
  ) {
    return "x";
  }
  if (resolvedState.value === "stopped") {
    return "check";
  }
  return "check";
});

const isSpinning = computed(() => {
  return (
    resolvedState.value === "stopping" ||
    (props.isRunning && !isWarningState.value && !isErrorState.value)
  );
});

const isWarningState = computed(() => {
  return (
    props.isInterrupted ||
    resolvedState.value === "awaiting_review" ||
    resolvedState.value === "timeout" ||
    resolvedState.value === "stop_unconfirmed" ||
    (props.budget != null && !props.budget.isTerminal)
  );
});

const isErrorState = computed(() => {
  if (props.isRunning) return false;
  return Boolean(
    props.error || resolvedState.value === "error" || props.budget?.isTerminal,
  );
});

const isBlue = computed(() => {
  return props.isRunning && !isWarningState.value && !isErrorState.value;
});
</script>

<template>
  <div
    v-if="shouldRender"
    aria-live="polite"
    class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 rounded-lg border shadow-sm transition-all"
    :class="{
      'bg-blue-50 border-blue-200': isBlue,
      'bg-amber-50 border-amber-200': isWarningState,
      'bg-red-50 border-red-200': isErrorState,
      'bg-gray-50 border-gray-200': resolvedState === 'stopped',
    }"
  >
    <div class="flex items-start sm:items-center gap-3 flex-1 min-w-0">
      <BaseIcon
        :name="statusIcon"
        class="shrink-0 mt-0.5 sm:mt-0"
        :class="{
          'animate-spin text-blue-500': isSpinning,
          'text-amber-500': isWarningState,
          'text-red-500': isErrorState,
          'text-gray-500': resolvedState === 'stopped',
        }"
      />
      <span
        class="text-sm font-medium leading-relaxed break-words flex-1"
        :class="{
          'text-blue-800': isBlue,
          'text-amber-800': isWarningState,
          'text-red-800': isErrorState,
          'text-gray-700': resolvedState === 'stopped',
        }"
        :title="statusText"
        >{{ statusText }}</span
      >
    </div>

    <!-- 停止待确认：核实停止按钮 -->
    <div
      v-if="resolvedState === 'stop_unconfirmed'"
      class="flex items-center gap-2 shrink-0 self-end sm:self-center"
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

    <!-- 人工审批：查看审批按钮 -->
    <div
      v-else-if="resolvedState === 'awaiting_review' || isInterrupted"
      class="flex items-center gap-2 shrink-0 self-end sm:self-center"
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

    <!-- 预算操作：调整请求 -->
    <div
      v-else-if="budget?.actionType === 'adjust_draft'"
      class="flex items-center gap-2 shrink-0 self-end sm:self-center"
    >
      <button
        class="px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 transition-colors"
        @click="emit('action', 'adjust_draft')"
      >
        {{ budget.actionLabel || "调整请求" }}
      </button>
    </div>

    <!-- 预算操作：新建会话 -->
    <div
      v-else-if="budget?.actionType === 'new_thread'"
      class="flex items-center gap-2 shrink-0 self-end sm:self-center"
    >
      <button
        class="px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 transition-colors"
        @click="emit('action', 'new_thread')"
      >
        {{ budget.actionLabel || "新建会话" }}
      </button>
    </div>

    <!-- 运行中取消按钮 -->
    <div
      v-else-if="isRunning && resolvedState !== 'stopping'"
      class="flex items-center gap-2 shrink-0 self-end sm:self-center"
    >
      <button
        :disabled="disabled"
        class="px-3 py-1.5 text-xs text-gray-600 bg-white border border-gray-300 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200 transition-colors"
        @click="emit('cancel')"
      >
        取消
      </button>
    </div>
  </div>
</template>
