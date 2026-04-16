<script setup lang="ts">
import type { Message } from '@langchain/langgraph-sdk'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import type { LocationQueryRaw } from 'vue-router'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import ButtonWithTooltip from '@/components/platform/ButtonWithTooltip.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'
import { useUiStore } from '@/stores/ui'
import { copyText } from '@/utils/clipboard'
import { shortId } from '@/utils/format'
import { getMessageText, toPrettyJson } from '@/utils/threads'
import ChatArtifactPanel from './ChatArtifactPanel.vue'
import ChatComposer from './ChatComposer.vue'
import ChatContextDrawer from './ChatContextDrawer.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatRunOptionsDialog from './ChatRunOptionsDialog.vue'
import ChatThreadDrawer from './ChatThreadDrawer.vue'
import { buildChatCompactModeView } from '../compact-mode-view-model'
import { normalizeChatInspectorFiles } from '../inspector-view-model'
import { buildChatLiveFollowView } from '../live-follow-view-model'
import { createChatMessageActions } from '../message-actions'
import { buildChatDisplayMessages } from '../message-view-model'
import { buildChatPlanView } from '../plan-view-model'
import { isChatViewportNearBottom } from '../scroll-state'
import { buildChatThreadListView, type ChatThreadStatusFilter } from '../thread-list-view-model'
import { useChatAttachments } from '../composables/useChatAttachments'
import { useChatWorkspace } from '../composables/useChatWorkspace'
import type { ChatResolvedTarget, ChatWorkspaceDisplay, ChatWorkspaceFeatures } from '../types'

type InspectorTabKey = 'overview' | 'tasks' | 'files' | 'history'
type FollowPauseReason = 'manualScroll' | 'contextDrawer' | 'runtimeOptions' | 'messageMeta'
const CHAT_DRAFT_STORAGE_PREFIX = 'pw:chat:draft'

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
  'compact-mode-change': [value: boolean]
}>()

const route = useRoute()
const router = useRouter()
const uiStore = useUiStore()
const { activeProjectId, activeProject } = useWorkspaceProjectContext()

const composerInput = ref('')
const threadSearch = ref('')
const threadStatusFilter = ref<ChatThreadStatusFilter>('all')
const threadsDrawerOpen = ref(false)
const contextDrawerOpen = ref(false)
const runtimeOptionsDialogOpen = ref(false)
const inspectorInitialTab = ref<InspectorTabKey>('overview')
const messagesViewport = ref<HTMLDivElement | null>(null)
const messagesContent = ref<HTMLDivElement | null>(null)
const sourceNoteDismissed = ref(false)
const deletingThreadId = ref('')
const editingMessageId = ref('')
const editingMessageValue = ref('')
const autoFollowEnabled = ref(true)
const unreadMessageCount = ref(0)
const bufferedStreamActivity = ref(false)
const expandedMessageMetaIds = ref<string[]>([])
const followPauseState = reactive<Record<FollowPauseReason, boolean>>({
  manualScroll: false,
  contextDrawer: false,
  runtimeOptions: false,
  messageMeta: false
})
const draftRunOptions = reactive({
  modelId: '',
  enableTools: false,
  toolNames: [] as string[],
  temperature: '',
  maxTokens: '',
  debugMode: false
})

const workspace = useChatWorkspace({
  projectId: computed(() => activeProjectId.value || ''),
  target: computed(() => props.target),
  initialThreadId: computed(() => props.initialThreadId?.trim() || '')
})
const attachmentState = useChatAttachments()

