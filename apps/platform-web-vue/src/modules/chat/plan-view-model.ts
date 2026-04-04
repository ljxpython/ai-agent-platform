type TodoStatus = 'pending' | 'in_progress' | 'completed'

export type ChatPlanTodo = {
  id: string
  content: string
  status: TodoStatus
}

export type ChatPlanView = {
  initialPlanTodos: ChatPlanTodo[]
  liveTodos: ChatPlanTodo[]
  planTodos: ChatPlanTodo[]
  ephemeralTodos: ChatPlanTodo[]
  activeTask: ChatPlanTodo | null
  totalTasks: number
  completedTasks: number
  allTasksCompleted: boolean
  hasFrozenPlan: boolean
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, unknown>
}

function normalizeTodoStatus(value: unknown): TodoStatus {
  if (value === 'in_progress') {
    return 'in_progress'
  }
  if (value === 'completed') {
    return 'completed'
  }
  return 'pending'
}

function parseJsonValue(value: string): unknown {
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

function normalizeToolArgs(args: unknown): Record<string, unknown> {
  if (args && typeof args === 'object' && !Array.isArray(args)) {
    return args as Record<string, unknown>
  }

  if (typeof args === 'string') {
    const parsed = parseJsonValue(args)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
  }

  return {}
}

function extractToolCalls(message: unknown): Array<Record<string, unknown>> {
  const record = asRecord(message)
  if (Array.isArray(record.tool_calls)) {
    return record.tool_calls.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
  }

  const additionalKwargs = asRecord(record.additional_kwargs)
  if (Array.isArray(additionalKwargs.tool_calls)) {
    return additionalKwargs.tool_calls.filter(
      (item): item is Record<string, unknown> => Boolean(item && typeof item === 'object')
    )
  }

  if (Array.isArray(record.content)) {
    return record.content
      .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
      .filter((item) => item.type === 'tool_use')
  }

  return []
}

function buildTodoIdentityMap(todos: ChatPlanTodo[]) {
  const counters = new Map<string, number>()

  return todos.map((item) => {
    const normalizedContent = item.content.trim().toLowerCase()
    const nextCount = (counters.get(normalizedContent) || 0) + 1
    counters.set(normalizedContent, nextCount)

    return {
      ...item,
      identity: `${normalizedContent}#${nextCount}`
    }
  })
}

function pickMoreAdvancedStatus(left: TodoStatus, right: TodoStatus): TodoStatus {
  const rank = (status: TodoStatus) => {
    if (status === 'completed') {
      return 2
    }
    if (status === 'in_progress') {
      return 1
    }
    return 0
  }

  return rank(left) >= rank(right) ? left : right
}

export function normalizeChatPlanTodoList(rawTodos: unknown, fallbackIdPrefix = 'todo'): ChatPlanTodo[] {
  if (!Array.isArray(rawTodos)) {
    return []
  }

  return rawTodos
    .map((item, index) => {
      const todo = asRecord(item)
      const content =
        typeof todo.content === 'string'
          ? todo.content
          : typeof todo.text === 'string'
            ? todo.text
            : ''

      if (!content.trim()) {
        return null
      }

      return {
        id:
          typeof todo.id === 'string' && todo.id.trim()
            ? todo.id
            : `${fallbackIdPrefix}-${index + 1}`,
        content: content.trim(),
        status: normalizeTodoStatus(todo.status)
      } satisfies ChatPlanTodo
    })
    .filter((item): item is ChatPlanTodo => item !== null)
}

export function extractInitialPlanTodosFromMessages(messages: unknown): ChatPlanTodo[] {
  if (!Array.isArray(messages)) {
    return []
  }

  for (const message of messages) {
    for (const toolCall of extractToolCalls(message)) {
      const name = typeof toolCall.name === 'string' ? toolCall.name.trim() : ''
      if (name !== 'write_todos') {
        continue
      }

      const args = normalizeToolArgs(toolCall.args)
      const todos = normalizeChatPlanTodoList(args.todos, 'todo-plan')
      if (todos.length > 0) {
        return todos
      }
    }
  }

  return []
}

export function buildChatPlanView(values?: Record<string, unknown> | null): ChatPlanView {
  const liveTodos = normalizeChatPlanTodoList(values?.todos, 'todo-live')
  const initialPlanTodos = extractInitialPlanTodosFromMessages(values?.messages)
  const hasFrozenPlan = initialPlanTodos.length > 0

  if (!hasFrozenPlan) {
    const completedTasks = liveTodos.filter((item) => item.status === 'completed').length
    const activeTask =
      liveTodos.find((item) => item.status === 'in_progress') ||
      liveTodos.find((item) => item.status === 'pending') ||
      null

    return {
      initialPlanTodos: [],
      liveTodos,
      planTodos: liveTodos,
      ephemeralTodos: [],
      activeTask,
      totalTasks: liveTodos.length,
      completedTasks,
      allTasksCompleted: liveTodos.length > 0 && completedTasks === liveTodos.length,
      hasFrozenPlan: false
    }
  }

  const planWithIdentity = buildTodoIdentityMap(initialPlanTodos)
  const liveWithIdentity = buildTodoIdentityMap(liveTodos)
  const liveStatusByIdentity = new Map(liveWithIdentity.map((item) => [item.identity, item.status]))
  const planIdentitySet = new Set(planWithIdentity.map((item) => item.identity))

  const planTodos = planWithIdentity.map(({ identity, ...item }) => ({
    ...item,
    status: liveStatusByIdentity.has(identity)
      ? pickMoreAdvancedStatus(item.status, liveStatusByIdentity.get(identity) as TodoStatus)
      : item.status
  }))

  const ephemeralTodos = liveWithIdentity
    .filter((item) => !planIdentitySet.has(item.identity))
    .map(({ identity: _identity, ...item }) => item)

  const completedTasks = planTodos.filter((item) => item.status === 'completed').length
  const activeTask =
    planTodos.find((item) => item.status === 'in_progress') ||
    planTodos.find((item) => item.status === 'pending') ||
    null

  return {
    initialPlanTodos,
    liveTodos,
    planTodos,
    ephemeralTodos,
    activeTask,
    totalTasks: planTodos.length,
    completedTasks,
    allTasksCompleted: planTodos.length > 0 && completedTasks === planTodos.length,
    hasFrozenPlan: true
  }
}
