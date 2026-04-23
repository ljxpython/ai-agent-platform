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
})
