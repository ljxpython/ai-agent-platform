<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import EmptyState from '@/components/platform/EmptyState.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { writeRecentChatTarget } from '@/utils/chatTarget'
import BaseChatTemplate from '@/modules/chat/components/BaseChatTemplate.vue'
import { resolveChatTarget } from '@/modules/chat/types'

const route = useRoute()
const workspaceStore = useWorkspaceStore()

const sqlAgentTarget = computed(() =>
  resolveChatTarget({
    targetType: 'graph',
    graphId: 'sql_agent',
    updatedAt: new Date().toISOString()
  })
)

const initialThreadId = computed(() =>
  typeof route.query.threadId === 'string' && route.query.threadId.trim() ? route.query.threadId.trim() : ''
)

watchEffect(() => {
  if (!workspaceStore.currentProjectId) {
    return
  }

  writeRecentChatTarget(workspaceStore.currentProjectId, {
    targetType: 'graph',
    graphId: 'sql_agent'
  })
})
</script>

<template>
  <section class="pw-page-shell">
    <EmptyState
      v-if="!workspaceStore.currentProject"
      icon="project"
      title="请先选择项目"
      description="SQL Agent 也是项目级入口。没有项目上下文，数据库问答线程和运行记录都没法落地。"
    />

    <BaseChatTemplate
      v-else
      :target="sqlAgentTarget"
      :initial-thread-id="initialThreadId"
      context-notice="SQL Agent 现在不再是写偏好说明页，而是直接复用通用 chat 基座。当前页面会固定把目标锁在 graph: sql_agent。"
      :display="{
        title: 'SQL Agent',
        description:
          '这里已经是可用的 SQL 对话工作台。线程、运行参数和历史都挂在同一套通用 chat 基座上，后面不需要再维护第二套页面。',
        emptyTitle: '开始你的 SQL 对话',
        emptyDescription:
          '直接提问即可，比如让它分析表结构、解释 SQL 或辅助生成查询语句。第一条消息发出时会自动创建 sql_agent thread。'
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