const currentProject = activeProject
const renderMessages = computed(() => workspace.messages.value)
const displayMessages = computed(() => buildChatDisplayMessages(renderMessages.value))
const composerAttachments = computed(() => attachmentState.attachments.value)
const planView = computed(() => buildChatPlanView(workspace.displayState.value))
const inspectorFiles = computed(() => normalizeChatInspectorFiles(workspace.displayState.value))
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
const visibleSourceNote = computed(() => Boolean(props.sourceNote.trim()) && !sourceNoteDismissed.value)
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
const isInspectingMessageMeta = computed(() => expandedMessageMetaIds.value.length > 0)
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
const liveFollowView = computed(() =>
  buildChatLiveFollowView({
    autoFollowEnabled: autoFollowEnabled.value,
    isRunning: workspace.sending.value,
    unreadMessageCount: unreadMessageCount.value,
    bufferedStreamActivity: bufferedStreamActivity.value
  })
)
const liveFollowPillClass = computed(() => {
  if (liveFollowView.value.tone === 'success') {
    return 'pw-pill-soft-success'
  }

  if (liveFollowView.value.tone === 'warning') {
    return 'pw-pill-soft-warning'
  }

  return 'pw-pill-soft-info'
})
const compactModeView = computed(() =>
  buildChatCompactModeView({
    activeThreadId: workspace.activeThreadId.value,
    messageCount: renderMessages.value.length,
    isRunning: workspace.sending.value,
    loadingThreadDetail: workspace.loadingThreadDetail.value
  })
)
const isCompactMode = computed(() => compactModeView.value.enabled)
const showJumpToLatestNotice = computed(
  () =>
    !contextDrawerOpen.value &&
    !runtimeOptionsDialogOpen.value &&
    liveFollowView.value.noticeVisible
)
const jumpToLatestTitle = computed(() => liveFollowView.value.title)
const jumpToLatestDescription = computed(() => {
  if (isInspectingMessageMeta.value) {
    return '你正在查看工具或子任务详情，点击可回到底部继续跟随。'
  }

  return liveFollowView.value.description
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
const composerDraftKey = computed(() => {
  const projectId = activeProjectId.value.trim()
  const targetId = props.target?.resolvedTargetId?.trim() || 'no-target'
  const threadId = workspace.activeThreadId.value.trim() || '__new__'

  if (!projectId) {
    return ''
  }

  return `${CHAT_DRAFT_STORAGE_PREFIX}:${projectId}:${targetId}:${threadId}`
})

function readComposerDraft(storageKey: string) {
  if (typeof window === 'undefined' || !storageKey) {
    return ''
  }

  return window.localStorage.getItem(storageKey) || ''
}

function writeComposerDraft(storageKey: string, value: string) {
  if (typeof window === 'undefined' || !storageKey) {
    return
  }

  if (value.trim()) {
    window.localStorage.setItem(storageKey, value)
    return
  }

  window.localStorage.removeItem(storageKey)
}

function resetBufferedActivity() {
  unreadMessageCount.value = 0
  bufferedStreamActivity.value = false
}

let scheduledScrollBehavior: globalThis.ScrollBehavior = 'auto'
let scheduledScrollFrameId: number | null = null
let keepPinnedFrameId: number | null = null

function mergeScheduledBehavior(nextBehavior: globalThis.ScrollBehavior) {
  if (scheduledScrollBehavior === 'smooth' || nextBehavior === 'smooth') {
    scheduledScrollBehavior = 'smooth'
    return
  }

  scheduledScrollBehavior = nextBehavior
}

async function scrollMessagesToLatest(behavior: globalThis.ScrollBehavior = 'auto') {
  await nextTick()

  const viewport = messagesViewport.value
  if (!viewport) {
    return
  }

  viewport.scrollTo({
    top: viewport.scrollHeight,
    behavior
  })
}

function scheduleScrollToLatest(behavior: globalThis.ScrollBehavior = 'auto') {
  mergeScheduledBehavior(behavior)

  if (scheduledScrollFrameId !== null) {
    return
  }

  if (typeof window === 'undefined' || typeof window.requestAnimationFrame !== 'function') {
    void scrollMessagesToLatest(scheduledScrollBehavior)
    scheduledScrollBehavior = 'auto'
    return
  }

  scheduledScrollFrameId = window.requestAnimationFrame(() => {
    const nextBehavior = scheduledScrollBehavior
    scheduledScrollBehavior = 'auto'
    scheduledScrollFrameId = null
    void scrollMessagesToLatest(nextBehavior)
  })
}

function stopKeepPinnedToBottomLoop() {
  if (keepPinnedFrameId === null || typeof window === 'undefined') {
    return
  }

  window.cancelAnimationFrame(keepPinnedFrameId)
  keepPinnedFrameId = null
}

function keepPinnedToBottomLoop() {
  if (
    typeof window === 'undefined' ||
    !workspace.sending.value ||
    !autoFollowEnabled.value
  ) {
    stopKeepPinnedToBottomLoop()
    return
  }

  const viewport = messagesViewport.value
  if (viewport) {
    viewport.scrollTo({
      top: viewport.scrollHeight,
      behavior: 'auto'
    })
  }

  keepPinnedFrameId = window.requestAnimationFrame(() => {
    keepPinnedToBottomLoop()
  })
}

function updateAutoFollowState(options?: {
  resumeBehavior?: globalThis.ScrollBehavior
  skipScroll?: boolean
}) {
  const nextEnabled = !Object.values(followPauseState).some(Boolean)
  autoFollowEnabled.value = nextEnabled

  if (!nextEnabled) {
    return
  }

  resetBufferedActivity()

  if (!options?.skipScroll) {
    scheduleScrollToLatest(options?.resumeBehavior ?? 'auto')
  }
}

function setFollowPauseReason(
  reason: FollowPauseReason,
  isPaused: boolean,
  options?: {
    resumeBehavior?: globalThis.ScrollBehavior
    skipScroll?: boolean
  }
) {
  if (followPauseState[reason] === isPaused) {
    return
  }

  followPauseState[reason] = isPaused
  updateAutoFollowState(options)
}

function clearExpandedMessageMeta() {
  if (expandedMessageMetaIds.value.length === 0) {
    return
  }

  expandedMessageMetaIds.value = []
  setFollowPauseReason('messageMeta', false, { resumeBehavior: 'smooth' })
}

function resumeAutoFollow(behavior: globalThis.ScrollBehavior = 'auto') {
  setFollowPauseReason('manualScroll', false, { resumeBehavior: behavior })
  clearExpandedMessageMeta()
  updateAutoFollowState({ resumeBehavior: behavior })
}

function handleMessagesScroll() {
  const viewport = messagesViewport.value
  if (!viewport) {
    return
  }

  if (isChatViewportNearBottom(viewport)) {
    setFollowPauseReason('manualScroll', false, { skipScroll: true })
    if (autoFollowEnabled.value) {
      resetBufferedActivity()
    }
    return
  }

  if (!followPauseState.manualScroll) {
    setFollowPauseReason('manualScroll', true, { skipScroll: true })
  }
}

function handleMessagesContentResize() {
  if (autoFollowEnabled.value) {
    scheduleScrollToLatest('auto')
    return
  }

  if (workspace.sending.value) {
    bufferedStreamActivity.value = true
  }
}

function syncThreadIdToRoute(threadId: string) {
  const normalizedThreadId = threadId.trim()
  const currentRouteThreadId =
    typeof route.query.threadId === 'string' && route.query.threadId.trim() ? route.query.threadId.trim() : ''

  if (normalizedThreadId === currentRouteThreadId) {
    return
  }

  const nextQuery: LocationQueryRaw = { ...route.query }

  if (normalizedThreadId) {
    nextQuery.threadId = normalizedThreadId
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
  () => isCompactMode.value,
  (nextValue) => {
    emit('compact-mode-change', nextValue)

    if (nextValue && autoFollowEnabled.value) {
      scheduleScrollToLatest('auto')
    }
  },
  { immediate: true }
)

watch(
  () => props.sourceNote,
  () => {
    sourceNoteDismissed.value = false
  }
)

watch(
  () => composerDraftKey.value,
  (nextKey) => {
    composerInput.value = readComposerDraft(nextKey)
  },
  { immediate: true }
)

watch(
  () => composerInput.value,
  (nextValue) => {
    writeComposerDraft(composerDraftKey.value, nextValue)
  }
)

watch(
  () => displayMessages.value.length,
  (nextCount, previousCount) => {
    const delta = Math.max(0, nextCount - previousCount)
    if (delta === 0) {
      return
    }

    if (autoFollowEnabled.value) {
      scheduleScrollToLatest(previousCount === 0 ? 'auto' : 'smooth')
      return
    }

    unreadMessageCount.value += delta
  }
)

watch(
  () => workspace.lastEventAt.value,
  (nextValue, previousValue) => {
    if (!nextValue || nextValue === previousValue) {
      return
    }

    if (autoFollowEnabled.value) {
      scheduleScrollToLatest('auto')
      return
    }

    bufferedStreamActivity.value = true
  }
)

watch(
  () => workspace.activeThreadId.value,
  () => {
    messageActions.cancelEditMessage()
    deletingThreadId.value = ''
    expandedMessageMetaIds.value = []
    followPauseState.manualScroll = false
    followPauseState.contextDrawer = false
    followPauseState.runtimeOptions = false
    followPauseState.messageMeta = false
    resetBufferedActivity()
    updateAutoFollowState({ skipScroll: true })
    scheduleScrollToLatest('auto')
  }
)

watch(
  () => contextDrawerOpen.value,
  (isOpen) => {
    setFollowPauseReason('contextDrawer', isOpen, {
      resumeBehavior: 'smooth',
      skipScroll: isOpen
    })
  }
)

watch(
  () => runtimeOptionsDialogOpen.value,
  (isOpen) => {
    setFollowPauseReason('runtimeOptions', isOpen, {
      resumeBehavior: 'smooth',
      skipScroll: isOpen
    })
  }
)

watch(
  [() => workspace.sending.value, () => autoFollowEnabled.value],
  ([isSending, canFollow], _previous, onCleanup) => {
    stopKeepPinnedToBottomLoop()

    if (typeof window === 'undefined' || !isSending || !canFollow) {
      return
    }

    keepPinnedFrameId = window.requestAnimationFrame(() => {
      keepPinnedToBottomLoop()
    })

    onCleanup(() => {
      stopKeepPinnedToBottomLoop()
    })
  },
  { immediate: true }
)

watch(
  messagesContent,
  (element, _previous, onCleanup) => {
    if (!element || typeof ResizeObserver === 'undefined') {
      return
    }

    const observer = new ResizeObserver(() => {
      handleMessagesContentResize()
    })
    observer.observe(element)

    onCleanup(() => {
      observer.disconnect()
    })
  },
  {
    flush: 'post'
  }
)

onBeforeUnmount(() => {
  if (scheduledScrollFrameId === null || typeof window === 'undefined') {
    stopKeepPinnedToBottomLoop()
    return
  }

  window.cancelAnimationFrame(scheduledScrollFrameId)
  scheduledScrollFrameId = null
  stopKeepPinnedToBottomLoop()
})

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
  const draftContent = composerInput.value
  const draftAttachments = composerAttachments.value.map((attachment) => ({
    ...attachment,
    metadata: attachment.metadata ? { ...attachment.metadata } : undefined
  }))

  if (!draftContent.trim() && draftAttachments.length === 0) {
    return
  }

  composerInput.value = ''
  attachmentState.resetAttachments()

  void workspace.sendMessage(draftContent, draftAttachments)
    .then((sent) => {
      if (sent) {
        return
      }

      if (!composerInput.value.trim() && composerAttachments.value.length === 0) {
        composerInput.value = draftContent
        attachmentState.attachments.value = draftAttachments
      }
    })
    .catch(() => {
      if (!composerInput.value.trim() && composerAttachments.value.length === 0) {
        composerInput.value = draftContent
        attachmentState.attachments.value = draftAttachments
      }
    })
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

function openRuntimeOptionsDialog() {
  syncDraftRunOptions()
  runtimeOptionsDialogOpen.value = true
}

function openInspectorDrawer(tab: InspectorTabKey = 'overview') {
  inspectorInitialTab.value = tab
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
  runtimeOptionsDialogOpen.value = false
}

function handleDismissSourceNote() {
  sourceNoteDismissed.value = true
}

function handleJumpToLatest() {
  resumeAutoFollow('smooth')
}

function handleMessageMetaExpandedChange(messageId: string, expanded: boolean) {
  const normalizedId = messageId.trim()
  if (!normalizedId) {
    return
  }

  if (expanded) {
    if (!expandedMessageMetaIds.value.includes(normalizedId)) {
      expandedMessageMetaIds.value = [...expandedMessageMetaIds.value, normalizedId]
    }
    setFollowPauseReason('messageMeta', true, { skipScroll: true })
    return
  }

  if (!expandedMessageMetaIds.value.includes(normalizedId)) {
    return
  }

  expandedMessageMetaIds.value = expandedMessageMetaIds.value.filter((item) => item !== normalizedId)
  setFollowPauseReason('messageMeta', expandedMessageMetaIds.value.length > 0, {
    resumeBehavior: 'smooth'
  })
}

async function handleContinue() {
  await workspace.continueDebugRun()
}

async function handleCancelRun() {
  await workspace.cancelActiveRun()
}
</script>

<template>
  <section class="pw-page-shell flex flex-1 min-h-0 flex-col">
    <PageHeader
      :eyebrow="props.target?.targetType === 'graph' ? 'Graph Chat' : 'Assistant Chat'"
      :title="display.title"
      :description="display.description"
      :compact="isCompactMode"
    />

    <div
      v-if="visibleSourceNote"
      class="pw-panel-info flex flex-wrap items-center justify-between gap-3 text-sky-900 transition-all duration-200 dark:text-sky-50"
      :class="isCompactMode ? 'gap-2 rounded-xl px-3 py-3' : ''"
    >
      <div
        class="min-w-0 flex items-center gap-3 transition-all duration-200"
        :class="isCompactMode ? 'gap-2' : ''"
      >
        <span
          class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-white/70 text-sky-600 transition-all duration-200 dark:bg-dark-900/60 dark:text-sky-200"
          :class="isCompactMode ? 'h-8 w-8 rounded-xl' : ''"
        >
          <BaseIcon
            name="info"
            size="sm"
          />
        </span>
        <div class="min-w-0">
          <div
            class="text-sm font-semibold text-sky-800 transition-all duration-200 dark:text-sky-100"
            :class="isCompactMode ? 'text-xs' : ''"
          >
            当前目标来源已记录
          </div>
          <p
            class="text-xs leading-6 text-sky-700/90 transition-all duration-200 dark:text-sky-100/80"
            :class="isCompactMode ? 'leading-5 line-clamp-1' : ''"
          >
            完整说明已经收进会话详情的概览页，不再在页面顶部重复堆内容。
          </p>
        </div>
      </div>

      <div
        class="flex shrink-0 items-center gap-2 transition-all duration-200"
        :class="isCompactMode ? 'gap-1.5' : ''"
      >
        <BaseButton
          variant="ghost"
          @click="openInspectorDrawer('overview')"
        >
          查看会话详情
        </BaseButton>
        <button
          type="button"
          class="inline-flex h-9 w-9 items-center justify-center rounded-xl text-sky-500 transition hover:bg-white hover:text-sky-700 dark:text-sky-200 dark:hover:bg-dark-900 dark:hover:text-white"
          aria-label="关闭目标来源提示"
          @click="handleDismissSourceNote"
        >
          <BaseIcon
            name="x"
            size="sm"
          />
        </button>
      </div>
    </div>

    <StateBanner
      v-if="contextNotice"
      title="上下文说明"
      :description="contextNotice"
      variant="success"
      :compact="isCompactMode"
    />

    <StateBanner
      v-if="workspace.error.value"
      title="聊天线程加载失败"
      :description="workspace.error.value"
      variant="danger"
      :compact="isCompactMode"
    />

    <StateBanner
      v-if="activeRunFailureDescription"
      title="当前对话运行失败"
      :description="activeRunFailureDescription"
      variant="danger"
      :compact="isCompactMode"
    />

    <StateBanner
      v-if="workspace.runtimeError.value"
      title="运行时目录加载失败"
      :description="workspace.runtimeError.value"
      variant="warning"
      :compact="isCompactMode"
    />

    <StateBanner
      v-if="workspace.detailInfo.value"
      title="运行状态更新"
      :description="workspace.detailInfo.value"
      variant="info"
      :compact="isCompactMode"
    />

    <StateBanner
      v-if="workspace.detailWarning.value"
      title="会话状态部分未同步"
      :description="workspace.detailWarning.value"
      variant="warning"
      :compact="isCompactMode"
    />

    <StateBanner
      v-if="debugStatusDescription"
      title="Debug 已暂停"
      :description="debugStatusDescription"
      variant="info"
      :compact="isCompactMode"
    />

    <StateBanner
      v-if="hasBlockingInterrupt"
      title="等待人工决策"
      description="当前运行进入 interrupt 状态。先处理下面的中断面板，再继续和 agent 交互。"
      variant="warning"
      :compact="isCompactMode"
    />

    <StateBanner
      v-if="workspace.isViewingBranch.value"
      title="当前正在查看历史分支"
      description="你现在看到的是某个 checkpoint 分支下的消息快照。继续发送、编辑或重试时，会基于这个分支重新生成新的对话路径。"
      variant="info"
      :compact="isCompactMode"
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

    <EmptyState
      v-else-if="workspace.accessDeniedMessage.value"
      icon="shield"
      title="当前项目没有运行工作台权限"
      :description="workspace.accessDeniedMessage.value"
      action-label="重新同步"
      @action="workspace.refreshActiveThread"
    />

    <SurfaceCard
      v-else
      class="flex min-h-0 flex-1 flex-col overflow-hidden p-0"
    >
      <div
        class="border-b border-gray-100 px-5 py-4 transition-all duration-200 dark:border-dark-800 md:px-6 md:py-5"
        :class="isCompactMode ? 'px-4 py-3 md:px-5 md:py-3.5' : ''"
      >
        <div
          class="flex flex-wrap items-start justify-between gap-4 transition-all duration-200"
          :class="isCompactMode ? 'gap-3' : ''"
        >
          <div class="min-w-0">
            <div
              class="text-lg font-semibold text-gray-900 transition-all duration-200 dark:text-white"
              :class="isCompactMode ? 'text-base' : ''"
            >
              {{ workspace.selectedThreadSummary.value?.title || display.emptyTitle || '开始一个新对话' }}
            </div>
            <div
              class="mt-2 text-sm leading-7 text-gray-500 transition-all duration-200 dark:text-dark-300"
              :class="isCompactMode ? 'mt-1 text-xs leading-5 line-clamp-2' : ''"
            >
              {{
                workspace.selectedThreadSummary.value?.preview ||
                  display.emptyDescription ||
                  '选择历史 thread 或直接发第一条消息，消息画布会在这里持续复用。'
              }}
            </div>

            <div
              v-if="showContextBar"
              class="mt-4 flex flex-wrap gap-2 transition-all duration-200"
              :class="isCompactMode ? 'mt-3 gap-1.5' : ''"
            >
              <span
                v-for="pill in headerPills"
                :key="pill.label"
                class="pw-pill"
                :class="isCompactMode ? 'gap-1.5 px-2.5 py-1 text-[11px]' : ''"
              >
                <span class="text-gray-400 dark:text-dark-400">{{ pill.label }}</span>
                <span class="max-w-[220px] truncate text-gray-700 dark:text-white">{{ pill.value }}</span>
              </span>
            </div>
          </div>

          <div
            class="flex flex-wrap items-center gap-2 transition-all duration-200"
            :class="isCompactMode ? 'gap-1.5' : ''"
          >
            <div
              v-if="liveFollowView.visible"
              class="pw-pill-soft gap-2 px-3 py-2 text-xs font-medium"
              :class="[liveFollowPillClass, isCompactMode ? 'gap-1.5 px-2.5 py-1.5 text-[11px]' : '']"
            >
              <BaseIcon
                :name="liveFollowView.icon"
                size="xs"
              />
              <span>{{ liveFollowView.pillLabel }}</span>
            </div>
            <div class="flex items-center gap-1">
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
            </div>
            <ButtonWithTooltip
              variant="secondary"
              tooltip="查看当前 target、thread、运行上下文、ToDo、Files 和 checkpoint 历史，不会打断主消息区阅读。"
              @click="openInspectorDrawer('overview')"
            >
              <BaseIcon
                name="overview"
                size="sm"
              />
              会话详情
            </ButtonWithTooltip>
            <div v-if="allowRunOptions">
              <ButtonWithTooltip
                variant="secondary"
                tooltip="修改后续运行要用的模型、工具、Debug Mode 和生成参数，不会回改已经开始的这轮执行。"
                @click="openRuntimeOptionsDialog"
              >
                <BaseIcon
                  name="runtime"
                  size="sm"
                />
                运行参数
              </ButtonWithTooltip>
            </div>
            <ButtonWithTooltip
              variant="secondary"
              tooltip="重新从服务端拉取当前会话状态。适合流式中断、切页面回来后状态漂移、或你怀疑前端没跟上后端时使用。"
              :disabled="workspace.loadingThreads.value || workspace.loadingThreadDetail.value"
              @click="workspace.refreshActiveThread"
            >
              <BaseIcon
                name="refresh"
                size="sm"
              />
              重新同步
            </ButtonWithTooltip>
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
        class="min-h-0 flex flex-1 flex-col overflow-hidden"
        :class="
          showArtifacts && hasArtifactEntries
            ? isCompactMode
              ? 'lg:grid lg:grid-cols-[minmax(0,1fr)_320px]'
              : 'lg:grid lg:grid-cols-[minmax(0,1fr)_360px]'
            : ''
        "
      >
        <div class="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <div
            ref="messagesViewport"
            class="min-h-0 flex-1 overflow-y-auto px-5 py-4 md:px-6 md:py-5"
            :class="isCompactMode ? 'px-4 py-3 md:px-5 md:py-4' : ''"
            @scroll="handleMessagesScroll"
          >
            <div
              ref="messagesContent"
              class="flex min-h-full flex-col justify-end"
            >
              <div
                v-if="workspace.loadingThreadDetail.value && renderMessages.length === 0"
                class="space-y-4"
              >
                <div
                  v-for="index in 3"
                  :key="index"
                  class="pw-panel-muted h-28 animate-pulse"
                />
              </div>

              <div
                v-else-if="displayMessages.length === 0"
                class="flex h-full items-center justify-center"
              >
                <div class="pw-panel-muted mx-auto flex w-full max-w-xl flex-col items-center px-6 py-10 text-center">
                  <div class="pw-empty-state-icon mb-4">
                    <BaseIcon
                      name="chat"
                      size="lg"
                    />
                  </div>
                  <h3 class="text-lg font-semibold text-gray-950 dark:text-white">
                    {{ display.emptyTitle || '从这里开始第一轮对话' }}
                  </h3>
                  <p class="mt-3 max-w-md text-sm leading-7 text-gray-500 dark:text-dark-300">
                    {{ display.emptyDescription || '输入框已经可用。发出第一条消息时会自动创建 thread，并把后续历史沉淀到当前项目。' }}
                  </p>
                </div>
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
                @message-meta-expanded-change="handleMessageMetaExpandedChange"
              />
            </div>
          </div>

          <div
            v-if="showJumpToLatestNotice"
            class="pointer-events-none absolute bottom-5 right-5 z-10 flex justify-end"
          >
            <div class="pointer-events-auto pw-panel w-[calc(100vw-2.5rem)] px-4 py-3 sm:w-[320px]">
              <div class="flex items-start gap-3">
                <span class="mt-1 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/30 dark:text-primary-100">
                  <BaseIcon
                    :name="liveFollowView.icon"
                    size="sm"
                  />
                </span>
                <span class="min-w-0 flex-1">
                  <span class="block text-sm font-semibold text-gray-900 dark:text-white">
                    {{ jumpToLatestTitle }}
                  </span>
                  <span class="mt-1 block text-xs leading-6 text-gray-500 dark:text-dark-300">
                    {{ jumpToLatestDescription }}
                  </span>
                </span>
              </div>
              <div class="mt-3 flex flex-wrap justify-end gap-2">
                <BaseButton
                  v-if="liveFollowView.showStopAction"
                  variant="danger"
                  :disabled="workspace.cancelling.value"
                  @click="handleCancelRun"
                >
                  <BaseIcon
                    name="x"
                    size="sm"
                  />
                  {{ workspace.cancelling.value ? '停止中...' : '停止生成' }}
                </BaseButton>
                <BaseButton @click="handleJumpToLatest">
                  <BaseIcon
                    name="chevron-down"
                    size="sm"
                  />
                  回到最新
                </BaseButton>
              </div>
            </div>
          </div>
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
        :can-start-thread="workspace.canStartThread.value"
        :show-continue-action="showContinueAction"
        :can-send-fresh-message="canSendFreshMessage"
        :cancelling="workspace.cancelling.value"
        :send-button-label="sendButtonLabel"
        :last-event-at="workspace.lastEventAt.value"
        :on-resume-interrupted-run="workspace.resumeInterruptedRun"
        :compact="isCompactMode"
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
      :initial-tab="inspectorInitialTab"
      :show-history="showHistory"
      :show-artifacts="showArtifacts"
      :allow-reset-target="allowResetTarget"
      :target-text="workspace.targetText.value"
      :project-name="currentProject?.name || ''"
      :active-thread-id="workspace.activeThreadId.value"
      :last-run-id="workspace.lastRunId.value"
      :selected-branch="workspace.selectedBranch.value"
      :latest-message-preview="workspace.latestMessagePreview.value"
      :history-items="workspace.historyItems.value"
      :is-viewing-branch="workspace.isViewingBranch.value"
      :plan-view="planView"
      :files="inspectorFiles"
      :values="workspace.displayState.value"
      :is-running="workspace.sending.value"
      :has-interrupt="hasBlockingInterrupt"
      :source-note="props.sourceNote"
      :context-notice="props.contextNotice"
      :on-update-state="workspace.updateThreadStatePatch"
      @close="contextDrawerOpen = false"
      @select-branch="workspace.selectBranch($event)"
      @reset-target="handleResetTarget"
    />

    <ChatRunOptionsDialog
      :show="runtimeOptionsDialogOpen"
      :selected-tools-label="selectedToolsLabel"
      :draft-run-options="draftRunOptions"
      :runtime-models="workspace.runtimeModels.value"
      :runtime-tools="workspace.runtimeTools.value"
      :loading-runtime="workspace.loadingRuntime.value"
      @close="runtimeOptionsDialogOpen = false"
      @update:model-id="draftRunOptions.modelId = $event"
      @update:enable-tools="draftRunOptions.enableTools = $event"
      @toggle-tool="toggleDraftTool"
      @update:debug-mode="draftRunOptions.debugMode = $event"
      @update:temperature="draftRunOptions.temperature = $event"
      @update:max-tokens="draftRunOptions.maxTokens = $event"
      @restore="restoreDraftRunOptions"
      @apply="applyDraftRunOptions"
    />
  </section>
</template>
