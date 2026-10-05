import {
  inject,
  provide,
  ref,
  shallowReactive,
  shallowRef,
  type Ref,
  type Slots,
} from "vue";
import type { AgentContext } from "@/services/agents/types";
import type { ChatAttachmentBlock } from "@/utils/chat-content";
import type { ChatThread } from "@/services/threads/session.service";
import type ChatSession from "../components/ChatSession.vue";

export type PoolTarget = {
  graphId: string;
  agentId?: string;
  name: string;
  context: AgentContext;
  disabled?: boolean;
};
export type PoolView = {
  outlet: HTMLElement;
  slots: Slots;
  focusMode: Ref<boolean>;
  canWrite: Ref<boolean>;
  projectName: Ref<string>;
  threadTitle: Ref<string>;
  onThread: (id: string) => void;
  onFork: (id: string) => void;
  onRefresh: () => void;
  onRevoked: () => void;
};
export type PoolEntry = {
  instanceId: string;
  scope: string;
  projectId: string;
  target: PoolTarget;
  threadId: Ref<string | undefined>;
  initialThread: Ref<ChatThread | undefined>;
  draft: Ref<string>;
  attachments: Ref<ChatAttachmentBlock[]>;
  context: Ref<AgentContext>;
  recursionLimit: Ref<number>;
  draftKey: string;
  view: Ref<PoolView | undefined>;
  sessionRef: Ref<InstanceType<typeof ChatSession> | null>;
  visible: Ref<boolean>;
  canWrite: Ref<boolean>;
  needsRefresh: boolean;
  pendingThreadRoute?: string;
  generation: number;
  disposed: boolean;
  lastViewedAt: number;
};

export function createChatSessionPool() {
  const entries = shallowReactive(new Map<string, PoolEntry>());
  const byThread = new Map<string, string>();
  const byDraft = new Map<string, string>();
  let activeId: string | undefined;

  function acquire(
    scope: string,
    projectId: string,
    kind: string,
    target: PoolTarget,
    threadId?: string,
    draftId = "new",
  ) {
    const indexKey = threadId
      ? `${scope}:${threadId}`
      : `${scope}:${kind}:${target.agentId ?? target.graphId}:${draftId}`;
    const id = (threadId ? byThread : byDraft).get(indexKey);
    const existing = id ? entries.get(id) : undefined;
    if (existing) {
      if (!threadId && existing.threadId.value) {
        // 请求的是新草稿（!threadId），但此 draft 已经升级绑定了真实会话，严禁作为草稿复用！
        byDraft.delete(indexKey);
      } else {
        if (
          existing.target.graphId !== target.graphId ||
          existing.target.agentId !== target.agentId
        )
          throw new Error("Agent 与对话的执行目标不一致");
        return existing;
      }
    }
    const draftKey = [
      "pw:chat:draft",
      scope,
      kind,
      target.agentId ?? target.graphId,
      threadId ?? draftId,
    ].join(":");
    let savedDraft = "";
    try {
      savedDraft = sessionStorage.getItem(draftKey) ?? "";
    } catch {
      /* storage may be disabled */
    }
    const entry: PoolEntry = {
      instanceId: crypto.randomUUID(),
      scope,
      projectId,
      target,
      threadId: ref(threadId),
      initialThread: shallowRef(),
      draft: ref(savedDraft),
      attachments: ref([]),
      context: ref({ ...target.context }),
      recursionLimit: ref(1000),
      draftKey,
      view: shallowRef(),
      sessionRef: shallowRef(null),
      visible: ref(false),
      canWrite: ref(false),
      needsRefresh: false,
      generation: 0,
      disposed: false,
      lastViewedAt: Date.now(),
    };
    entries.set(entry.instanceId, entry);
    (threadId ? byThread : byDraft).set(indexKey, entry.instanceId);
    return entry;
  }

  function bindThread(entry: PoolEntry, threadId: string) {
    if (entry.disposed) return;
    const key = `${entry.scope}:${threadId}`;
    const other = byThread.get(key);
    if (other && other !== entry.instanceId)
      throw new Error("会话已由另一实例持有，请重新核实运行状态");
    entry.threadId.value = threadId;
    byThread.set(key, entry.instanceId);
    for (const [dKey, instId] of byDraft.entries()) {
      if (instId === entry.instanceId) {
        byDraft.delete(dKey);
      }
    }
  }

  function attachView(entry: PoolEntry, view: PoolView) {
    if (entry.disposed) throw new Error("会话已关闭");
    const previous = activeId ? entries.get(activeId) : undefined;
    if (previous && previous !== entry) {
      previous.visible.value = false;
      previous.view.value = undefined;
    }
    activeId = entry.instanceId;
    entry.view.value = view;
    entry.canWrite = view.canWrite;
    entry.visible.value = true;
    entry.lastViewedAt = Date.now();
    if (entry.pendingThreadRoute) {
      const id = entry.pendingThreadRoute;
      entry.pendingThreadRoute = undefined;
      view.onThread(id);
    }
    if (entry.needsRefresh) {
      entry.needsRefresh = false;
      view.onRefresh();
    }
    return () => {
      if (entry.view.value !== view) return;
      entry.visible.value = false;
      entry.view.value = undefined;
      if (activeId === entry.instanceId) activeId = undefined;
    };
  }

  function remove(entry: PoolEntry) {
    if (entry.disposed) return;
    entry.disposed = true;
    entry.generation++;
    entry.visible.value = false;
    entry.view.value = undefined;
    entry.pendingThreadRoute = undefined;
    entries.delete(entry.instanceId);
    for (const [key, id] of byThread)
      if (id === entry.instanceId) byThread.delete(key);
    for (const [key, id] of byDraft)
      if (id === entry.instanceId) byDraft.delete(key);
    if (activeId === entry.instanceId) activeId = undefined;
    try {
      sessionStorage.removeItem(entry.draftKey);
    } catch {
      /* storage may be disabled */
    }
  }

  function clearScope() {
    for (const entry of [...entries.values()]) remove(entry);
  }

  return { entries, acquire, bindThread, attachView, remove, clearScope };
}

export type ChatSessionPool = ReturnType<typeof createChatSessionPool>;
const poolKey = Symbol("chat-session-pool");
export function provideChatSessionPool(pool: ChatSessionPool) {
  provide(poolKey, pool);
}
export function useChatSessionPool() {
  const pool = inject<ChatSessionPool>(poolKey);
  if (!pool) throw new Error("Workspace 会话宿主不可用");
  return pool;
}
