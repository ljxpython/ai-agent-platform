<script setup lang="ts">
import BaseSelect from '@/components/base/BaseSelect.vue'
import type { KnowledgeGraphLayoutMode } from '@/modules/knowledge/utils/knowledge-graph-types'

defineProps<{
  maxDepth: number
  maxNodes: number
  layoutMode: KnowledgeGraphLayoutMode
  showNodeLabels: boolean
  showEdgeLabels: boolean
  enableNodeDrag: boolean
}>()

const emit = defineEmits<{
  (event: 'update:maxDepth', value: number): void
  (event: 'update:maxNodes', value: number): void
  (event: 'update:layoutMode', value: KnowledgeGraphLayoutMode): void
  (event: 'update:showNodeLabels', value: boolean): void
  (event: 'update:showEdgeLabels', value: boolean): void
  (event: 'update:enableNodeDrag', value: boolean): void
}>()
</script>

<template>
  <div class="w-72 overflow-hidden rounded-xl border border-gray-200 bg-white/96 shadow-lg backdrop-blur-md dark:border-dark-700 dark:bg-dark-900/95">
    <div class="border-b border-gray-200/80 px-3 py-2 dark:border-dark-700">
    <div class="text-xs font-semibold text-gray-800 dark:text-dark-100">
      图谱设置
    </div>
    </div>

    <div class="space-y-4 p-3">
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
        max_depth
        <input
          :value="maxDepth"
          min="1"
          max="8"
          type="number"
          class="pw-input"
          @input="emit('update:maxDepth', Number(($event.target as HTMLInputElement).value || 3))"
        >
      </label>
      <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
        max_nodes
        <input
          :value="maxNodes"
          min="1"
          max="2000"
          type="number"
          class="pw-input"
          @input="emit('update:maxNodes', Number(($event.target as HTMLInputElement).value || 200))"
        >
      </label>
    </div>

    <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
      布局
      <BaseSelect
        :model-value="layoutMode"
        @update:model-value="emit('update:layoutMode', String($event || 'forceatlas2') as KnowledgeGraphLayoutMode)"
      >
        <option value="forceatlas2">forceatlas2</option>
        <option value="circular">circular</option>
      </BaseSelect>
    </label>

    <div class="grid gap-2 text-sm text-gray-700 dark:text-dark-200">
      <label class="flex items-center gap-2">
        <input
          :checked="showNodeLabels"
          type="checkbox"
          @change="emit('update:showNodeLabels', ($event.target as HTMLInputElement).checked)"
        >
        显示节点标签
      </label>
      <label class="flex items-center gap-2">
        <input
          :checked="showEdgeLabels"
          type="checkbox"
          @change="emit('update:showEdgeLabels', ($event.target as HTMLInputElement).checked)"
        >
        显示边标签
      </label>
      <label class="flex items-center gap-2">
        <input
          :checked="enableNodeDrag"
          type="checkbox"
          @change="emit('update:enableNodeDrag', ($event.target as HTMLInputElement).checked)"
        >
        启用节点拖动
      </label>
    </div>

    <div class="rounded-lg bg-gray-50 px-3 py-3 text-xs text-gray-500 dark:bg-dark-800/80 dark:text-dark-400">
      参数修改后点“刷新”重拉子图；布局切换会直接在当前图里重排。
    </div>
    </div>
  </div>
</template>
