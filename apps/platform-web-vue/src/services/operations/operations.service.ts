import { getPlatformHttpClient } from '@/services/platform/control-plane'
import type {
  ManagementDownload,
  ManagementOperation,
  ManagementOperationPage,
  OperationStatus
} from '@/types/management'

export type ListOperationsOptions = {
  projectId?: string
  kind?: string
  status?: OperationStatus
  requestedBy?: string
  limit?: number
  offset?: number
}

export type SubmitOperationPayload = {
  kind: string
  project_id?: string
  idempotency_key?: string
  input_payload?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export async function listOperations(options?: ListOperationsOptions): Promise<ManagementOperationPage> {
  const client = getPlatformHttpClient('operations')
  const response = await client.get('/api/operations', {
    params: {
      project_id: options?.projectId?.trim() || undefined,
      kind: options?.kind?.trim() || undefined,
      status: options?.status || undefined,
      requested_by: options?.requestedBy?.trim() || undefined,
      limit: options?.limit ?? 50,
      offset: options?.offset ?? 0
    }
  })
  return response.data as ManagementOperationPage
}

export async function getOperationDetail(operationId: string): Promise<ManagementOperation> {
  const client = getPlatformHttpClient('operations')
  const response = await client.get(`/api/operations/${encodeURIComponent(operationId)}`)
  return response.data as ManagementOperation
}

export async function submitOperation(payload: SubmitOperationPayload): Promise<ManagementOperation> {
  const client = getPlatformHttpClient('operations')
  const response = await client.post('/api/operations', payload)
  return response.data as ManagementOperation
}

export async function cancelOperation(operationId: string): Promise<ManagementOperation> {
  const client = getPlatformHttpClient('operations')
  const response = await client.post(`/api/operations/${encodeURIComponent(operationId)}/cancel`)
  return response.data as ManagementOperation
}

function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) {
    return null
  }
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const plainMatch = header.match(/filename="?([^";]+)"?/i)
  return plainMatch?.[1] ?? null
}

export async function downloadOperationArtifact(operationId: string): Promise<ManagementDownload> {
  const client = getPlatformHttpClient('operations')
  const response = await client.get(`/api/operations/${encodeURIComponent(operationId)}/artifact`, {
    responseType: 'blob'
  })
  return {
    blob: response.data as Blob,
    filename: parseContentDispositionFilename(String(response.headers['content-disposition'] || '')),
    contentType: String(response.headers['content-type'] || '')
  }
}

export function getOperationFailureMessage(operation: ManagementOperation): string {
  const errorMessage = operation.error_payload?.message
  if (typeof errorMessage === 'string' && errorMessage.trim()) {
    return errorMessage.trim()
  }
  if (operation.status === 'cancelled') {
    return '操作已取消'
  }
  return `操作 ${operation.kind} 执行失败`
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function isTerminalStatus(status: OperationStatus) {
  return status === 'succeeded' || status === 'failed' || status === 'cancelled'
}

export async function waitForOperationTerminalState(
  operationId: string,
  options?: {
    pollMs?: number
    timeoutMs?: number
  }
): Promise<ManagementOperation> {
  const pollMs = options?.pollMs ?? 1000
  const timeoutMs = options?.timeoutMs ?? 60000
  const startedAt = Date.now()

  while (true) {
    const current = await getOperationDetail(operationId)
    if (isTerminalStatus(current.status)) {
      return current
    }

    if (Date.now() - startedAt >= timeoutMs) {
      throw new Error(`操作 ${operationId} 等待超时，请稍后到 operations 中心查看状态。`)
    }

    await sleep(pollMs)
  }
}
