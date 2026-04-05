<script setup lang="ts">
defineProps<{
  title: string
  description: string
  eyebrow?: string
}>()
</script>

<template>
  <header class="pw-page-header">
    <div>
      <div
        v-if="eyebrow"
        class="pw-page-eyebrow"
      >
        {{ eyebrow }}
      </div>
      <h1 class="pw-page-title mt-1">
        {{ title }}
      </h1>
      <p class="pw-page-description">
        {{ description }}
      </p>
    </div>
    <div
      v-if="$slots.actions"
      class="flex flex-wrap items-center gap-3"
    >
      <slot name="actions" />
    </div>
  </header>
</template>
