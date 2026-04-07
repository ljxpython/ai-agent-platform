import type { Message } from '@langchain/langgraph-sdk'
import { getMessageText } from '@/utils/chat-content'

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

export type ChatToolResultRenderMode = 'default' | 'chart-image'

export type ChatToolResultView = {
  mode: ChatToolResultRenderMode
  text?: string
  imageUrl?: string
}

function isLikelyHttpUrl(value: string) {
  return /^https?:\/\/\S+$/i.test(value.trim())
}

function sanitizeUrl(value: string) {
  return value.trim().replace(/[),.;]+$/, '')
}

function extractUrlFromText(value: string) {
  const matched = value.match(/https?:\/\/[^\s)>"']+/i)
  if (!matched) {
    return undefined
  }

  const normalized = sanitizeUrl(matched[0])
  return isLikelyHttpUrl(normalized) ? normalized : undefined
}

function extractUrlFromUnknown(value: unknown, depth = 0): string | undefined {
  if (depth > 4 || value == null) {
    return undefined
  }

  if (typeof value === 'string') {
    return extractUrlFromText(value)
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const url = extractUrlFromUnknown(item, depth + 1)
      if (url) {
        return url
      }
    }
    return undefined
  }

  const record = asRecord(value)
  for (const key of ['url', 'uri', 'src']) {
    const url = extractUrlFromUnknown(record[key], depth + 1)
    if (url) {
      return url
    }
  }

  const nestedImageUrl = asRecord(record.image_url)
  if (Object.keys(nestedImageUrl).length > 0) {
    const url = extractUrlFromUnknown(nestedImageUrl.url, depth + 1)
    if (url) {
      return url
    }
  }

  for (const valueItem of Object.values(record)) {
    const url = extractUrlFromUnknown(valueItem, depth + 1)
    if (url) {
      return url
    }
  }

  return undefined
}

function isChartVisualizationTool(toolName: string) {
  const normalized = toolName.trim().toLowerCase()
  if (!normalized.startsWith('generate_')) {
    return false
  }

  return /(chart|diagram|map|graph|spreadsheet)$/.test(normalized)
}

export function buildChatToolResultView(toolName: string, toolResult?: Message): ChatToolResultView {
  const text = toolResult ? getMessageText(toolResult.content).trim() : ''

  if (!toolResult) {
    return { mode: 'default' }
  }

  if (isChartVisualizationTool(toolName)) {
    const artifact = (toolResult as Message & { artifact?: unknown }).artifact
    const imageUrl = extractUrlFromUnknown(artifact) || extractUrlFromUnknown(text)
    if (imageUrl) {
      return {
        mode: 'chart-image',
        text,
        imageUrl
      }
    }
  }

  return {
    mode: 'default',
    text: text || undefined
  }
}
