<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger'
  }>(),
  {
    tone: 'neutral'
  }
)

const pillClass = computed(() => {
  const variants: Record<NonNullable<typeof props.tone>, string> = {
    neutral: 'border-gray-200 bg-gray-50 text-gray-600 dark:border-dark-700 dark:bg-dark-900/80 dark:text-dark-300',
    info: 'border-primary-100 bg-primary-50 text-primary-700 dark:border-primary-900/40 dark:bg-primary-950/20 dark:text-primary-300',
    success: 'border-emerald-100 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300',
    warning: 'border-amber-100 bg-amber-50 text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300',
    danger: 'border-rose-100 bg-rose-50 text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/20 dark:text-rose-300'
  }

  return variants[props.tone]
})

const dotClass = computed(() => {
  const variants: Record<NonNullable<typeof props.tone>, string> = {
    neutral: 'bg-gray-400',
    info: 'bg-primary-500',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-rose-500'
  }

  return variants[props.tone]
})
</script>

<template>
  <span
    class="inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium"
    :class="pillClass"
  >
    <span
      class="h-2 w-2 rounded-full"
      :class="dotClass"
    />
    <span>
      <slot />
    </span>
  </span>
</template>
