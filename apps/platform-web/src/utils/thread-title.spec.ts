import { describe, expect, it } from 'vitest'
import { deriveMessagePreview, deriveThreadTitle, extractLastMessagePreview } from './thread-title'

describe('deriveThreadTitle', () => {
  it('cleans default quick prompt template into short category title', () => {
    const raw = '设计功能方案：根据业务需求给出优雅的架构与接口设计'
    expect(deriveThreadTitle(raw)).toBe('设计功能方案')
  })

  it('extracts custom requirements appended after quick prompt template', () => {
    const raw = '设计功能方案：实现电商分布式订单结算系统与库存扣减'
    expect(deriveThreadTitle(raw)).toBe('实现电商分布式订单结算系统与库存扣减')
  })

  it('extracts first line for normal plain text prompt', () => {
    const raw = '帮我排查一下这个 Docker 镜像启动报错\n日志如下：xxxx'
    expect(deriveThreadTitle(raw)).toBe('帮我排查一下这个 Docker 镜像启动报错')
  })

  it('handles rich text array block', () => {
    const raw = [{ type: 'text', text: '分析当前项目：全面梳理代码库结构与模块依赖关系' }]
    expect(deriveThreadTitle(raw)).toBe('分析当前项目')
  })

  it('falls back to default title on empty input', () => {
    expect(deriveThreadTitle('')).toBe('新对话')
    expect(deriveThreadTitle(null)).toBe('新对话')
  })
})

describe('deriveMessagePreview', () => {
  it('truncates preview to 60 characters with squashed whitespaces', () => {
    const text = '这是很长的一句话   里面有很多空格\n换行符等等。'
    expect(deriveMessagePreview(text)).toBe('这是很长的一句话 里面有很多空格 换行符等等。')
  })
})

describe('extractLastMessagePreview', () => {
  it('finds the latest message with valid content and formats preview', () => {
    const messages = [
      { id: '1', content: '第一条消息' },
      { id: '2', content: '' },
      { id: '3', content: '最后一条有效的助手回答内容' }
    ]
    expect(extractLastMessagePreview(messages)).toBe('最后一条有效的助手回答内容')
  })

  it('returns empty string on invalid or empty messages array', () => {
    expect(extractLastMessagePreview([])).toBe('')
    expect(extractLastMessagePreview(null as any)).toBe('')
  })
})
