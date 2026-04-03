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

const textClass = computed(() => {
  const variants: Record<NonNullable<typeof props.tone>, string> = {
    neutral: 'text-slate-600 dark:text-dark-300',
    info: 'text-primary-700 dark:text-primary-300',
    success: 'text-emerald-700 dark:text-emerald-300',
    warning: 'text-amber-700 dark:text-amber-300',
    danger: 'text-rose-700 dark:text-rose-300'
  }

  return variants[props.tone]
})

const dotClass = computed(() => {
  const variants: Record<NonNullable<typeof props.tone>, string> = {
    neutral: 'bg-slate-400',
    info: 'bg-primary-500',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-rose-500'
  }

  return variants[props.tone]
})
</script>

<template>
  <span class="inline-flex items-center gap-2">
    <span
      class="h-2.5 w-2.5 rounded-full"
      :class="dotClass"
    />
    <span
      class="text-sm"
      :class="textClass"
    >
      <slot />
    </span>
  </span>
</template>
