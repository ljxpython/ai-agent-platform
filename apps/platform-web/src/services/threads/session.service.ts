import { Client, type Checkpoint, type Interrupt, type Run, type Thread, type ThreadState } from '@langchain/langgraph-sdk'
import { getLanggraphApiUrl } from '@/services/langgraph/client'

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
    if (!response.ok) throw new Error(`读取会话失败（${response.status}）`)
    return response.json() as Promise<T>
  }
  return {
    client,
    create: (graphId: string, agentId: string | undefined, title: string) => client.threads.create({ graphId, metadata: { agent_id: agentId, title } }),
    get: (threadId: string) => client.threads.get(threadId),
    // The gateway exposes checkpoint_id on GET state, not the SDK's extra checkpoint route.
    state: (threadId: string, checkpoint?: Checkpoint) => read<ThreadState<ChatState> & { interrupts?: Interrupt[] }>(`/threads/${encodeURIComponent(threadId)}/state${checkpoint?.checkpoint_id ? `?checkpoint_id=${encodeURIComponent(checkpoint.checkpoint_id)}` : ''}`),
    // SDK 1.10 types before as Config; the public wire contract requires a Checkpoint.
    history: (threadId: string, before?: Checkpoint, limit = 20) => read<ChatCheckpoint[]>(`/threads/${encodeURIComponent(threadId)}/history`, { method: 'POST', body: JSON.stringify({ limit, before }) }),
    list: (offset = 0) => client.threads.search({ limit: 20, offset, sortBy: 'updated_at', sortOrder: 'desc', select: ['thread_id', 'metadata', 'status', 'created_at', 'updated_at'] }),
    count: () => client.threads.count(),
    remove: (threadId: string) => client.threads.delete(threadId),
    runs: (threadId: string): Promise<Run[]> => client.runs.list(threadId, { limit: 20 }),
    run: (threadId: string, runId: string) => client.runs.get(threadId, runId),
    cancel: (threadId: string, runId: string) => client.runs.cancel(threadId, runId, false, 'interrupt')
  }
}
