<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import { findAssistantByTargetId } from '@/services/assistants/assistants.service'
import { getGraphCatalogItem } from '@/services/graphs/graphs.service'
import {
  buildRuntimeSnapshotWarning,
  getRuntimeThreadSnapshot,
  listRuntimeThreadsPage,
  normalizeRuntimeGatewayError,
  resolveRuntimePermissionDescription,
  type RuntimeGatewayErrorMeta
} from '@/services/runtime-gateway/workspace.service'
import type { ManagementThread, ThreadHistoryEntry } from '@/types/management'
import { writeRecentChatTarget } from '@/utils/chatTarget'
import {
  formatThreadTime,
  getHistoryEntryId,
  getHistoryEntryTime,
  getMessageText,
  getThreadAssistantId,
  getThreadAssistantName,
  getThreadGraphId,
  getThreadGraphName,
  getThreadListTitle,
  getThreadMessages,
  getThreadPreviewText,
  hasDistinctThreadAssistantTarget,
  toPrettyJson
} from '@/utils/threads'

const route = useRoute()
const router = useRouter()
const { activeProjectId, activeProject } = useWorkspaceProjectContext()

const loading = ref(false)
const detailLoading = ref(false)
const error = ref('')
const detailError = ref('')
const detailWarning = ref('')
const listErrorMeta = ref<RuntimeGatewayErrorMeta | null>(null)
const detailErrorMeta = ref<RuntimeGatewayErrorMeta | null>(null)
const total = ref(0)
const pageSize = ref(20)
const offset = ref(0)
const items = ref<ManagementThread[]>([])
const selectedThreadId = ref(typeof route.query.threadId === 'string' ? route.query.threadId : '')
const selectedThread = ref<ManagementThread | null>(null)
const threadState = ref<Record<string, unknown> | null>(null)
const historyItems = ref<ThreadHistoryEntry[]>([])
const expandedHistoryIds = ref<Record<string, boolean>>({})
const resolvedAssistantNames = ref<Record<string, string>>({})
const resolvedGraphNames = ref<Record<string, string>>({})

const previewQuery = ref(typeof route.query.threadQuery === 'string' ? route.query.threadQuery : '')
const threadIdQuery = ref(typeof route.query.threadThreadId === 'string' ? route.query.threadThreadId : '')
const assistantFilter = ref(
  typeof route.query.threadAssistantId === 'string' ? route.query.threadAssistantId : ''
)
const graphFilter = ref(typeof route.query.threadGraphId === 'string' ? route.query.threadGraphId : '')
const statusFilter = ref(typeof route.query.threadStatus === 'string' ? route.query.threadStatus : '')

const appliedFilters = ref({
  query: previewQuery.value,
  threadId: threadIdQuery.value,
  assistantId: assistantFilter.value,
  graphId: graphFilter.value,
  status: statusFilter.value
})

const currentProject = activeProject
const accessDeniedMessage = computed(() => resolveRuntimePermissionDescription(detailErrorMeta.value || listErrorMeta.value))
const currentPage = computed(() => Math.floor(offset.value / pageSize.value) + 1)
const maxPage = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const messages = computed(() => getThreadMessages(selectedThread.value, threadState.value))
const assistantIdsToResolve = computed(() => {
  const ids = new Set<string>()
  for (const thread of [selectedThread.value, ...items.value]) {
    if (!hasDistinctThreadAssistantTarget(thread) || getThreadAssistantName(thread)) {
      continue
    }
    const assistantId = getThreadAssistantId(thread)
    if (assistantId && !resolvedAssistantNames.value[assistantId]) {
      ids.add(assistantId)
    }
  }
  return Array.from(ids).sort()
})
const graphIdsToResolve = computed(() => {
  const ids = new Set<string>()
  for (const thread of [selectedThread.value, ...items.value]) {
    if (getThreadGraphName(thread)) {
      continue
    }
    const graphId = getThreadGraphId(thread)
    if (graphId && !resolvedGraphNames.value[graphId]) {
      ids.add(graphId)
    }
  }
  return Array.from(ids).sort()
})

let targetNameToken = 0

