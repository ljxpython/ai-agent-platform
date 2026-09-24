import { shallowReactive } from "vue";
import { createPinia, defineStore, getActivePinia, setActivePinia } from "pinia";
import type { BaseMessage } from "@langchain/core/messages";
import type { ChatCheckpoint, ChatThread } from "@/services/threads/session.service";

export interface SessionCacheEntry {
  threadId: string;
  projectId: string;
  history: ChatCheckpoint[];
  messages: BaseMessage[];
  thread?: ChatThread;
  updatedAt: number;
}

const MAX_CACHED_SESSIONS = 40;

const useChatSessionStoreDef = defineStore("chat-session-cache", () => {
  const sessions = shallowReactive(new Map<string, SessionCacheEntry>());
  const lastActiveThreads = shallowReactive(new Map<string, string>());

  function makeKey(projectId: string, threadId: string): string {
    return `${projectId}:${threadId}`;
  }

  function makeScopeKey(projectId: string, routeScope: string): string {
    return `${projectId}:${routeScope}`;
  }

  function pruneIfNeeded() {
    if (sessions.size <= MAX_CACHED_SESSIONS) return;
    let oldestKey: string | undefined;
    let oldestTime = Infinity;
    for (const [key, entry] of sessions.entries()) {
      if (entry.updatedAt < oldestTime) {
        oldestTime = entry.updatedAt;
        oldestKey = key;
      }
    }
    if (oldestKey) {
      sessions.delete(oldestKey);
    }
  }

  function ensureEntry(projectId: string, threadId: string): SessionCacheEntry {
    const key = makeKey(projectId, threadId);
    const existing = sessions.get(key);
    if (existing) {
      return existing;
    }
    const created: SessionCacheEntry = {
      projectId,
      threadId,
      history: [],
      messages: [],
      updatedAt: Date.now(),
    };
    sessions.set(key, created);
    pruneIfNeeded();
    return created;
  }

  function getSession(projectId: string, threadId?: string | null): SessionCacheEntry | undefined {
    if (!projectId || !threadId) return undefined;
    return sessions.get(makeKey(projectId, threadId));
  }

  function setSessionHistory(
    projectId: string,
    threadId: string,
    history: ChatCheckpoint[],
  ) {
    if (!projectId || !threadId) return;
    const entry = ensureEntry(projectId, threadId);
    sessions.set(makeKey(projectId, threadId), {
      ...entry,
      history,
      updatedAt: Date.now(),
    });
  }

  function setSessionMessages(
    projectId: string,
    threadId: string,
    messages: BaseMessage[],
  ) {
    if (!projectId || !threadId || messages.length === 0) return;
    const entry = ensureEntry(projectId, threadId);
    sessions.set(makeKey(projectId, threadId), {
      ...entry,
      messages,
      updatedAt: Date.now(),
    });
  }

  function setSessionThread(
    projectId: string,
    threadId: string,
    thread: ChatThread | undefined,
  ) {
    if (!projectId || !threadId || !thread) return;
    const entry = ensureEntry(projectId, threadId);
    sessions.set(makeKey(projectId, threadId), {
      ...entry,
      thread,
      updatedAt: Date.now(),
    });
  }

  function removeSession(projectId: string, threadId: string) {
    if (!projectId || !threadId) return;
    sessions.delete(makeKey(projectId, threadId));
    for (const [scopeKey, activeId] of lastActiveThreads.entries()) {
      if (scopeKey.startsWith(`${projectId}:`) && activeId === threadId) {
        lastActiveThreads.delete(scopeKey);
      }
    }
  }

  function setLastActiveThread(
    projectId: string,
    routeScope: "workspace-chat" | "workspace-dear-agent",
    threadId?: string | null,
  ) {
    if (!projectId) return;
    const key = makeScopeKey(projectId, routeScope);
    if (threadId) {
      lastActiveThreads.set(key, threadId);
    } else {
      lastActiveThreads.delete(key);
    }
  }

  function getLastActiveThread(
    projectId: string,
    routeScope: "workspace-chat" | "workspace-dear-agent",
  ): string | undefined {
    if (!projectId) return undefined;
    return lastActiveThreads.get(makeScopeKey(projectId, routeScope));
  }

  function clearAll() {
    sessions.clear();
    lastActiveThreads.clear();
  }

  return {
    sessions,
    lastActiveThreads,
    getSession,
    setSessionHistory,
    setSessionMessages,
    setSessionThread,
    removeSession,
    setLastActiveThread,
    getLastActiveThread,
    clearAll,
  };
});

export function useChatSessionStore() {
  if (!getActivePinia()) {
    setActivePinia(createPinia());
  }
  return useChatSessionStoreDef();
}

