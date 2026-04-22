<script setup lang="ts">
defineProps<{
  items: Array<{ label: string; color: string }>
}>()
</script>

<template>
  <div class="w-56 overflow-hidden rounded-xl border border-gray-200 bg-white/96 shadow-lg backdrop-blur-md dark:border-dark-700 dark:bg-dark-900/95">
    <div class="flex items-center justify-between border-b border-gray-200/80 px-3 py-2 dark:border-dark-700">
      <div class="text-xs font-semibold text-gray-800 dark:text-dark-100">
        Legend
      </div>
      <div class="text-[10px] text-gray-400 dark:text-dark-500">
        {{ items.length }} types
      </div>
    </div>

    <div class="max-h-72 space-y-1 overflow-y-auto p-2">
      <div
        v-for="item in items"
        :key="item.label"
        class="flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-gray-50 dark:hover:bg-dark-800/80"
      >
        <span
          class="h-3 w-3 shrink-0 rounded-full ring-1 ring-gray-200 dark:ring-dark-600"
          :style="{ backgroundColor: item.color }"
        />
        <span class="truncate text-xs text-gray-700 dark:text-dark-200">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>
