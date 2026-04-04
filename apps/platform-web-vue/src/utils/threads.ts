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

export function getThreadGraphId(thread?: ManagementThread | null): string | null {
  const value = asRecord(thread?.metadata).graph_id
  return typeof value === 'string' && value.trim() ? value : null
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
    getThreadGraphId(thread),
    coerceText(metadata.title),
    coerceText(metadata.name)
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

export function getHistoryEntryPreviewText(entry: ThreadHistoryEntry, index: number): string {
  const messages = extractMessages(entry)
  if (messages.length > 0) {
    const firstConversationMessage =
      messages.find((item) => item?.type === 'human') ||
      messages.find((item) => item?.type === 'ai') ||
      messages[0]

    const preview = normalizePreviewText(summarizeMessageContent(firstConversationMessage?.content))
    if (preview) {
      return preview
    }
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
