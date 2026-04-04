<script setup lang="ts">
import type { Message } from '@langchain/langgraph-sdk'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import type { LocationQueryRaw } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { useUiStore } from '@/stores/ui'
import { useWorkspaceStore } from '@/stores/workspace'
import { copyText } from '@/utils/clipboard'
import { shortId } from '@/utils/format'
import { getMessageText, toPrettyJson } from '@/utils/threads'
import ChatArtifactPanel from './ChatArtifactPanel.vue'
import ChatComposer from './ChatComposer.vue'
import ChatContextDrawer from './ChatContextDrawer.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatThreadDrawer from './ChatThreadDrawer.vue'
import { createChatMessageActions } from '../message-actions'
import { buildChatDisplayMessages } from '../message-view-model'
import { buildChatThreadListView, type ChatThreadStatusFilter } from '../thread-list-view-model'
import { useChatAttachments } from '../composables/useChatAttachments'
import { useChatWorkspace } from '../composables/useChatWorkspace'
import type { ChatResolvedTarget, ChatWorkspaceDisplay, ChatWorkspaceFeatures } from '../types'

const props = withDefaults(
  defineProps<{
    target: ChatResolvedTarget | null
    display: ChatWorkspaceDisplay
    features?: ChatWorkspaceFeatures
    initialThreadId?: string
    sourceNote?: string
    contextNotice?: string
    allowResetTarget?: boolean
  }>(),
  {
    features: () => ({}),
    initialThreadId: '',
    sourceNote: '',
    contextNotice: '',
    allowResetTarget: false
  }
)

const emit = defineEmits<{
  'reset-target': []
}>()

const route = useRoute()
const router = useRouter()
const uiStore = useUiStore()
const workspaceStore = useWorkspaceStore()

const composerInput = ref('')
const threadSearch = ref('')
const threadStatusFilter = ref<ChatThreadStatusFilter>('all')
const threadsDrawerOpen = ref(false)
const contextDrawerOpen = ref(false)
const messagesViewport = ref<HTMLDivElement | null>(null)
const sourceNoteDismissed = ref(false)
const deletingThreadId = ref('')
const editingMessageId = ref('')
const editingMessageValue = ref('')
const draftRunOptions = reactive({
  modelId: '',
  enableTools: false,
  toolNames: [] as string[],
  temperature: '',
  maxTokens: '',
  debugMode: false
})

const workspace = useChatWorkspace({
  projectId: computed(() => workspaceStore.currentProjectId || ''),
  target: computed(() => props.target),
  initialThreadId: computed(() => props.initialThreadId?.trim() || '')
})
const attachmentState = useChatAttachments()

const currentProject = computed(() => workspaceStore.currentProject)
const renderMessages = computed(() => workspace.messages.value)
const displayMessages = computed(() => buildChatDisplayMessages(renderMessages.value))
const composerAttachments = computed(() => attachmentState.attachments.value)
const allowRunOptions = computed(() => props.features?.allowRunOptions ?? true)
const showHistory = computed(() => props.features?.showHistory ?? true)
const showArtifacts = computed(() => props.features?.showArtifacts ?? true)
const showContextBar = computed(() => props.features?.showContextBar ?? true)
const hasArtifactEntries = computed(() => {
  const rawEntries = workspace.displayState.value?.ui
  return Array.isArray(rawEntries) && rawEntries.length > 0
})
const hasComposerContent = computed(
  () => Boolean(composerInput.value.trim()) || composerAttachments.value.length > 0
)
const showContinueAction = computed(
  () => !workspace.sending.value && workspace.canContinueDebug.value
)
const hasBlockingInterrupt = computed(
  () => workspace.interruptPayload.value !== undefined && !workspace.canContinueDebug.value
)
const activeRunFailureDescription = computed(() => {
  if (workspace.detailError.value.trim()) {
    return workspace.detailError.value.trim()
  }

  return workspace.threadFailureMessage.value.trim()
})
const canSendFreshMessage = computed(
  () =>
    workspace.canSend.value &&
    !showContinueAction.value &&
    !hasBlockingInterrupt.value &&
    hasComposerContent.value
)
const sendButtonLabel = computed(() => (workspace.runOptions.debugMode ? 'Step' : '发送消息'))
const debugStatusDescription = computed(() => {
  if (!workspace.canContinueDebug.value) {
    return ''
  }

  const payload = workspace.interruptPayload.value
  if (!payload) {
    return '当前运行已在断点暂停，可以继续后续执行。'
  }

  return `当前运行已在断点暂停：${toPrettyJson(payload)}`
})

