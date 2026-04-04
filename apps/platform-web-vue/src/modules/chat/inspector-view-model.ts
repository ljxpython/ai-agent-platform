import type { Message } from '@langchain/langgraph-sdk'
import { getMessageText } from '@/utils/chat-content'
import {
  buildChatMessageMetaView,
  type ChatSubAgentCard,
  type ChatToolCallCard
} from './message-meta-view-model'

export type ChatInspectorFile = {
  path: string
  content: string
  lineCount: number
}

export type ChatInspectorToolSection = {
  id: string
  title: string
  summary: string
  pending: boolean
  toolCalls: ChatToolCallCard[]
  subAgentCards: ChatSubAgentCard[]
}

function normalizeFileContent(rawContent: unknown): string {
  if (typeof rawContent === 'string') {
    return rawContent
  }

  if (rawContent && typeof rawContent === 'object') {
    const fileRecord = rawContent as Record<string, unknown>
    if ('content' in fileRecord) {
      const content = fileRecord.content
      if (typeof content === 'string') {
        return content
      }
      if (Array.isArray(content)) {
        return content.map((item) => String(item)).join('\n')
      }
      if (content != null) {
        return JSON.stringify(content, null, 2)
      }
      return ''
    }

    return JSON.stringify(fileRecord, null, 2)
  }

  if (rawContent == null) {
    return ''
  }

  return String(rawContent)
}

function summarizeToolSection(toolCalls: ChatToolCallCard[], subAgentCards: ChatSubAgentCard[]) {
  const parts: string[] = []

  if (toolCalls.length > 0) {
    parts.push(`${toolCalls.length} 个工具调用`)
  }

  if (subAgentCards.length > 0) {
    parts.push(`${subAgentCards.length} 个子任务`)
  }

  return parts.join(' / ')
}

function buildSectionTitle(message: Message, index: number) {
  const text = getMessageText(message.content).trim()
  if (text) {
    return text.replace(/\s+/g, ' ').slice(0, 48)
  }

  return `Assistant 回合 ${index + 1}`
}

export function normalizeChatInspectorFiles(values?: Record<string, unknown> | null): ChatInspectorFile[] {
  const rawFiles = values?.files
  if (!rawFiles || typeof rawFiles !== 'object' || Array.isArray(rawFiles)) {
    return []
  }

  return Object.entries(rawFiles as Record<string, unknown>)
    .map(([path, rawContent]) => {
      const content = normalizeFileContent(rawContent)

      return {
        path,
        content,
        lineCount: content ? content.split('\n').length : 0
      }
    })
    .sort((left, right) => left.path.localeCompare(right.path))
}

export function buildChatInspectorToolSections(messages: Message[]) {
  const sections: ChatInspectorToolSection[] = []
  let assistantTurnIndex = 0

  for (const message of messages) {
    if (message.type !== 'ai') {
      continue
    }

    const metaView = buildChatMessageMetaView(message, messages)
    if (metaView.toolCalls.length === 0 && metaView.subAgentCards.length === 0) {
      continue
    }

    sections.push({
      id: message.id || `assistant-turn-${assistantTurnIndex + 1}`,
      title: buildSectionTitle(message, assistantTurnIndex),
      summary: summarizeToolSection(metaView.toolCalls, metaView.subAgentCards),
      pending:
        metaView.toolCalls.some((item) => item.status === 'pending') ||
        metaView.subAgentCards.some((item) => item.status === 'pending'),
      toolCalls: metaView.toolCalls,
      subAgentCards: metaView.subAgentCards
    })

    assistantTurnIndex += 1
  }

  return sections.reverse()
}
