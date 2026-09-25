import {
  Client,
  type Checkpoint,
  type Interrupt,
  type Run,
  type Thread,
  type ThreadState,
} from "@langchain/langgraph-sdk";
import { getLanggraphApiUrl } from "@/services/langgraph/client";

export type AccessPolicy = "review" | "workspace_write" | "full_access";
export type ChatState = Record<string, unknown> & { messages: unknown[] };
export type ChatThread = Thread<ChatState>;
export type ChatCheckpoint = ThreadState<ChatState>;
export type ThreadAction =
  | "read"
  | "comment"
  | "edit"
  | "share"
  | "delete"
  | "approve"
  | "terminal"
  | "full_access";

export function hasThreadAction(
  thread: Pick<ChatThread, "metadata"> | undefined,
  action: ThreadAction,
): boolean {
  const actions = thread?.metadata?.allowed_actions;
  return Array.isArray(actions) && actions.includes(action);
}

export function createSessionService(
  fetch: typeof globalThis.fetch,
  projectId?: string,
  userId?: string,
) {
  const client = new Client<ChatState>({
    apiUrl: getLanggraphApiUrl(),
    callerOptions: { fetch, maxRetries: 0 },
    defaultHeaders: projectId ? { "x-project-id": projectId } : undefined,
  });
  const pendingKey =
    projectId && userId ? `pw:thread:create:${userId}:${projectId}` : null;
  function pendingThreadId(): string | null {
    if (!pendingKey || typeof sessionStorage === "undefined") return null;
    try {
      return sessionStorage.getItem(pendingKey);
    } catch {
      return null;
    }
  }
  function setPendingThreadId(id: string | null) {
    if (!pendingKey || typeof sessionStorage === "undefined") return;
    try {
      if (id) sessionStorage.setItem(pendingKey, id);
      else sessionStorage.removeItem(pendingKey);
    } catch {
      /* Browser storage can be disabled. */
    }
  }
  async function read<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers);
    if (projectId) headers.set("x-project-id", projectId);
    headers.set("content-type", "application/json");
    const response = await fetch(`${getLanggraphApiUrl()}${path}`, {
      ...init,
      headers,
    });
    if (!response.ok) {
      let detail = "";
      try {
        const body = (await response.clone().json()) as {
          message?: string;
          detail?: string;
        };
        detail = body?.message || body?.detail || "";
      } catch {
        // ignore json parse error
      }
      throw new Error(
        detail
          ? `${detail}（${response.status}）`
          : `读取会话失败（${response.status}）`,
      );
    }
    return response.json() as Promise<T>;
  }
  return {
    client,
    create: async (
      graphId: string,
      agentId: string | undefined,
      title: string,
      accessPolicy?: AccessPolicy,
      preview?: string,
    ) => {
      const pendingId = pendingThreadId();
      if (pendingId) {
        const result = await read<{ status: string; thread?: ChatThread }>(
          `/threads/${encodeURIComponent(pendingId)}/reconcile`,
          { method: "POST" },
        );
        if (result.status === "ready" && result.thread) {
          setPendingThreadId(null);
          return result.thread;
        }
        throw new Error(`会话创建结果待确认（${pendingId}），请稍后重试`);
      }
      try {
        return await client.threads.create({
          graphId,
          metadata: {
            graph_id: graphId,
            agent_id: agentId,
            title,
            ...(preview ? { preview } : {}),
            ...(accessPolicy ? { access_policy: accessPolicy } : {}),
          },
        });
      } catch (error) {
        const raw = (error as { text?: unknown })?.text;
        if (typeof raw === "string") {
          try {
            const body = JSON.parse(raw) as {
              error?: { extra?: { thread_id?: unknown } };
            };
            const id = body.error?.extra?.thread_id;
            if (typeof id === "string" && /^[0-9a-f-]{36}$/i.test(id)) {
              setPendingThreadId(id);
              throw new Error(`会话创建结果待确认（${id}），请稍后重试`);
            }
          } catch (parseError) {
            if (parseError instanceof SyntaxError) throw error;
            throw parseError;
          }
        }
        throw error;
      }
    },
    get: (threadId: string) => client.threads.get(threadId),
    // The gateway exposes checkpoint_id on GET state, not the SDK's extra checkpoint route.
    state: (threadId: string, checkpoint?: Checkpoint) =>
      read<ThreadState<ChatState> & { interrupts?: Interrupt[] }>(
        `/threads/${encodeURIComponent(threadId)}/state${checkpoint?.checkpoint_id ? `?checkpoint_id=${encodeURIComponent(checkpoint.checkpoint_id)}` : ""}`,
      ),
    // SDK 1.10 types before as Config; the public wire contract requires a Checkpoint.
    history: (threadId: string, before?: Checkpoint, limit = 20) =>
      read<ChatCheckpoint[]>(
        `/threads/${encodeURIComponent(threadId)}/history`,
        { method: "POST", body: JSON.stringify({ limit, before }) },
      ),
    list: (
      options:
        | number
        | { offset?: number; metadata?: Record<string, unknown> } = 0,
    ) => {
      const offset =
        typeof options === "number" ? options : (options.offset ?? 0);
      const metadata =
        typeof options === "object" && options.metadata
          ? options.metadata
          : undefined;
      return client.threads.search({
        limit: 20,
        offset,
        sortBy: "updated_at",
        sortOrder: "desc",
        select: ["thread_id", "metadata", "status", "created_at", "updated_at"],
        ...(metadata ? { metadata } : {}),
      });
    },
    count: async (options?: {
      metadata?: Record<string, unknown>;
      status?: import("@langchain/langgraph-sdk").ThreadStatus;
    }): Promise<number> => {
      const metadata = options?.metadata;
      const status = options?.status;
      const response = (await client.threads.count(
        metadata || status ? { metadata, status } : undefined,
      )) as unknown;
      if (typeof response === "number" && !Number.isNaN(response))
        return response;
      if (typeof response === "object" && response !== null) {
        const payload = response as { count?: unknown; total?: unknown };
        if (typeof payload.count === "number" && !Number.isNaN(payload.count))
          return payload.count;
        if (typeof payload.total === "number" && !Number.isNaN(payload.total))
          return payload.total;
      }
      return 0;
    },
    remove: (threadId: string) => client.threads.delete(threadId),
    resume: (threadId: string, resume: Record<string, unknown>) =>
      read<{ thread_id: string; run_id: string }>(
        `/threads/${encodeURIComponent(threadId)}/runs`,
        {
          method: "POST",
          body: JSON.stringify({ command: { resume } }),
        },
      ),
    runs: (threadId: string): Promise<Run[]> =>
      client.runs.list(threadId, { limit: 20 }),
    run: (threadId: string, runId: string) => client.runs.get(threadId, runId),
    cancel: (threadId: string, runId: string) =>
      client.runs.cancel(threadId, runId, false, "interrupt"),
    fork: (threadId: string, checkpointId: string, title?: string) =>
      read<ChatThread>(`/threads/${encodeURIComponent(threadId)}/fork`, {
        method: "POST",
        body: JSON.stringify({
          checkpoint_id: checkpointId,
          ...(title ? { title } : {}),
        }),
      }),
    update: (
      threadId: string,
      metadata: { title?: string; preview?: string },
    ) =>
      read<ChatThread>(`/threads/${encodeURIComponent(threadId)}`, {
        method: "PATCH",
        body: JSON.stringify(metadata),
      }),
    summarizeTitle: (
      threadId: string,
      messages?: Array<{ role: string; content: string }>,
    ) =>
      read<{
        thread_id: string;
        title: string;
        metadata?: Record<string, unknown>;
      }>(`/threads/${encodeURIComponent(threadId)}/title/summarize`, {
        method: "POST",
        body: JSON.stringify(messages ? { messages } : {}),
      }),
  };
}
