import type { Message } from '@langchain/langgraph-sdk'
import { getMessageText } from '@/utils/chat-content'
import { toPrettyJson } from '@/utils/threads'

type ToolCallResultMap = Record<string, Message>

type ToolCallLike = {
  id?: string
  name?: string
  args?: unknown
}

export type ChatToolCallArgEntry = {
  key: string
  valueText: string
}

export type ChatToolCallCard = {
  key: string
  name: string
  idLabel: string
  status: 'pending' | 'completed'
  argsEntries: ChatToolCallArgEntry[]
  resultText?: string
}

export type ChatSubAgentCard = {
  id: string
  name: string
  status: 'pending' | 'completed'
  input: string
  output?: string
}

function normalizeToolArgs(args: unknown): Record<string, unknown> {
  if (args && typeof args === 'object' && !Array.isArray(args)) {
    return args as Record<string, unknown>
  }

  if (typeof args === 'string') {
    try {
      const parsed = JSON.parse(args)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      // ignore parse failure
    }

    return {
      input: args
    }
  }

  return {}
}

function toArgEntries(args: unknown): ChatToolCallArgEntry[] {
  return Object.entries(normalizeToolArgs(args)).map(([key, value]) => ({
    key,
    valueText: typeof value === 'string' ? value : toPrettyJson(value)
  }))
}

function normalizeToolCallInput(args: unknown): string {
  if (args == null) {
    return ''
  }
  if (typeof args === 'string') {
    return args
  }
  if (typeof args === 'object') {
    const record = args as Record<string, unknown>
    const task =
      typeof record.task === 'string'
        ? record.task
        : typeof record.description === 'string'
          ? record.description
          : ''
    if (task.trim()) {
      return task
    }
    return toPrettyJson(record)
  }
  return String(args)
}

function getSubAgentName(args: unknown): string {
  if (!args || typeof args !== 'object') {
    return 'sub-agent'
  }

  const record = args as Record<string, unknown>
  return typeof record.subagent_type === 'string' && record.subagent_type.trim()
    ? record.subagent_type.trim()
    : 'sub-agent'
}

export function buildToolResultsByCallId(messages: Message[]): ToolCallResultMap {
  return messages.reduce<ToolCallResultMap>((result, item) => {
    if (item.type === 'tool' && typeof item.tool_call_id === 'string' && item.tool_call_id.trim()) {
      result[item.tool_call_id] = item
    }
    return result
  }, {})
}

export function buildChatMessageMetaView(message: Message, allMessages: Message[]) {
  const toolResultsByCallId = buildToolResultsByCallId(allMessages)

  if (message.type !== 'ai' || !Array.isArray(message.tool_calls)) {
    return {
      toolCalls: [] as ChatToolCallCard[],
      subAgentCards: [] as ChatSubAgentCard[]
    }
  }

  const toolCalls: ChatToolCallCard[] = []
  const subAgentCards: ChatSubAgentCard[] = []

  message.tool_calls.forEach((item, index) => {
    const toolCall = (item || {}) as ToolCallLike
    const toolCallId = typeof toolCall.id === 'string' && toolCall.id.trim() ? toolCall.id : ''
    const toolName = typeof toolCall.name === 'string' && toolCall.name.trim() ? toolCall.name : ''
    const toolResult = toolCallId ? toolResultsByCallId[toolCallId] : undefined

    if (toolName === 'task') {
      const output = toolResult ? getMessageText(toolResult.content) : ''
      subAgentCards.push({
        id: toolCallId || `task-${message.id || 'message'}-${index + 1}`,
        name: getSubAgentName(toolCall.args),
        status: toolResult ? 'completed' : 'pending',
        input: normalizeToolCallInput(toolCall.args),
        output: output || undefined
      })
      return
    }

    toolCalls.push({
      key: toolCallId || `${toolName || 'tool'}-${index + 1}`,
      name: toolName || 'Unknown Tool',
      idLabel: toolCallId || `tool-${index + 1}`,
      status: toolResult ? 'completed' : 'pending',
      argsEntries: toArgEntries(toolCall.args),
      resultText: toolResult ? getMessageText(toolResult.content) || undefined : undefined
    })
  })

  return {
    toolCalls,
    subAgentCards
  }
}
