import type { Message } from '@langchain/langgraph-sdk'
import {
  buildChatInspectorToolSections,
  normalizeChatInspectorFiles
} from './inspector-view-model'

describe('chat inspector view model', () => {
  it('会规范化线程文件并保留内容行数', () => {
    expect(
      normalizeChatInspectorFiles({
        files: {
          'docs/spec.md': {
            content: ['# title', 'content']
          },
          'notes.txt': 'hello'
        }
      })
    ).toEqual([
      {
        path: 'docs/spec.md',
        content: '# title\ncontent',
        lineCount: 2
      },
      {
        path: 'notes.txt',
        content: 'hello',
        lineCount: 1
      }
    ])
  })

  it('会把工具调用按 assistant 回合聚合到检查面板区块', () => {
    const messages = [
      {
        id: 'ai-1',
        type: 'ai',
        content: '先搜索一下',
        tool_calls: [
          {
            id: 'tool-1',
            name: 'search',
            args: {
              query: 'langgraph'
            }
          }
        ]
      },
      {
        id: 'tool-result-1',
        type: 'tool',
        tool_call_id: 'tool-1',
        content: '搜索完成'
      },
      {
        id: 'ai-2',
        type: 'ai',
        content: '',
        tool_calls: [
          {
            id: 'task-1',
            name: 'task',
            args: {
              subagent_type: 'researcher',
              task: '继续深挖'
            }
          }
        ]
      }
    ] as Message[]

    const sections = buildChatInspectorToolSections(messages)

    expect(sections).toHaveLength(2)
    expect(sections[0]).toMatchObject({
      id: 'ai-2',
      summary: '1 个子任务',
      pending: true
    })
    expect(sections[1]).toMatchObject({
      id: 'ai-1',
      title: '先搜索一下',
      summary: '1 个工具调用',
      pending: false
    })
  })
})
