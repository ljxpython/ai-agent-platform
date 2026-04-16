<script setup lang="ts">
import { onClickOutside } from '@vueuse/core'
import { computed, ref } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'

const props = defineProps<{
  labels: string[]
  popularLabels: string[]
  queryInput: string
  selectedLabel: string
  loadingLabels: boolean
  loadingGraph: boolean
  canRead: boolean
}>()

const emit = defineEmits<{
  (event: 'update:queryInput', value: string): void
  (event: 'load-labels'): void
  (event: 'refresh-graph'): void
  (event: 'open-graph', label: string): void
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)
const displayLabel = computed(() => props.selectedLabel || '*')
const mergedOptions = computed(() => {
  const source = props.queryInput.trim() ? props.labels : props.popularLabels.length ? props.popularLabels : props.labels
  const unique = Array.from(new Set(['*', ...source]))
  return unique.slice(0, 12)
})

function handleSelect(label: string) {
  open.value = false
  emit('open-graph', label)
}

onClickOutside(rootRef, () => {
  open.value = false
})
</script>

<template>
  <div
    ref="rootRef"
    class="pointer-events-auto flex items-center gap-2"
  >
    <button
      type="button"
      class="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white/96 text-gray-500 shadow-sm transition hover:border-primary-300 hover:text-primary-700 dark:border-dark-700 dark:bg-dark-900/95 dark:text-dark-300"
      :disabled="loadingGraph || !canRead"
      @click="emit('refresh-graph')"
    >
      <BaseIcon
        name="refresh"
        size="xs"
      />
    </button>

    <div class="relative w-full min-w-[240px] max-w-[400px]">
      <button
        type="button"
        class="flex h-8 w-full items-center justify-between rounded-lg border border-gray-200 bg-white/96 px-3 text-sm font-medium text-gray-800 shadow-sm transition hover:border-primary-300 dark:border-dark-700 dark:bg-dark-900/95 dark:text-dark-100"
        @click="open = !open"
      >
        <span class="truncate">{{ displayLabel }}</span>
        <BaseIcon
          name="chevron-down"
          size="xs"
        />
      </button>

      <div
        v-if="open"
        class="absolute left-0 right-0 top-10 z-20 overflow-hidden rounded-xl border border-gray-200 bg-white/98 p-2 shadow-xl backdrop-blur-md dark:border-dark-700 dark:bg-dark-900/98"
      >
        <div class="flex items-center gap-2">
          <BaseInput
            :model-value="queryInput"
            placeholder="搜索节点名称"
            @focus="open = true"
            @update:model-value="emit('update:queryInput', String($event || ''))"
          />
          <button
            type="button"
            class="rounded-lg px-2 py-1.5 text-xs text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-white"
            :disabled="loadingLabels || !canRead"
            @click="emit('load-labels')"
          >
            查找
          </button>
        </div>

        <div class="mt-2 max-h-72 overflow-y-auto">
          <button
            v-for="label in mergedOptions"
            :key="label"
            type="button"
            class="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition hover:bg-gray-50 dark:hover:bg-dark-800/80"
            @click="handleSelect(label)"
          >
            <span class="truncate">{{ label }}</span>
            <span
              v-if="selectedLabel === label"
              class="text-[10px] text-primary-600 dark:text-primary-300"
            >
              current
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
