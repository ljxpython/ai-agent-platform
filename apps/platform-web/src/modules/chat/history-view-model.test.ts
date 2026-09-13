import { buildChatHistoryView } from './history-view-model'

describe('chat history view model', () => {
  it('会提取 checkpoint 关系、分叉数量和当前快照状态', () => {
    const view = buildChatHistoryView({
      items: [
        {
          checkpoint_id: 'cp-3',
          parent_checkpoint_id: 'cp-2',
          values: {
            messages: [{ type: 'human', content: '第三步' }]
          },
          metadata: {
            step: 3,
            source: 'loop'
          },
          tasks: [{ id: 'task-1' }]
        },
        {
          checkpoint_id: 'cp-2b',
          parent_checkpoint_id: 'cp-1',
          values: {
            messages: [{ type: 'human', content: '分支 B' }]
          },
          metadata: {
            step: 2
          }
        },
        {
          checkpoint_id: 'cp-2',
          parent_checkpoint_id: 'cp-1',
          values: {
            messages: [{ type: 'human', content: '分支 A' }]
          },
          metadata: {
            step: 2
          }
        }
      ],
      selectedBranch: 'cp-1>cp-2',
      isViewingBranch: true
    })

    expect(view.branchGroupCount).toBe(1)
    expect(view.activeCheckpointId).toBe('cp-2')
    expect(view.items[1]).toMatchObject({
      id: 'cp-2b',
      siblingCount: 2,
      isCurrent: false,
      isInSelectedPath: false
    })
    expect(view.items[2]).toMatchObject({
      id: 'cp-2',
      siblingCount: 2,
      isCurrent: true,
      isInSelectedPath: true
    })
  })

  it('不查看分支时默认把第一条 checkpoint 当成当前快照', () => {
    const view = buildChatHistoryView({
      items: [
        {
          checkpoint_id: 'latest',
          values: {
            messages: [{ type: 'human', content: '最新内容' }]
          }
        },
        {
          checkpoint_id: 'old',
          values: {
            messages: [{ type: 'human', content: '旧内容' }]
          }
        }
      ],
      selectedBranch: '',
      isViewingBranch: false
    })

    expect(view.activeCheckpointId).toBe('latest')
    expect(view.items[0]?.isCurrent).toBe(true)
    expect(view.items[1]?.isCurrent).toBe(false)
  })

  it('能够基于当前 step 的最新动作精准生成预览标题', () => {
    const view = buildChatHistoryView({
      items: [
        // 1. 等待审批 step
        {
          checkpoint_id: 'cp-interrupt',
          interrupts: [{ value: 'approval required' }],
          values: {
            messages: [{ type: 'human', content: '初始提问' }]
          }
        },
        // 2. 工具调用 step
        {
          checkpoint_id: 'cp-tool-call',
          values: {
            messages: [
              { type: 'human', content: '初始提问' },
              {
                type: 'ai',
                content: '',
                tool_calls: [
                  {
                    name: 'write_file',
                    args: { file_path: 'report.py' }
                  }
                ]
              }
            ]
          }
        },
        // 3. 工具执行完成 step
        {
          checkpoint_id: 'cp-tool-result',
          values: {
            messages: [
              { type: 'human', content: '初始提问' },
              { type: 'tool', name: 'write_file', content: '成功写入 45 行代码' }
            ]
          }
        },
        // 4. Agent 回复文本 step
        {
          checkpoint_id: 'cp-ai-reply',
          values: {
            messages: [
              { type: 'human', content: '初始提问' },
              { type: 'ai', content: '已完成缺陷修复与代码验证' }
            ]
          }
        },
        // 5. 纯内部中间件 step (例如 ModelCallLimitMiddleware 流转)
        {
          checkpoint_id: 'cp-middleware-internal',
          tasks: [{ name: 'ModelCallLimitMiddleware.after_model' }],
          values: {
            messages: [
              { type: 'human', content: '初始提问' },
              { type: 'ai', content: '已完成缺陷修复与代码验证' }
            ]
          }
        },
        // 6. 空 tasks 且无新消息的纯系统 step (对应用户实际遇到的中间步骤)
        {
          checkpoint_id: 'cp-system-internal-frame',
          parent_checkpoint_id: 'cp-ai-reply',
          metadata: { step: 181 },
          values: {
            messages: [
              { type: 'human', content: '初始提问' },
              { type: 'ai', content: '已完成缺陷修复与代码验证' }
            ]
          }
        }
      ],
      selectedBranch: '',
      isViewingBranch: false
    })

    expect(view.items[0]?.preview).toBe('🛑 等待审批: 需要人工确认操作')
    expect(view.items[0]?.isKeyMilestone).toBe(true)
    expect(view.items[1]?.preview).toContain('🔧 调用工具: write_file (report.py)')
    expect(view.items[1]?.isKeyMilestone).toBe(true)
    expect(view.items[2]?.preview).toContain('📥 工具完成 [write_file]: 成功写入 45 行代码')
    expect(view.items[2]?.isKeyMilestone).toBe(true)
    expect(view.items[3]?.preview).toContain('🤖 Agent: 已完成缺陷修复与代码验证')
    expect(view.items[3]?.isKeyMilestone).toBe(true)
    expect(view.items[4]?.preview).toBe('⚙️ 系统检查点 [ModelCallLimitMiddleware]')
    expect(view.items[4]?.isKeyMilestone).toBe(false)
    expect(view.items[5]?.isKeyMilestone).toBe(false)
    expect(view.keyMilestoneCount).toBe(4)
    expect(view.totalEntries).toBe(6)
  })

  it('能够精准识别 checkpoint 的角色归属（用户提问/Agent回复/工具/系统）并准确统计', () => {
    const view = buildChatHistoryView({
      items: [
        {
          checkpoint_id: 'cp-user',
          metadata: { step: 1 },
          values: {
            messages: [{ type: 'human', content: '用户说第一句话' }]
          }
        },
        {
          checkpoint_id: 'cp-tool',
          metadata: { step: 2 },
          values: {
            messages: [
              { type: 'human', content: '用户说第一句话' },
              { type: 'ai', tool_calls: [{ name: 'read_file' }] }
            ]
          }
        },
        {
          checkpoint_id: 'cp-agent',
          metadata: { step: 3 },
          values: {
            messages: [
              { type: 'human', content: '用户说第一句话' },
              { type: 'ai', content: '这是最终结论' }
            ]
          }
        },
        {
          checkpoint_id: 'cp-sys',
          metadata: { step: 4 },
          tasks: [{ name: 'PregelMiddleware' }],
          values: { messages: [] }
        }
      ],
      selectedBranch: '',
      isViewingBranch: false
    })

    expect(view.items[0]?.role).toBe('user')
    expect(view.items[0]?.roleLabel).toBe('用户提问')
    expect(view.items[1]?.role).toBe('tool')
    expect(view.items[1]?.roleLabel).toBe('工具调用')
    expect(view.items[2]?.role).toBe('agent')
    expect(view.items[2]?.roleLabel).toBe('Agent 回复')
    expect(view.items[3]?.role).toBe('system')
    expect(view.items[3]?.roleLabel).toBe('系统检查点')

    expect(view.userCount).toBe(1)
    expect(view.toolCount).toBe(1)
    expect(view.agentCount).toBe(1)
    expect(view.systemCount).toBe(1)
  })
})


