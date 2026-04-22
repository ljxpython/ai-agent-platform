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
  selectLabel: string
}

export type ChatHistoryView = {
  totalEntries: number
  branchGroupCount: number
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

    return {
      id,
      parentId,
      preview: getHistoryEntryPreviewText(entry, index),
      time: getHistoryEntryTime(entry),
      messageCount: extractMessageCount(entry),
      taskCount: extractTaskCount(entry),
      step: extractStep(entry),
      source: extractSource(entry),
      hasInterrupts: extractHasInterrupts(entry),
      siblingCount,
      childCount,
      isLatest,
      isCurrent,
      isInSelectedPath,
      selectLabel: isCurrent ? '当前快照' : childCount > 0 || siblingCount > 1 ? '查看此分支' : '查看此快照'
    }
  })

  return {
    totalEntries: options.items.length,
    branchGroupCount,
    activeCheckpointId,
    selectedPathIds,
    items
  }
}
