<script setup lang="ts">
import { computed } from 'vue'
import type { ChatToolCallCard } from '../message-meta-view-model'

const props = defineProps<{
  tool: ChatToolCallCard
}>()

const shouldRenderChartImage = computed(
  () => props.tool.resultRenderMode === 'chart-image' && typeof props.tool.resultImageUrl === 'string'
)
</script>

<template>
  <div
    v-if="shouldRenderChartImage"
    class="space-y-3"
  >
    <div class="overflow-hidden rounded-xl border border-slate-200/80 bg-white dark:border-dark-700 dark:bg-dark-950/80">
      <div class="border-b border-slate-200/80 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:border-dark-700 dark:text-dark-400">
        Chart
      </div>
      <div class="bg-slate-50/80 p-3 dark:bg-dark-900/70">
        <img
          :src="tool.resultImageUrl"
          :alt="`${tool.name} chart result`"
          class="block max-h-[420px] w-full rounded-lg border border-slate-200/80 bg-white object-contain dark:border-dark-700 dark:bg-dark-950"
          loading="lazy"
          referrerpolicy="no-referrer"
        >
      </div>
    </div>

    <div class="flex items-center justify-end">
      <a
        :href="tool.resultImageUrl"
        target="_blank"
        rel="noreferrer noopener"
        class="pw-table-tool-button inline-flex h-8 items-center rounded-lg px-3 text-xs"
      >
        打开图表
      </a>
    </div>
  </div>

  <pre
    v-else-if="tool.resultText"
    class="pw-panel-muted overflow-auto whitespace-pre-wrap break-words px-3 py-3 text-xs leading-6 text-gray-600 dark:text-dark-100"
  >{{ tool.resultText }}</pre>
</template>