const stats = computed(() => [
  {
    label: '当前项目',
    value: currentProject.value?.name || '未选择',
    hint: 'Threads 只看当前项目下的线程',
    icon: 'project',
    tone: 'primary'
  },
  {
    label: '当前页结果',
    value: items.value.length,
    hint: `总线程数 ${total.value}`,
    icon: 'threads',
    tone: 'success'
  },
  {
    label: '当前详情消息',
    value: messages.value.length,
    hint: selectedThreadId.value ? '仅在选中 thread 后才加载详情' : '尚未选择 thread',
    icon: 'chat',
    tone: 'warning'
  },
  {
    label: '历史节点',
    value: historyItems.value.length,
    hint: selectedThreadId.value ? '默认不展开 payload，避免拖慢页面' : '尚未加载历史',
    icon: 'activity',
    tone: 'danger'
  }
])

function syncRouteQuery() {
  const query: Record<string, string> = {}

  if (appliedFilters.value.query.trim()) {
    query.threadQuery = appliedFilters.value.query.trim()
  }
  if (appliedFilters.value.threadId.trim()) {
    query.threadThreadId = appliedFilters.value.threadId.trim()
  }
  if (appliedFilters.value.assistantId.trim()) {
    query.threadAssistantId = appliedFilters.value.assistantId.trim()
  }
  if (appliedFilters.value.graphId.trim()) {
    query.threadGraphId = appliedFilters.value.graphId.trim()
  }
  if (appliedFilters.value.status.trim()) {
    query.threadStatus = appliedFilters.value.status.trim()
  }
  if (selectedThreadId.value.trim()) {
    query.threadId = selectedThreadId.value.trim()
  }

  void router.replace({ path: '/workspace/threads', query })
}

async function loadThreads() {
  const projectId = activeProjectId.value
  if (!projectId) {
    items.value = []
    total.value = 0
    error.value = ''
    listErrorMeta.value = null
    return
  }

  loading.value = true
  error.value = ''
  listErrorMeta.value = null

  try {
    const payload = await listRuntimeThreadsPage(projectId, {
      query: appliedFilters.value.query,
      threadId: appliedFilters.value.threadId,
      assistantId: appliedFilters.value.assistantId,
      graphId: appliedFilters.value.graphId,
      status: appliedFilters.value.status,
      limit: pageSize.value,
      offset: offset.value
    })

    items.value = payload.items
    total.value = payload.total

    if (selectedThreadId.value && !payload.items.some((item) => item.thread_id === selectedThreadId.value)) {
      selectedThreadId.value = payload.items[0]?.thread_id || ''
    }
  } catch (loadError) {
    const normalizedError = normalizeRuntimeGatewayError(loadError, '线程列表加载失败')
    items.value = []
    total.value = 0
    error.value = normalizedError.message
    listErrorMeta.value = normalizedError
  } finally {
    loading.value = false
  }
}

async function loadThreadDetail() {
  const projectId = activeProjectId.value
  if (!projectId || !selectedThreadId.value) {
    selectedThread.value = null
    threadState.value = null
    historyItems.value = []
    detailError.value = ''
    detailWarning.value = ''
    detailErrorMeta.value = null
    return
  }

  const selectedSummary = items.value.find((item) => item.thread_id === selectedThreadId.value) || null
  if (selectedSummary) {
    selectedThread.value = selectedSummary
  }

  detailLoading.value = true
  detailError.value = ''
  detailWarning.value = ''
  detailErrorMeta.value = null

  try {
    const snapshot = await getRuntimeThreadSnapshot(projectId, selectedThreadId.value, {
      summary: selectedSummary,
      historyLimit: 20
    })

    selectedThread.value = snapshot.detail
    threadState.value = snapshot.state
    historyItems.value = snapshot.history
    detailWarning.value = buildRuntimeSnapshotWarning(snapshot)
  } catch (loadError) {
    const normalizedError = normalizeRuntimeGatewayError(loadError, '线程详情加载失败')
    selectedThread.value = null
    threadState.value = null
    historyItems.value = []
    detailError.value = normalizedError.message
    detailWarning.value = ''
    detailErrorMeta.value = normalizedError
  } finally {
    detailLoading.value = false
  }
}

