<script setup lang="ts">
import type { AssistantPendingReview } from "../types";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

defineProps<{
  review: AssistantPendingReview;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  (e: "decision", decision: "approve" | "reject"): void;
}>();
</script>

<template>
  <div
    class="flex flex-col bg-white dark:bg-dark-900 border-2 border-amber-300 dark:border-amber-700/80 rounded-2xl p-4 shadow-md space-y-3 transition-all"
  >
    <!-- 头部警示条 -->
    <div class="flex items-center gap-2 text-amber-700 dark:text-amber-400">
      <BaseIcon name="alert" class="w-5 h-5 shrink-0 animate-bounce" />
      <span class="text-xs font-bold tracking-tight uppercase">
        需要用户人工确认执行
      </span>
    </div>

    <!-- 待执行的操作列表 -->
    <div
      v-for="(action, index) in review.actions"
      :key="index"
      class="space-y-2 bg-gray-50/80 dark:bg-dark-950/60 p-3 rounded-xl border border-gray-200/70 dark:border-dark-800"
    >
      <div class="flex items-center justify-between text-xs">
        <span
          class="font-bold text-gray-900 dark:text-white flex items-center gap-1.5 font-mono"
        >
          <BaseIcon name="settings-2" class="w-3.5 h-3.5 text-sky-500" />
          {{ action.name }}
        </span>
      </div>

      <p class="text-xs text-gray-600 dark:text-dark-300 leading-relaxed">
        {{ action.description }}
      </p>

      <!-- 参数展示 -->
      <div v-if="action.args && Object.keys(action.args).length > 0">
        <div
          class="text-[10px] font-semibold text-gray-400 dark:text-dark-400 mb-0.5"
        >
          拟执行参数:
        </div>
        <pre
          class="p-2 bg-white dark:bg-dark-900 rounded border border-gray-200 dark:border-dark-700 font-mono text-[11px] text-gray-700 dark:text-dark-300 overflow-x-auto"
          >{{ JSON.stringify(action.args, null, 2) }}</pre
        >
      </div>
    </div>

    <!-- 决策操作栏（仅 执行 vs 不执行） -->
    <div class="flex items-center justify-end gap-3 pt-1">
      <BaseButton
        variant="ghost"
        size="sm"
        :disabled="disabled"
        class="text-gray-600 dark:text-dark-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40"
        data-testid="assistant-reject-btn"
        @click="emit('decision', 'reject')"
      >
        <BaseIcon name="x" class="w-4 h-4 mr-1 text-red-500" />
        不执行 (拒绝)
      </BaseButton>

      <BaseButton
        variant="primary"
        size="sm"
        :disabled="disabled"
        class="bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
        data-testid="assistant-approve-btn"
        @click="emit('decision', 'approve')"
      >
        <BaseIcon name="check" class="w-4 h-4 mr-1" />
        执行 (确认)
      </BaseButton>
    </div>
  </div>
</template>
