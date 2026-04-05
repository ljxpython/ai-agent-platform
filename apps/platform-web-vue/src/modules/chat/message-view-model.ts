import type { Message } from '@langchain/langgraph-sdk'
import { getChatMessageIdentifier } from './branching'

export type ChatDisplayMessage = {
  id: string
  originalIndex: number
  message: Message
  roleLabel: string
  bubbleClass: string
  wrapClass: string
}

function collectLinkedToolCallIds(messages: Message[]) {
  const linkedToolCallIds = new Set<string>()

  for (const message of messages) {
    if (message.type !== 'ai' || !Array.isArray(message.tool_calls)) {
      continue
    }

    for (const toolCall of message.tool_calls) {
      if (typeof toolCall?.id === 'string' && toolCall.id.trim()) {
        linkedToolCallIds.add(toolCall.id)
      }
    }
  }

  return linkedToolCallIds
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
    return 'border-primary-200 bg-primary-50/90 text-primary-950 dark:border-primary-900/40 dark:bg-primary-950/30 dark:text-primary-50'
  }
  if (message.type === 'tool') {
    return 'border-amber-200 bg-amber-50/90 text-amber-950 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-50'
  }
  if (message.type === 'system') {
    return 'border-gray-200 bg-gray-50 text-gray-800 dark:border-dark-700 dark:bg-dark-900/70 dark:text-gray-200'
  }
  return 'border-white/70 bg-white/95 text-gray-900 dark:border-dark-700 dark:bg-dark-900/85 dark:text-white'
}

export function getChatMessageWrapClass(message: Message) {
  return message.type === 'human' ? 'items-end' : 'items-start'
}

export function buildChatDisplayMessages(messages: Message[]): ChatDisplayMessage[] {
  const linkedToolCallIds = collectLinkedToolCallIds(messages)

  return messages.reduce<ChatDisplayMessage[]>((result, message, index) => {
    if (!isVisibleChatMessage(message, linkedToolCallIds)) {
      return result
    }

    result.push({
      id: getChatMessageIdentifier(message, index),
      originalIndex: index,
      message,
      roleLabel: getChatMessageRoleLabel(message),
      bubbleClass: getChatMessageBubbleClass(message),
      wrapClass: getChatMessageWrapClass(message)
    })

    return result
  }, [])
}
