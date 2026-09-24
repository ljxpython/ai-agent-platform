import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { coerceMessageLikeToMessage } from "@langchain/core/messages";
import { useChatSessionStore } from "./useChatSessionStore";
import type { ChatCheckpoint, ChatThread } from "@/services/threads/session.service";

describe("useChatSessionStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("caches and retrieves session history, messages, and thread metadata per project and thread", () => {
    const store = useChatSessionStore();
    const msg = coerceMessageLikeToMessage({ id: "msg-1", type: "human", content: "Hello SWR" });
    const historyRow = {
      checkpoint: { checkpoint_id: "cp-1", thread_id: "thread-1", checkpoint_ns: "" },
      values: { messages: [{ id: "msg-1", type: "human", content: "Hello SWR" }] },
    } as unknown as ChatCheckpoint;
    const threadObj = {
      thread_id: "thread-1",
      updated_at: "2026-09-24T10:00:00Z",
      metadata: { graph_id: "simple_agent", allowed_actions: ["read", "comment"] },
    } as unknown as ChatThread;

    store.setSessionMessages("proj-1", "thread-1", [msg]);
    store.setSessionHistory("proj-1", "thread-1", [historyRow]);
    store.setSessionThread("proj-1", "thread-1", threadObj);

    const cached = store.getSession("proj-1", "thread-1");
    expect(cached).toBeDefined();
    expect(cached?.messages).toHaveLength(1);
    expect(cached?.messages[0]?.id).toBe("msg-1");
    expect(cached?.history).toHaveLength(1);
    expect(cached?.thread?.thread_id).toBe("thread-1");

    // Different project is isolated
    expect(store.getSession("proj-2", "thread-1")).toBeUndefined();
  });

  it("remembers and clears lastActiveThread per project and route scope", () => {
    const store = useChatSessionStore();

    store.setLastActiveThread("proj-1", "workspace-chat", "thread-alpha");
    store.setLastActiveThread("proj-1", "workspace-dear-agent", "thread-beta");

    expect(store.getLastActiveThread("proj-1", "workspace-chat")).toBe("thread-alpha");
    expect(store.getLastActiveThread("proj-1", "workspace-dear-agent")).toBe("thread-beta");

    store.removeSession("proj-1", "thread-alpha");
    expect(store.getLastActiveThread("proj-1", "workspace-chat")).toBeUndefined();
    expect(store.getLastActiveThread("proj-1", "workspace-dear-agent")).toBe("thread-beta");

    store.setLastActiveThread("proj-1", "workspace-dear-agent", null);
    expect(store.getLastActiveThread("proj-1", "workspace-dear-agent")).toBeUndefined();
  });
});
