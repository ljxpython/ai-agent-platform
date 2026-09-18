import { Client, type Checkpoint, type Interrupt, type Run, type Thread, type ThreadState } from '@langchain/langgraph-sdk'
import { getLanggraphApiUrl } from '@/services/langgraph/client'

export type AccessPolicy = 'review' | 'workspace_write' | 'full_access'
export type ChatState = Record<string, unknown> & { messages: unknown[] }
export type ChatThread = Thread<ChatState>
export type ChatCheckpoint = ThreadState<ChatState>

export function createSessionService(fetch: typeof globalThis.fetch, projectId?: string) {
  const client = new Client<ChatState>({ apiUrl: getLanggraphApiUrl(), callerOptions: { fetch, maxRetries: 0 }, defaultHeaders: projectId ? { 'x-project-id': projectId } : undefined })
  async function read<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers)
    if (projectId) headers.set('x-project-id', projectId)
    headers.set('content-type', 'application/json')
    const response = await fetch(`${getLanggraphApiUrl()}${path}`, { ...init, headers })
    if (!response.ok) {
      let detail = ''
      try {
        const body = (await response.clone().json()) as { message?: string; detail?: string }
        detail = body?.message || body?.detail || ''
      } catch {
        // ignore json parse error
      }
      throw new Error(detail ? `${detail}（${response.status}）` : `读取会话失败（${response.status}）`)
    }
    return response.json() as Promise<T>
  }
  return {
    client,
    create: (graphId: string, agentId: string | undefined, title: string, accessPolicy?: AccessPolicy, preview?: string) =>
      client.threads.create({
        graphId,
        metadata: {
          graph_id: graphId,
          agent_id: agentId,
          title,
          ...(preview ? { preview } : {}),
          ...(accessPolicy ? { access_policy: accessPolicy } : {}),
        },
      }),
    get: (threadId: string) => client.threads.get(threadId),
    // The gateway exposes checkpoint_id on GET state, not the SDK's extra checkpoint route.
    state: (threadId: string, checkpoint?: Checkpoint) => read<ThreadState<ChatState> & { interrupts?: Interrupt[] }>(`/threads/${encodeURIComponent(threadId)}/state${checkpoint?.checkpoint_id ? `?checkpoint_id=${encodeURIComponent(checkpoint.checkpoint_id)}` : ''}`),
    // SDK 1.10 types before as Config; the public wire contract requires a Checkpoint.
    history: (threadId: string, before?: Checkpoint, limit = 20) => read<ChatCheckpoint[]>(`/threads/${encodeURIComponent(threadId)}/history`, { method: 'POST', body: JSON.stringify({ limit, before }) }),
    list: (options: number | { offset?: number; metadata?: Record<string, unknown> } = 0) => {
      const offset = typeof options === 'number' ? options : options.offset ?? 0
      const metadata = typeof options === 'object' && options.metadata ? options.metadata : undefined
      return client.threads.search({
        limit: 20,
        offset,
        sortBy: 'updated_at',
        sortOrder: 'desc',
        select: ['thread_id', 'metadata', 'status', 'created_at', 'updated_at'],
        ...(metadata ? { metadata } : {})
      })
    },
    count: async (options?: { metadata?: Record<string, unknown>; status?: import('@langchain/langgraph-sdk').ThreadStatus }): Promise<number> => {
      const metadata = options?.metadata
      const status = options?.status
      const response = (await client.threads.count(metadata || status ? { metadata, status } : undefined)) as unknown
      if (typeof response === 'number' && !Number.isNaN(response)) return response
      if (typeof response === 'object' && response !== null) {
        const payload = response as { count?: unknown; total?: unknown }
        if (typeof payload.count === 'number' && !Number.isNaN(payload.count)) return payload.count
        if (typeof payload.total === 'number' && !Number.isNaN(payload.total)) return payload.total
      }
      return 0
    },
    remove: (threadId: string) => client.threads.delete(threadId),
    runs: (threadId: string): Promise<Run[]> => client.runs.list(threadId, { limit: 20 }),
    run: (threadId: string, runId: string) => client.runs.get(threadId, runId),
    cancel: (threadId: string, runId: string) => client.runs.cancel(threadId, runId, false, 'interrupt'),
    fork: (threadId: string, checkpointId: string, title?: string) =>
      read<ChatThread>(`/threads/${encodeURIComponent(threadId)}/fork`, {
        method: 'POST',
        body: JSON.stringify({ checkpoint_id: checkpointId, ...(title ? { title } : {}) })
      }),
    update: (threadId: string, metadata: { title?: string; preview?: string }) =>
      read<ChatThread>(`/threads/${encodeURIComponent(threadId)}`, {
        method: 'PATCH',
        body: JSON.stringify(metadata)
      })
  }
}
