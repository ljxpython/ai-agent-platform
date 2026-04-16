<script setup lang="ts">
import { computed, ref, watch, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import TestcaseOverviewStrip from '@/components/platform/TestcaseOverviewStrip.vue'
import TestcaseWorkspaceNav from '@/components/platform/TestcaseWorkspaceNav.vue'
import { getTestcaseOverview } from '@/services/testcase/testcase.service'
import type { TestcaseOverview } from '@/types/management'
import { writeRecentChatTarget } from '@/utils/chatTarget'
import BaseChatTemplate from '@/modules/chat/components/BaseChatTemplate.vue'
import { resolveChatTarget } from '@/modules/chat/types'

const route = useRoute()
const { activeProjectId, activeProject } = useWorkspaceProjectContext()

const overview = ref<TestcaseOverview | null>(null)
const loading = ref(false)
const error = ref('')

const testcaseTarget = computed(() =>
  resolveChatTarget({
    targetType: 'graph',
    graphId: 'test_case_agent',
    graphName: 'Test Case Agent',
    updatedAt: new Date().toISOString()
  })
)

const initialThreadId = computed(() =>
  typeof route.query.threadId === 'string' && route.query.threadId.trim() ? route.query.threadId.trim() : ''
)

watchEffect(() => {
  if (!activeProjectId.value) {
    return
  }

  writeRecentChatTarget(activeProjectId.value, {
    targetType: 'graph',
    graphId: 'test_case_agent',
    graphName: 'Test Case Agent'
  })
})

async function loadOverview(projectId: string) {
  loading.value = true
  error.value = ''

  try {
    overview.value = await getTestcaseOverview(projectId)
  } catch (loadError) {
    overview.value = null
    error.value = loadError instanceof Error ? loadError.message : 'Testcase Agent 概览加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => activeProjectId.value,
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
  <section class="pw-page-shell flex h-full min-h-0 flex-col">
    <TestcaseWorkspaceNav />

    <StateBanner
      v-if="error"
      title="Testcase Agent 概览加载失败"
      :description="error"
      variant="warning"
    />

    <TestcaseOverviewStrip :overview="overview" />

    <EmptyState
      v-if="!activeProject"
      icon="project"
      title="请先选择项目"
      description="Testcase Agent 工作区也是项目级入口。没有项目上下文，文档解析、测试用例和生成会话都没法稳定落地。"
    />

    <BaseChatTemplate
      v-else
      :target="testcaseTarget"
      :initial-thread-id="initialThreadId"
      context-notice="当前页面固定接入 graph: test_case_agent。生成过程会复用通用 chat 基座，但目标不会切到其他 assistant 或 graph。"
      source-note="当前入口来自 Testcase Agent 工作区。建议上传真实 PDF 文档后直接让 agent 解析并生成正式测试用例，文档与用例结果会落在当前项目范围内。"
      :display="{
        title: 'Testcase Agent · AI 对话生成',
        description:
          '这里固定绑定 `test_case_agent`，用于发起文档解析、提炼和测试用例生成对话。',
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
