import { buildChatPlanView, extractInitialPlanTodosFromMessages } from './plan-view-model'

describe('chat plan view model', () => {
  it('优先从第一次 write_todos 工具调用提取主计划，并把后续新增任务归到临时执行项', () => {
    const values = {
      messages: [
        {
          id: 'human-1',
          type: 'human',
          content: '帮我完成一个复杂任务'
        },
        {
          id: 'ai-1',
          type: 'ai',
          content: '',
          tool_calls: [
            {
              id: 'tool-1',
              name: 'write_todos',
              args: {
                todos: [
                  { content: '收集上下文', status: 'in_progress' },
                  { content: '输出方案', status: 'pending' }
                ]
              }
            }
          ]
        },
        {
          id: 'ai-2',
          type: 'ai',
          content: '',
          tool_calls: [
            {
              id: 'tool-2',
              name: 'write_todos',
              args: {
                todos: [
                  { content: '补充排查', status: 'in_progress' },
                  { content: '输出方案', status: 'pending' }
                ]
              }
            }
          ]
        }
      ],
      todos: [
        { content: '收集上下文', status: 'completed' },
        { content: '输出方案', status: 'in_progress' },
        { content: '补充排查', status: 'pending' }
      ]
    }

    const planView = buildChatPlanView(values)

    expect(planView.hasFrozenPlan).toBe(true)
    expect(planView.initialPlanTodos.map((item) => item.content)).toEqual(['收集上下文', '输出方案'])
    expect(planView.planTodos).toMatchObject([
      { content: '收集上下文', status: 'completed' },
      { content: '输出方案', status: 'in_progress' }
    ])
    expect(planView.ephemeralTodos).toMatchObject([{ content: '补充排查', status: 'pending' }])
    expect(planView.activeTask?.content).toBe('输出方案')
  })

  it('支持从字符串参数里的 write_todos 结果提取首版计划', () => {
    const messages = [
      {
        id: 'ai-1',
        type: 'ai',
        tool_calls: [
          {
            id: 'tool-1',
            name: 'write_todos',
            args: JSON.stringify({
              todos: [{ content: '建立计划', status: 'in_progress' }]
            })
          }
        ]
      }
    ]

    expect(extractInitialPlanTodosFromMessages(messages)).toMatchObject([
      { content: '建立计划', status: 'in_progress' }
    ])
  })

  it('没有 write_todos 时退回实时 todos，不冻结主计划', () => {
    const planView = buildChatPlanView({
      messages: [],
      todos: [
        { content: '直接执行', status: 'in_progress' },
        { content: '整理结果', status: 'pending' }
      ]
    })

    expect(planView.hasFrozenPlan).toBe(false)
    expect(planView.planTodos).toMatchObject([
      { content: '直接执行', status: 'in_progress' },
      { content: '整理结果', status: 'pending' }
    ])
    expect(planView.ephemeralTodos).toEqual([])
  })
})