const selectedToolsLabel = computed(() => {
  if (!draftRunOptions.enableTools) {
    return '已关闭'
  }
  if (draftRunOptions.toolNames.length === 0) {
    return '全部按默认策略'
  }
  return `${draftRunOptions.toolNames.length} 个工具`
})

const headerPills = computed(() => [
  {
    label: 'Target',
    value: workspace.targetText.value
  },
  {
    label: 'Thread',
    value: workspace.activeThreadId.value ? shortId(workspace.activeThreadId.value) : '未创建'
  }
])

const threadStatusFilters = [
  { value: 'all', label: '全部' },
  { value: 'interrupted', label: '待处理' },
  { value: 'busy', label: '运行中' },
  { value: 'idle', label: '空闲' },
  { value: 'error', label: '异常' }
] as const
const threadListView = computed(() =>
  buildChatThreadListView({
    items: workspace.threadSummary.value,
    query: threadSearch.value,
    statusFilter: threadStatusFilter.value
  })
)
const filteredThreadSummary = computed(() => threadListView.value.filteredItems)
const groupedThreadSummary = computed(() => threadListView.value.groups)

function syncThreadIdToRoute(threadId: string) {
  const nextQuery: LocationQueryRaw = { ...route.query }

  if (threadId.trim()) {
    nextQuery.threadId = threadId.trim()
  } else {
    delete nextQuery.threadId
  }

  void router.replace({
    path: route.path,
    query: nextQuery
  })
}

watch(
  () => workspace.activeThreadId.value,
  (threadId) => {
    syncThreadIdToRoute(threadId || '')
  }
)

watch(
  () => props.sourceNote,
  () => {
    sourceNoteDismissed.value = false
  }
)

watch(
  () => displayMessages.value.length,
  async () => {
    await nextTick()
    if (messagesViewport.value) {
      messagesViewport.value.scrollTop = messagesViewport.value.scrollHeight
    }
  }
)

watch(
  () => workspace.activeThreadId.value,
  () => {
    messageActions.cancelEditMessage()
    deletingThreadId.value = ''
  }
)

const messageActions = createChatMessageActions({
  messageMetadataById: workspace.messageMetadataById,
  sending: workspace.sending,
  hasBlockingInterrupt,
  editingMessageId,
  editingMessageValue,
  selectBranch: workspace.selectBranch,
  retryMessage: workspace.retryMessage,
  editHumanMessage: workspace.editHumanMessage
})

async function handleCopyMessage(message: Message) {
  const text = getMessageText(message.content).trim()
  if (!text) {
    uiStore.pushToast({
      type: 'warning',
      title: '没有可复制的文本',
      message: '当前消息主要是附件或结构化数据。'
    })
    return
  }

  const copied = await copyText(text)
  uiStore.pushToast({
    type: copied ? 'success' : 'error',
    title: copied ? '消息已复制' : '复制失败',
    message: copied ? '已写入系统剪贴板。' : '浏览器拒绝了复制动作。'
  })
}

async function submitEditMessage(message: Message, messageId: string) {
  const result = await messageActions.submitEditMessage(message, messageId)
  if (!result.ok && result.reason === 'empty-content') {
    uiStore.pushToast({
      type: 'warning',
      title: '消息内容不能为空',
      message: '至少保留一段文本或者附件。'
    })
  }

  if (result.ok) {
    uiStore.pushToast({
      type: 'success',
      title: '已基于历史节点重发消息',
      message: '新的分支回复已经开始生成。'
    })
  }
}

async function handleRetryMessage(messageId: string) {
  const retried = await messageActions.handleRetryMessage(messageId)
  if (retried) {
    uiStore.pushToast({
      type: 'success',
      title: '已重新生成回复',
      message: '当前回复会从对应 checkpoint 重新执行。'
    })
  }
}

