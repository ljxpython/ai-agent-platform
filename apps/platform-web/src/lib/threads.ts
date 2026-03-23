import type { Message } from "@langchain/langgraph-sdk";

import type { ManagementThread, ThreadHistoryEntry } from "@/lib/management-api/threads";

export function formatThreadTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function getThreadAssistantId(thread?: ManagementThread | null): string | null {
  const metadata = thread?.metadata;
  if (!metadata || typeof metadata !== "object") {
    return null;
  }
  const value = (metadata as Record<string, unknown>).assistant_id;
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

export function getThreadGraphId(thread?: ManagementThread | null): string | null {
  const metadata = thread?.metadata;
  if (!metadata || typeof metadata !== "object") {
    return null;
  }
  const value = (metadata as Record<string, unknown>).graph_id;
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

export function getThreadMessages(thread?: ManagementThread | null, state?: Record<string, unknown> | null): Message[] {
  const stateMessages = extractMessages(state);
  if (stateMessages.length > 0) {
    return stateMessages;
  }
  return extractMessages(thread?.values);
}

export function getHistoryEntryId(entry: ThreadHistoryEntry, index: number): string {
  const checkpoint = entry.checkpoint;
  if (checkpoint && typeof checkpoint === "object") {
    const checkpointId = (checkpoint as Record<string, unknown>).checkpoint_id;
    if (typeof checkpointId === "string" && checkpointId.trim()) {
      return checkpointId;
    }
  }
  const rawId = entry.checkpoint_id;
  if (typeof rawId === "string" && rawId.trim()) {
    return rawId;
  }
  return `history-${index}`;
}

export function getHistoryEntryTime(entry: ThreadHistoryEntry): string {
  const metadata = entry.metadata;
  if (metadata && typeof metadata === "object") {
    const createdAt = (metadata as Record<string, unknown>).created_at;
    if (typeof createdAt === "string" && createdAt.trim()) {
      return formatThreadTime(createdAt);
    }
  }
  const checkpoint = entry.checkpoint;
  if (checkpoint && typeof checkpoint === "object") {
    const threadTs = (checkpoint as Record<string, unknown>).thread_ts;
    if (typeof threadTs === "string" && threadTs.trim()) {
      return formatThreadTime(threadTs);
    }
  }
  return "-";
}

export function toPrettyJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value);
  }
}

function extractMessages(source: unknown): Message[] {
  if (!source || typeof source !== "object") {
    return [];
  }
  const values = source as Record<string, unknown>;
  const messages = values.messages;
  return Array.isArray(messages) ? (messages as Message[]) : [];
}
