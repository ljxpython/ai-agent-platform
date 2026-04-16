<script setup lang="ts">
import { onClickOutside } from '@vueuse/core'
import { computed, ref } from 'vue'
import BaseInput from '@/components/base/BaseInput.vue'
import type { KnowledgeGraphNodeSummary } from '@/modules/knowledge/utils/knowledge-graph-types'

const props = defineProps<{
  modelValue: string
  matches: KnowledgeGraphNodeSummary[]
  quickFocusNodes: KnowledgeGraphNodeSummary[]
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'preview-node', nodeId: string): void
  (event: 'clear-preview'): void
  (event: 'focus-node', nodeId: string): void
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)

const options = computed(() => props.quickFocusNodes.slice(0, 8))

function handleFocus() {
  open.value = true
}

function handlePreview(nodeId: string) {
  emit('preview-node', nodeId)
}

function handleSelect(nodeId: string) {
  emit('focus-node', nodeId)
  open.value = false
}

onClickOutside(rootRef, () => {
  open.value = false
  emit('clear-preview')
})
</script>

<template>
  <div
    ref="rootRef"
    class="w-[320px] overflow-visible rounded-xl border border-gray-200 bg-white/96 p-1.5 shadow-lg backdrop-blur-md dark:border-dark-700 dark:bg-dark-900/95"
  >
    <div class="flex items-center gap-2 rounded-lg">
      <BaseInput
        :model-value="modelValue"
        placeholder="搜索当前子图中的节点"
        @focus="handleFocus"
        @update:model-value="emit('update:modelValue', String($event || ''))"
      />
      <span class="shrink-0 text-[10px] text-gray-400 dark:text-dark-500">{{ matches.length }}</span>
    </div>

    <div
      v-if="open"
      class="mt-2 max-h-[260px] space-y-1 overflow-y-auto"
    >
      <div v-if="options.length">
        <button
          v-for="node in options"
          :key="node.id"
          type="button"
          class="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition hover:bg-gray-50 dark:hover:bg-dark-800/80"
          @mouseenter="handlePreview(node.id)"
          @focus="handlePreview(node.id)"
          @click="handleSelect(node.id)"
        >
          <div class="flex min-w-0 items-center gap-2">
            <span
              class="h-2.5 w-2.5 shrink-0 rounded-full"
              :style="{ backgroundColor: node.color }"
            />
            <div class="truncate text-sm font-medium text-gray-800 dark:text-dark-100">{{ node.label }}</div>
          </div>
          <div class="min-w-0 text-right">
            <div class="mt-1 text-xs text-gray-400 dark:text-dark-500">
              {{ node.typeLabel }} · degree {{ node.degree }}
            </div>
          </div>
        </button>
      </div>

      <p
        v-else
        class="px-3 py-2 text-sm text-gray-500 dark:text-dark-300"
      >
        当前没有符合搜索条件的节点。
      </p>
    </div>
  </div>
</template>
