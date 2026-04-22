<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps<{
  projectId: string
}>()

const route = useRoute()

const items = computed(() => {
  const prefix = `/workspace/projects/${props.projectId}/knowledge`
  return [
    { to: `${prefix}/documents`, label: '文档' },
    { to: `${prefix}/retrieval`, label: '检索' },
    { to: `${prefix}/graph`, label: '图谱' },
    { to: `${prefix}/settings`, label: '设置' }
  ]
})

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
