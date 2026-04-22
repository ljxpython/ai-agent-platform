<script setup lang="ts">
import { computed, ref, watch, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import EmptyState from '@/components/platform/EmptyState.vue'
import { findAssistantByTargetId } from '@/services/assistants/assistants.service'
import { getGraphCatalogItem } from '@/services/graphs/graphs.service'
import {
  clearRecentChatTarget,
  hasChatTargetDisplayName,
  mergeChatTargets,
  normalizeChatTarget,
  readRecentChatTarget,
  writeRecentChatTarget,
  type ChatTargetPreference
} from '@/utils/chatTarget'
import BaseChatTemplate from '../components/BaseChatTemplate.vue'
import ChatEntryGuide from '../components/ChatEntryGuide.vue'
import { resolveChatTarget } from '../types'

const route = useRoute()
const router = useRouter()
const { activeProjectId, activeProject } = useWorkspaceProjectContext()

const explicitTarget = computed(() =>
  normalizeChatTarget({
    targetType: typeof route.query.targetType === 'string' ? route.query.targetType : null,
    assistantId: typeof route.query.assistantId === 'string' ? route.query.assistantId : null,
    assistantName: typeof route.query.assistantName === 'string' ? route.query.assistantName : null,
    graphId: typeof route.query.graphId === 'string' ? route.query.graphId : null,
    graphName: typeof route.query.graphName === 'string' ? route.query.graphName : null
  })
)

const recentTarget = computed(() => {
  const projectId = activeProjectId.value
  if (!projectId) {
    return null
  }
  return readRecentChatTarget(projectId)
})

const targetPreference = computed(() => {
  if (explicitTarget.value) {
    return mergeChatTargets(explicitTarget.value, recentTarget.value)
  }

  return recentTarget.value
})
const hydratedTargetPreference = ref<ChatTargetPreference | null>(null)
const activeTargetPreference = computed(() => hydratedTargetPreference.value || targetPreference.value)
const activeTarget = computed(() => resolveChatTarget(activeTargetPreference.value))
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
  if (activeTargetPreference.value && activeProjectId.value) {
    writeRecentChatTarget(activeProjectId.value, activeTargetPreference.value)
  }
})

watch(
  [activeProjectId, targetPreference],
  async ([projectId, target], _previous, onCleanup) => {
    hydratedTargetPreference.value = target

    if (!projectId || !target || hasChatTargetDisplayName(target)) {
      return
    }

    let cancelled = false
    onCleanup(() => {
      cancelled = true
    })

    try {
      if (target.targetType === 'graph') {
        const graphId = target.graphId?.trim() || target.assistantId?.trim() || ''
        const graph = await getGraphCatalogItem(projectId, graphId)
        if (!cancelled && graph) {
          hydratedTargetPreference.value = mergeChatTargets(
            {
              ...target,
              graphName: graph.display_name || graph.graph_id
            },
            target
          )
        }
        return
      }

      const assistantId = target.assistantId?.trim() || ''
      const assistant = await findAssistantByTargetId(projectId, assistantId)
      if (!cancelled && assistant) {
        hydratedTargetPreference.value = mergeChatTargets(
          {
            ...target,
            assistantName: assistant.name || assistant.langgraph_assistant_id || assistant.id
          },
          target
        )
      }
    } catch {
      if (!cancelled) {
        hydratedTargetPreference.value = target
      }
    }
  },
  { immediate: true }
)

function clearTarget() {
  if (activeProjectId.value) {
    clearRecentChatTarget(activeProjectId.value)
  }

  void router.replace({
    path: '/workspace/chat',
    query: {}
  })
}
</script>

<template>
  <section class="pw-page-shell pw-chat-page-shell">
    <EmptyState
      v-if="!activeProject"
      icon="project"
      title="请先选择项目"
      description="Chat 是项目级工作区。没有项目上下文，assistant、graph、thread 这些目标都不成立。"
    />

    <ChatEntryGuide
      v-else-if="!activeTarget"
      :project-name="activeProject.name"
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
        emptyTitle: '',
        emptyDescription: ''
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