async function handleDeleteThread(threadId: string) {
  if (!threadId.trim() || deletingThreadId.value) {
    return
  }

  const confirmed =
    typeof window === 'undefined'
      ? true
      : window.confirm('删除这个会话后无法恢复，确认继续吗？')

  if (!confirmed) {
    return
  }

  deletingThreadId.value = threadId
  try {
    await workspace.deleteThread(threadId)
    uiStore.pushToast({
      type: 'success',
      title: '会话已删除',
      message: threadId
    })
  } catch (error) {
    uiStore.pushToast({
      type: 'error',
      title: '删除失败',
      message: error instanceof Error ? error.message : '线程删除失败'
    })
  } finally {
    deletingThreadId.value = ''
  }
}

async function handleSend() {
  const sent = await workspace.sendMessage(composerInput.value, composerAttachments.value)
  if (sent) {
    composerInput.value = ''
    attachmentState.resetAttachments()
  }
}

async function handleSelectThread(threadId: string) {
  await workspace.selectThread(threadId)
  threadsDrawerOpen.value = false
}

function handleResetTarget() {
  emit('reset-target')
  contextDrawerOpen.value = false
}

function syncDraftRunOptions() {
  draftRunOptions.modelId = workspace.runOptions.modelId
  draftRunOptions.enableTools = workspace.runOptions.enableTools
  draftRunOptions.toolNames = [...workspace.runOptions.toolNames]
  draftRunOptions.temperature = workspace.runOptions.temperature
  draftRunOptions.maxTokens = workspace.runOptions.maxTokens
  draftRunOptions.debugMode = workspace.runOptions.debugMode
}

function openContextDrawer() {
  syncDraftRunOptions()
  contextDrawerOpen.value = true
}

function toggleDraftTool(toolKey: string) {
  const normalizedToolKey = toolKey.trim()
  if (!normalizedToolKey) {
    return
  }

  const exists = draftRunOptions.toolNames.includes(normalizedToolKey)
  draftRunOptions.toolNames = exists
    ? draftRunOptions.toolNames.filter((item) => item !== normalizedToolKey)
    : [...draftRunOptions.toolNames, normalizedToolKey]
}

function restoreDraftRunOptions() {
  syncDraftRunOptions()
}

function applyDraftRunOptions() {
  workspace.runOptions.modelId = draftRunOptions.modelId
  workspace.runOptions.enableTools = draftRunOptions.enableTools
  workspace.runOptions.toolNames = [...draftRunOptions.toolNames]
  workspace.runOptions.temperature = draftRunOptions.temperature
  workspace.runOptions.maxTokens = draftRunOptions.maxTokens
  workspace.runOptions.debugMode = draftRunOptions.debugMode
  contextDrawerOpen.value = false
}

async function handleContinue() {
  await workspace.continueDebugRun()
}

