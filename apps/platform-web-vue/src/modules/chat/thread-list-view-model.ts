export type ChatThreadStatusFilter = 'all' | 'idle' | 'busy' | 'interrupted' | 'error'

export type ChatThreadSummaryItem = {
  id: string
  title: string
  preview: string
  updatedAt: string
  time: string
  status: string
}

export type ChatThreadSummaryGroup = {
  key: string
  label: string
  items: ChatThreadSummaryItem[]
}

const THREAD_GROUP_LABELS: Record<string, string> = {
  interrupted: '待处理',
  today: '今天',
  yesterday: '昨天',
  week: '最近一周',
  older: '更早'
}

function calcDayDiff(rawValue: string, now = new Date()) {
  const value = rawValue.trim()
  if (!value || value === '--') {
    return Number.POSITIVE_INFINITY
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return Number.POSITIVE_INFINITY
  }

  const nowAtMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const dateAtMidnight = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  return Math.floor((nowAtMidnight.getTime() - dateAtMidnight.getTime()) / (1000 * 60 * 60 * 24))
}

export function getChatThreadGroupKey(item: Pick<ChatThreadSummaryItem, 'status' | 'updatedAt'>, now = new Date()) {
  if (item.status === 'interrupted') {
    return 'interrupted'
  }

  const dayDiff = calcDayDiff(item.updatedAt, now)
  if (dayDiff <= 0) {
    return 'today'
  }
  if (dayDiff === 1) {
    return 'yesterday'
  }
  if (dayDiff < 7) {
    return 'week'
  }
  return 'older'
}

export function buildChatThreadListView(options: {
  items: ChatThreadSummaryItem[]
  query: string
  statusFilter: ChatThreadStatusFilter
  now?: Date
}) {
  const normalizedQuery = options.query.trim().toLowerCase()
  const normalizedStatus = options.statusFilter
  const now = options.now || new Date()

  const filteredItems = options.items.filter((item) => {
    const matchesStatus = normalizedStatus === 'all' ? true : item.status === normalizedStatus
    const matchesQuery = [item.title, item.preview, item.time, item.status]
      .join(' ')
      .toLowerCase()
      .includes(normalizedQuery)

    return matchesStatus && matchesQuery
  })

  const groups: ChatThreadSummaryGroup[] = []
  const order = ['interrupted', 'today', 'yesterday', 'week', 'older']

  for (const key of order) {
    const items = filteredItems.filter((item) => getChatThreadGroupKey(item, now) === key)
    if (items.length > 0) {
      groups.push({
        key,
        label: THREAD_GROUP_LABELS[key] || key,
        items
      })
    }
  }

  return {
    filteredItems,
    groups
  }
}
