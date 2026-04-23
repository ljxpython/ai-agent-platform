import { buildChatThreadListView, getChatThreadGroupKey } from './thread-list-view-model'

describe('chat thread list view model', () => {
  const now = new Date('2026-04-04T12:00:00.000Z')

  const items = [
    {
      id: 'thread-interrupted',
      title: '需要人工处理',
      preview: '中断',
      updatedAt: '2026-04-04T11:00:00.000Z',
      time: '2026/04/04 19:00:00',
      status: 'interrupted'
    },
    {
      id: 'thread-today',
      title: '今天的对话',
      preview: '最新消息',
      updatedAt: '2026-04-04T08:00:00.000Z',
      time: '2026/04/04 16:00:00',
      status: 'idle'
    },
    {
      id: 'thread-yesterday',
      title: '昨天的对话',
      preview: '旧消息',
      updatedAt: '2026-04-03T08:00:00.000Z',
      time: '2026/04/03 16:00:00',
      status: 'busy'
    }
  ]

  it('会按中断、今天、昨天等顺序分组', () => {
    const view = buildChatThreadListView({
      items,
      query: '',
      statusFilter: 'all',
      now
    })

    expect(view.groups.map((group) => group.key)).toEqual(['interrupted', 'today', 'yesterday'])
    expect(view.groups[0]?.items[0]?.id).toBe('thread-interrupted')
  })

  it('会按查询词和状态筛选线程', () => {
    const byQuery = buildChatThreadListView({
      items,
      query: '昨天',
      statusFilter: 'all',
      now
    })
    expect(byQuery.filteredItems.map((item) => item.id)).toEqual(['thread-yesterday'])

    const byStatus = buildChatThreadListView({
      items,
      query: '',
      statusFilter: 'busy',
      now
    })
    expect(byStatus.filteredItems.map((item) => item.id)).toEqual(['thread-yesterday'])
  })

  it('会正确判断线程分组 key', () => {
    expect(getChatThreadGroupKey(items[0], now)).toBe('interrupted')
    expect(getChatThreadGroupKey(items[1], now)).toBe('today')
    expect(getChatThreadGroupKey(items[2], now)).toBe('yesterday')
  })
})
