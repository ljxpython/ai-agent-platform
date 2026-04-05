<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmptyState from '@/components/platform/EmptyState.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import {
  clearRecentChatTarget,
  normalizeChatTarget,
  readRecentChatTarget,
  writeRecentChatTarget
} from '@/utils/chatTarget'
import BaseChatTemplate from '../components/BaseChatTemplate.vue'
import ChatEntryGuide from '../components/ChatEntryGuide.vue'
import { resolveChatTarget } from '../types'

const route = useRoute()
const router = useRouter()
const workspaceStore = useWorkspaceStore()

const explicitTarget = computed(() =>
  normalizeChatTarget({
    targetType: typeof route.query.targetType === 'string' ? route.query.targetType : null,
    assistantId: typeof route.query.assistantId === 'string' ? route.query.assistantId : null,
    graphId: typeof route.query.graphId === 'string' ? route.query.graphId : null
  })
)

const recentTarget = computed(() => {
  const projectId = workspaceStore.currentProjectId
  if (!projectId || explicitTarget.value) {
    return null
  }
  return readRecentChatTarget(projectId)
})

const activeTarget = computed(() => resolveChatTarget(explicitTarget.value || recentTarget.value))
const initialThreadId = computed(() =>
  typeof route.query.threadId === 'string' && route.query.threadId.trim() ? route.query.threadId.trim() : ''
)

const sourceNote = computed(() => {
  if (explicitTarget.value) {
    return '当前目标来自页面显式参数。只要你从 Assistants、Graphs 或 Threads 带着目标进入，这里就会直接落到真正的对话工作台。'
  }

  if (recentTarget.value) {
    return '当前目标来自当前项目最近一次使用的聊天偏好。第一次选过 assistant 或 graph 之后，再打开 Chat 就不再显示引导页。'
  }

  return ''
})

watchEffect(() => {
  if (explicitTarget.value && workspaceStore.currentProjectId) {
    writeRecentChatTarget(workspaceStore.currentProjectId, explicitTarget.value)
  }
})

function clearTarget() {
  if (workspaceStore.currentProjectId) {
    clearRecentChatTarget(workspaceStore.currentProjectId)
  }

  void router.replace({
    path: '/workspace/chat',
    query: {}
  })
}
</script>

<template>
  <section class="pw-page-shell">
    <EmptyState
      v-if="!workspaceStore.currentProject"
      icon="project"
      title="请先选择项目"
      description="Chat 是项目级工作区。没有项目上下文，assistant、graph、thread 这些目标都不成立。"
    />

    <ChatEntryGuide
      v-else-if="!activeTarget"
      :project-name="workspaceStore.currentProject.name"
    />

    <BaseChatTemplate
      v-else
      :target="activeTarget"
      :initial-thread-id="initialThreadId"
      allow-reset-target
      :source-note="sourceNote"
      :display="{
        title: 'Agent Chat',
        description:
          '通用对话工作台已经接上真实 thread、run 和流式消息，不再是那个只会展示说明文案的半残页。',
        emptyTitle: '开始第一轮 Agent 对话',
        emptyDescription:
          '如果你是第一次用这个目标，直接输入消息就行。系统会自动创建 thread，并把后续历史沉淀到当前项目里。'
      }"
      :features="{
        allowRunOptions: true,
        showHistory: true,
        showArtifacts: true,
        showContextBar: true
      }"
      @reset-target="clearTarget"
    />
  </section>
</template>