function applyFilters() {
  appliedFilters.value = {
    query: previewQuery.value.trim(),
    threadId: threadIdQuery.value.trim(),
    assistantId: assistantFilter.value.trim(),
    graphId: graphFilter.value.trim(),
    status: statusFilter.value.trim()
  }
  offset.value = 0
  syncRouteQuery()
  void loadThreads()
}

function resetFilters() {
  previewQuery.value = ''
  threadIdQuery.value = ''
  assistantFilter.value = ''
  graphFilter.value = ''
  statusFilter.value = ''
  appliedFilters.value = {
    query: '',
    threadId: '',
    assistantId: '',
    graphId: '',
    status: ''
  }
  offset.value = 0
  selectedThreadId.value = ''
  syncRouteQuery()
  void loadThreads()
}

function selectThread(item: ManagementThread) {
  selectedThreadId.value = item.thread_id
  selectedThread.value = item
  expandedHistoryIds.value = {}
  syncRouteQuery()
  void loadThreadDetail()
}

function getAssistantDisplayName(thread?: ManagementThread | null) {
  const assistantName = getThreadAssistantName(thread)
  if (assistantName) {
    return assistantName
  }

  const assistantId = getThreadAssistantId(thread)
  if (!assistantId) {
    return '--'
  }

  return resolvedAssistantNames.value[assistantId] || assistantId
}

function getGraphDisplayName(thread?: ManagementThread | null) {
  const graphName = getThreadGraphName(thread)
  if (graphName) {
    return graphName
  }

  const graphId = getThreadGraphId(thread)
  if (!graphId) {
    return '--'
  }

  return resolvedGraphNames.value[graphId] || graphId
}

async function copyThreadId(threadId: string) {
  try {
    await navigator.clipboard.writeText(threadId)
  } catch {
    detailError.value = '复制 Thread ID 失败'
  }
}

function openInChat(threadId: string) {
  const graphId = getThreadGraphId(selectedThread.value)
  const assistantId = getThreadAssistantId(selectedThread.value)
  const query: Record<string, string> = { threadId }

  if (graphId) {
    const graphName = getGraphDisplayName(selectedThread.value)
    query.targetType = 'graph'
    query.graphId = graphId
    if (graphName && graphName !== '--') {
      query.graphName = graphName
    }
    if (activeProjectId.value) {
      writeRecentChatTarget(activeProjectId.value, {
        targetType: 'graph',
        graphId,
        graphName: graphName !== '--' ? graphName : undefined
      })
    }
  } else if (assistantId) {
    const assistantName = getAssistantDisplayName(selectedThread.value)
    query.targetType = 'assistant'
    query.assistantId = assistantId
    if (assistantName && assistantName !== '--') {
      query.assistantName = assistantName
    }
    if (activeProjectId.value) {
      writeRecentChatTarget(activeProjectId.value, {
        targetType: 'assistant',
        assistantId,
        assistantName: assistantName !== '--' ? assistantName : undefined
      })
    }
  }

  void router.push({ path: '/workspace/chat', query })
}

function toggleHistory(entryId: string) {
  expandedHistoryIds.value = {
    ...expandedHistoryIds.value,
    [entryId]: !expandedHistoryIds.value[entryId]
  }
}

watch(
  () => activeProjectId.value,
  async () => {
    targetNameToken += 1
    resolvedAssistantNames.value = {}
    resolvedGraphNames.value = {}
    offset.value = 0
    await loadThreads()
    await loadThreadDetail()
  },
  { immediate: true }
)

