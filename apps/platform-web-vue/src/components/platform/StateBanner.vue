<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description: string
    variant?: 'info' | 'success' | 'warning' | 'danger'
  }>(),
  {
    variant: 'info'
  }
)
</script>

<template>
  <div
    class="pw-banner"
    :class="
      variant === 'info'
        ? 'pw-banner-info'
        : variant === 'success'
          ? 'pw-banner-success'
          : variant === 'warning'
            ? 'pw-banner-warning'
            : 'pw-banner-danger'
    "
  >
    <div class="text-sm font-semibold text-slate-900 dark:text-white">
      {{ title }}
    </div>
    <p class="mt-2 text-sm leading-6 text-slate-600 dark:text-dark-300">
      {{ description }}
    </p>
  </div>
</template>
