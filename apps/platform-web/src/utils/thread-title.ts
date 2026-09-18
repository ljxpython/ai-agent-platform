const DEFAULT_QUICK_PROMPT_DESCRIPTIONS = new Set([
  '根据业务需求给出优雅的架构与接口设计',
  '全面梳理代码库结构与模块依赖关系',
  '排查潜在异常、安全漏洞与代码坏味道',
  '定位错误调用栈并提供直接可用的修复补丁'
])

export function deriveThreadTitle(content: unknown): string {
  if (typeof content !== 'string') {
    if (Array.isArray(content)) {
      const textBlock = content.find(
        (b) => b && typeof b === 'object' && b.type === 'text' && typeof b.text === 'string'
      )
      if (textBlock) return deriveThreadTitle(textBlock.text)
    }
    return '新对话'
  }

  const clean = content.trim()
  if (!clean) return '新对话'

  // 匹配常见的推荐模板提示词前缀，例如 "设计功能方案：xxx"
  const promptMatch = clean.match(
    /^(?:设计功能方案|分析当前项目|审查代码规范|调试系统问题)[：:]\s*(.*)$/s
  )
  if (promptMatch) {
    const detail = promptMatch[1]?.trim()
    if (!detail || DEFAULT_QUICK_PROMPT_DESCRIPTIONS.has(detail)) {
      return clean.split(/[：:]/)[0]?.trim() || '新对话'
    }
    // 用户有追加具体的业务内容，优先使用具体内容
    const firstLine = detail.split('\n')[0]?.trim() || detail
    return firstLine.slice(0, 40)
  }

  const firstLine = clean.split('\n')[0]?.trim() || clean
  return firstLine.slice(0, 40)
}

export function deriveMessagePreview(content: unknown): string {
  if (typeof content !== 'string') {
    if (Array.isArray(content)) {
      const textBlock = content.find(
        (b) => b && typeof b === 'object' && b.type === 'text' && typeof b.text === 'string'
      )
      if (textBlock) return deriveMessagePreview(textBlock.text)
    }
    return ''
  }
  const clean = content.replace(/\s+/g, ' ').trim()
  return clean.slice(0, 60)
}

export function extractLastMessagePreview(messages: unknown[]): string {
  if (!Array.isArray(messages) || !messages.length) return ''
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    if (!msg || typeof msg !== 'object') continue
    const content = (msg as { content?: unknown }).content
    const preview = deriveMessagePreview(content)
    if (preview) return preview
  }
  return ''
}
