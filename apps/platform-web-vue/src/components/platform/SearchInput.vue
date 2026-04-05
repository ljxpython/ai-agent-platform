<script setup lang="ts">
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'

withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    icon?: 'search' | 'filter'
  }>(),
  {
    placeholder: '',
    icon: 'search'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="relative">
    <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400 dark:text-dark-400">
      <BaseIcon
        :name="icon"
        size="sm"
      />
    </div>
    <BaseInput
      :model-value="modelValue"
      class="pl-10"
      :placeholder="placeholder"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>
</template>
