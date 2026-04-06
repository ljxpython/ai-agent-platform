export type ChatTargetType = 'assistant' | 'graph'

export type ChatTargetPreference = {
  targetType: ChatTargetType
  assistantId?: string
  assistantName?: string
  graphId?: string
  graphName?: string
  updatedAt: string
}

type ChatTargetInput = {
  targetType?: string | null
  assistantId?: string | null
  assistantName?: string | null
  graphId?: string | null
  graphName?: string | null
  updatedAt?: string | null
}

const STORAGE_KEY_PREFIX = 'platform-web-vue:chat-target:'

function getStorageKey(projectId: string) {
  return `${STORAGE_KEY_PREFIX}${projectId}`
}

function normalizeTargetName(value?: string | null) {
  const normalized = value?.trim() || ''
  return normalized || undefined
}

export function normalizeChatTarget(input?: ChatTargetInput | null): ChatTargetPreference | null {
  if (!input) {
    return null
  }

  const targetType = input.targetType === 'graph' ? 'graph' : 'assistant'
  const assistantId = input.assistantId?.trim() || ''
  const assistantName = normalizeTargetName(input.assistantName)
  const graphId = input.graphId?.trim() || ''
  const graphName = normalizeTargetName(input.graphName)
  const updatedAt = input.updatedAt?.trim() || new Date().toISOString()

  if (targetType === 'graph') {
    const resolvedGraphId = graphId || assistantId
    if (!resolvedGraphId) {
      return null
    }

    return {
      targetType,
      graphId: resolvedGraphId,
      graphName,
      updatedAt
    }
  }

  if (!assistantId) {
    return null
  }

  return {
    targetType,
    assistantId,
    assistantName,
    updatedAt
  }
}

function resolveComparableTargetId(target: ChatTargetPreference) {
  if (target.targetType === 'graph') {
    return target.graphId?.trim() || target.assistantId?.trim() || ''
  }

  return target.assistantId?.trim() || ''
}

export function hasChatTargetDisplayName(target?: ChatTargetPreference | null) {
  if (!target) {
    return false
  }

  if (target.targetType === 'graph') {
    return Boolean(target.graphName?.trim())
  }

  return Boolean(target.assistantName?.trim())
}

export function mergeChatTargets(
  preferred?: ChatTargetInput | null,
  fallback?: ChatTargetInput | null
): ChatTargetPreference | null {
  const normalizedPreferred = normalizeChatTarget(preferred)
  const normalizedFallback = normalizeChatTarget(fallback)

  if (!normalizedPreferred) {
    return normalizedFallback
  }

  if (!normalizedFallback) {
    return normalizedPreferred
  }

  if (
    normalizedPreferred.targetType !== normalizedFallback.targetType ||
    resolveComparableTargetId(normalizedPreferred) !== resolveComparableTargetId(normalizedFallback)
  ) {
    return normalizedPreferred
  }

  if (normalizedPreferred.targetType === 'graph') {
    return {
      ...normalizedFallback,
      ...normalizedPreferred,
      graphName: normalizedPreferred.graphName || normalizedFallback.graphName
    }
  }

  return {
    ...normalizedFallback,
    ...normalizedPreferred,
    assistantName: normalizedPreferred.assistantName || normalizedFallback.assistantName
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
