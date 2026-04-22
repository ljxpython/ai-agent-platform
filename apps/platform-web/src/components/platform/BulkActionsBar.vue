<script setup lang="ts">
import { computed, ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import type { BulkActionItem } from '@/components/platform/data-table'

withDefaults(
  defineProps<{
    selectedCount: number
    actions?: BulkActionItem[]
    summary?: string
    clearLabel?: string
  }>(),
  {
    actions: () => [],
    summary: '',
    clearLabel: '清空选择'
  }
)

const emit = defineEmits<{
  clear: []
}>()

const pendingKey = ref('')
const busy = computed(() => Boolean(pendingKey.value))

async function handleAction(action: BulkActionItem) {
  if (action.disabled || busy.value) {
    return
  }

  pendingKey.value = action.key

  try {
    await action.onSelect()
  } finally {
    pendingKey.value = ''
  }
}
</script>

<template>
  <div
    v-if="selectedCount > 0"
    class="pw-bulk-actions-bar"
  >
    <div class="min-w-0">
      <div class="text-sm font-semibold text-gray-900 dark:text-white">
        已选择 {{ selectedCount }} 项
      </div>
      <p
        v-if="summary"
        class="mt-1 text-sm text-gray-500 dark:text-dark-300"
      >
        {{ summary }}
      </p>
    </div>

    <div class="flex flex-wrap items-center justify-end gap-2">
      <BaseButton
        v-for="action in actions"
        :key="action.key"
        :variant="action.variant || 'secondary'"
        :disabled="action.disabled || busy"
        @click="handleAction(action)"
      >
        <BaseIcon
          v-if="action.icon"
          :name="action.icon as never"
          size="sm"
        />
        {{ action.label }}
      </BaseButton>

      <BaseButton
        variant="ghost"
        :disabled="busy"
        @click="emit('clear')"
      >
        <BaseIcon
          name="x"
          size="sm"
        />
        {{ clearLabel }}
      </BaseButton>
    </div>
  </div>
</template>
