import type { AgentContext } from './types'

export type ContextField = { key: 'model_id' | 'temperature' | 'max_tokens' | 'top_p' | 'execution_mode'; label: string; type: 'string' | 'number' | 'integer'; minimum?: number; maximum?: number }
const fields: ContextField[] = [
  { key: 'model_id', label: '模型', type: 'string' },
  { key: 'temperature', label: 'Temperature', type: 'number', minimum: 0, maximum: 2 },
  { key: 'max_tokens', label: '最大输出 Token', type: 'integer', minimum: 1 },
  { key: 'top_p', label: 'Top P', type: 'number', minimum: 0, maximum: 1 },
  { key: 'execution_mode', label: '执行模式', type: 'string' }
]

export function contextFields(schema: Record<string, unknown>): ContextField[] {
  const sections = Array.isArray(schema.sections) ? schema.sections : []
  const section = sections.find(value => value && typeof value === 'object' && value.key === 'context') as { properties?: Record<string, unknown> } | undefined
  return fields.filter(field => Object.prototype.hasOwnProperty.call(section?.properties ?? {}, field.key))
}

export function parseAgentContext(input: Record<string, unknown>, allowed = fields): AgentContext {
  const result: AgentContext = {}
  for (const field of allowed) {
    const value = input[field.key]
    if (value == null || value === '') continue
    if (field.key === 'model_id') {
      if (typeof value !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)) throw new Error('请选择模型记录')
      result.model_id = value
    } else if (field.key === 'execution_mode') {
      if (typeof value !== 'string' || !['flash', 'standard', 'pro', 'ultra'].includes(value)) {
        throw new Error('执行模式超出允许范围')
      }
      result.execution_mode = value as 'flash' | 'standard' | 'pro' | 'ultra'
    } else {
      const number = typeof value === 'number' ? value : typeof value === 'string' && value.trim() ? Number(value) : NaN
      if (!Number.isFinite(number) || field.type === 'integer' && !Number.isInteger(number) || field.minimum != null && number < field.minimum || field.maximum != null && number > field.maximum) throw new Error(`${field.label} 超出允许范围`)
      result[field.key] = number
    }
  }
  return result
}
