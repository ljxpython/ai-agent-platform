import type { Checkpoint, Message, ThreadState } from '@langchain/langgraph-sdk'

type ChatBranchNode<TState extends Record<string, unknown> = Record<string, unknown>> = {
  type: 'node'
  value: ThreadState<TState>
  path: string[]
}

type ChatBranchFork<TState extends Record<string, unknown> = Record<string, unknown>> = {
  type: 'fork'
  items: ChatBranchSequence<TState>[]
}

type ChatBranchSequence<TState extends Record<string, unknown> = Record<string, unknown>> = {
  type: 'sequence'
  items: Array<ChatBranchNode<TState> | ChatBranchFork<TState>>
}

export type ChatBranchContext<TState extends Record<string, unknown> = Record<string, unknown>> = {
  branchTree: ChatBranchSequence<TState>
  flatHistory: ThreadState<TState>[]
  branchByCheckpoint: Record<
    string,
    {
      branch: string | undefined
      branchOptions: string[] | undefined
    }
  >
  threadHead?: ThreadState<TState>
}

export type ChatMessageMetadata = {
  messageId: string
  checkpointId?: string
  firstSeenState?: ThreadState<Record<string, unknown>>
  parentCheckpoint?: Checkpoint | null
  branch?: string
  branchOptions?: string[]
}

const PATH_SEPARATOR = '>'
const ROOT_ID = '$'

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function findLast<T>(items: T[], predicate: (item: T) => boolean): T | undefined {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index]
    if (predicate(item)) {
      return item
    }
  }
  return undefined
}

function getStateMessages(state: ThreadState<Record<string, unknown>>): Message[] {
  const values = asRecord(state.values)
  return Array.isArray(values.messages) ? (values.messages as Message[]) : []
}

export function getChatMessageIdentifier(message: Message, index: number): string {
  return typeof message.id === 'string' && message.id.trim() ? message.id : `message-${index}`
}

export function normalizeHistoryStates(history: unknown[]): ThreadState<Record<string, unknown>>[] {
  return history.filter((item): item is ThreadState<Record<string, unknown>> => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      return false
    }

    const entry = item as Record<string, unknown>
    return (
      'values' in entry &&
      'checkpoint' in entry &&
      asRecord(entry.checkpoint).checkpoint_id !== undefined
    )
  })
}

function getBranchSequence<TState extends Record<string, unknown>>(
  history: ThreadState<TState>[]
): {
  rootSequence: ChatBranchSequence<TState>
  paths: string[][]
} {
  const nodeIds = new Set<string>()
  const childrenMap: Record<string, ThreadState<TState>[]> = {}

  if (history.length <= 1) {
    return {
      rootSequence: {
        type: 'sequence',
        items: history.map((value) => ({ type: 'node', value, path: [] }))
      },
      paths: []
    }
  }

  history.forEach((state) => {
    const checkpointId = state.parent_checkpoint?.checkpoint_id ?? ROOT_ID
    childrenMap[checkpointId] ??= []
    childrenMap[checkpointId].push(state)

    if (state.checkpoint?.checkpoint_id != null) {
      nodeIds.add(state.checkpoint.checkpoint_id)
    }
  })

  const maxId = (...ids: Array<string | null | undefined>) =>
    ids
      .filter((item): item is string => typeof item === 'string' && item.length > 0)
      .sort((left, right) => left.localeCompare(right))
      .slice(-1)[0]

  const lastOrphanedNode =
    childrenMap[ROOT_ID] == null
      ? Object.keys(childrenMap)
          .filter((parentId) => !nodeIds.has(parentId))
          .map((parentId) => {
            const queue = [parentId]
            const seen = new Set<string>()
            let lastId = parentId

            while (queue.length > 0) {
              const current = queue.shift()
              if (!current || seen.has(current)) {
                continue
              }
              seen.add(current)

              const children = (childrenMap[current] ?? []).flatMap(
                (item) => item.checkpoint?.checkpoint_id ?? []
              )

              lastId = maxId(lastId, ...children) ?? lastId
              queue.push(...children)
            }

            return { parentId, lastId }
          })
          .sort((left, right) => left.lastId.localeCompare(right.lastId))
          .slice(-1)[0]?.parentId
      : undefined

  if (lastOrphanedNode != null) {
    childrenMap[ROOT_ID] = childrenMap[lastOrphanedNode]
  }

  const rootSequence: ChatBranchSequence<TState> = { type: 'sequence', items: [] }
  const queue: Array<{ id: string; sequence: ChatBranchSequence<TState>; path: string[] }> = [
    { id: ROOT_ID, sequence: rootSequence, path: [] }
  ]

  const paths: string[][] = []
  const visited = new Set<string>()

  while (queue.length > 0) {
    const task = queue.shift()
    if (!task || visited.has(task.id)) {
      continue
    }
    visited.add(task.id)

    const children = childrenMap[task.id]
    if (!children || children.length === 0) {
      continue
    }

    let fork: ChatBranchFork<TState> | undefined
    if (children.length > 1) {
      fork = { type: 'fork', items: [] }
      task.sequence.items.push(fork)
    }

    for (const value of children) {
      const id = value.checkpoint?.checkpoint_id
      if (!id) {
        continue
      }

      let { sequence } = task
      let { path } = task

      if (fork) {
        sequence = { type: 'sequence', items: [] }
        fork.items.unshift(sequence)

        path = path.slice()
        path.push(id)
        paths.push(path)
      }

      sequence.items.push({ type: 'node', value, path })
      queue.push({ id, sequence, path })
    }
  }

  return { rootSequence, paths }
}

