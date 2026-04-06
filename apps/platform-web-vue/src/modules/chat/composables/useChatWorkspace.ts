import type { Command, Message } from '@langchain/langgraph-sdk'
import { computed, reactive, ref, watch, type ComputedRef, type Ref } from 'vue'
import { listRuntimeModels, listRuntimeTools } from '@/services/runtime/runtime.service'
import {
  buildRuntimeSnapshotWarning,
  cancelRuntimeRun,
  createRuntimeRunStream,
  createRuntimeThread,
  deleteRuntimeThread,
  getRuntimeThreadSnapshot,
  listRuntimeThreadsPage,
  normalizeRuntimeGatewayError,
  resolveRuntimePermissionDescription,
  updateRuntimeThreadState,
  type RuntimeGatewayErrorMeta
} from '@/services/runtime-gateway/workspace.service'
import type { ManagementThread } from '@/types/management'
import { summarizeMessageContent, type ChatAttachmentBlock } from '@/utils/chat-content'
import {
  formatThreadTime,
  getThreadListTitle,
  getThreadMessages,
  getThreadPreviewText,
  getThreadStateValues
} from '@/utils/threads'
import {
  buildChatMessageMetadata,
  getChatBranchContext,
  normalizeHistoryStates
} from '../branching'
import type { ChatResolvedTarget, ChatRunOptions } from '../types'

type UseChatWorkspaceOptions = {
  projectId: ComputedRef<string>
  target: ComputedRef<ChatResolvedTarget | null>
  initialThreadId: Ref<string>
}

function parseNumericInput(raw: string, kind: 'float' | 'int'): number | undefined {
  const normalized = raw.trim()
  if (!normalized) {
    return undefined
  }

  const parsed = kind === 'float' ? Number.parseFloat(normalized) : Number.parseInt(normalized, 10)
  return Number.isFinite(parsed) ? parsed : undefined
}

function buildRunConfig(runOptions: ChatRunOptions) {
  const configurable: Record<string, unknown> = {}

  if (runOptions.modelId.trim()) {
    configurable.model_id = runOptions.modelId.trim()
  }

  configurable.enable_tools = runOptions.enableTools
  if (runOptions.enableTools && runOptions.toolNames.length > 0) {
    configurable.tools = runOptions.toolNames
  }

  const temperature = parseNumericInput(runOptions.temperature, 'float')
  if (temperature !== undefined) {
    configurable.temperature = temperature
  }

  const maxTokens = parseNumericInput(runOptions.maxTokens, 'int')
  if (maxTokens !== undefined) {
    configurable.max_tokens = maxTokens
  }

  return Object.keys(configurable).length > 0
    ? {
        configurable
      }
    : undefined
}

function eventMatches(name: string, prefix: string) {
  return name === prefix || name.startsWith(`${prefix}|`)
}

function unwrapInterruptPayload(interrupt: unknown): unknown {
  if (Array.isArray(interrupt)) {
    return interrupt.map(unwrapInterruptPayload)
  }
  if (
    interrupt &&
    typeof interrupt === 'object' &&
    'value' in interrupt &&
    (interrupt as { value?: unknown }).value !== undefined
  ) {
    return (interrupt as { value?: unknown }).value
  }
  return interrupt
}

function hasMeaningfulInterruptPayload(interrupt: unknown): boolean {
  const payload = unwrapInterruptPayload(interrupt)

  if (Array.isArray(payload)) {
    return payload.some((item) => hasMeaningfulInterruptPayload(item))
  }

  if (!payload) {
    return false
  }

  if (typeof payload === 'object') {
    return Object.keys(payload as Record<string, unknown>).length > 0
  }

  return true
}

function isBreakpointInterrupt(interrupt: unknown): boolean {
  const payload = unwrapInterruptPayload(interrupt)
  if (Array.isArray(payload)) {
    return payload.length > 0 && payload.every((item) => isBreakpointInterrupt(item))
  }
  if (!payload || typeof payload !== 'object') {
    return false
  }
  return (payload as Record<string, unknown>).when === 'breakpoint'
}

