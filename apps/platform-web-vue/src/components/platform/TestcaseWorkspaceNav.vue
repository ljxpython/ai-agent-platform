<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const props = withDefaults(
  defineProps<{
    compact?: boolean
  }>(),
  {
    compact: false
  }
)

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
  <div
    class="flex flex-wrap gap-2 transition-all duration-200"
    :class="props.compact ? 'gap-1.5' : ''"
  >
    <router-link
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="pw-table-tool-button"
      :class="[
        isActive(item.to) ? 'pw-pagination-page-active' : '',
        props.compact ? 'h-8 px-2.5 text-xs' : ''
      ]"
    >
      {{ item.label }}
    </router-link>
  </div>
</template>
