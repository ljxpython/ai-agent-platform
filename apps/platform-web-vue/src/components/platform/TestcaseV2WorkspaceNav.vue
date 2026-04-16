<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const items = computed(() => [
  {
    to: '/workspace/testcase-v2/generate',
    label: 'AI 对话生成'
  },
  {
    to: '/workspace/testcase-v2/cases',
    label: '用例列表'
  },
  {
    to: '/workspace/testcase-v2/documents',
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
      class="pw-table-tool-button"
      :class="isActive(item.to) ? 'pw-pagination-page-active' : ''"
    >
      {{ item.label }}
    </router-link>
  </div>
</template>
