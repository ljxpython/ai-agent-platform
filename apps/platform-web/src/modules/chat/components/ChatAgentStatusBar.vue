<script setup lang="ts">
import { computed } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { formatThreadTime } from "@/utils/threads";
import type { BudgetViewModel } from "../budget/view-model";

const props = defineProps<{
  isRunning: boolean;
  isInterrupted: boolean;
  error?: string;
  lastEventAt?: string;
  disabled?: boolean;
  budget?: BudgetViewModel | null;
}>();

const emit = defineEmits<{
  resume: [];
  cancel: [];
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

const statusText = computed(() => {
  // 1. Interrupted has highest display priority
  if (props.isInterrupted) {
    return "等待人工确认";
  }
  // 2. 如果正在运行中，显示执行态或实时预警
  if (props.isRunning) {
    if (props.budget && !props.budget.isTerminal) {
      return `${props.budget.title}（${props.budget.description}）`;
    }
    return "Agent 正在执行...";
  }
  // 3. Budget terminal stop (e.g. model reached, safety error)
  if (props.budget?.isTerminal) {
    return `${props.budget.title}：${props.budget.description}`;
  }
  // 4. Native error
  if (props.error) {
    return `执行出错: ${formatError(props.error)}`;
  }
  // 5. Budget in-flight warning
  if (props.budget && !props.budget.isTerminal) {
    return `${props.budget.title}（${props.budget.description}）`;
  }
  return props.lastEventAt
    ? `最后活跃于 ${formatThreadTime(props.lastEventAt)}`
    : "就绪";
});

const statusIcon = computed(() => {
  if (props.isInterrupted) return "alert";
  if (props.budget && !props.budget.isTerminal) return "alert";
  if (props.isRunning) return "refresh";
  if (props.budget?.isTerminal || props.error) return "x";
  return "check";
});

const isWarningState = computed(() => {
  return (
    props.isInterrupted || (props.budget != null && !props.budget.isTerminal)
  );
});

const isErrorState = computed(() => {
  if (props.isRunning) return false;
  return Boolean(props.error || props.budget?.isTerminal);
});

const shouldRender = computed(() => {
  if (props.isInterrupted) return true;
  if (props.isRunning) {
    return Boolean(props.budget && !props.budget.isTerminal);
  }
  return Boolean(props.error || props.budget);
});
</script>

<template>
  <div
    v-if="shouldRender"
    aria-live="polite"
    class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 rounded-lg border shadow-sm transition-all"
    :class="{
      'bg-blue-50 border-blue-200':
        isRunning && !isWarningState && !isErrorState,
      'bg-amber-50 border-amber-200': isWarningState,
      'bg-red-50 border-red-200': isErrorState,
    }"
  >
    <div class="flex items-start sm:items-center gap-3 flex-1 min-w-0">
      <BaseIcon
        :name="statusIcon"
        class="shrink-0 mt-0.5 sm:mt-0"
        :class="{
          'animate-spin text-blue-500':
            isRunning && !isWarningState && !isErrorState,
          'text-amber-500': isWarningState,
          'text-red-500': isErrorState,
        }"
      />
      <span
        class="text-sm font-medium leading-relaxed break-words flex-1"
        :class="{
          'text-blue-800': isRunning && !isWarningState && !isErrorState,
          'text-amber-800': isWarningState,
          'text-red-800': isErrorState,
        }"
        :title="statusText"
        >{{ statusText }}</span
      >
    </div>

    <div
      v-if="
        isInterrupted || (budget && budget.actionType !== 'none') || isRunning
      "
      class="flex items-center gap-2 shrink-0 self-end sm:self-center"
    >
      <template v-if="isInterrupted">
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
      </template>

      <template v-else-if="budget?.actionType === 'adjust_draft'">
        <button
          class="px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 transition-colors"
          @click="emit('action', 'adjust_draft')"
        >
          {{ budget.actionLabel || "调整请求" }}
        </button>
      </template>

      <template v-else-if="budget?.actionType === 'new_thread'">
        <button
          class="px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 transition-colors"
          @click="emit('action', 'new_thread')"
        >
          {{ budget.actionLabel || "新建会话" }}
        </button>
      </template>

      <template v-else-if="isRunning">
        <button
          :disabled="disabled"
          class="px-3 py-1.5 text-xs text-gray-600 bg-white border border-gray-300 rounded hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-200 transition-colors"
          @click="emit('cancel')"
        >
          取消
        </button>
      </template>
    </div>
  </div>
</template>
