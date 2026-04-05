import { httpClient } from '@/services/http/client'
import type { ManagementThread, ThreadHistoryEntry } from '@/types/management'
import { getThreadListSearchText } from '@/utils/threads'

type ThreadListResponse = {
  items: ManagementThread[]
  total: number
  limit: number
  offset: number
}

type CountResponse = {
  count?: number
  total?: number
}

export type ListThreadsOptions = {
  limit?: number
  offset?: number
  query?: string
  threadId?: string
  assistantId?: string
  graphId?: string
  status?: string
}

export async function listThreadsPage(
  projectId: string,
  options?: ListThreadsOptions
): Promise<ThreadListResponse> {
  const limit = options?.limit ?? 20
  const offset = options?.offset ?? 0

  if (!projectId) {
    return { items: [], total: 0, limit, offset }
  }

  const metadata: Record<string, unknown> = {}
  if (options?.assistantId?.trim()) {
    metadata.assistant_id = options.assistantId.trim()
  }
  if (options?.graphId?.trim()) {
    metadata.graph_id = options.graphId.trim()
  }

  const payload: Record<string, unknown> = {
    limit,
    offset,
    sort_by: 'updated_at',
    sort_order: 'desc',
    select: ['thread_id', 'metadata', 'status', 'created_at', 'updated_at']
  }

  if (Object.keys(metadata).length > 0) {
    payload.metadata = metadata
  }
  if (options?.status?.trim()) {
    payload.status = options.status.trim()
  }

  const headers = {
    'x-project-id': projectId
  }

  const [itemsResponse, countResponse] = await Promise.all([
    httpClient
      .post('/api/langgraph/threads/search', payload, { headers })
      .then((response) => response.data as ManagementThread[] | { items?: ManagementThread[] })
      .catch(async () => {
        const fallbackPayload = { ...payload }
        delete fallbackPayload.select
        const response = await httpClient.post('/api/langgraph/threads/search', fallbackPayload, {
          headers
        })
        return response.data as ManagementThread[] | { items?: ManagementThread[] }
      }),
    httpClient
      .post('/api/langgraph/threads/count', payload, { headers })
      .then((response) => response.data as CountResponse)
      .catch(() => ({ count: 0 }))
  ])

  const rows = Array.isArray(itemsResponse)
    ? itemsResponse
    : Array.isArray(itemsResponse.items)
      ? itemsResponse.items
      : []

  const normalizedRows = rows.map((thread) => ({
    thread_id: thread.thread_id,
    metadata: thread.metadata,
    status: thread.status,
    created_at: thread.created_at,
    updated_at: thread.updated_at,
    values: thread.values
  })) as ManagementThread[]

  const query = options?.query?.trim().toLowerCase() || ''
  const threadIdQuery = options?.threadId?.trim().toLowerCase() || ''

  const filtered = query
    ? normalizedRows.filter((thread) => getThreadListSearchText(thread).includes(query))
    : normalizedRows

  const filteredByThreadId = threadIdQuery
    ? filtered.filter((thread) => {
        const normalizedThreadId = typeof thread.thread_id === 'string' ? thread.thread_id.toLowerCase() : ''
        return normalizedThreadId.includes(threadIdQuery)
      })
    : filtered

  const total =
    query.length > 0 || threadIdQuery.length > 0
      ? filteredByThreadId.length
      : typeof countResponse.count === 'number'
        ? countResponse.count
        : typeof (countResponse as CountResponse).total === 'number'
          ? (countResponse as CountResponse).total!
          : filteredByThreadId.length

  return {
    items: filteredByThreadId,
    total,
    limit,
    offset
  }
}

export async function getThreadDetail(projectId: string, threadId: string): Promise<ManagementThread> {
  const response = await httpClient.get(`/api/langgraph/threads/${encodeURIComponent(threadId)}`, {
    headers: {
      'x-project-id': projectId
    }
  })
  return response.data as ManagementThread
}

export async function getThreadHistoryPage(
  projectId: string,
  threadId: string,
  options?: { limit?: number; before?: string }
): Promise<ThreadHistoryEntry[]> {
  if (!projectId) {
    return []
  }

  const payload: Record<string, unknown> = {
    limit: options?.limit ?? 20
  }

  if (options?.before?.trim()) {
    payload.before = options.before.trim()
  }

  const response = await httpClient.post(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/history`,
    payload,
    {
      headers: {
        'x-project-id': projectId
      }
    }
  )

  const data = response.data as ThreadHistoryEntry[] | { items?: ThreadHistoryEntry[] }
  return Array.isArray(data) ? data : Array.isArray(data.items) ? data.items : []
}

export async function getThreadState(
  projectId: string,
  threadId: string
): Promise<Record<string, unknown>> {
  const response = await httpClient.get(`/api/langgraph/threads/${encodeURIComponent(threadId)}/state`, {
    headers: {
      'x-project-id': projectId
    }
  })
  return response.data as Record<string, unknown>
}