function extractInterruptPayload(state?: Record<string, unknown> | null): unknown {
  if (!state || typeof state !== 'object') {
    return undefined
  }

  if ('__interrupt__' in state && hasMeaningfulInterruptPayload(state.__interrupt__)) {
    return state.__interrupt__
  }

  if ('interrupt' in state && hasMeaningfulInterruptPayload(state.interrupt)) {
    return state.interrupt
  }

  if ('interrupts' in state && hasMeaningfulInterruptPayload(state.interrupts)) {
    return state.interrupts
  }

  const tasks = Array.isArray(state.tasks) ? state.tasks : []
  const taskInterrupts = tasks
    .map((task) => {
      if (!task || typeof task !== 'object') {
        return undefined
      }
      return (task as { interrupts?: unknown }).interrupts
    })
    .filter((item) => hasMeaningfulInterruptPayload(item))

  if (taskInterrupts.length === 1) {
    return taskInterrupts[0]
  }

  if (taskInterrupts.length > 1) {
    return taskInterrupts
  }

  return undefined
}

function hasPendingTaskToolCall(messages: Message[]): boolean {
  const resolvedToolCallIds = new Set<string>()

  for (const message of messages) {
    if (message.type === 'tool' && typeof message.tool_call_id === 'string' && message.tool_call_id.trim()) {
      resolvedToolCallIds.add(message.tool_call_id)
    }
  }

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message?.type !== 'ai' || !Array.isArray(message.tool_calls)) {
      continue
    }

    for (const toolCall of message.tool_calls) {
      if (!toolCall) {
        continue
      }
      const unresolved = !toolCall.id || !resolvedToolCallIds.has(toolCall.id)
      if (unresolved && toolCall.name === 'task') {
        return true
      }
    }
  }

  return false
}

function isAbortLikeError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true
  }
  if (error instanceof Error && /aborted|aborterror|cancelled|canceled/i.test(error.name + error.message)) {
    return true
  }
  return false
}

function extractErrorText(value: unknown): string {
  if (typeof value === 'string') {
    return value.trim()
  }

  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return ''
  }

  const record = value as Record<string, unknown>
  for (const key of ['error', 'message', 'detail']) {
    const candidate = record[key]
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim()
    }
  }

  return ''
}

function extractThreadFailureMessage(
  state?: Record<string, unknown> | null,
  threadStatus?: string | null
): string {
  const tasks = Array.isArray(state?.tasks) ? state.tasks : []
  for (const task of tasks) {
    if (!task || typeof task !== 'object') {
      continue
    }

    const taskError = extractErrorText((task as Record<string, unknown>).error)
    if (taskError) {
      return taskError
    }
  }

  const stateError = extractErrorText(state?.error)
  if (stateError) {
    return stateError
  }

  return threadStatus === 'error' ? '最近一次运行失败，请查看线程状态后继续。' : ''
}

