import {
  computed,
  getCurrentScope,
  onScopeDispose,
  ref,
  shallowRef,
  type ComputedRef,
  type Ref,
} from "vue";
import {
  coerceMessageLikeToMessage,
  type BaseMessage,
} from "@langchain/core/messages";
import type { Checkpoint } from "@langchain/langgraph-sdk";
import {
  createSessionService,
  type ChatCheckpoint,
} from "@/services/threads/session.service";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import { increasedForkTitle } from "@/utils/threads";
import { asObject } from "../transcript";
import { useChatSessionStore } from "../stores/useChatSessionStore";
import type { useChatSession } from "./useChatSession";

export interface UseChatActionsOptions {
  projectId: string;
  threadTitle?: string;
  session: ReturnType<typeof useChatSession>;
  displayedMessages: ComputedRef<BaseMessage[]> | (() => BaseMessage[]);
  messageMetadata:
    | ComputedRef<Record<string, { checkpointId?: string }>>
    | (() => Record<string, { checkpointId?: string }>);
  recursionLimit: Ref<number>;
  onForkThread?: (newThreadId: string) => void;
  onRefresh?: () => void;
  onLocalError?: (msg: string) => void;
}

export function useChatActions(options: UseChatActionsOptions) {
  const chatSessionStore = useChatSessionStore();
  const currentThreadId = computed(() => options.session.threadId.value || "");

  const initialCachedSession = currentThreadId.value
    ? chatSessionStore.getSession(options.projectId, currentThreadId.value)
    : undefined;

  const history = shallowRef<ChatCheckpoint[]>(
    initialCachedSession?.history ?? [],
  );
  const historyLoading = ref(false);
  const hasMoreHistory = ref(true);

  const editDraft = ref("");
  const editingMessageId = ref("");
  const editCheckpoint = shallowRef<Checkpoint | null>(null);
  const editLoading = ref(false);
  const forkingCheckpointId = ref<string>();

  let disposed = false;
  if (getCurrentScope()) {
    onScopeDispose(() => {
      disposed = true;
    });
  }

  const getDisplayedMessages = () =>
    typeof options.displayedMessages === "function"
      ? options.displayedMessages()
      : options.displayedMessages.value;

  const getMessageMetadata = () =>
    typeof options.messageMetadata === "function"
      ? options.messageMetadata()
      : options.messageMetadata.value;

  const coercedMessageCache = new Map<
    string,
    { sig: string; msg: BaseMessage }
  >();

  const latestHistoryMessages = computed<BaseMessage[]>(() => {
    const headRaw = history.value[0]?.values?.messages;
    if (!Array.isArray(headRaw) || headRaw.length === 0) return [];
    try {
      return headRaw.map((m) => {
        const rawObj =
          m && typeof m === "object" ? (m as Record<string, unknown>) : null;
        const rawId = typeof rawObj?.id === "string" ? rawObj.id : "";
        const rawContent =
          typeof rawObj?.content === "string"
            ? rawObj.content
            : JSON.stringify(rawObj?.content ?? "");
        const rawToolsLen = Array.isArray(rawObj?.tool_calls)
          ? rawObj.tool_calls.length
          : 0;
        const sig = `${rawId}:${rawContent.length}:${rawToolsLen}`;
        if (rawId) {
          const cached = coercedMessageCache.get(rawId);
          if (cached && cached.sig === sig) {
            return cached.msg;
          }
        }
        const coerced = coerceMessageLikeToMessage(
          m as Parameters<typeof coerceMessageLikeToMessage>[0],
        );
        if (rawId) {
          coercedMessageCache.set(rawId, { sig, msg: coerced });
        }
        return coerced;
      });
    } catch {
      return [];
    }
  });

  function cancelEdit() {
    editingMessageId.value = "";
    editDraft.value = "";
    editCheckpoint.value = null;
  }

  function findParentCheckpointForMessage(
    messageId: string,
    content: string,
  ): Checkpoint | null {
    const states = history.value;
    if (states.length === 0) return null;

    const matchMsg = (msg: unknown) => {
      const obj = asObject(msg);
      return (
        obj.id === messageId ||
        obj.key === messageId ||
        ((obj.type === "human" || obj.role === "user") &&
          typeof obj.content === "string" &&
          content &&
          obj.content.trim() === content.trim())
      );
    };

    const firstSeenIndex = states.findIndex((state) =>
      (state.values.messages ?? []).some(matchMsg),
    );

    if (firstSeenIndex > 0) {
      return states[firstSeenIndex - 1].checkpoint;
    }

    if (firstSeenIndex === 0) {
      const firstState = states[0];
      if (firstState.parent_checkpoint?.checkpoint_id) {
        return firstState.parent_checkpoint;
      }
    }

    return null;
  }

  function findForkCheckpointForMessage(messageId: string): string | undefined {
    const meta = getMessageMetadata()[messageId];
    if (meta?.checkpointId) {
      return meta.checkpointId;
    }
    const allMsgs = getDisplayedMessages();
    const targetIndex = allMsgs.findIndex(
      (m) => m.id === messageId || (m as any).key === messageId,
    );
    const subsequentIds = new Set<string>();
    if (targetIndex >= 0) {
      for (let i = targetIndex + 1; i < allMsgs.length; i++) {
        const id = allMsgs[i]?.id || (allMsgs[i] as any)?.key;
        if (id) subsequentIds.add(id);
      }
    }

    const matchMsg = (msg: unknown) => {
      const obj = asObject(msg);
      return obj.id === messageId || obj.key === messageId;
    };

    const matched = history.value.find((state) => {
      const msgs = (state.values.messages ?? []) as unknown[];
      const hasTarget = msgs.some(matchMsg);
      if (!hasTarget) return false;
      if (subsequentIds.size === 0) return true;
      const hasSubsequent = msgs.some((msg) => {
        const obj = asObject(msg);
        const id = (obj.id || obj.key) as string;
        return Boolean(id && subsequentIds.has(id));
      });
      return !hasSubsequent;
    });

    if (matched?.checkpoint?.checkpoint_id) {
      return matched.checkpoint.checkpoint_id;
    }

    const subsequentMsgs =
      targetIndex >= 0 ? allMsgs.slice(targetIndex + 1) : [];
    const hasSubsequentHuman = subsequentMsgs.some(
      (m) =>
        m.type === "human" ||
        (m as any).role === "user" ||
        (m as any).role === "human",
    );
    if (
      !hasSubsequentHuman &&
      history.value.length === 1 &&
      history.value[0]?.checkpoint?.checkpoint_id
    ) {
      return history.value[0].checkpoint.checkpoint_id;
    }

    return undefined;
  }

  let lastLoadedHistoryThreadId = currentThreadId.value;

  async function loadHistory(reset = false, limit = 20) {
    const thread = currentThreadId.value;
    if (!thread || historyLoading.value) return;
    historyLoading.value = true;
    try {
      const rows = await options.session.service.history(
        thread,
        reset ? undefined : history.value[history.value.length - 1]?.checkpoint,
        limit,
      );
      if (disposed || currentThreadId.value !== thread) return;
      if (reset) {
        const isSameHeadCheckpoint =
          lastLoadedHistoryThreadId === thread &&
          history.value.length > 0 &&
          history.value.length === rows.length &&
          history.value[0]?.checkpoint?.checkpoint_id ===
            rows[0]?.checkpoint?.checkpoint_id;
        if (
          !isSameHeadCheckpoint &&
          (rows.length > 0 ||
            history.value.length === 0 ||
            lastLoadedHistoryThreadId !== thread)
        ) {
          history.value = rows;
          lastLoadedHistoryThreadId = thread;
        }
      } else {
        const seenIds = new Set(
          history.value.map((r) => r.checkpoint.checkpoint_id),
        );
        const appended = rows.filter(
          (r) => !seenIds.has(r.checkpoint.checkpoint_id),
        );
        history.value = [...history.value, ...appended];
      }
      if (history.value.length > 0) {
        chatSessionStore.setSessionHistory(
          options.projectId,
          thread,
          history.value,
        );
      }
      hasMoreHistory.value = rows.length === limit;
    } catch (cause) {
      if (!disposed) {
        console.warn(
          `[loadHistory] Failed to load history snapshot for ${thread}:`,
          cause,
        );
      }
    } finally {
      if (!disposed) historyLoading.value = false;
    }
  }

  async function edit(messageId: string, text: string) {
    if (!options.session.canSend.value || !currentThreadId.value) return;
    options.onLocalError?.("");
    editingMessageId.value = messageId;
    editDraft.value = text;
    editCheckpoint.value = null;

    let targetCheckpoint = findParentCheckpointForMessage(messageId, text);
    if (targetCheckpoint) {
      editCheckpoint.value = targetCheckpoint;
      return;
    }

    editLoading.value = true;
    try {
      const rows = await options.session.service.history(
        currentThreadId.value,
        undefined,
        100,
      );
      if (disposed) return;
      if (rows && rows.length > 0) {
        history.value = rows;
        targetCheckpoint = findParentCheckpointForMessage(messageId, text);
        if (targetCheckpoint) {
          editCheckpoint.value = targetCheckpoint;
          return;
        }
      }

      let current = await options.session.service.state(currentThreadId.value);
      const contains = (state: ChatCheckpoint) =>
        (state.values.messages ?? []).some((m) => {
          const obj = asObject(m);
          return (
            obj.id === messageId ||
            obj.key === messageId ||
            ((obj.type === "human" || obj.role === "user") &&
              typeof obj.content === "string" &&
              text &&
              obj.content.trim() === text.trim())
          );
        });
      for (let depth = 0; depth < 10 && !disposed; depth++) {
        if (!contains(current) || !current.parent_checkpoint) break;
        const parent = await options.session.service.state(
          currentThreadId.value,
          current.parent_checkpoint,
        );
        if (!contains(parent)) {
          editCheckpoint.value = parent.checkpoint;
          return;
        }
        current = parent;
      }

      if (!disposed && !editCheckpoint.value) {
        options.onLocalError?.(
          "未找到该消息之前可恢复的检查点，无法安全创建分支",
        );
      }
    } catch (cause) {
      if (!disposed) {
        options.onLocalError?.(
          cause instanceof Error ? cause.message : "读取分支失败",
        );
      }
    } finally {
      if (!disposed) editLoading.value = false;
    }
  }

  async function submitEditedBranch() {
    if (!editDraft.value.trim()) return;
    let checkpoint = editCheckpoint.value;
    if (!checkpoint && editingMessageId.value) {
      checkpoint = findParentCheckpointForMessage(
        editingMessageId.value,
        editDraft.value,
      );
      if (checkpoint) editCheckpoint.value = checkpoint;
    }
    if (!checkpoint) {
      options.onLocalError?.(
        "未找到该消息之前可恢复的检查点，无法安全创建分支",
      );
      return;
    }
    const draftText = editDraft.value;
    cancelEdit();
    await options.session.fork(
      checkpoint,
      draftText,
      options.recursionLimit.value,
    );
  }

  async function retryMessage(id: string) {
    await edit(id, "");
    if (!disposed && editCheckpoint.value) {
      const ok = await options.session.fork(editCheckpoint.value);
      if (ok) {
        cancelEdit();
      }
    }
  }

  async function forkToNewThread(messageId: string, checkpointId?: string) {
    const thread = currentThreadId.value;
    if (!thread || !messageId || forkingCheckpointId.value) return;
    if (options.session.busy.value) return;

    forkingCheckpointId.value = checkpointId || messageId;
    options.onLocalError?.("");
    try {
      let resolvedCheckpointId: string | undefined =
        checkpointId || findForkCheckpointForMessage(messageId);

      if (!resolvedCheckpointId) {
        let pageCount = 0;
        while (!resolvedCheckpointId && pageCount < 5) {
          pageCount++;
          const oldestCheckpoint =
            history.value[history.value.length - 1]?.checkpoint;
          try {
            const rows = await options.session.service.history(
              thread,
              oldestCheckpoint,
              50,
            );
            if (disposed || !rows || rows.length === 0) break;
            const existingIds = new Set(
              history.value
                .map((s) => s.checkpoint?.checkpoint_id)
                .filter(Boolean),
            );
            const newRows = rows.filter(
              (r) =>
                r.checkpoint?.checkpoint_id &&
                !existingIds.has(r.checkpoint.checkpoint_id),
            );
            if (newRows.length === 0) break;
            history.value = [...history.value, ...newRows];
            resolvedCheckpointId = findForkCheckpointForMessage(messageId);
          } catch {
            break;
          }
        }
      }

      if (!resolvedCheckpointId) {
        const allMsgs = getDisplayedMessages();
        const targetIndex = allMsgs.findIndex(
          (m) => m.id === messageId || (m as any).key === messageId,
        );
        const subsequentMsgs =
          targetIndex >= 0 ? allMsgs.slice(targetIndex + 1) : [];
        const hasSubsequentHuman = subsequentMsgs.some(
          (m) =>
            m.type === "human" ||
            (m as any).role === "user" ||
            (m as any).role === "human",
        );
        const isLatestTurn = targetIndex === -1 || !hasSubsequentHuman;
        if (isLatestTurn) {
          resolvedCheckpointId =
            history.value[0]?.checkpoint?.checkpoint_id || undefined;
          if (!resolvedCheckpointId) {
            try {
              const currentState = await options.session.service.state(thread);
              resolvedCheckpointId =
                currentState?.checkpoint?.checkpoint_id ||
                (currentState as any)?.checkpoint_id ||
                undefined;
            } catch {
              /* ignore state fetch error */
            }
          }
        }
      }

      if (
        !resolvedCheckpointId &&
        history.value.length === 1 &&
        history.value[0]?.checkpoint?.checkpoint_id
      ) {
        resolvedCheckpointId =
          history.value[0].checkpoint.checkpoint_id || undefined;
      }

      if (!resolvedCheckpointId) {
        throw new Error(
          "未找到该轮次有效的历史快照，无法创建分支（请刷新后重试）",
        );
      }

      const sessionService = createSessionService(
        createLanggraphAuthorizedFetch(),
        options.projectId,
      );
      const newTitle = increasedForkTitle(options.threadTitle);
      const target = await sessionService.fork(
        thread,
        resolvedCheckpointId,
        newTitle,
      );
      if (!target?.thread_id) {
        throw new Error("未能获取新分支会话 ID");
      }
      options.onForkThread?.(target.thread_id);
      options.onRefresh?.();
    } catch (cause) {
      options.onLocalError?.(
        cause instanceof Error ? cause.message : "创建分支失败",
      );
    } finally {
      forkingCheckpointId.value = undefined;
    }
  }

  return {
    history,
    historyLoading,
    hasMoreHistory,
    latestHistoryMessages,
    editDraft,
    editingMessageId,
    editCheckpoint,
    editLoading,
    forkingCheckpointId,
    cancelEdit,
    loadHistory,
    edit,
    submitEditedBranch,
    retryMessage,
    forkToNewThread,
    findParentCheckpointForMessage,
    findForkCheckpointForMessage,
  };
}