watch(
  [() => activeProjectId.value, assistantIdsToResolve, graphIdsToResolve],
  async ([projectId, assistantIds, graphIds]) => {
    if (!projectId) {
      return
    }

    if (assistantIds.length === 0 && graphIds.length === 0) {
      return
    }

    const currentToken = ++targetNameToken
    const [assistantEntries, graphEntries] = await Promise.all([
      Promise.all(
        assistantIds.map(async (assistantId) => {
          try {
            const assistant = await findAssistantByTargetId(projectId, assistantId)
            return [assistantId, assistant?.name || ''] as const
          } catch {
            return [assistantId, ''] as const
          }
        })
      ),
      Promise.all(
        graphIds.map(async (graphId) => {
          try {
            const graph = await getGraphCatalogItem(projectId, graphId)
            return [graphId, graph?.display_name || ''] as const
          } catch {
            return [graphId, ''] as const
          }
        })
      )
    ])

    if (currentToken !== targetNameToken) {
      return
    }

    if (assistantEntries.length > 0) {
      resolvedAssistantNames.value = {
        ...resolvedAssistantNames.value,
        ...Object.fromEntries(assistantEntries.filter(([, name]) => Boolean(name)))
      }
    }

    if (graphEntries.length > 0) {
      resolvedGraphNames.value = {
        ...resolvedGraphNames.value,
        ...Object.fromEntries(graphEntries.filter(([, name]) => Boolean(name)))
      }
    }
  },
  { immediate: true }
)

