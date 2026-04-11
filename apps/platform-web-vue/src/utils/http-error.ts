import { isAxiosError } from 'axios'
import { hasStoredAuthSession } from '@/services/auth/token'

function extractErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const data = error.response?.data
    if (data && typeof data === 'object') {
      for (const key of ['message', 'detail', 'error']) {
        const candidate = (data as Record<string, unknown>)[key]
        if (typeof candidate === 'string' && candidate.trim()) {
          return candidate.trim()
        }
      }
    }

    if (typeof error.message === 'string' && error.message.trim()) {
      return error.message.trim()
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message.trim()
  }

  return ''
}

function extractErrorStatus(error: unknown): number | null {
  if (isAxiosError(error)) {
    return error.response?.status ?? null
  }

  if (error && typeof error === 'object') {
    const status = (error as { status?: unknown; statusCode?: unknown }).status
    if (typeof status === 'number') {
      return status
    }

    const statusCode = (error as { statusCode?: unknown }).statusCode
    if (typeof statusCode === 'number') {
      return statusCode
    }
  }

  return null
}

export function resolvePlatformHttpErrorMessage(
  error: unknown,
  fallbackMessage: string,
  resourceLabel: string
): string {
  const status = extractErrorStatus(error)
  const upstreamMessage = extractErrorMessage(error)

  if (!hasStoredAuthSession()) {
    return '当前登录态缺少控制面会话。请重新登录后再试。'
  }

  if (status === 401) {
    return '当前登录态已失效，请重新登录后再试。'
  }

  if (status === 403) {
    return `当前账号没有访问${resourceLabel}的权限。`
  }

  if (status === 404) {
    return `${resourceLabel}接口不存在，先确认前端环境是否已接到 platform-api-v2。`
  }

  if (typeof status === 'number' && status >= 500) {
    return upstreamMessage || `${resourceLabel}后端处理失败，请查看 platform-api-v2 日志。`
  }

  return upstreamMessage || fallbackMessage
}
