<script setup lang="ts">
import { computed, ref, watch, watchEffect } from 'vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import TestcaseOverviewStrip from '@/components/platform/TestcaseOverviewStrip.vue'
import TestcaseWorkspaceNav from '@/components/platform/TestcaseWorkspaceNav.vue'
import { getTestcaseOverview } from '@/services/testcase/testcase.service'
import { useWorkspaceStore } from '@/stores/workspace'
import type { TestcaseOverview } from '@/types/management'
import { writeRecentChatTarget } from '@/utils/chatTarget'
import BaseChatTemplate from '@/modules/chat/components/BaseChatTemplate.vue'
import { resolveChatTarget } from '@/modules/chat/types'

const workspaceStore = useWorkspaceStore()

const overview = ref<TestcaseOverview | null>(null)
const loading = ref(false)
const error = ref('')

const testcaseTarget = computed(() =>
  resolveChatTarget({
    targetType: 'graph',
    graphId: 'test_case_agent',
    updatedAt: new Date().toISOString()
  })
)

watchEffect(() => {
  if (!workspaceStore.currentProjectId) {
    return
  }

  writeRecentChatTarget(workspaceStore.currentProjectId, {
    targetType: 'graph',
    graphId: 'test_case_agent'
  })
})

async function loadOverview(projectId: string) {
  loading.value = true
  error.value = ''

  try {
    overview.value = await getTestcaseOverview(projectId)
  } catch (loadError) {
    overview.value = null
    error.value = loadError instanceof Error ? loadError.message : 'Testcase 概览加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => workspaceStore.currentProjectId,
  (projectId) => {
    if (!projectId) {
      overview.value = null
      error.value = ''
      return
    }

    void loadOverview(projectId)
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <TestcaseWorkspaceNav />

    <StateBanner
      v-if="error"
      title="Testcase 概览加载失败"
      :description="error"
      variant="warning"
    />

    <TestcaseOverviewStrip :overview="overview" />

    <EmptyState
      v-if="!workspaceStore.currentProject"
      icon="project"
      title="请先选择项目"
      description="Testcase 工作区也是项目级入口。没有项目上下文，文档解析、测试用例和生成会话都没法稳定落地。"
    />

    <BaseChatTemplate
      v-else
      :target="testcaseTarget"
      context-notice="当前页面固定接入 graph: test_case_agent。生成过程会复用通用 chat 基座，但目标不会切到其他 assistant 或 graph。"
      source-note="当前入口来自 Testcase 工作区。建议上传真实 PDF 文档后直接让 agent 解析并生成正式测试用例，文档与用例结果会落在当前项目范围内。"
      :display="{
        title: 'Testcase · AI 对话生成',
        description:
          '这里已经不再是占位页，而是固定绑定 `test_case_agent` 的正式生成工作台。上传 PDF 后可以直接发起解析、提炼和用例生成对话。',
        emptyTitle: '上传 PDF 开始生成',
        emptyDescription:
          '推荐使用真实需求文档。第一条消息发出时会自动创建 testcase 生成线程，后续历史和运行记录都会沉淀在当前项目里。'
      }"
      :features="{
        allowRunOptions: true,
        showHistory: true,
        showArtifacts: true,
        showContextBar: true
      }"
    />
  </section>
</template>
