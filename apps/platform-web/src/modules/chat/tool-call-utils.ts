import type { Message } from '@langchain/langgraph-sdk'

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function parseJsonValue(value: string): unknown {
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

export type ChatNormalizedToolCall = {
  id: string
  name: string
  args: unknown
}

function normalizeToolCallName(toolCall: Record<string, unknown>) {
  const fn = asRecord(toolCall.function)
  const nameCandidates = [fn.name, toolCall.name, toolCall.type]

  for (const candidate of nameCandidates) {
    if (typeof candidate === 'string' && candidate.trim() && candidate !== 'tool_use') {
      return candidate.trim()
    }
  }

  return ''
}

function normalizeToolCallArgs(toolCall: Record<string, unknown>) {
  const fn = asRecord(toolCall.function)
  const rawArgs = fn.arguments ?? toolCall.args ?? toolCall.input

  if (typeof rawArgs === 'string') {
    return parseJsonValue(rawArgs)
  }

  return rawArgs ?? {}
}

function normalizeToolCallId(toolCall: Record<string, unknown>, messageId: string, index: number) {
  const rawId = toolCall.id
  if (typeof rawId === 'string' && rawId.trim()) {
    return rawId.trim()
  }
  return `${messageId || 'tool'}-${index + 1}`
}

function collectRawToolCalls(message: Message) {
  if (message.type !== 'ai') {
    return []
  }

  const additionalKwargs = asRecord(message.additional_kwargs)
  if (Array.isArray(additionalKwargs.tool_calls) && additionalKwargs.tool_calls.length > 0) {
    return additionalKwargs.tool_calls
  }

  if (Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
    return message.tool_calls
  }

  if (Array.isArray(message.content)) {
    return message.content.filter((item) => asRecord(item).type === 'tool_use')
  }

  return []
}

export function extractToolCallsFromMessage(message: Message): ChatNormalizedToolCall[] {
  const messageId = typeof message.id === 'string' ? message.id : ''

  return collectRawToolCalls(message)
    .map((toolCall, index) => {
      const record = asRecord(toolCall)
      const name = normalizeToolCallName(record)
      if (!name) {
        return null
      }

      return {
        id: normalizeToolCallId(record, messageId, index),
        name,
        args: normalizeToolCallArgs(record)
      } satisfies ChatNormalizedToolCall
    })
    .filter((item): item is ChatNormalizedToolCall => item !== null)
}

export function collectLinkedToolCallIds(messages: Message[]) {
  const linkedToolCallIds = new Set<string>()

  for (const message of messages) {
    for (const toolCall of extractToolCallsFromMessage(message)) {
      if (toolCall.id.trim()) {
        linkedToolCallIds.add(toolCall.id)
      }
    }
  }

  return linkedToolCallIds
}
