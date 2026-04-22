import type { Interrupt } from '@langchain/langgraph-sdk'

export type HitlDecisionType = 'approve' | 'edit' | 'reject'

export type HitlAction = {
  name: string
  args: Record<string, unknown>
  description?: string
}

export type HitlReviewConfig = {
  action_name: string
  allowed_decisions: HitlDecisionType[]
  args_schema?: Record<string, unknown>
}

export type HitlRequest = {
  action_requests: HitlAction[]
  review_configs: HitlReviewConfig[]
}

export type HitlDecision =
  | { type: 'approve' }
  | { type: 'reject'; message?: string }
  | { type: 'edit'; edited_action: { name: string; args: Record<string, unknown> } }

export function isHitlInterruptSchema(
  value: unknown
): value is Interrupt<HitlRequest> | Interrupt<HitlRequest>[] {
  const candidate = Array.isArray(value) ? value[0] : value
  if (!candidate || typeof candidate !== 'object') {
    return false
  }

  const interrupt = candidate as Interrupt<HitlRequest>
  if (!interrupt.value || typeof interrupt.value !== 'object') {
    return false
  }

  const request = interrupt.value as Partial<HitlRequest>
  if (!Array.isArray(request.action_requests) || request.action_requests.length === 0) {
    return false
  }
  if (!Array.isArray(request.review_configs) || request.review_configs.length === 0) {
    return false
  }

  return (
    request.action_requests.every((item) => {
      return (
        item &&
        typeof item === 'object' &&
        typeof item.name === 'string' &&
        item.args !== null &&
        typeof item.args === 'object'
      )
    }) &&
    request.review_configs.every((item) => {
      return (
        item &&
        typeof item === 'object' &&
        typeof item.action_name === 'string' &&
        Array.isArray(item.allowed_decisions)
      )
    })
  )
}

export function prettifyInterruptLabel(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function stringifyInterruptValue(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (value == null) {
    return ''
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
