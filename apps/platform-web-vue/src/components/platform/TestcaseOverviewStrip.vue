<script setup lang="ts">
import { computed } from 'vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import type { TestcaseOverview } from '@/types/management'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  overview: TestcaseOverview | null
}>()

const items = computed(() => [
  {
    label: '正式用例',
    value: props.overview?.test_cases_total ?? 0,
    hint: props.overview?.latest_batch_id || '无批次',
    icon: 'testcase',
    tone: 'primary'
  },
  {
    label: '解析文档',
    value: props.overview?.documents_total ?? 0,
    hint: `parsed=${props.overview?.parsed_documents_total ?? 0}`,
    icon: 'folder',
    tone: 'success'
  },
  {
    label: '失败文档',
    value: props.overview?.failed_documents_total ?? 0,
    hint: (props.overview?.failed_documents_total ?? 0) > 0 ? '需要回看' : '状态正常',
    icon: 'activity',
    tone: 'warning'
  },
  {
    label: '最近活动',
    value: props.overview?.latest_activity_at ? formatDateTime(props.overview.latest_activity_at) : '--',
    hint: props.overview?.project_id || '未选择项目',
    icon: 'overview',
    tone: 'danger'
  }
])
</script>

<template>
  <div class="grid gap-4 xl:grid-cols-4">
    <MetricCard
      v-for="item in items"
      :key="item.label"
      :label="item.label"
      :value="item.value"
      :hint="item.hint"
      :icon="item.icon"
      :tone="item.tone"
    />
  </div>
</template>