export function useChatWorkspace(options: UseChatWorkspaceOptions) {
  const threadItems = ref<ManagementThread[]>([])
  const activeThreadId = ref(options.initialThreadId.value.trim())
  const activeThread = ref<ManagementThread | null>(null)
  const activeState = ref<Record<string, unknown> | null>(null)
  const activeStateRaw = ref<Record<string, unknown> | null>(null)
  const historyItems = ref<Record<string, unknown>[]>([])
  const loadingThreads = ref(false)
  const loadingThreadDetail = ref(false)
  const loadingRuntime = ref(false)
  const creatingThread = ref(false)
  const sending = ref(false)
  const cancelling = ref(false)
  const error = ref('')
  const detailError = ref('')
  const detailWarning = ref('')
  const runtimeError = ref('')
  const threadErrorMeta = ref<RuntimeGatewayErrorMeta | null>(null)
  const detailErrorMeta = ref<RuntimeGatewayErrorMeta | null>(null)
  const lastRunId = ref('')
  const currentRunId = ref('')
  const lastEventAt = ref('')
  const runOptions = reactive<ChatRunOptions>({
    modelId: '',
    enableTools: false,
    toolNames: [],
    temperature: '',
    maxTokens: '',
    debugMode: false
  })
  const runtimeModels = ref(awaitableEmptyModels())
  const runtimeTools = ref(awaitableEmptyTools())
  const currentStreamAbortController = ref<AbortController | null>(null)
  const selectedBranch = ref('')
  const branchResetPending = ref(false)

  let threadListToken = 0
  let detailToken = 0

  const normalizedHistoryItems = computed(() => normalizeHistoryStates(historyItems.value))
  const branchContext = computed(() => getChatBranchContext(selectedBranch.value, normalizedHistoryItems.value))
  const displayStateRaw = computed<Record<string, unknown> | null>(() => {
    if (selectedBranch.value) {
      const branchState = branchContext.value.threadHead
      if (branchState && typeof branchState === 'object' && !Array.isArray(branchState)) {
        return branchState as unknown as Record<string, unknown>
      }
    }

    return activeStateRaw.value
  })
  const displayState = computed<Record<string, unknown> | null>(() => {
    if (selectedBranch.value) {
      const branchValues = branchContext.value.threadHead?.values
      if (branchValues && typeof branchValues === 'object' && !Array.isArray(branchValues)) {
        return branchValues as Record<string, unknown>
      }
    }

    return activeState.value
  })
  const messages = computed<Message[]>(() => {
    return (getThreadMessages(activeThread.value, displayState.value) as Message[]).filter(
      (item) => item && item.type !== 'remove'
    )
  })
  const messageMetadataById = computed(() =>
    buildChatMessageMetadata(messages.value, normalizedHistoryItems.value, branchContext.value)
  )

  const threadSummary = computed(() =>
    threadItems.value.map((item) => ({
      id: item.thread_id,
      title: getThreadListTitle(item),
      preview: getThreadPreviewText(item),
      updatedAt: item.updated_at || item.created_at || '',
      time: formatThreadTime(item.updated_at || item.created_at),
      status: item.status || 'idle'
    }))
  )

  const selectedThreadSummary = computed(() =>
    threadSummary.value.find((item) => item.id === activeThreadId.value) || null
  )

  const canStartThread = computed(
    () => Boolean(options.projectId.value && options.target.value) && !creatingThread.value && !sending.value
  )

  const canSend = computed(
    () => Boolean(options.projectId.value && options.target.value && !creatingThread.value && !sending.value)
  )
  const selectedBranchCheckpointId = computed(
    () => branchContext.value.threadHead?.checkpoint?.checkpoint_id?.trim() || ''
  )
  const isViewingBranch = computed(() => selectedBranch.value.trim().length > 0)

  const interruptPayload = computed(() => extractInterruptPayload(displayStateRaw.value))
  const threadFailureMessage = computed(() =>
    extractThreadFailureMessage(displayStateRaw.value, activeThread.value?.status)
  )
  const accessDeniedMessage = computed(() => {
    const permissionError = detailErrorMeta.value || threadErrorMeta.value
    return resolveRuntimePermissionDescription(permissionError)
  })
  const hasBreakpointInterrupt = computed(() => isBreakpointInterrupt(interruptPayload.value))
  const canContinueDebug = computed(() => {
    if (!runOptions.debugMode || sending.value) {
      return false
    }

    if (selectedBranch.value) {
      return interruptPayload.value !== undefined && hasBreakpointInterrupt.value
    }

    if (interruptPayload.value !== undefined) {
      return hasBreakpointInterrupt.value
    }

    return activeThread.value?.status === 'interrupted'
  })

  function applyStateSnapshot(nextState: Record<string, unknown> | null) {
    if (branchResetPending.value) {
      selectedBranch.value = ''
      branchResetPending.value = false
    }

    activeStateRaw.value = nextState
    const resolvedValues = getThreadStateValues(nextState)
    activeState.value = resolvedValues

    if (activeThread.value && resolvedValues) {
      activeThread.value = {
        ...activeThread.value,
        values: resolvedValues
      }
    }
  }

  async function loadRuntimeCatalog() {
    const projectId = options.projectId.value.trim()
    if (!projectId) {
      runtimeModels.value = awaitableEmptyModels()
      runtimeTools.value = awaitableEmptyTools()
      runtimeError.value = ''
      return
    }

    loadingRuntime.value = true
    runtimeError.value = ''

    try {
      const [modelsPayload, toolsPayload] = await Promise.all([
        listRuntimeModels(projectId),
        listRuntimeTools(projectId)
      ])
      runtimeModels.value = Array.isArray(modelsPayload.models) ? modelsPayload.models : awaitableEmptyModels()
      runtimeTools.value = Array.isArray(toolsPayload.tools) ? toolsPayload.tools : awaitableEmptyTools()

      if (!runOptions.modelId.trim()) {
        const defaultModel =
          runtimeModels.value.find((item) => item.is_default)?.model_id || runtimeModels.value[0]?.model_id || ''
        runOptions.modelId = defaultModel
      }
    } catch (loadError) {
      const normalizedError = normalizeRuntimeGatewayError(loadError, '运行时目录加载失败')
      runtimeModels.value = awaitableEmptyModels()
      runtimeTools.value = awaitableEmptyTools()
      runtimeError.value = normalizedError.message
    } finally {
      loadingRuntime.value = false
    }
  }

  async function loadThreadDetail(threadId: string) {
    const projectId = options.projectId.value.trim()
    const normalizedThreadId = threadId.trim()

    if (!projectId || !normalizedThreadId) {
      activeThread.value = null
      activeState.value = null
      activeStateRaw.value = null
      historyItems.value = []
      selectedBranch.value = ''
      branchResetPending.value = false
      detailError.value = ''
      detailWarning.value = ''
      detailErrorMeta.value = null
      return
    }

    const currentToken = ++detailToken
    loadingThreadDetail.value = true
    detailError.value = ''
    detailWarning.value = ''
    detailErrorMeta.value = null

    try {
      const fallbackSummary = threadItems.value.find((item) => item.thread_id === normalizedThreadId) || null
      const snapshot = await getRuntimeThreadSnapshot(projectId, normalizedThreadId, {
        summary: fallbackSummary,
        historyLimit: 12
      })

      if (currentToken !== detailToken) {
        return
      }

      activeThreadId.value = normalizedThreadId
      activeThread.value = snapshot.detail
      selectedBranch.value = ''
      branchResetPending.value = false
      applyStateSnapshot(snapshot.state)
      historyItems.value = Array.isArray(snapshot.history) ? snapshot.history : []
      detailWarning.value = buildRuntimeSnapshotWarning(snapshot)
    } catch (loadError) {
      if (currentToken !== detailToken) {
        return
      }

      const normalizedError = normalizeRuntimeGatewayError(loadError, '线程详情加载失败')
      activeThread.value = null
      activeState.value = null
      activeStateRaw.value = null
      historyItems.value = []
      selectedBranch.value = ''
      branchResetPending.value = false
      detailError.value = normalizedError.message
      detailWarning.value = ''
      detailErrorMeta.value = normalizedError
    } finally {
      if (currentToken === detailToken) {
        loadingThreadDetail.value = false
      }
    }
  }

  async function loadThreadList(preferredThreadId = '') {
    const projectId = options.projectId.value.trim()
    const target = options.target.value

    if (!projectId || !target) {
      threadItems.value = []
      activeThreadId.value = ''
      activeThread.value = null
      activeState.value = null
      activeStateRaw.value = null
      historyItems.value = []
      selectedBranch.value = ''
      branchResetPending.value = false
      error.value = ''
      threadErrorMeta.value = null
      loadingThreads.value = false
      return
    }

    const currentToken = ++threadListToken
    loadingThreads.value = true
    error.value = ''
    threadErrorMeta.value = null

    try {
      const payload = await listRuntimeThreadsPage(projectId, {
        limit: 100,
        offset: 0,
        assistantId: target.targetType === 'assistant' ? target.assistantId : undefined,
        graphId: target.targetType === 'graph' ? target.graphId || target.resolvedTargetId : undefined
      })

      if (currentToken !== threadListToken) {
        return
      }

      threadItems.value = Array.isArray(payload.items) ? payload.items : []

      const nextThreadId =
        preferredThreadId.trim() ||
        activeThreadId.value.trim() ||
        options.initialThreadId.value.trim() ||
        threadItems.value[0]?.thread_id ||
        ''

      if (!nextThreadId) {
        activeThreadId.value = ''
        activeThread.value = null
        activeState.value = null
        activeStateRaw.value = null
        historyItems.value = []
        selectedBranch.value = ''
        branchResetPending.value = false
        detailError.value = ''
        detailWarning.value = ''
        detailErrorMeta.value = null
        return
      }

      await loadThreadDetail(nextThreadId)
    } catch (loadError) {
      if (currentToken !== threadListToken) {
        return
      }

      const normalizedError = normalizeRuntimeGatewayError(loadError, '线程列表加载失败')
      threadItems.value = []
      activeThreadId.value = ''
      activeThread.value = null
      activeState.value = null
      activeStateRaw.value = null
      historyItems.value = []
      selectedBranch.value = ''
      branchResetPending.value = false
      detailWarning.value = ''
      error.value = normalizedError.message
      threadErrorMeta.value = normalizedError
    } finally {
      if (currentToken === threadListToken) {
        loadingThreads.value = false
      }
    }
  }

  async function createThread() {
    const projectId = options.projectId.value.trim()
    const target = options.target.value

    if (!projectId || !target) {
      throw new Error('缺少项目或聊天目标')
    }

    creatingThread.value = true
    detailError.value = ''
    detailWarning.value = ''
    detailErrorMeta.value = null

    try {
      const normalizedThread = await createRuntimeThread(projectId, {
        targetType: target.targetType,
        resolvedTargetId: target.resolvedTargetId,
        displayName: target.displayName,
        assistantId: target.assistantId,
        assistantName: target.assistantName,
        graphId: target.graphId,
        graphName: target.graphName
      })
      threadItems.value = [normalizedThread, ...threadItems.value.filter((item) => item.thread_id !== normalizedThread.thread_id)]
      activeThreadId.value = normalizedThread.thread_id
      activeThread.value = normalizedThread
      selectedBranch.value = ''
      branchResetPending.value = false
      applyStateSnapshot(
        normalizedThread.values && typeof normalizedThread.values === 'object'
          ? (normalizedThread.values as Record<string, unknown>)
          : { messages: [] }
      )
      historyItems.value = []
      return normalizedThread
    } finally {
      creatingThread.value = false
    }
  }

  async function streamRun(params: {
    threadId: string
    input?: Record<string, unknown> | null
    command?: Command
    interruptBefore?: '*' | string[]
    interruptAfter?: '*' | string[]
    checkpointId?: string
  }) {
    const projectId = options.projectId.value.trim()
    const target = options.target.value

    if (!projectId || !target) {
      return false
    }

    const abortController = new AbortController()
    currentStreamAbortController.value = abortController

    try {
      const stream = createRuntimeRunStream({
        projectId,
        threadId: params.threadId,
        targetId: target.resolvedTargetId,
        input: params.input,
        command: params.command,
        checkpointId: params.checkpointId || undefined,
        config: buildRunConfig(runOptions),
        interruptBefore: params.interruptBefore,
        interruptAfter: params.interruptAfter,
        signal: abortController.signal,
        onRunCreated: (payload) => {
          currentRunId.value = payload.run_id?.trim() || ''
          lastRunId.value = payload.run_id?.trim() || ''
        }
      })

      for await (const event of stream) {
        const eventName = typeof event.event === 'string' ? event.event : ''

        if (eventMatches(eventName, 'metadata')) {
          const payload = event.data as { run_id?: string }
          currentRunId.value = payload.run_id?.trim() || currentRunId.value
          lastRunId.value = payload.run_id?.trim() || lastRunId.value
          continue
        }

        if (eventMatches(eventName, 'values')) {
          const nextValues =
            event.data && typeof event.data === 'object'
              ? (event.data as Record<string, unknown>)
              : { messages: [...messages.value] }
          applyStateSnapshot(nextValues)
          lastEventAt.value = new Date().toISOString()
          continue
        }

        if (eventMatches(eventName, 'tasks')) {
          if (event.data && typeof event.data === 'object') {
            const nextState = {
              ...(activeStateRaw.value || activeState.value || {}),
              tasks: event.data
            }
            applyStateSnapshot(nextState)
          }
          continue
        }

        if (eventMatches(eventName, 'error')) {
          const payload = event.data as { message?: string; error?: string }
          detailError.value = payload.message || payload.error || '对话运行失败'
        }
      }

      await loadThreadList(params.threadId)
      return true
    } catch (runError) {
      if (isAbortLikeError(runError)) {
        if (!cancelling.value) {
          detailError.value = '当前运行已中断'
        }
        await loadThreadDetail(params.threadId)
        return false
      }

      detailError.value = normalizeRuntimeGatewayError(runError, '对话发送失败').message
      return false
    } finally {
      sending.value = false
      cancelling.value = false
      currentStreamAbortController.value = null
      currentRunId.value = ''
    }
  }

  async function startNewThread() {
    try {
      await createThread()
      error.value = ''
      return true
    } catch (createError) {
      detailError.value = normalizeRuntimeGatewayError(createError, '新建对话失败').message
      return false
    }
  }

  async function selectThread(threadId: string) {
    const normalizedThreadId = threadId.trim()
    if (!normalizedThreadId || normalizedThreadId === activeThreadId.value) {
      return
    }
    await loadThreadDetail(normalizedThreadId)
  }

  async function refreshActiveThread() {
    if (activeThreadId.value.trim()) {
      await loadThreadDetail(activeThreadId.value)
      return
    }
    await loadThreadList()
  }

  async function sendMessage(content: string, attachments: ChatAttachmentBlock[] = []) {
    const projectId = options.projectId.value.trim()
    const target = options.target.value
    const normalizedContent = content.trim()
    const normalizedAttachments = attachments.filter((item) => item && typeof item === 'object')

    if (!projectId || !target || sending.value || (!normalizedContent && normalizedAttachments.length === 0)) {
      return false
    }

    sending.value = true
    cancelling.value = false
    error.value = ''
    detailError.value = ''
    detailWarning.value = ''
    lastRunId.value = ''

    const humanMessageContent =
      normalizedAttachments.length > 0
        ? ([...(normalizedContent ? [{ type: 'text', text: normalizedContent }] : []), ...normalizedAttachments] as Message['content'])
        : normalizedContent

    const humanMessage: Message = {
      type: 'human',
      content: humanMessageContent
    }

    try {
      const currentThread = activeThreadId.value.trim() ? activeThread.value || threadItems.value.find((item) => item.thread_id === activeThreadId.value) || null : null
      const usableThread = currentThread || (await createThread())
      const usableThreadId = usableThread.thread_id
      const optimisticBaseState =
        (displayState.value && typeof displayState.value === 'object' ? displayState.value : activeState.value) || {}

      if (selectedBranch.value) {
        branchResetPending.value = true
      }

      applyStateSnapshot({
        ...optimisticBaseState,
        messages: [...messages.value, humanMessage]
      })

      return await streamRun({
        threadId: usableThreadId,
        checkpointId: selectedBranchCheckpointId.value || undefined,
        input: {
          messages: [humanMessage]
        },
        ...(runOptions.debugMode ? { interruptBefore: ['tools'] } : {})
      })
    } catch (runError) {
      detailError.value = normalizeRuntimeGatewayError(runError, '对话发送失败').message
      return false
    }
  }

  async function continueDebugRun() {
    const threadId = activeThreadId.value.trim()
    if (!threadId || !canContinueDebug.value) {
      return false
    }

    sending.value = true
    cancelling.value = false
    error.value = ''
    detailError.value = ''
    detailWarning.value = ''

    const pendingTaskToolCall = hasPendingTaskToolCall(messages.value)

    if (selectedBranch.value) {
      branchResetPending.value = true
    }

    return await streamRun({
      threadId,
      checkpointId: selectedBranchCheckpointId.value || undefined,
      ...(pendingTaskToolCall ? { interruptAfter: ['tools'] } : { interruptBefore: ['tools'] })
    })
  }

  async function cancelActiveRun() {
    const projectId = options.projectId.value.trim()
    const threadId = activeThreadId.value.trim()

    if (!sending.value || !projectId || !threadId) {
      return false
    }

    cancelling.value = true

    try {
      if (currentRunId.value.trim()) {
        await cancelRuntimeRun(projectId, threadId, currentRunId.value)
      }
    } catch {
      // 服务端取消失败时，仍然中止当前前端流，避免页面继续假死。
    } finally {
      currentStreamAbortController.value?.abort()
    }

    return true
  }

  async function updateThreadStatePatch(values: Record<string, unknown>) {
    const projectId = options.projectId.value.trim()
    const threadId = activeThreadId.value.trim()

    if (!projectId || !threadId) {
      throw new Error('缺少可更新的线程上下文')
    }

    await updateRuntimeThreadState(projectId, threadId, values)
    await loadThreadDetail(threadId)
    return true
  }

  async function deleteThread(threadId: string) {
    const projectId = options.projectId.value.trim()
    const normalizedThreadId = threadId.trim()

    if (!projectId || !normalizedThreadId) {
      throw new Error('缺少可删除的线程上下文')
    }

    await deleteRuntimeThread(projectId, normalizedThreadId)

    const remaining = threadItems.value.filter((item) => item.thread_id !== normalizedThreadId)
    threadItems.value = remaining

    if (activeThreadId.value === normalizedThreadId) {
      const nextThreadId = remaining[0]?.thread_id || ''
      if (!nextThreadId) {
        activeThreadId.value = ''
        activeThread.value = null
        activeState.value = null
        activeStateRaw.value = null
        historyItems.value = []
        selectedBranch.value = ''
        branchResetPending.value = false
        return true
      }

      await loadThreadDetail(nextThreadId)
    }

    return true
  }

  async function resumeInterruptedRun(resumePayload: unknown) {
    const threadId = activeThreadId.value.trim()
    if (!threadId || interruptPayload.value === undefined || sending.value) {
      return false
    }

    sending.value = true
    cancelling.value = false
    error.value = ''
    detailError.value = ''
    detailWarning.value = ''

    if (selectedBranch.value) {
      branchResetPending.value = true
    }

    return await streamRun({
      threadId,
      checkpointId: selectedBranchCheckpointId.value || undefined,
      input: null,
      command: {
        resume: resumePayload
      }
    })
  }

  function selectBranch(branch: string) {
    selectedBranch.value = branch.trim()
    detailError.value = ''
  }

  async function retryMessage(messageId: string) {
    const threadId = activeThreadId.value.trim()
    const checkpointId = messageMetadataById.value[messageId]?.parentCheckpoint?.checkpoint_id?.trim() || ''

    if (!threadId || !checkpointId || sending.value) {
      return false
    }

    sending.value = true
    cancelling.value = false
    error.value = ''
    detailError.value = ''
    detailWarning.value = ''
    lastRunId.value = ''

    if (selectedBranch.value) {
      branchResetPending.value = true
    }

    return await streamRun({
      threadId,
      checkpointId,
      ...(runOptions.debugMode ? { interruptBefore: ['tools'] } : {})
    })
  }

  async function editHumanMessage(messageId: string, content: Message['content']) {
    const threadId = activeThreadId.value.trim()
    const metadata = messageMetadataById.value[messageId]
    const checkpointId = metadata?.parentCheckpoint?.checkpoint_id?.trim() || ''

    if (!threadId || !checkpointId || sending.value) {
      return false
    }

    const nextMessage: Message = {
      type: 'human',
      content
    }
    const firstSeenValues =
      metadata?.firstSeenState?.values &&
      typeof metadata.firstSeenState.values === 'object' &&
      !Array.isArray(metadata.firstSeenState.values)
        ? (metadata.firstSeenState.values as Record<string, unknown>)
        : null
    const checkpointMessages = (getThreadMessages(null, firstSeenValues) as Message[]).filter(
      (item) => item && item.type !== 'remove'
    )

    sending.value = true
    cancelling.value = false
    error.value = ''
    detailError.value = ''
    detailWarning.value = ''
    lastRunId.value = ''

    if (selectedBranch.value) {
      branchResetPending.value = true
    }

    if (firstSeenValues) {
      applyStateSnapshot({
        ...firstSeenValues,
        messages: [...checkpointMessages, nextMessage]
      })
    }

    return await streamRun({
      threadId,
      checkpointId,
      input: {
        messages: [nextMessage]
      },
      ...(runOptions.debugMode ? { interruptBefore: ['tools'] } : {})
    })
  }

  function toggleTool(toolKey: string) {
    const normalizedToolKey = toolKey.trim()
    if (!normalizedToolKey) {
      return
    }

    const exists = runOptions.toolNames.includes(normalizedToolKey)
    runOptions.toolNames = exists
      ? runOptions.toolNames.filter((item) => item !== normalizedToolKey)
      : [...runOptions.toolNames, normalizedToolKey]
  }

  watch(
    [() => options.projectId.value, () => options.target.value?.resolvedTargetId],
    async () => {
      activeThreadId.value = options.initialThreadId.value.trim()
      lastRunId.value = ''
      lastEventAt.value = ''
      await Promise.all([loadRuntimeCatalog(), loadThreadList(options.initialThreadId.value)])
    },
    { immediate: true }
  )

  watch(
    () => options.initialThreadId.value,
    async (nextThreadId) => {
      const normalizedThreadId = nextThreadId.trim()
      if (!normalizedThreadId || normalizedThreadId === activeThreadId.value) {
        return
      }

      if (threadItems.value.some((item) => item.thread_id === normalizedThreadId)) {
        await loadThreadDetail(normalizedThreadId)
        return
      }

      await loadThreadList(normalizedThreadId)
    }
  )

  return {
    activeThreadId,
    activeThread,
    activeState,
    displayState,
    canSend,
    canStartThread,
    creatingThread,
    cancelActiveRun,
    canContinueDebug,
    accessDeniedMessage,
    detailError,
    detailWarning,
    deleteThread,
    editHumanMessage,
    error,
    historyItems,
    interruptPayload,
    isViewingBranch,
    lastEventAt,
    lastRunId,
    loadingRuntime,
    loadingThreadDetail,
    loadingThreads,
    messageMetadataById,
    messages,
    refreshActiveThread,
    retryMessage,
    runOptions,
    runtimeError,
    runtimeModels,
    runtimeTools,
    cancelling,
    continueDebugRun,
    selectedBranch,
    selectBranch,
    selectThread,
    selectedThreadSummary,
    sendMessage,
    sending,
    startNewThread,
    threadFailureMessage,
    threadItems,
    threadSummary,
    toggleTool,
    resumeInterruptedRun,
    updateThreadStatePatch,
    targetText: computed(() => options.target.value?.label || '--'),
    targetTypeText: computed(() => (options.target.value?.targetType === 'graph' ? 'Graph' : 'Assistant')),
    latestMessagePreview: computed(() => {
      const lastMessage = messages.value[messages.value.length - 1]
      return lastMessage ? summarizeMessageContent(lastMessage.content) : ''
    })
  }
}

function awaitableEmptyModels() {
  return [] as Awaited<ReturnType<typeof listRuntimeModels>>['models']
}

function awaitableEmptyTools() {
  return [] as Awaited<ReturnType<typeof listRuntimeTools>>['tools']
}
