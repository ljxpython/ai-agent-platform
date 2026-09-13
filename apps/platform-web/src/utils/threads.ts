import type { ManagementThread, ThreadHistoryEntry } from '@/types/management'
import {
  getMessageAttachments as extractMessageAttachments,
  getMessageText as extractMessageText,
  summarizeMessageContent
} from '@/utils/chat-content'

function coerceText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

export function formatThreadTime(value?: string | null): string {
  if (!value) {
    return '--'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN')
}

export function getThreadAssistantId(thread?: ManagementThread | null): string | null {
  const value = asRecord(thread?.metadata).assistant_id
  return typeof value === 'string' && value.trim() ? value : null
}

export function getThreadAssistantName(thread?: ManagementThread | null): string | null {
  const value = asRecord(thread?.metadata).assistant_name
  return typeof value === 'string' && value.trim() ? value : null
}

export function getThreadGraphId(thread?: ManagementThread | null): string | null {
  const value = asRecord(thread?.metadata).graph_id
  return typeof value === 'string' && value.trim() ? value : null
}

export function getThreadGraphName(thread?: ManagementThread | null): string | null {
  const value = asRecord(thread?.metadata).graph_name
  return typeof value === 'string' && value.trim() ? value : null
}

export function hasDistinctThreadAssistantTarget(thread?: ManagementThread | null): boolean {
  const assistantId = getThreadAssistantId(thread)
  if (!assistantId) {
    return false
  }

  const graphId = getThreadGraphId(thread)
  return !graphId || assistantId !== graphId
}

export function getThreadListTitle(thread?: ManagementThread | null): string {
  if (!thread) {
    return 'Thread'
  }

  const metadata = asRecord(thread.metadata)
  const title = coerceText(metadata.title)
  if (title) {
    return title
  }

  const name = coerceText(metadata.name)
  if (name) {
    return name
  }

  const threadId = coerceText(thread.thread_id)
  if (!threadId) {
    return 'Thread'
  }
  if (threadId.length <= 24) {
    return threadId
  }
  return `${threadId.slice(0, 8)}...${threadId.slice(-8)}`
}

export function getThreadListSearchText(thread?: ManagementThread | null): string {
  if (!thread) {
    return ''
  }

  const metadata = asRecord(thread.metadata)
  return [
    thread.thread_id,
    thread.status,
    getThreadAssistantId(thread),
    getThreadAssistantName(thread),
    getThreadGraphId(thread),
    getThreadGraphName(thread),
    coerceText(metadata.title),
    coerceText(metadata.name),
    coerceText(metadata.target_display_name)
  ]
    .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    .join(' ')
    .toLowerCase()
}

type ThreadMessage = {
  id?: string
  type?: string
  content?: unknown
}

function getMessagesFromRecord(record: Record<string, unknown>): ThreadMessage[] {
  if (Array.isArray(record.messages)) {
    return record.messages as ThreadMessage[]
  }

  const nestedValues = asRecord(record.values)
  if (Array.isArray(nestedValues.messages)) {
    return nestedValues.messages as ThreadMessage[]
  }

  const stateRecord = asRecord(record.state)
  const stateValues = asRecord(stateRecord.values)
  if (Array.isArray(stateValues.messages)) {
    return stateValues.messages as ThreadMessage[]
  }

  const checkpointRecord = asRecord(record.checkpoint)
  const channelValues = asRecord(checkpointRecord.channel_values)
  if (Array.isArray(channelValues.messages)) {
    return channelValues.messages as ThreadMessage[]
  }

  return []
}

function extractMessages(source: unknown): ThreadMessage[] {
  if (!source || typeof source !== 'object') {
    return []
  }

  return getMessagesFromRecord(source as Record<string, unknown>)
}

function normalizePreviewText(value: string): string {
  return value.replace(/\s+/g, ' ').trim().slice(0, 96)
}

export function getThreadMessages(
  thread?: ManagementThread | null,
  state?: Record<string, unknown> | null
): ThreadMessage[] {
  const stateMessages = extractMessages(state)
  if (stateMessages.length) {
    return stateMessages
  }
  return extractMessages(thread?.values)
}

export function getMessageText(content: unknown): string {
  return extractMessageText(content)
}

export function getMessageAttachments(content: unknown) {
  return extractMessageAttachments(content)
}

export function getThreadPreviewText(thread?: Pick<ManagementThread, 'thread_id' | 'values'> | null): string {
  if (!thread) {
    return ''
  }
  const messages = extractMessages(thread.values)
  if (!messages.length) {
    return thread.thread_id
  }
  const firstMessage = messages[0]
  return summarizeMessageContent(firstMessage?.content) || thread.thread_id
}

export function getHistoryEntryId(entry: ThreadHistoryEntry, index: number): string {
  const checkpointId = asRecord(entry.checkpoint).checkpoint_id
  if (typeof checkpointId === 'string' && checkpointId.trim()) {
    return checkpointId
  }
  const rawId = entry.checkpoint_id
  if (typeof rawId === 'string' && rawId.trim()) {
    return rawId
  }
  return `history-${index}`
}

export function getHistoryEntryTime(entry: ThreadHistoryEntry): string {
  const metadataCreatedAt = asRecord(entry.metadata).created_at
  if (typeof metadataCreatedAt === 'string' && metadataCreatedAt.trim()) {
    return formatThreadTime(metadataCreatedAt)
  }
  const checkpointThreadTs = asRecord(entry.checkpoint).thread_ts
  if (typeof checkpointThreadTs === 'string' && checkpointThreadTs.trim()) {
    return formatThreadTime(checkpointThreadTs)
  }
  return '--'
}

function formatMessageActionPreview(message: ThreadMessage): string {
  const messageRecord = asRecord(message)
  const messageType = String(message.type || '').toLowerCase()

  // 1. 如果有 tool_calls (AI 决策发起工具调用)
  const toolCalls = Array.isArray(messageRecord.tool_calls)
    ? messageRecord.tool_calls
    : Array.isArray(asRecord(messageRecord.additional_kwargs).tool_calls)
      ? (asRecord(messageRecord.additional_kwargs).tool_calls as unknown[])
      : []

  if (toolCalls.length > 0) {
    const firstCall = asRecord(toolCalls[0])
    const callName = String(firstCall.name || asRecord(firstCall.function).name || '工具')
    const callArgs = asRecord(firstCall.args || asRecord(firstCall.function).arguments)
    const target =
      coerceText(callArgs.path) ||
      coerceText(callArgs.file_path) ||
      coerceText(callArgs.command) ||
      coerceText(callArgs.url) ||
      coerceText(callArgs.query)
    const targetSuffix = target ? ` (${target.length > 25 ? target.slice(0, 22) + '...' : target})` : ''
    return `🔧 调用工具: ${callName}${targetSuffix}`
  }

  // 2. 如果是 tool 消息 (工具返回结果)
  if (messageType === 'tool') {
    const toolName = coerceText(messageRecord.name) || '工具'
    const contentText = normalizePreviewText(summarizeMessageContent(message.content))
    const detail = contentText ? `: ${contentText}` : ''
    return `📥 工具完成 [${toolName}]${detail}`
  }

  // 3. 如果是 human 消息 (用户提问)
  if (messageType === 'human') {
    const text = normalizePreviewText(summarizeMessageContent(message.content))
    return text ? `👤 用户: ${text}` : '👤 用户输入'
  }

  // 4. 如果是 ai 消息 (Agent 输出)
  if (messageType === 'ai') {
    const text = normalizePreviewText(summarizeMessageContent(message.content))
    return text ? `🤖 Agent: ${text}` : '🤖 Agent 组织答复'
  }

  const text = normalizePreviewText(summarizeMessageContent(message.content))
  return text || ''
}

export function getHistoryEntryPreviewText(entry: ThreadHistoryEntry, index: number): string {
  if (Array.isArray(entry.interrupts) && entry.interrupts.length > 0) {
    return '🛑 等待审批: 需要人工确认操作'
  }

  const tasks = Array.isArray(entry.tasks) ? (entry.tasks as Record<string, unknown>[]) : []
  const isPureMiddleware =
    tasks.length > 0 &&
    tasks.every((t) => {
      const name = String(t?.name || '')
      return name.includes('Middleware') || name.includes('__pregel')
    })

  if (isPureMiddleware) {
    const firstTaskName = String(tasks[0]?.name || '')
    const shortName = firstTaskName.split('.')[0] || '系统状态'
    return `⚙️ 系统检查点 [${shortName}]`
  }

  const messages = extractMessages(entry)
  if (messages.length > 0) {
    const latestMessage = messages[messages.length - 1]
    if (latestMessage) {
      const actionText = formatMessageActionPreview(latestMessage)
      if (actionText) {
        return actionText
      }
    }
  }

  const metadata = asRecord(entry.metadata)
  const langgraphNode = coerceText(metadata.langgraph_node) || coerceText(metadata.node)
  if (langgraphNode) {
    return `节点执行: ${langgraphNode}`
  }

  const valuesRecord = asRecord(entry.values)
  const multimodalSummary = normalizePreviewText(coerceText(valuesRecord.multimodal_summary))
  if (multimodalSummary) {
    return multimodalSummary
  }

  return getHistoryEntryId(entry, index)
}

export function toPrettyJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return String(value)
  }
}

export function getThreadStateValues(
  state?: Record<string, unknown> | null
): Record<string, unknown> | null {
  if (!state || typeof state !== 'object') {
    return null
  }

  const nestedValues = asRecord(state.values)
  if (Object.keys(nestedValues).length > 0) {
    return nestedValues
  }

  return state
}
