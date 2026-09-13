import type { ThreadHistoryEntry } from '@/types/management'
import { getHistoryEntryId, getHistoryEntryPreviewText, getHistoryEntryTime } from '@/utils/threads'

type ChatHistoryViewItem = {
  id: string
  parentId: string
  preview: string
  time: string
  messageCount: number
  taskCount: number
  step: string
  source: string
  hasInterrupts: boolean
  siblingCount: number
  childCount: number
  isLatest: boolean
  isCurrent: boolean
  isInSelectedPath: boolean
  isKeyMilestone: boolean
  selectLabel: string
  rawEntry: ThreadHistoryEntry
}

export type ChatHistoryView = {
  totalEntries: number
  branchGroupCount: number
  keyMilestoneCount: number
  activeCheckpointId: string
  selectedPathIds: string[]
  items: ChatHistoryViewItem[]
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function extractParentCheckpointId(entry: ThreadHistoryEntry) {
  const directParent = entry.parent_checkpoint_id
  if (typeof directParent === 'string' && directParent.trim()) {
    return directParent.trim()
  }

  const nestedParent = asRecord(entry.parent_checkpoint).checkpoint_id
  return typeof nestedParent === 'string' && nestedParent.trim() ? nestedParent.trim() : ''
}

function extractSelectedPathIds(selectedBranch: string) {
  const normalized = selectedBranch.trim()
  if (!normalized) {
    return []
  }

  const pathItems = normalized.split('>').map((item) => item.trim()).filter(Boolean)
  return pathItems.length > 0 ? pathItems : [normalized]
}

function extractMessageCount(entry: ThreadHistoryEntry) {
  const values = asRecord(entry.values)
  return Array.isArray(values.messages) ? values.messages.length : 0
}

function extractTaskCount(entry: ThreadHistoryEntry) {
  return Array.isArray(entry.tasks) ? entry.tasks.length : 0
}

function extractHasInterrupts(entry: ThreadHistoryEntry) {
  return Array.isArray(entry.interrupts) && entry.interrupts.length > 0
}

function extractStep(entry: ThreadHistoryEntry) {
  const step = asRecord(entry.metadata).step
  if (typeof step === 'number') {
    return `step ${step}`
  }
  if (typeof step === 'string' && step.trim()) {
    return step.trim()
  }
  return '--'
}

function extractSource(entry: ThreadHistoryEntry) {
  const source = asRecord(entry.metadata).source
  return typeof source === 'string' && source.trim() ? source.trim() : ''
}

function getMessagesList(entry: ThreadHistoryEntry): Record<string, unknown>[] {
  const values = asRecord(entry.values)
  if (Array.isArray(values.messages)) {
    return values.messages as Record<string, unknown>[]
  }
  const channelValues = asRecord(asRecord(entry.checkpoint).channel_values)
  if (Array.isArray(channelValues.messages)) {
    return channelValues.messages as Record<string, unknown>[]
  }
  return []
}

function hasMeaningfulActionMessage(message: Record<string, unknown>): boolean {
  const type = String(message.type || '').toLowerCase()
  const toolCalls = Array.isArray(message.tool_calls)
    ? message.tool_calls
    : Array.isArray(asRecord(message.additional_kwargs).tool_calls)
      ? (asRecord(message.additional_kwargs).tool_calls as unknown[])
      : []

  if (toolCalls.length > 0) return true
  if (type === 'tool' || type === 'human') return true
  if (type === 'ai') {
    const text = typeof message.content === 'string' ? message.content.trim() : ''
    return text.length > 0
  }
  return false
}

function isSameActionMessage(a?: Record<string, unknown>, b?: Record<string, unknown>): boolean {
  if (!a || !b) return false
  if (a.id && b.id && a.id === b.id) return true
  const aType = String(a.type || '').toLowerCase()
  const bType = String(b.type || '').toLowerCase()
  if (aType !== bType) return false

  const aCalls = Array.isArray(a.tool_calls)
    ? a.tool_calls
    : Array.isArray(asRecord(a.additional_kwargs).tool_calls)
      ? (asRecord(a.additional_kwargs).tool_calls as unknown[])
      : []
  const bCalls = Array.isArray(b.tool_calls)
    ? b.tool_calls
    : Array.isArray(asRecord(b.additional_kwargs).tool_calls)
      ? (asRecord(b.additional_kwargs).tool_calls as unknown[])
      : []

  if (aCalls.length !== bCalls.length) return false

  const aContent = typeof a.content === 'string' ? a.content : JSON.stringify(a.content ?? '')
  const bContent = typeof b.content === 'string' ? b.content : JSON.stringify(b.content ?? '')
  return aContent === bContent
}

function isKeyMilestoneEntry(
  entry: ThreadHistoryEntry,
  info: {
    isLatest: boolean
    hasInterrupts: boolean
    childCount: number
    siblingCount: number
  },
  directParent?: ThreadHistoryEntry
): boolean {
  if (info.isLatest) return true
  if (info.hasInterrupts) return true
  if (info.childCount > 0 || info.siblingCount > 1) return true

  const tasks = Array.isArray(entry.tasks) ? (entry.tasks as Record<string, unknown>[]) : []
  const isPureMiddleware =
    tasks.length > 0 &&
    tasks.every((t) => {
      const name = String(t?.name || '')
      return name.includes('Middleware') || name.includes('__pregel')
    })

  if (isPureMiddleware) {
    return false
  }

  // 若存在明确父节点，检查是否完全没有产生新的动作消息且无业务 task
  if (directParent) {
    const currentMessages = getMessagesList(entry)
    const parentMessages = getMessagesList(directParent)
    const latestMsg = currentMessages[currentMessages.length - 1]
    const parentLatestMsg = parentMessages[parentMessages.length - 1]

    const hasNoNewMessages =
      currentMessages.length <= parentMessages.length &&
      isSameActionMessage(latestMsg, parentLatestMsg)

    if (hasNoNewMessages) {
      const hasBusinessTask = tasks.some((t) => {
        const name = String(t?.name || '')
        return name && !name.includes('Middleware') && !name.includes('__pregel')
      })
      if (!hasBusinessTask) {
        return false
      }
    }
  }

  // 检查是否包含有意义的业务动作消息（用户输入、工具发起、工具完成、AI实质回复）
  const currentMessages = getMessagesList(entry)
  if (currentMessages.length > 0) {
    const latestMsg = currentMessages[currentMessages.length - 1]
    if (latestMsg && hasMeaningfulActionMessage(latestMsg)) {
      return true
    }
  }

  // 检查是否有实质性业务 Task
  const hasBusinessTask = tasks.some((t) => {
    const name = String(t?.name || '')
    return name && !name.includes('Middleware') && !name.includes('__pregel')
  })
  if (hasBusinessTask) {
    return true
  }

  return false
}

export function buildChatHistoryView(options: {
  items: ThreadHistoryEntry[]
  selectedBranch: string
  isViewingBranch: boolean
}): ChatHistoryView {
  const selectedPathIds = extractSelectedPathIds(options.selectedBranch)
  const activeCheckpointId = options.isViewingBranch
    ? selectedPathIds[selectedPathIds.length - 1] || ''
    : options.items.length > 0
      ? getHistoryEntryId(options.items[0], 0)
      : ''

  const entryById = new Map<string, ThreadHistoryEntry>()
  options.items.forEach((entry, index) => {
    entryById.set(getHistoryEntryId(entry, index), entry)
  })

  const childrenByParent = options.items.reduce<Record<string, string[]>>((result, entry, index) => {
    const parentId = extractParentCheckpointId(entry)
    const itemId = getHistoryEntryId(entry, index)
    if (!parentId) {
      return result
    }
    result[parentId] ??= []
    result[parentId].push(itemId)
    return result
  }, {})

  const branchGroupCount = Object.values(childrenByParent).filter((items) => items.length > 1).length

  const items = options.items.map((entry, index) => {
    const id = getHistoryEntryId(entry, index)
    const parentId = extractParentCheckpointId(entry)
    const siblingCount = parentId ? childrenByParent[parentId]?.length ?? 0 : 0
    const childCount = childrenByParent[id]?.length ?? 0
    const isLatest = index === 0
    const isCurrent = activeCheckpointId ? activeCheckpointId === id : isLatest
    const isInSelectedPath = selectedPathIds.includes(id)
    const hasInterrupts = extractHasInterrupts(entry)

    // 仅基于明确的 directParent 进行无变化状态帧剔除
    const directParent = parentId ? entryById.get(parentId) : undefined

    const isKeyMilestone = isKeyMilestoneEntry(
      entry,
      {
        isLatest,
        hasInterrupts,
        childCount,
        siblingCount
      },
      directParent
    )

    return {
      id,
      parentId,
      preview: getHistoryEntryPreviewText(entry, index),
      time: getHistoryEntryTime(entry),
      messageCount: extractMessageCount(entry),
      taskCount: extractTaskCount(entry),
      step: extractStep(entry),
      source: extractSource(entry),
      hasInterrupts,
      siblingCount,
      childCount,
      isLatest,
      isCurrent,
      isInSelectedPath,
      isKeyMilestone,
      selectLabel: isCurrent ? '当前快照' : childCount > 0 || siblingCount > 1 ? '查看此分支' : '查看此快照',
      rawEntry: entry
    }
  })

  const keyMilestoneCount = items.filter((item) => item.isKeyMilestone).length

  return {
    totalEntries: options.items.length,
    branchGroupCount,
    keyMilestoneCount,
    activeCheckpointId,
    selectedPathIds,
    items
  }
}