async function handleCancelRun() {
  await workspace.cancelActiveRun()
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      :eyebrow="props.target?.targetType === 'graph' ? 'Graph Chat' : 'Assistant Chat'"
      :title="display.title"
      :description="display.description"
    />

    <div
      v-if="sourceNote && !sourceNoteDismissed"
      class="relative"
    >
      <StateBanner
        title="目标来源"
        :description="sourceNote"
        variant="info"
      />
      <button
        type="button"
        class="absolute right-3 top-3 rounded-xl p-2 text-gray-400 transition hover:bg-white/80 hover:text-gray-700 dark:hover:bg-dark-900/80 dark:hover:text-dark-100"
        aria-label="关闭目标来源提示"
        @click="sourceNoteDismissed = true"
      >
        <BaseIcon
          name="x"
          size="sm"
        />
      </button>
    </div>

    <StateBanner
      v-if="contextNotice"
      title="上下文说明"
      :description="contextNotice"
      variant="success"
    />

    <StateBanner
      v-if="workspace.error.value"
      title="聊天线程加载失败"
      :description="workspace.error.value"
      variant="danger"
    />

    <StateBanner
      v-if="activeRunFailureDescription"
      title="当前对话运行失败"
      :description="activeRunFailureDescription"
      variant="danger"
    />

    <StateBanner
      v-if="workspace.runtimeError.value"
      title="运行时目录加载失败"
      :description="workspace.runtimeError.value"
      variant="warning"
    />

    <StateBanner
      v-if="debugStatusDescription"
      title="Debug 已暂停"
      :description="debugStatusDescription"
      variant="info"
    />

    <StateBanner
      v-if="hasBlockingInterrupt"
      title="等待人工决策"
      description="当前运行进入 interrupt 状态。先处理下面的中断面板，再继续和 agent 交互。"
      variant="warning"
    />

    <StateBanner
      v-if="workspace.isViewingBranch.value"
      title="当前正在查看历史分支"
      description="你现在看到的是某个 checkpoint 分支下的消息快照。继续发送、编辑或重试时，会基于这个分支重新生成新的对话路径。"
      variant="info"
    />

    <EmptyState
      v-if="!currentProject"
      icon="project"
      title="请先选择项目"
      description="Chat 是严格的项目级工作区。没有项目上下文，线程、图谱和助手这些东西全都不成立。"
    />

    <EmptyState
      v-else-if="!target"
      icon="chat"
      title="请先选择聊天目标"
      description="当前页已经是聊天工作台，但没有明确 assistant 或 graph，先从入口页选一个真实目标再进来。"
    />

    <SurfaceCard
      v-else
      class="flex min-h-[720px] flex-col overflow-hidden p-0"
    >
      <div class="border-b border-gray-100 px-6 py-5 dark:border-dark-800">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="min-w-0">
            <div class="text-lg font-semibold text-gray-900 dark:text-white">
              {{ workspace.selectedThreadSummary.value?.title || display.emptyTitle || '开始一个新对话' }}
            </div>
            <div class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
              {{
                workspace.selectedThreadSummary.value?.preview ||
                  display.emptyDescription ||
                  '选择历史 thread 或直接发第一条消息，消息画布会在这里持续复用。'
              }}
            </div>

            <div
              v-if="showContextBar"
              class="mt-4 flex flex-wrap gap-2"
            >
              <span
                v-for="pill in headerPills"
                :key="pill.label"
                class="pw-pill"
              >
                <span class="text-gray-400 dark:text-dark-400">{{ pill.label }}</span>
                <span class="max-w-[220px] truncate text-gray-700 dark:text-white">{{ pill.value }}</span>
              </span>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <BaseButton
              variant="secondary"
              @click="threadsDrawerOpen = true"
            >
              <BaseIcon
                name="threads"
                size="sm"
              />
              会话 {{ workspace.threadItems.value.length }}
            </BaseButton>
            <BaseButton
              variant="secondary"
              @click="openContextDrawer"
            >
              <BaseIcon
                name="runtime"
                size="sm"
              />
              运行上下文
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="workspace.loadingThreads.value || workspace.loadingThreadDetail.value"
              @click="workspace.refreshActiveThread"
            >
              <BaseIcon
                name="refresh"
                size="sm"
              />
              刷新
            </BaseButton>
            <BaseButton
              :disabled="!workspace.canStartThread.value"
              @click="workspace.startNewThread"
            >
              <BaseIcon
                name="chat"
                size="sm"
              />
              新对话
            </BaseButton>
          </div>
        </div>
      </div>

      <div
        class="min-h-0 flex-1 overflow-hidden"
        :class="showArtifacts && hasArtifactEntries ? 'lg:grid lg:grid-cols-[minmax(0,1fr)_360px]' : ''"
      >
        <div
          ref="messagesViewport"
          class="min-h-0 overflow-y-auto px-6 py-5"
        >
          <div
            v-if="workspace.loadingThreadDetail.value && renderMessages.length === 0"
            class="space-y-4"
          >
            <div
              v-for="index in 3"
              :key="index"
              class="pw-card-glass h-28 animate-pulse"
            />
          </div>

          <div
            v-else-if="displayMessages.length === 0"
            class="flex h-full items-center justify-center"
          >
            <EmptyState
              icon="chat"
              :title="display.emptyTitle || '从这里开始第一轮对话'"
              :description="display.emptyDescription || '输入框已经可用。发出第一条消息时会自动创建 thread，并把后续历史沉淀到当前项目。'"
            />
          </div>

          <ChatMessageList
            v-else
            :display-messages="displayMessages"
            :all-messages="renderMessages"
            :editing-message-id="editingMessageId"
            :editing-message-value="editingMessageValue"
            :is-running="workspace.sending.value"
            :get-message-meta="messageActions.getMessageMeta"
            :get-message-branch-index="messageActions.getMessageBranchIndex"
            :has-branch-switcher="messageActions.hasBranchSwitcher"
            :can-edit-message="messageActions.canEditMessage"
            :can-retry-message="messageActions.canRetryMessage"
            @update:editing-message-value="editingMessageValue = $event"
            @copy-message="handleCopyMessage"
            @cancel-edit="messageActions.cancelEditMessage"
            @submit-edit="submitEditMessage"
            @start-edit="messageActions.startEditMessage"
            @retry-message="handleRetryMessage"
            @select-previous-branch="messageActions.selectPreviousMessageBranch"
            @select-next-branch="messageActions.selectNextMessageBranch"
          />
        </div>

        <ChatArtifactPanel
          v-if="showArtifacts && hasArtifactEntries"
          :values="workspace.displayState.value"
        />
      </div>

      <ChatComposer
        v-model="composerInput"
        :attachments="composerAttachments"
        :is-running="workspace.sending.value"
        :has-blocking-interrupt="hasBlockingInterrupt"
        :interrupt-payload="workspace.interruptPayload.value"
        :display-state="workspace.displayState.value"
        :can-start-thread="workspace.canStartThread.value"
        :show-continue-action="showContinueAction"
        :can-send-fresh-message="canSendFreshMessage"
        :cancelling="workspace.cancelling.value"
        :send-button-label="sendButtonLabel"
        :last-event-at="workspace.lastEventAt.value"
        :on-resume-interrupted-run="workspace.resumeInterruptedRun"
        :on-update-state="workspace.updateThreadStatePatch"
        @send="handleSend"
        @cancel="handleCancelRun"
        @continue-run="handleContinue"
        @new-thread="workspace.startNewThread"
        @file-input-change="attachmentState.handleInputChange"
        @composer-paste="attachmentState.handlePaste"
        @remove-attachment="attachmentState.removeAttachment"
      />
    </SurfaceCard>

    <ChatThreadDrawer
      :show="threadsDrawerOpen"
      :show-context-bar="showContextBar"
      :target-text="workspace.targetText.value"
      :target-type-text="workspace.targetTypeText.value"
      :search="threadSearch"
      :status-filter="threadStatusFilter"
      :filters="threadStatusFilters"
      :loading="workspace.loadingThreads.value"
      :thread-count="workspace.threadItems.value.length"
      :filtered-count="filteredThreadSummary.length"
      :can-start-thread="workspace.canStartThread.value"
      :active-thread-id="workspace.activeThreadId.value"
      :deleting-thread-id="deletingThreadId"
      :groups="groupedThreadSummary"
      @close="threadsDrawerOpen = false"
      @update:search="threadSearch = $event"
      @update:status-filter="threadStatusFilter = $event"
      @start-new-thread="workspace.startNewThread"
      @select-thread="handleSelectThread"
      @delete-thread="handleDeleteThread"
    />

    <ChatContextDrawer
      :show="contextDrawerOpen"
      :allow-run-options="allowRunOptions"
      :show-history="showHistory"
      :show-artifacts="showArtifacts"
      :allow-reset-target="allowResetTarget"
      :target-text="workspace.targetText.value"
      :project-name="currentProject?.name || ''"
      :active-thread-id="workspace.activeThreadId.value"
      :last-run-id="workspace.lastRunId.value"
      :selected-branch="workspace.selectedBranch.value"
      :latest-message-preview="workspace.latestMessagePreview.value"
      :selected-tools-label="selectedToolsLabel"
      :draft-run-options="draftRunOptions"
      :runtime-models="workspace.runtimeModels.value"
      :runtime-tools="workspace.runtimeTools.value"
      :loading-runtime="workspace.loadingRuntime.value"
      :history-items="workspace.historyItems.value"
      :is-viewing-branch="workspace.isViewingBranch.value"
      @close="contextDrawerOpen = false"
      @update:model-id="draftRunOptions.modelId = $event"
      @update:enable-tools="draftRunOptions.enableTools = $event"
      @toggle-tool="toggleDraftTool"
      @update:debug-mode="draftRunOptions.debugMode = $event"
      @update:temperature="draftRunOptions.temperature = $event"
      @update:max-tokens="draftRunOptions.maxTokens = $event"
      @select-branch="workspace.selectBranch($event)"
      @reset-target="handleResetTarget"
      @restore="restoreDraftRunOptions"
      @apply="applyDraftRunOptions"
    />
  </section>
</template>
