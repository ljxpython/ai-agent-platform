import { describe, expect, it } from 'vitest'
import type { Message } from '@langchain/langgraph-sdk'
import { extractToolCallsFromMessage } from './tool-call-utils'
import { buildChatToolResultView } from './tool-result-renderers'

describe('chat tool call helpers', () => {
  it('extracts legacy additional_kwargs tool calls', () => {
    const message = {
      id: 'ai-1',
      type: 'ai',
      content: '',
      additional_kwargs: {
        tool_calls: [
          {
            id: 'call-1',
            function: {
              name: 'generate_bar_chart',
              arguments: JSON.stringify({
                title: 'Monthly Revenue'
              })
            }
          }
        ]
      }
    } satisfies Message

    expect(extractToolCallsFromMessage(message)).toEqual([
      {
        id: 'call-1',
        name: 'generate_bar_chart',
        args: {
          title: 'Monthly Revenue'
        }
      }
    ])
  })

  it('builds a chart renderer view from chart tool result urls', () => {
    const toolMessage = {
      type: 'tool',
      tool_call_id: 'call-1',
      content: 'https://example.com/chart-output.png'
    } satisfies Message

    expect(buildChatToolResultView('generate_bar_chart', toolMessage)).toEqual({
      mode: 'chart-image',
      text: 'https://example.com/chart-output.png',
      imageUrl: 'https://example.com/chart-output.png'
    })
  })
})
