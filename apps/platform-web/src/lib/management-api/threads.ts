import type { Message, Thread } from "@langchain/langgraph-sdk";

import { createManagementApiClient } from "./client";

export type ManagementThread = Thread & {
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ThreadHistoryEntry = Record<string, unknown>;

type ThreadListResponse = {
  items: ManagementThread[];
  total: number;
  limit: number;
  offset: number;
};

type CountResponse = {
  count?: number;
  total?: number;
};

export type ListThreadsOptions = {
  limit?: number;
  offset?: number;
  query?: string;
  threadId?: string;
  assistantId?: string;
  graphId?: string;
  status?: string;
};

export async function listThreadsPage(
  projectId: string,
  options?: ListThreadsOptions,
): Promise<ThreadListResponse> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  const limit = options?.limit ?? 20;
  const offset = options?.offset ?? 0;
  if (!client || !projectId) {
    return { items: [], total: 0, limit, offset };
  }

  const metadata: Record<string, unknown> = {};
  if (options?.assistantId?.trim()) {
    metadata.assistant_id = options.assistantId.trim();
  }
  if (options?.graphId?.trim()) {
    metadata.graph_id = options.graphId.trim();
  }

  const payload: Record<string, unknown> = {
    limit,
    offset,
    sort_by: "updated_at",
    sort_order: "desc",
  };
  if (Object.keys(metadata).length > 0) {
    payload.metadata = metadata;
  }
  if (options?.status?.trim()) {
    payload.status = options.status.trim();
  }

  const [itemsResponse, countResponse] = await Promise.all([
    client.post<ManagementThread[] | { items?: ManagementThread[] }>("/api/langgraph/threads/search", payload),
    client.post<CountResponse>("/api/langgraph/threads/count", payload).catch(() => ({ count: 0 })),
  ]);

  const rows = Array.isArray(itemsResponse)
    ? itemsResponse
    : Array.isArray(itemsResponse.items)
      ? itemsResponse.items
      : [];

  const query = options?.query?.trim().toLowerCase() || "";
  const threadIdQuery = options?.threadId?.trim().toLowerCase() || "";
  const filtered = query
    ? rows.filter((thread) => {
        const normalizedThreadId = typeof thread.thread_id === "string" ? thread.thread_id.toLowerCase() : "";
        const preview = getThreadPreviewText(thread).toLowerCase();
        return normalizedThreadId.includes(query) || preview.includes(query);
      })
    : rows;

  const filteredByThreadId = threadIdQuery
    ? filtered.filter((thread) => {
        const normalizedThreadId = typeof thread.thread_id === "string" ? thread.thread_id.toLowerCase() : "";
        return normalizedThreadId.includes(threadIdQuery);
      })
    : filtered;

  const normalizedCount = countResponse as CountResponse;

  const total =
    query.length > 0 || threadIdQuery.length > 0
      ? filteredByThreadId.length
      : typeof normalizedCount.count === "number"
        ? normalizedCount.count
        : typeof normalizedCount.total === "number"
          ? normalizedCount.total
          : filteredByThreadId.length;

  return {
    items: filteredByThreadId,
    total,
    limit,
    offset,
  };
}

export async function getThreadDetail(projectId: string, threadId: string): Promise<ManagementThread> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.get<ManagementThread>(`/api/langgraph/threads/${encodeURIComponent(threadId)}`);
}

export async function getThreadHistoryPage(
  projectId: string,
  threadId: string,
  options?: { limit?: number; before?: string },
): Promise<ThreadHistoryEntry[]> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client || !projectId) {
    return [];
  }
  const payload: Record<string, unknown> = {
    limit: options?.limit ?? 20,
  };
  if (options?.before?.trim()) {
    payload.before = options.before.trim();
  }
  const response = await client.post<ThreadHistoryEntry[] | { items?: ThreadHistoryEntry[] }>(
    `/api/langgraph/threads/${encodeURIComponent(threadId)}/history`,
    payload,
  );
  return Array.isArray(response)
    ? response
    : Array.isArray(response.items)
      ? response.items
      : [];
}

export async function getThreadState(
  projectId: string,
  threadId: string,
): Promise<Record<string, unknown>> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client || !projectId) {
    throw new Error("management_api_unavailable");
  }
  return client.get<Record<string, unknown>>(`/api/langgraph/threads/${encodeURIComponent(threadId)}/state`);
}

export function getThreadPreviewText(thread: Pick<ManagementThread, "thread_id" | "values">): string {
  const values = thread.values;
  if (!values || typeof values !== "object") {
    return thread.thread_id;
  }
  const messages = (values as { messages?: Message[] }).messages;
  if (!Array.isArray(messages) || messages.length === 0) {
    return thread.thread_id;
  }
  const firstMessage = messages[0];
  if (!firstMessage) {
    return thread.thread_id;
  }
  const content = firstMessage.content;
  if (typeof content === "string") {
    return content || thread.thread_id;
  }
  const texts = content
    .filter((item): item is { type: "text"; text: string } => item?.type === "text")
    .map((item) => item.text.trim())
    .filter(Boolean);
  return texts.join(" ") || thread.thread_id;
}
