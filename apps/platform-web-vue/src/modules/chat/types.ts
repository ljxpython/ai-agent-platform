import type { Message } from '@langchain/langgraph-sdk'
import type {
  ManagementThread,
  RuntimeModelItem,
  RuntimeToolItem,
  ThreadHistoryEntry
} from '@/types/management'
import type { ChatTargetPreference } from '@/utils/chatTarget'

export type ChatResolvedTarget = ChatTargetPreference & {
  resolvedTargetId: string
  label: string
}

export type ChatWorkspaceDisplay = {
  title: string
  description: string
  emptyTitle?: string
  emptyDescription?: string
}

export type ChatWorkspaceFeatures = {
  allowRunOptions?: boolean
  showHistory?: boolean
  showArtifacts?: boolean
  showContextBar?: boolean
}

export type ChatRunOptions = {
  modelId: string
  enableTools: boolean
  toolNames: string[]
  temperature: string
  maxTokens: string
  debugMode: boolean
}

export type ChatWorkspaceThread = ManagementThread
export type ChatWorkspaceHistoryEntry = ThreadHistoryEntry
export type ChatWorkspaceMessage = Message

export type ChatRuntimeCatalog = {
  models: RuntimeModelItem[]
  tools: RuntimeToolItem[]
}

export function resolveChatTarget(target?: ChatTargetPreference | null): ChatResolvedTarget | null {
  if (!target) {
    return null
  }

  if (target.targetType === 'graph') {
    const graphId = target.graphId?.trim() || target.assistantId?.trim() || ''
    if (!graphId) {
      return null
    }

    return {
      targetType: 'graph',
      graphId,
      updatedAt: target.updatedAt,
      resolvedTargetId: graphId,
      label: `Graph · ${graphId}`
    }
  }

  const assistantId = target.assistantId?.trim() || ''
  if (!assistantId) {
    return null
  }

  return {
    targetType: 'assistant',
    assistantId,
    updatedAt: target.updatedAt,
    resolvedTargetId: assistantId,
    label: `Assistant · ${assistantId}`
  }
}