watch(
  () => offset.value,
  () => {
    syncRouteQuery()
    void loadThreads()
  }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Threads"
      title="Threads"
      description="线程页现在按你之前要求改成先加载列表，点中某个 thread 之后才拉详情、消息和历史，不再一上来把所有线程内容一起怼出来。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="loadThreads"
        >
          刷新列表
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="线程列表加载失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="detailWarning"
      title="线程快照部分未同步"
      :description="detailWarning"
      variant="warning"
    />

    <div class="grid gap-4 xl:grid-cols-4">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <SurfaceCard class="space-y-4">
      <div class="grid gap-3 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
        <BaseInput
          v-model="previewQuery"
          placeholder="搜索 thread id / assistant / graph / status"
        />
        <BaseInput
          v-model="threadIdQuery"
          placeholder="thread id 模糊匹配"
        />
        <BaseInput
          v-model="assistantFilter"
          placeholder="assistant id"
        />
        <BaseInput
          v-model="graphFilter"
          placeholder="graph id"
        />
        <BaseInput
          v-model="statusFilter"
          placeholder="status"
        />
        <div class="flex gap-2">
          <BaseButton @click="applyFilters">
            搜索
          </BaseButton>
          <BaseButton
            variant="secondary"
            @click="resetFilters"
          >
            清空
          </BaseButton>
        </div>
      </div>
    </SurfaceCard>

    <EmptyState
      v-if="!currentProject"
      icon="project"
      title="请先选择项目"
      description="没有项目上下文，就没法从管理端正确过滤当前项目下的 thread。"
    />

    <EmptyState
      v-else-if="accessDeniedMessage"
      icon="shield"
      title="当前项目没有线程工作台权限"
      :description="accessDeniedMessage"
      action-label="刷新列表"
      @action="loadThreads"
    />

    <div
      v-else
      class="grid gap-6 xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]"
    >
      <SurfaceCard class="space-y-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="pw-page-eyebrow">
              Thread List
            </div>
            <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
              Page {{ currentPage }} / {{ maxPage }}
            </div>
          </div>
          <div class="flex gap-2">
            <BaseButton
              variant="secondary"
              :disabled="loading || offset === 0"
              @click="offset = Math.max(0, offset - pageSize)"
            >
              上一页
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="loading || offset + pageSize >= total"
              @click="offset = offset + pageSize"
            >
              下一页
            </BaseButton>
          </div>
        </div>

        <div
          v-if="loading"
          class="space-y-3"
        >
          <div
            v-for="index in 4"
            :key="index"
            class="pw-card-glass h-28 animate-pulse"
          />
        </div>

        <div
          v-else-if="items.length"
          class="space-y-0 overflow-hidden rounded-2xl border border-gray-200/80 dark:border-dark-700"
        >
          <button
            v-for="item in items"
            :key="item.thread_id"
            type="button"
            class="flex min-h-28 w-full flex-col justify-between border-t border-gray-200/70 px-4 py-3 text-left transition-colors first:border-t-0 dark:border-dark-700/70"
            :class="
              item.thread_id === selectedThreadId
                ? 'bg-primary-50/80 dark:bg-primary-950/20'
                : 'bg-white/60 hover:bg-gray-50 dark:bg-dark-900/30 dark:hover:bg-dark-800/50'
            "
            @click="selectThread(item)"
          >
            <div class="grid gap-2">
              <div class="line-clamp-2 overflow-hidden break-words text-sm font-medium text-gray-900 dark:text-white">
                {{ getThreadListTitle(item) }}
              </div>
              <div class="flex flex-wrap gap-2 text-[11px] text-gray-500 dark:text-dark-300">
                <span
                  v-if="item.status"
                  class="rounded-full border border-gray-200/80 px-2 py-0.5 dark:border-dark-700"
                >
                  {{ item.status }}
                </span>
                <span
                  v-if="hasDistinctThreadAssistantTarget(item)"
                  class="rounded-full border border-gray-200/80 px-2 py-0.5 dark:border-dark-700"
                >
                  Assistant · {{ getAssistantDisplayName(item) }}
                </span>
                <span
                  v-if="getThreadGraphId(item)"
                  class="rounded-full border border-gray-200/80 px-2 py-0.5 dark:border-dark-700"
                >
                  Graph · {{ getGraphDisplayName(item) }}
                </span>
              </div>
            </div>
            <div class="grid gap-1">
              <div class="font-mono text-[11px] text-gray-400 dark:text-dark-400">
                {{ item.thread_id }}
              </div>
              <div class="text-[11px] text-gray-400 dark:text-dark-400">
                updated {{ formatThreadTime(item.updated_at ?? item.created_at ?? null) }}
              </div>
            </div>
          </button>
        </div>

        <EmptyState
          v-else
          icon="threads"
          title="当前筛选下没有线程"
          description="已经改成只加载当前页列表，不会再把所有 thread 的消息全量拖进来。现在只是当前筛选下没有结果。"
        />
      </SurfaceCard>

      <div class="space-y-4">
        <StateBanner
          v-if="detailError"
          title="线程详情加载失败"
          :description="detailError"
          variant="danger"
        />

        <EmptyState
          v-if="!selectedThreadId"
          icon="threads"
          title="先选择一个 Thread"
          description="线程详情、历史和消息预览都改成按需加载。先在左边点一条 thread，再看右侧内容。"
        />

        <template v-else>
          <SurfaceCard
            v-if="selectedThread"
            class="space-y-4"
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="text-base font-semibold text-gray-900 dark:text-white">
                  Thread Summary
                </div>
                <div class="mt-1 font-mono text-xs text-gray-400 dark:text-dark-400">
                  {{ selectedThread.thread_id }}
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <BaseButton
                  variant="secondary"
                  @click="copyThreadId(selectedThread.thread_id)"
                >
                  复制 Thread ID
                </BaseButton>
                <BaseButton
                  variant="secondary"
                  @click="openInChat(selectedThread.thread_id)"
                >
                  Open in Chat
                </BaseButton>
              </div>
            </div>

            <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <div class="pw-card-glass p-3">
                <div class="text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  Status
                </div>
                <div class="mt-2">
                  <StatusPill :tone="selectedThread.status ? 'info' : 'neutral'">
                    {{ selectedThread.status || '--' }}
                  </StatusPill>
                </div>
              </div>
              <div class="pw-card-glass p-3">
                <div class="text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  Assistant
                </div>
                <div class="mt-2 break-all text-sm text-gray-900 dark:text-white">
                  {{ hasDistinctThreadAssistantTarget(selectedThread) ? getAssistantDisplayName(selectedThread) : '--' }}
                </div>
              </div>
              <div class="pw-card-glass p-3">
                <div class="text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  Graph
                </div>
                <div class="mt-2 break-all text-sm text-gray-900 dark:text-white">
                  {{ getThreadGraphId(selectedThread) ? getGraphDisplayName(selectedThread) : '--' }}
                </div>
              </div>
              <div class="pw-card-glass p-3">
                <div class="text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  Created
                </div>
                <div class="mt-2 text-sm text-gray-900 dark:text-white">
                  {{ formatThreadTime(selectedThread.created_at) }}
                </div>
              </div>
              <div class="pw-card-glass p-3">
                <div class="text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  Updated
                </div>
                <div class="mt-2 text-sm text-gray-900 dark:text-white">
                  {{ formatThreadTime(selectedThread.updated_at) }}
                </div>
              </div>
              <div class="pw-card-glass p-3">
                <div class="text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  Preview
                </div>
                <div class="mt-2 line-clamp-3 text-sm text-gray-500 dark:text-dark-300">
                  {{ getThreadPreviewText(selectedThread) }}
                </div>
              </div>
            </div>
          </SurfaceCard>

          <SurfaceCard class="space-y-4">
            <div class="text-base font-semibold text-gray-900 dark:text-white">
              Recent Messages
            </div>

            <div
              v-if="detailLoading"
              class="text-sm text-gray-500 dark:text-dark-300"
            >
              正在加载线程详情...
            </div>

            <div
              v-else-if="messages.length"
              class="space-y-3"
            >
              <div
                v-for="(message, index) in messages.slice(-12).reverse()"
                :key="message.id || `${message.type}-${index}`"
                class="pw-card-glass p-3"
              >
                <div class="mb-1 text-xs font-medium uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  {{ message.type || 'message' }}
                </div>
                <div class="whitespace-pre-wrap break-words text-sm text-gray-700 dark:text-gray-200">
                  {{ getMessageText(message.content) || '--' }}
                </div>
              </div>
            </div>

            <EmptyState
              v-else
              icon="chat"
              title="当前线程没有消息预览"
              description="没有从当前 thread state 里解析到 messages。"
            />
          </SurfaceCard>

          <SurfaceCard class="space-y-4">
            <div class="text-base font-semibold text-gray-900 dark:text-white">
              History
            </div>

            <div
              v-if="detailLoading"
              class="text-sm text-gray-500 dark:text-dark-300"
            >
              正在加载历史节点...
            </div>

            <div
              v-else-if="historyItems.length"
              class="space-y-3"
            >
              <article
                v-for="(entry, index) in historyItems"
                :key="getHistoryEntryId(entry, index)"
                class="pw-card-glass p-3"
              >
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div class="grid gap-1">
                    <div class="font-mono text-xs text-gray-400 dark:text-dark-400">
                      {{ getHistoryEntryId(entry, index) }}
                    </div>
                    <div class="text-xs text-gray-500 dark:text-dark-300">
                      {{ getHistoryEntryTime(entry) }}
                    </div>
                  </div>
                  <button
                    type="button"
                    class="rounded-lg border border-gray-200 bg-white px-2 py-1 text-[11px] text-gray-500 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300"
                    @click="toggleHistory(getHistoryEntryId(entry, index))"
                  >
                    {{ expandedHistoryIds[getHistoryEntryId(entry, index)] ? '收起 payload' : '展开 payload' }}
                  </button>
                </div>
                <pre
                  v-if="expandedHistoryIds[getHistoryEntryId(entry, index)]"
                  class="mt-3 overflow-x-auto whitespace-pre-wrap break-words text-xs text-gray-700 dark:text-gray-200"
                >{{ toPrettyJson(entry) }}</pre>
              </article>
            </div>

            <EmptyState
              v-else
              icon="activity"
              title="当前线程没有历史节点"
              description="没有拿到 checkpoint history。"
            />
          </SurfaceCard>

          <SurfaceCard class="space-y-4">
            <div class="text-base font-semibold text-gray-900 dark:text-white">
              Raw Data
            </div>
            <div class="grid gap-4 xl:grid-cols-2">
              <div>
                <div class="mb-2 text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  Metadata
                </div>
                <pre class="max-h-[320px] overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-gray-50 p-3 text-xs text-gray-700 dark:bg-dark-900 dark:text-gray-200">{{ toPrettyJson(selectedThread?.metadata) }}</pre>
              </div>
              <div>
                <div class="mb-2 text-xs uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
                  State
                </div>
                <pre class="max-h-[320px] overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-gray-50 p-3 text-xs text-gray-700 dark:bg-dark-900 dark:text-gray-200">{{ toPrettyJson(threadState) }}</pre>
              </div>
            </div>
          </SurfaceCard>
        </template>
      </div>
    </div>
  </section>
</template>
