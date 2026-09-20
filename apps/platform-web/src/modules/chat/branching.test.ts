import type { Message, ThreadState } from '@langchain/langgraph-sdk'
import { buildChatMessageMetadata, getChatBranchContext } from './branching'

function createState(
  checkpointId: string,
  parentCheckpointId: string | null,
  messages: Message[]
): ThreadState<Record<string, unknown>> {
  return {
    values: { messages },
    next: [],
    tasks: [],
    metadata: {},
    created_at: '2026-04-04T00:00:00.000Z',
    checkpoint: {
      checkpoint_id: checkpointId,
      thread_id: 'thread-1',
      checkpoint_ns: ''
    },
    parent_checkpoint: parentCheckpointId
      ? {
          checkpoint_id: parentCheckpointId,
          thread_id: 'thread-1',
          checkpoint_ns: ''
        }
      : null
  } as ThreadState<Record<string, unknown>>
}

describe('chat branching', () => {
  const humanMessage: Message = {
    id: 'human-1',
    type: 'human',
    content: '请只回答一个字：甲'
  }
  const originalAiMessage: Message = {
    id: 'ai-original',
    type: 'ai',
    content: '甲'
  }
  const retriedAiMessage: Message = {
    id: 'ai-retry',
    type: 'ai',
    content: '甲'
  }

  const history = [
    createState('checkpoint-ai-retry', 'checkpoint-human', [humanMessage, retriedAiMessage]),
    createState('checkpoint-ai-original', 'checkpoint-human', [humanMessage, originalAiMessage]),
    createState('checkpoint-human', 'checkpoint-root', [humanMessage]),
    createState('checkpoint-root', null, [])
  ]

  it('默认分支会落到最新的 retry 路径，并把 branch 选项挂在共享消息上', () => {
    const branchContext = getChatBranchContext('', history)

    expect(branchContext.threadHead?.checkpoint?.checkpoint_id).toBe('checkpoint-ai-retry')

    const metadata = buildChatMessageMetadata(
      [humanMessage, retriedAiMessage],
      history,
      branchContext
    )

    expect(metadata['human-1']).toMatchObject({
      branch: 'checkpoint-ai-retry',
      branchOptions: ['checkpoint-ai-original', 'checkpoint-ai-retry']
    })
    expect(metadata['ai-retry']?.branchOptions).toBeUndefined()
  })

  it('显式切换到旧分支后，会返回对应的历史 head', () => {
    const latestBranch = getChatBranchContext('', history)
    const latestMetadata = buildChatMessageMetadata(
      [humanMessage, retriedAiMessage],
      history,
      latestBranch
    )
    const previousBranch = latestMetadata['human-1']?.branchOptions?.[0]

    expect(previousBranch).toBe('checkpoint-ai-original')

    const previousBranchContext = getChatBranchContext(previousBranch || '', history)
    const previousMetadata = buildChatMessageMetadata(
      [humanMessage, originalAiMessage],
      history,
      previousBranchContext
    )

    expect(previousBranchContext.threadHead?.checkpoint?.checkpoint_id).toBe('checkpoint-ai-original')
    expect(previousMetadata['human-1']).toMatchObject({
      branch: 'checkpoint-ai-original',
      branchOptions: ['checkpoint-ai-original', 'checkpoint-ai-retry']
    })
  })

  it('无新增消息的路由节点分叉仍挂到最后一条可见消息', () => {
    const routed = [
      createState('retry', 'route', [humanMessage, retriedAiMessage]),
      createState('original', 'route', [humanMessage, originalAiMessage]),
      createState('route', 'human', [humanMessage]),
      createState('human', 'root', [humanMessage]),
      createState('root', null, [])
    ]
    const context = getChatBranchContext('', routed)
    expect(buildChatMessageMetadata([humanMessage, retriedAiMessage], routed, context)['human-1']?.branchOptions).toEqual(['original', 'retry'])
    const metadata = buildChatMessageMetadata([humanMessage, retriedAiMessage], routed, context)
    expect(metadata['human-1']?.parentCheckpoint?.checkpoint_id).toBe('root')
    expect(metadata['human-1']?.firstSeenState?.checkpoint.checkpoint_id).toBe('human')
  })

  it('多轮对话中定位历史消息的 checkpointId，且绝对不包含后续轮次的消息', () => {
    const h1: Message = { id: 'h1', type: 'human', content: 'Turn 1 User' }
    const a1: Message = { id: 'a1', type: 'ai', content: 'Turn 1 AI' }
    const h2: Message = { id: 'h2', type: 'human', content: 'Turn 2 User' }
    const a2: Message = { id: 'a2', type: 'ai', content: 'Turn 2 AI' }

    // 历史倒序：最新在 0
    const fullHistory = [
      createState('cp-4', 'cp-3', [h1, a1, h2, a2]),
      createState('cp-3', 'cp-2', [h1, a1, h2]),
      createState('cp-2', 'cp-1', [h1, a1]),
      createState('cp-1', null, [h1]),
    ]
    const context = getChatBranchContext('', fullHistory)
    const meta = buildChatMessageMetadata([h1, a1, h2, a2], fullHistory, context)

    // a1 是第 1 轮结束时的 AI 消息，定位出来的 checkpoint 必须是 cp-2，绝不能是包含 h2/a2 的 cp-3 或 cp-4
    expect(meta['a1']?.checkpointId).toBe('cp-2')
    // h2 是第 2 轮的用户消息，对应 cp-3
    expect(meta['h2']?.checkpointId).toBe('cp-3')
    // a2 是当前最新轮次的 AI 消息，对应 cp-4
    expect(meta['a2']?.checkpointId).toBe('cp-4')

    // 场景 2：当 history 被第二轮的中间步骤截断，第一轮的 cp-2 不在历史中时
    const truncatedHistory = [
      createState('cp-4', 'cp-3', [h1, a1, h2, a2]),
      createState('cp-3', 'cp-2', [h1, a1, h2]),
    ]
    const truncatedContext = getChatBranchContext('', truncatedHistory)
    const truncatedMeta = buildChatMessageMetadata([h1, a1, h2, a2], truncatedHistory, truncatedContext)
    // 此时 truncatedHistory 中的所有 checkpoint 都包含了后续的 h2，因此 a1 的 checkpointId 必须安全返回 undefined，不能误判为第二轮的 checkpoint！
    expect(truncatedMeta['a1']?.checkpointId).toBeUndefined()
  })
})

