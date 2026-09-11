<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { formatThreadTime } from '@/utils/threads'

const props = defineProps<{
  isRunning: boolean
  isInterrupted: boolean
  error?: string
  lastEventAt?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'resume': []
  'cancel': []
}>()

const statusText = computed(() => {
  if (props.isRunning) return 'Agent 正在执行...'
  if (props.isInterrupted) return '等待人工确认'
  if (props.error) return `执行出错: ${props.error}`
  return props.lastEventAt ? `最后活跃于 ${formatThreadTime(props.lastEventAt)}` : '就绪'
})

const statusIcon = computed(() => {
  if (props.isRunning) return 'refresh'
  if (props.isInterrupted) return 'alert'
  if (props.error) return 'x'
  return 'check'
})
</script>

<template>
  <div
    v-if="isRunning || isInterrupted || error"
    class="flex flex-wrap sm:flex-nowrap items-center justify-between p-3 rounded-lg border shadow-sm transition-all"
    :class="{
      'bg-blue-50 border-blue-200': isRunning,
      'bg-amber-50 border-amber-200': isInterrupted,
      'bg-red-50 border-red-200': error
    }"
  >
    <div class="flex items-center gap-3 w-full sm:w-auto overflow-hidden">
      <BaseIcon
        :name="statusIcon"
        :class="{
          'animate-spin text-blue-500': isRunning,
          'text-amber-500': isInterrupted,
          'text-red-500': error
        }"
      />
      <span
        class="text-sm font-medium truncate"
        :class="{
          'text-blue-800': isRunning,
          'text-amber-800': isInterrupted,
          'text-red-800': error
        }"
        :title="statusText"
      >{{ statusText }}</span>
    </div>

    <div
      v-if="isInterrupted"
      class="flex items-center gap-2 mt-2 sm:mt-0 shrink-0"
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
  </div>
</template>
