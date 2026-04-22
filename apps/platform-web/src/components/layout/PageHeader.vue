<script setup lang="ts">
defineProps<{
  title: string
  description: string
  eyebrow?: string
  compact?: boolean
}>()
</script>

<template>
  <header
    class="pw-page-header transition-all duration-200"
    :class="compact ? 'mb-1 gap-1.5 xl:items-center' : ''"
  >
    <div>
      <div
        v-if="eyebrow"
        class="pw-page-eyebrow transition-all duration-200"
        :class="compact ? 'text-[10px] tracking-[0.14em]' : ''"
      >
        {{ eyebrow }}
      </div>
      <h1
        class="pw-page-title mt-1 transition-all duration-200"
        :class="compact ? 'text-[18px] md:text-[20px]' : ''"
      >
        {{ title }}
      </h1>
      <p
        class="pw-page-description transition-all duration-200"
        :class="compact ? 'mt-0 hidden' : ''"
      >
        {{ description }}
      </p>
    </div>
    <div
      v-if="$slots.actions"
      class="flex flex-wrap items-center gap-3 transition-all duration-200"
      :class="compact ? 'gap-1.5' : ''"
    >
      <slot name="actions" />
    </div>
  </header>
</template>
