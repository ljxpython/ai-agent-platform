<script setup lang="ts">
import { computed } from "vue";
import type { RetrySummaryItem } from "../../diagnostics/types";
import {
  formatAttempts,
  formatDuration,
  getModelErrorCodeLabel,
  getRetryOutcomeBadge,
  getRetrySeverity,
  getRetryUnitLabel,
} from "../../diagnostics/view-model";

const props = defineProps<{
  retries: RetrySummaryItem[];
  runStatus?: string | null;
}>();

const hasRecoveredAttempt = computed(() => {
  return (
    props.runStatus === "success" &&
    props.retries.some((r) => r.outcome !== "success" || r.attempts > 1)
  );
});
</script>

<template>
  <div
    v-if="retries.length > 0"
    class="space-y-2"
    data-testid="run-retries-section"
  >
    <div class="flex items-center justify-between">
      <span
        class="font-semibold text-gray-700 dark:text-gray-300 text-[11px] uppercase tracking-wider"
      >
        调用尝试与重试
      </span>
      <span
        v-if="hasRecoveredAttempt"
        class="text-[10px] text-amber-600 dark:text-amber-400"
      >
        已通过重试或备选路径完成
      </span>
      <span v-else class="text-[10px] text-gray-400 font-mono">
        共 {{ retries.length }} 项
      </span>
    </div>

    <div class="space-y-2">
      <div
        v-for="item in retries"
        :key="item.observation_id"
        class="rounded-lg border p-2.5 space-y-1 font-mono text-[11px]"
        :class="{
          'border-emerald-200 bg-emerald-50/50 text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300':
            getRetrySeverity(item.outcome, runStatus) === 'success',
          'border-amber-200 bg-amber-50/60 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300':
            getRetrySeverity(item.outcome, runStatus) === 'warning',
          'border-red-200 bg-red-50/60 text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300':
            getRetrySeverity(item.outcome, runStatus) === 'error',
          'border-gray-200 bg-gray-50/60 text-gray-700 dark:border-dark-700 dark:bg-dark-800/40 dark:text-gray-300':
            getRetrySeverity(item.outcome, runStatus) === 'muted',
        }"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-1.5 min-w-0">
            <span class="font-semibold truncate">
              {{ getRetryUnitLabel(item.unit, item.role) }}
            </span>
            <span
              v-if="item.scope === 'subagent'"
              class="rounded bg-black/5 dark:bg-white/10 px-1 py-0.2 text-[9px]"
            >
              子智能体
            </span>
          </div>

          <div class="flex items-center gap-1.5 shrink-0">
            <!-- 尝试次数徽章 -->
            <span
              class="rounded px-1.5 py-0.5 leading-none text-[9px] font-mono border"
              :class="
                item.attempts > 1
                  ? 'bg-amber-100/80 border-amber-300 text-amber-800 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-300'
                  : 'bg-white/80 border-gray-200 text-gray-600 dark:bg-dark-900 dark:border-dark-700 dark:text-gray-400'
              "
            >
              {{ formatAttempts(item.attempts) }}
            </span>

            <!-- 结果徽章 -->
            <span
              class="rounded px-1.5 py-0.5 leading-none text-[9px] font-semibold"
              :class="{
                'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300':
                  getRetryOutcomeBadge(item.outcome, runStatus).variant ===
                  'success',
                'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300':
                  getRetryOutcomeBadge(item.outcome, runStatus).variant ===
                  'warning',
                'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300':
                  getRetryOutcomeBadge(item.outcome, runStatus).variant ===
                  'error',
                'bg-gray-200 text-gray-700 dark:bg-dark-700 dark:text-gray-300':
                  getRetryOutcomeBadge(item.outcome, runStatus).variant ===
                  'muted',
              }"
            >
              {{ getRetryOutcomeBadge(item.outcome, runStatus).label }}
            </span>
          </div>
        </div>

        <!-- 详细信息：耗时与错误码 -->
        <div class="flex items-center gap-2 text-[10px] opacity-80">
          <span v-if="item.duration_ms !== null">
            耗时: {{ formatDuration(item.duration_ms) }}
          </span>
          <span v-if="item.code">
            原因: {{ getModelErrorCodeLabel(item.code) }}
          </span>
        </div>

        <!-- Namespace 截短显示 -->
        <div
          v-if="item.namespace.length > 0"
          class="text-[10px] opacity-60 truncate"
          :title="item.namespace.join(' / ')"
        >
          Namespace: {{ item.namespace.join(" / ") }}
        </div>
      </div>
    </div>
  </div>
</template>
