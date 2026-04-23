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
})
