import type { Message } from '@langchain/langgraph-sdk'
import {
  buildChatDisplayMessages,
  getChatMessageBubbleClass,
  getChatMessageRoleLabel,
  getChatMessageWrapClass
} from './message-view-model'

describe('chat message view model', () => {
  it('会过滤掉已经挂到 AI tool_calls 下的 tool message', () => {
    const messages: Message[] = [
      {
        id: 'human-1',
        type: 'human',
        content: 'hello'
      },
      {
        id: 'ai-1',
        type: 'ai',
        content: '',
        tool_calls: [
          {
            id: 'tool-call-1',
            name: 'write_todos',
            args: {}
          }
        ]
      } as Message,
      {
        id: 'tool-1',
        type: 'tool',
        tool_call_id: 'tool-call-1',
        content: 'updated todos'
      } as Message,
      {
        id: 'tool-2',
        type: 'tool',
        tool_call_id: 'tool-call-2',
        content: 'standalone tool output'
      } as Message
    ]

    const displayMessages = buildChatDisplayMessages(messages)

    expect(displayMessages.map((item) => item.id)).toEqual(['human-1', 'ai-1', 'tool-2'])
  })

  it('会兼容 additional_kwargs 里的 legacy tool_calls 关联', () => {
    const messages: Message[] = [
      {
        id: 'ai-legacy',
        type: 'ai',
        content: '',
        additional_kwargs: {
          tool_calls: [
            {
              id: 'legacy-call-1',
              function: {
                name: 'generate_bar_chart',
                arguments: '{}'
              }
            }
          ]
        }
      },
      {
        id: 'tool-legacy',
        type: 'tool',
        tool_call_id: 'legacy-call-1',
        content: 'https://example.com/chart.png'
      } as Message
    ]

    const displayMessages = buildChatDisplayMessages(messages)

    expect(displayMessages.map((item) => item.id)).toEqual(['ai-legacy'])
  })

  it('会为不同消息类型生成稳定的展示元数据', () => {
    const humanMessage = { id: 'human-1', type: 'human', content: 'hello' } as Message
    const toolMessage = { id: 'tool-1', type: 'tool', content: 'done' } as Message
    const aiMessage = { id: 'ai-1', type: 'ai', content: 'world' } as Message

    expect(getChatMessageRoleLabel(humanMessage)).toBe('你')
    expect(getChatMessageRoleLabel(toolMessage)).toBe('Tool')
    expect(getChatMessageRoleLabel(aiMessage)).toBe('Agent')

    expect(getChatMessageWrapClass(humanMessage)).toBe('items-end')
    expect(getChatMessageWrapClass(aiMessage)).toBe('items-start')

    expect(getChatMessageBubbleClass(humanMessage)).toContain('bg-primary-50/80')
    expect(getChatMessageBubbleClass(toolMessage)).toContain('bg-amber-50/80')
    expect(getChatMessageBubbleClass(aiMessage)).toContain('bg-white')
  })
})
