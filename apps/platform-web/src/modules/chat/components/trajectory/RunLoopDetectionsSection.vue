<script setup lang="ts">
import type { LoopDetectionItem } from "../../diagnostics/types";
import {
  getLoopDetectionBadge,
  getLoopDetectionCodeLabel,
} from "../../diagnostics/view-model";

defineProps<{
  loopDetections: LoopDetectionItem[];
}>();
</script>

<template>
  <div
    v-if="loopDetections.length > 0"
    class="space-y-2"
    data-testid="run-loop-detections-section"
  >
    <div class="flex items-center justify-between">
      <span
        class="font-semibold text-gray-700 dark:text-gray-300 text-[11px] uppercase tracking-wider"
      >
        循环保护记录
      </span>
      <span class="text-[10px] text-gray-400 font-mono">
        共 {{ loopDetections.length }} 条
      </span>
    </div>

    <div class="space-y-2">
      <div
        v-for="item in loopDetections"
        :key="item.observation_id"
        class="rounded-lg border p-2.5 space-y-1 font-mono text-[11px]"
        :class="
          item.code === 'tool_loop_reached'
            ? 'border-red-200 bg-red-50/60 text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300'
            : 'border-amber-200 bg-amber-50/60 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300'
        "
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-1.5 min-w-0">
            <span class="font-semibold truncate font-sans">
              {{ getLoopDetectionCodeLabel(item.code) }}
            </span>
            <span
              v-if="item.scope === 'subagent'"
              class="rounded bg-gray-200/70 dark:bg-dark-700 px-1 py-0.2 text-[9px] text-gray-600 dark:text-gray-300"
            >
              子任务
            </span>
          </div>

          <div class="flex items-center gap-1.5 shrink-0">
            <span class="text-[10px] text-gray-500 dark:text-dark-400">
              重复 {{ item.repetitions }} / 阈值 {{ item.threshold }}
            </span>
            <span
              class="rounded px-1.5 py-0.5 leading-none text-[9px] font-semibold"
              :class="{
                'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-900':
                  getLoopDetectionBadge(item.code).variant === 'warning',
                'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300 border border-red-200 dark:border-red-900':
                  getLoopDetectionBadge(item.code).variant === 'error',
                'bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-gray-300':
                  getLoopDetectionBadge(item.code).variant === 'muted',
              }"
            >
              {{ getLoopDetectionBadge(item.code).label }}
            </span>
          </div>
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