function getBranchView<TState extends Record<string, unknown>>(
  sequence: ChatBranchSequence<TState>,
  branch: string
): {
  history: ThreadState<TState>[]
  branchByCheckpoint: Record<
    string,
    {
      branch: string | undefined
      branchOptions: string[] | undefined
    }
  >
} {
  const path = branch
    .split(PATH_SEPARATOR)
    .map((item) => item.trim())
    .filter(Boolean)
  const history: ThreadState<TState>[] = []
  const branchByCheckpoint: Record<
    string,
    {
      branch: string | undefined
      branchOptions: string[] | undefined
    }
  > = {}

  const forkStack = path.slice()
  const queue = [...sequence.items]

  while (queue.length > 0) {
    const item = queue.shift()
    if (!item) {
      continue
    }

    if (item.type === 'node') {
      history.push(item.value)
      const checkpointId = item.value.checkpoint?.checkpoint_id
      if (!checkpointId) {
        continue
      }

      branchByCheckpoint[checkpointId] = {
        branch: item.path.join(PATH_SEPARATOR) || undefined,
        branchOptions: undefined
      }
      continue
    }

    const forkId = forkStack.shift()
    const index =
      forkId != null
        ? item.items.findIndex((value) => {
            const firstItem = value.items[0]
            return firstItem?.type === 'node' && firstItem.value.checkpoint?.checkpoint_id === forkId
          })
        : -1
    const selectedIndex = index >= 0 ? index : item.items.length - 1
    const selectedSequence = selectedIndex >= 0 ? item.items[selectedIndex] : undefined
    const branchOptions = item.items
      .map((value) => {
        const firstItem = value.items[0]
        return firstItem?.type === 'node' ? firstItem.path.join(PATH_SEPARATOR) : ''
      })
      .filter(Boolean)
    const selectedBranch = branchOptions[selectedIndex]
    const previousCheckpointId = history[history.length - 1]?.checkpoint?.checkpoint_id

    if (previousCheckpointId) {
      const current = branchByCheckpoint[previousCheckpointId]
      branchByCheckpoint[previousCheckpointId] = {
        branch: selectedBranch || current?.branch,
        branchOptions: branchOptions.length > 1 ? branchOptions : current?.branchOptions
      }
    }

    if (selectedSequence) {
      queue.unshift(...selectedSequence.items)
    }
  }

  return { history, branchByCheckpoint }
}

export function getChatBranchContext<TState extends Record<string, unknown>>(
  branch: string,
  history: ThreadState<TState>[] | undefined
): ChatBranchContext<TState> {
  const { rootSequence: branchTree } = getBranchSequence(history ?? [])
  const { history: flatHistory, branchByCheckpoint } = getBranchView(branchTree, branch)

  return {
    branchTree,
    flatHistory,
    branchByCheckpoint,
    threadHead: flatHistory[flatHistory.length - 1]
  }
}

export function buildChatMessageMetadata(
  messages: Message[],
  history: ThreadState<Record<string, unknown>>[],
  branchContext: ChatBranchContext<Record<string, unknown>>
): Record<string, ChatMessageMetadata> {
  const shownBranchOptions = new Set<string>()

  return messages.reduce<Record<string, ChatMessageMetadata>>((result, message, index) => {
    const messageId = getChatMessageIdentifier(message, index)
    const firstSeenState = findLast(history, (state) =>
      getStateMessages(state)
        .map((item, messageIndex) => getChatMessageIdentifier(item, messageIndex))
        .includes(messageId)
    )

    const checkpointId = firstSeenState?.checkpoint?.checkpoint_id ?? undefined
    let branch = checkpointId ? branchContext.branchByCheckpoint[checkpointId] : undefined

    const optionsShown = branch?.branchOptions?.join(',')
    if (optionsShown) {
      if (shownBranchOptions.has(optionsShown)) {
        branch = undefined
      } else {
        shownBranchOptions.add(optionsShown)
      }
    }

    result[messageId] = {
      messageId,
      checkpointId,
      firstSeenState,
      parentCheckpoint: firstSeenState?.parent_checkpoint,
      branch: branch?.branch,
      branchOptions: branch?.branchOptions
    }

    return result
  }, {})
}
