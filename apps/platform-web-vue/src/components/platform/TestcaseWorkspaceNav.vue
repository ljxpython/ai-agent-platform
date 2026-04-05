<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const items = computed(() => [
  {
    to: '/workspace/testcase/generate',
    label: 'AI 对话生成'
  },
  {
    to: '/workspace/testcase/cases',
    label: '用例列表'
  },
  {
    to: '/workspace/testcase/documents',
    label: '文档列表'
  }
])

function isActive(path: string) {
  return route.path === path
}
</script>

<template>
  <div class="flex flex-wrap gap-2">
    <router-link
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="inline-flex h-10 items-center rounded-full border px-4 text-sm font-medium transition-colors"
      :class="
        isActive(item.to)
          ? 'border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-900/40 dark:bg-primary-950/20 dark:text-primary-300'
          : 'border-gray-200 bg-white/80 text-gray-500 hover:text-gray-900 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-300 dark:hover:text-white'
      "
    >
      {{ item.label }}
    </router-link>
  </div>
</template>
