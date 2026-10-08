<script setup lang="ts">
import type { PreparationSummaryItem } from "../../diagnostics/types";
import {
  formatDuration,
  getPreparationComponentLabel,
  getPreparationErrorCodeLabel,
  getPreparationOutcomeBadge,
} from "../../diagnostics/view-model";

defineProps<{
  preparations: PreparationSummaryItem[];
}>();
</script>

<template>
  <div
    v-if="preparations.length > 0"
    class="space-y-2"
    data-testid="run-preparations-section"
  >
    <div class="flex items-center justify-between">
      <span
        class="font-semibold text-gray-700 dark:text-gray-300 text-[11px] uppercase tracking-wider"
      >
        运行准备记录
      </span>
      <span class="text-[10px] text-gray-400 font-mono">
        共 {{ preparations.length }} 项
      </span>
    </div>

    <div class="space-y-2">
      <div
        v-for="item in preparations"
        :key="item.observation_id"
        class="rounded-lg border p-2.5 space-y-1 font-mono text-[11px] border-gray-100 bg-gray-50/40 dark:border-dark-800 dark:bg-dark-950/30"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-1.5 min-w-0">
            <span
              class="font-semibold text-gray-800 dark:text-gray-200 truncate"
            >
              {{ getPreparationComponentLabel(item.component) }}
            </span>
            <span
              v-if="item.scope === 'subagent'"
              class="rounded bg-gray-200/70 dark:bg-dark-700 px-1 py-0.2 text-[9px] text-gray-600 dark:text-gray-300"
            >
              子智能体
            </span>
          </div>

          <div class="flex items-center gap-1.5 shrink-0">
            <span
              v-if="item.duration_ms !== null"
              class="text-[10px] text-gray-500 dark:text-dark-400"
            >
              {{ formatDuration(item.duration_ms) }}
            </span>
            <span
              class="rounded px-1.5 py-0.5 leading-none text-[9px] font-semibold"
              :class="{
                'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900':
                  getPreparationOutcomeBadge(item.outcome).variant ===
                  'success',
                'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-200 dark:border-blue-900':
                  getPreparationOutcomeBadge(item.outcome).variant === 'blue',
                'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-900':
                  getPreparationOutcomeBadge(item.outcome).variant ===
                  'warning',
                'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300 border border-red-200 dark:border-red-900':
                  getPreparationOutcomeBadge(item.outcome).variant === 'error',
                'bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-gray-300':
                  getPreparationOutcomeBadge(item.outcome).variant === 'muted',
              }"
            >
              {{ getPreparationOutcomeBadge(item.outcome).label }}
            </span>
          </div>
        </div>

        <div
          v-if="item.error_code"
          class="text-[10px] text-red-600 dark:text-red-400 font-sans"
        >
          异常说明：{{ getPreparationErrorCodeLabel(item.error_code) }}
        </div>

        <div
          v-if="item.namespace.length > 0"
          class="text-[10px] text-gray-400 truncate"
          :title="item.namespace.join(' / ')"
        >
          Namespace: {{ item.namespace.join(" / ") }}
        </div>
      </div>
    </div>
  </div>
</template>
