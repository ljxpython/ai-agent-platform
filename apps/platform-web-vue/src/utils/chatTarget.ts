export type ChatTargetType = 'assistant' | 'graph'

export type ChatTargetPreference = {
  targetType: ChatTargetType
  assistantId?: string
  graphId?: string
  updatedAt: string
}

type ChatTargetInput = {
  targetType?: string | null
  assistantId?: string | null
  graphId?: string | null
  updatedAt?: string | null
}

const STORAGE_KEY_PREFIX = 'platform-web-vue:chat-target:'

function getStorageKey(projectId: string) {
  return `${STORAGE_KEY_PREFIX}${projectId}`
}

export function normalizeChatTarget(input?: ChatTargetInput | null): ChatTargetPreference | null {
  if (!input) {
    return null
  }

  const targetType = input.targetType === 'graph' ? 'graph' : 'assistant'
  const assistantId = input.assistantId?.trim() || ''
  const graphId = input.graphId?.trim() || ''
  const updatedAt = input.updatedAt?.trim() || new Date().toISOString()

  if (targetType === 'graph') {
    const resolvedGraphId = graphId || assistantId
    if (!resolvedGraphId) {
      return null
    }

    return {
      targetType,
      graphId: resolvedGraphId,
      updatedAt
    }
  }

  if (!assistantId) {
    return null
  }

  return {
    targetType,
    assistantId,
    updatedAt
  }
}

export function writeRecentChatTarget(projectId: string, input: ChatTargetInput) {
  if (!projectId.trim() || typeof window === 'undefined') {
    return
  }

  const target = normalizeChatTarget(input)
  if (!target) {
    return
  }

  window.localStorage.setItem(getStorageKey(projectId), JSON.stringify(target))
}

export function readRecentChatTarget(projectId: string): ChatTargetPreference | null {
  if (!projectId.trim() || typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(getStorageKey(projectId))
  if (!raw) {
    return null
  }

  try {
    return normalizeChatTarget(JSON.parse(raw) as ChatTargetInput)
  } catch {
    window.localStorage.removeItem(getStorageKey(projectId))
    return null
  }
}

export function clearRecentChatTarget(projectId: string) {
  if (!projectId.trim() || typeof window === 'undefined') {
    return
  }
  window.localStorage.removeItem(getStorageKey(projectId))
}
