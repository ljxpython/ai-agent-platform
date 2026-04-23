import type { Message } from '@langchain/langgraph-sdk'
import { ref } from 'vue'
import { buildEditedMessageContent, createChatMessageActions } from './message-actions'

describe('chat message actions', () => {
  it('会为数组内容保留附件并更新文本', () => {
    const message = {
      type: 'human',
      content: [
        { type: 'text', text: 'old' },
        {
          type: 'file',
          mimeType: 'application/pdf',
          name: 'spec.pdf',
          data: 'base64-data'
        }
      ]
    } as unknown as Message

    const nextContent = buildEditedMessageContent(message, 'new text')

    expect(Array.isArray(nextContent)).toBe(true)
    expect(nextContent[0]).toMatchObject({ type: 'text', text: 'new text' })
    expect((nextContent as Array<unknown>).length).toBe(2)
  })

  it('会基于 metadata 判断编辑、重试和分支切换能力', async () => {
    const selectBranch = vi.fn()
    const retryMessage = vi.fn(async () => true)
    const editHumanMessage = vi.fn(async () => true)

    const actions = createChatMessageActions({
      messageMetadataById: ref({
        'human-1': {
          parentCheckpoint: {
            checkpoint_id: 'cp-1',
            thread_id: 'thread-1',
            checkpoint_ns: ''
          },
          branch: 'branch-b',
          branchOptions: ['branch-a', 'branch-b', 'branch-c']
        },
        'ai-1': {
          parentCheckpoint: {
            checkpoint_id: 'cp-2',
            thread_id: 'thread-1',
            checkpoint_ns: ''
          }
        }
      }),
      sending: ref(false),
      hasBlockingInterrupt: ref(false),
      editingMessageId: ref(''),
      editingMessageValue: ref(''),
      selectBranch,
      retryMessage,
      editHumanMessage
    })

    const humanMessage = { id: 'human-1', type: 'human', content: 'hello' } as Message
    const aiMessage = { id: 'ai-1', type: 'ai', content: 'world' } as Message

    expect(actions.canEditMessage(humanMessage, 'human-1')).toBe(true)
    expect(actions.canRetryMessage(aiMessage, 'ai-1')).toBe(true)
    expect(actions.hasBranchSwitcher('human-1')).toBe(true)
    expect(actions.getMessageBranchIndex('human-1')).toBe(1)

    actions.selectPreviousMessageBranch('human-1')
    expect(selectBranch).toHaveBeenCalledWith('branch-a')

    actions.startEditMessage(humanMessage, 'human-1')
    expect(actions.submitEditMessage).toBeTypeOf('function')

    const result = await actions.submitEditMessage(humanMessage, 'human-1')
    expect(result.ok).toBe(true)
    expect(editHumanMessage).toHaveBeenCalled()

    await actions.handleRetryMessage('ai-1')
    expect(retryMessage).toHaveBeenCalledWith('ai-1')
  })
})
