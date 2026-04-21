import type { Message } from '@langchain/langgraph-sdk'
import { formatThreadTime } from '@/utils/threads'
import { getChatMessageIdentifier } from './branching'
import { collectLinkedToolCallIds } from './tool-call-utils'

export type ChatDisplayMessage = {
  id: string
  originalIndex: number
  message: Message
  roleLabel: string
  bubbleClass: string
  wrapClass: string
  timeText: string
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }

  return value as Record<string, unknown>
}

function resolveMessageTimestampValue(message: Message): string {
  const messageRecord = asRecord(message)
  const directTimestamp =
    messageRecord.created_at || messageRecord.updated_at || messageRecord.createdAt || messageRecord.updatedAt

  if (typeof directTimestamp === 'string' && directTimestamp.trim()) {
    return directTimestamp
  }

  const metadataRecord = asRecord(messageRecord.metadata)
  const responseMetadataRecord = asRecord(messageRecord.response_metadata)
  const additionalKwargsRecord = asRecord(messageRecord.additional_kwargs)
  const candidateValues = [
    metadataRecord.created_at,
    metadataRecord.updated_at,
    metadataRecord.createdAt,
    metadataRecord.updatedAt,
    responseMetadataRecord.created_at,
    responseMetadataRecord.updated_at,
    responseMetadataRecord.createdAt,
    responseMetadataRecord.updatedAt,
    additionalKwargsRecord.created_at,
    additionalKwargsRecord.updated_at,
    additionalKwargsRecord.createdAt,
    additionalKwargsRecord.updatedAt
  ]

  const matchedValue = candidateValues.find((value) => typeof value === 'string' && value.trim())
  return typeof matchedValue === 'string' ? matchedValue : ''
}

export function getChatMessageTimeText(message: Message): string {
  const rawTimestamp = resolveMessageTimestampValue(message)
  return rawTimestamp ? formatThreadTime(rawTimestamp) : ''
}

export function isVisibleChatMessage(message: Message, linkedToolCallIds: Set<string>) {
  if (message.type !== 'tool') {
    return true
  }

  return !(typeof message.tool_call_id === 'string' && linkedToolCallIds.has(message.tool_call_id))
}

export function getChatMessageRoleLabel(message: Message) {
  if (message.type === 'human') {
    return '你'
  }
  if (message.type === 'tool') {
    return 'Tool'
  }
  if (message.type === 'system') {
    return 'System'
  }
  return 'Agent'
}

export function getChatMessageBubbleClass(message: Message) {
  if (message.type === 'human') {
    return 'border-primary-200 bg-primary-50/80 text-primary-950 dark:border-primary-900/40 dark:bg-primary-950/25 dark:text-primary-50'
  }
  if (message.type === 'tool') {
    return 'border-amber-200 bg-amber-50/80 text-amber-950 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-50'
  }
  if (message.type === 'system') {
    return 'border-gray-200 bg-gray-50 text-gray-800 dark:border-dark-700 dark:bg-dark-900/70 dark:text-gray-200'
  }
  return 'border-gray-200 bg-white text-gray-900 dark:border-dark-700 dark:bg-dark-900/85 dark:text-white'
}

export function getChatMessageWrapClass(message: Message) {
  return message.type === 'human' ? 'items-end' : 'items-start'
}

export function buildChatDisplayMessages(messages: Message[], lastEventAt = ''): ChatDisplayMessage[] {
  const linkedToolCallIds = collectLinkedToolCallIds(messages)

  const visibleMessages = messages.reduce<ChatDisplayMessage[]>((result, message, index) => {
    if (!isVisibleChatMessage(message, linkedToolCallIds)) {
      return result
    }

    result.push({
      id: getChatMessageIdentifier(message, index),
      originalIndex: index,
      message,
      roleLabel: getChatMessageRoleLabel(message),
      bubbleClass: getChatMessageBubbleClass(message),
      wrapClass: getChatMessageWrapClass(message),
      timeText: getChatMessageTimeText(message)
    })

    return result
  }, [])

  if (lastEventAt.trim()) {
    const lastVisibleMessage =
      visibleMessages.length > 0 ? visibleMessages[visibleMessages.length - 1] : undefined
    if (lastVisibleMessage && !lastVisibleMessage.timeText) {
      lastVisibleMessage.timeText = formatThreadTime(lastEventAt)
    }
  }

  return visibleMessages
}
