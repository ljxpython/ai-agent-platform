import { isAxiosError } from 'axios'
import { hasStoredAuthSession } from '@/services/auth/token'

export interface PlatformValidationDetail {
  loc?: Array<string | number>
  message?: string
  type?: string
}

function extractEnvelopeFields(raw: unknown): {
  message?: string
  code?: string
  requestId?: string
  details?: PlatformValidationDetail[]
} {
  if (!raw || typeof raw !== 'object') return {}
  const record = raw as Record<string, unknown>
  const nestedError =
    record.error && typeof record.error === 'object'
      ? (record.error as Record<string, unknown>)
      : undefined
  const metaObj =
    record.meta && typeof record.meta === 'object'
      ? (record.meta as Record<string, unknown>)
      : undefined

  let message: string | undefined
  if (typeof nestedError?.message === 'string' && nestedError.message.trim()) {
    message = nestedError.message.trim()
  } else {
    for (const key of ['message', 'detail', 'error']) {
      const candidate = record[key]
      if (typeof candidate === 'string' && candidate.trim()) {
        message = candidate.trim()
        break
      }
    }
  }

  const code =
    typeof nestedError?.code === 'string'
      ? nestedError.code
      : typeof record.code === 'string'
        ? record.code
        : undefined
  const requestId =
    typeof record.request_id === 'string'
      ? record.request_id
      : typeof metaObj?.request_id === 'string'
        ? metaObj.request_id
        : undefined

  const rawDetails = Array.isArray(nestedError?.details)
    ? nestedError.details
    : Array.isArray(record.details)
      ? record.details
      : undefined
  const details = rawDetails
    ? (rawDetails.filter(
        (item): item is PlatformValidationDetail =>
          Boolean(item && typeof item === 'object')
      ) as PlatformValidationDetail[])
    : undefined

  return { message, code, requestId, details }
}

export function extractPlatformHttpError(
  err: unknown,
  fallbackMessage = '请求失败'
): {
  status: number | null
  code?: string
  message: string
  requestId?: string
  details?: PlatformValidationDetail[]
} {
  const status = extractErrorStatus(err)
  if (err && typeof err === 'object') {
    const maybeAxios = err as {
      response?: { data?: unknown }
      code?: unknown
      message?: unknown
    }
    const { message, code, requestId, details } = extractEnvelopeFields(
      maybeAxios.response?.data ?? err
    )
    const resolvedCode =
      code || (typeof maybeAxios.code === 'string' ? maybeAxios.code : undefined)
    const resolvedMessage =
      message ||
      (typeof maybeAxios.message === 'string' && maybeAxios.message.trim()
        ? maybeAxios.message.trim()
        : fallbackMessage)
    return {
      status,
      code: resolvedCode,
      message: resolvedMessage,
      requestId,
      details
    }
  }
  return {
    status,
    message:
      err instanceof Error && err.message.trim()
        ? err.message.trim()
        : fallbackMessage
  }
}

function extractErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    const { message } = extractEnvelopeFields(error.response?.data)
    if (message) return message

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
    const responseStatus = (error as { response?: { status?: unknown } }).response?.status
    if (typeof responseStatus === 'number') {
      return responseStatus
    }

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

export interface PlatformUnwrappedHttpError extends Error {
  code?: string
  requestId?: string
  status?: number
  details?: PlatformValidationDetail[]
}

export async function unwrapPlatformHttpError(
  err: unknown,
  fallbackMessage = '请求失败'
): Promise<PlatformUnwrappedHttpError> {
  if (err && typeof err === 'object') {
    const maybeAxios = err as {
      response?: {
        data?: unknown
        status?: number
      }
      message?: string
    }
    const response = maybeAxios.response
    if (response) {
      const status = response.status
      let payload: unknown = response.data
      if (payload instanceof Blob) {
        try {
          payload = JSON.parse(await payload.text())
        } catch {
          payload = null
        }
      }
      if (payload && typeof payload === 'object') {
        const { message, code, requestId, details } = extractEnvelopeFields(payload)
        const customErr = new Error(
          message || maybeAxios.message || fallbackMessage
        ) as PlatformUnwrappedHttpError
        customErr.code = code
        customErr.requestId = requestId
        customErr.status = status
        customErr.details = details
        return customErr
      }
    }
  }
  return (err instanceof Error ? err : new Error(String(err))) as PlatformUnwrappedHttpError
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
    return `${resourceLabel}接口不存在，先确认前端环境是否已接到 platform-api。`
  }

  if (typeof status === 'number' && status >= 500) {
    return upstreamMessage || `${resourceLabel}后端处理失败，请查看 platform-api 日志。`
  }

  return upstreamMessage || fallbackMessage
}
