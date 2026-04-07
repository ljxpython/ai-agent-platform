<script setup lang="ts">
import { computed } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'

const props = withDefaults(
  defineProps<{
    title: string
    description: string
    variant?: 'info' | 'success' | 'warning' | 'danger'
  }>(),
  {
    variant: 'info'
  }
)

const bannerClass = computed(() => {
  if (props.variant === 'success') {
    return 'pw-banner-success'
  }

  if (props.variant === 'warning') {
    return 'pw-banner-warning'
  }

  if (props.variant === 'danger') {
    return 'pw-banner-danger'
  }

  return 'pw-banner-info'
})

const iconClass = computed(() => {
  const variants: Record<NonNullable<typeof props.variant>, string> = {
    info: 'bg-primary-100 text-primary-700 dark:bg-primary-950/40 dark:text-primary-300',
    success: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
    warning: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
    danger: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
  }

  return variants[props.variant]
})

const iconName = computed(() => {
  const variants: Record<NonNullable<typeof props.variant>, 'sparkle' | 'shield' | 'activity'> = {
    info: 'sparkle',
    success: 'shield',
    warning: 'activity',
    danger: 'activity'
  }

  return variants[props.variant]
})
</script>

<template>
  <div
    class="pw-banner"
    :class="bannerClass"
  >
    <div class="flex items-start gap-3">
      <div
        class="mt-0.5 flex h-8 w-8 items-center justify-center rounded-xl"
        :class="iconClass"
      >
        <BaseIcon
          :name="iconName"
          size="sm"
        />
      </div>
      <div class="min-w-0">
        <div class="text-sm font-semibold text-gray-900 dark:text-white">
          {{ title }}
        </div>
        <p class="mt-1.5 text-sm leading-6 text-gray-600 dark:text-dark-300">
          {{ description }}
        </p>
      </div>
    </div>
  </div>
</template>
