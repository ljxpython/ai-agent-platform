<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'

const props = withDefaults(
  defineProps<{
    label: string
    value: number | string
    hint: string
    icon?: string
    tone?: string
  }>(),
  {
    icon: 'overview',
    tone: 'primary'
  }
)

const iconClass = computed(() => {
  const variants: Record<string, string> = {
    primary: 'bg-primary-100 text-primary-600 dark:bg-primary-950/40 dark:text-primary-300',
    success: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300',
    warning: 'bg-amber-100 text-amber-600 dark:bg-amber-950/40 dark:text-amber-300',
    danger: 'bg-rose-100 text-rose-600 dark:bg-rose-950/40 dark:text-rose-300'
  }

  return variants[props.tone] || variants.primary
})
</script>

<template>
  <article class="pw-stat-card pw-card-hover">
    <div
      class="pw-stat-icon"
      :class="iconClass"
    >
      <BaseIcon
        :name="icon as never"
        size="md"
      />
    </div>
    <div class="min-w-0 flex-1">
      <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
        {{ label }}
      </div>
      <div class="mt-2 text-[28px] font-semibold tracking-tight text-gray-950 dark:text-white">
        {{ value }}
      </div>
      <p class="mt-2 text-sm leading-6 text-gray-500 dark:text-dark-300">
        {{ hint }}
      </p>
    </div>
  </article>
</template>
