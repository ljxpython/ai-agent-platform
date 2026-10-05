import { computed, shallowReactive, shallowRef } from "vue";
import { useChannelEffect, useMessages, type AnyStream } from "@langchain/vue";
import {
  coerceMessageLikeToMessage,
  type BaseMessage,
} from "@langchain/core/messages";

const coerce = (value: unknown): BaseMessage[] =>
  Array.isArray(value)
    ? value.map((message) => coerceMessageLikeToMessage(message))
    : [];

export function getMsgType(msg: BaseMessage): string {
  const raw = msg as unknown as { _getType?: () => string; role?: string };
  return (
    msg.type ||
    (typeof raw._getType === "function" ? raw._getType() : "") ||
    raw.role ||
    ""
  );
}

export function hasToolCalls(msg: BaseMessage): boolean {
  const raw = msg as unknown as Record<string, unknown>;
  return Array.isArray(raw.tool_calls) && raw.tool_calls.length > 0;
}

/**
 * 1. 融入思维链（Live Reasoning Deltas）
 */
export function injectLiveReasonings(
  messages: readonly BaseMessage[],
  liveReasonings: Map<string, string>,
  activeMessageId: string | undefined,
  isLoading: boolean,
  owned: Map<string, BaseMessage>,
): BaseMessage[] {
  const current = messages.map((message) => {
    if (!isLoading && message.id && owned.has(message.id)) {
      return owned.get(message.id)!;
    }
    if (isLoading && message.id) {
      const liveReasoning =
        liveReasonings.get(message.id) ?? liveReasonings.get("__live__");
      if (liveReasoning) {
        const raw = message as unknown as Record<string, unknown>;
        const additionalKwargs =
          (raw.additional_kwargs as Record<string, unknown> | undefined) ?? {};
        if (
          !additionalKwargs.reasoning_content &&
          !additionalKwargs.reasoning
        ) {
          return coerceMessageLikeToMessage({
            ...raw,
            additional_kwargs: {
              ...additionalKwargs,
              reasoning_content: liveReasoning,
            },
          } as any);
        }
      }
    }
    return message;
  });

  if (isLoading && liveReasonings.size > 0) {
    const activeReasoning =
      (activeMessageId ? liveReasonings.get(activeMessageId) : undefined) ??
      liveReasonings.get("__live__") ??
      [...liveReasonings.values()][liveReasonings.size - 1];
    if (activeReasoning) {
      const lastMsg = current[current.length - 1];
      const lastIsAi =
        lastMsg &&
        (lastMsg.type === "ai" ||
          (lastMsg as unknown as { _getType?: () => string })._getType?.() ===
            "ai");
      if (!lastIsAi) {
        current.push(
          coerceMessageLikeToMessage({
            id: activeMessageId || "streaming-ai-live",
            type: "ai",
            content: "",
            additional_kwargs: {
              reasoning_content: activeReasoning,
            },
          } as any),
        );
      }
    }
  }

  return current;
}

/**
 * 2. 权威快照与流式增量正序对齐
 */
export function reconcileSnapshotWithStream(
  snapshot: readonly BaseMessage[],
  current: readonly BaseMessage[],
): BaseMessage[] {
  if (snapshot.length === 0) {
    return [...current];
  }
  const currentById = new Map<string, BaseMessage>();
  for (const msg of current) {
    if (msg.id) currentById.set(msg.id, msg);
  }
  // 严格以 snapshot 权威检查点时间线为基底（保留正序），并融入 current 中的实时增强
  const merged = snapshot.map(
    (msg) => (msg.id && currentById.get(msg.id)) || msg,
  );
  // 将 current 中尚未落盘到 snapshot 的最新增量消息追加在末尾
  const snapshotIds = new Set(snapshot.map((msg) => msg.id).filter(Boolean));
  for (const msg of current) {
    if (!msg.id || !snapshotIds.has(msg.id)) {
      merged.push(msg);
    }
  }
  return merged;
}

/**
 * 3. 提取子智能体委派任务输入（防止向父/根级泄露）
 */
export function extractSubagentTaskInputs(
  merged: readonly BaseMessage[],
  subagentsList: Iterable<{ taskInput?: string }>,
): Set<string> {
  const inputs = new Set<string>();
  for (const agent of subagentsList) {
    if (typeof agent.taskInput === "string" && agent.taskInput.trim()) {
      inputs.add(agent.taskInput.trim());
    }
  }
  for (const msg of merged) {
    const raw = msg as unknown as Record<string, unknown>;
    if (Array.isArray(raw.tool_calls)) {
      for (const tc of raw.tool_calls as Array<{
        name?: string;
        args?: Record<string, unknown>;
      }>) {
        if (tc?.name === "task" && tc.args && typeof tc.args === "object") {
          for (const key of ["description", "prompt", "task", "instructions"]) {
            const val = tc.args[key];
            if (typeof val === "string" && val.trim()) inputs.add(val.trim());
          }
        }
      }
    }
  }
  return inputs;
}

/**
 * SDK 1.10 root projection includes generic (non task/tools) subgraph text.
 * Use exact-scope values to distinguish returned answers from private child text.
 */
export function useTranscriptMessages(
  stream: AnyStream,
  namespace: readonly string[] = [],
) {
  const messages = useMessages(stream, () => ({ namespace }));
  const sources = shallowReactive(new Map<string, readonly string[]>());
  const scopedSnapshot = shallowRef<readonly BaseMessage[]>([]);
  const liveReasonings = shallowReactive(new Map<string, string>());
  let activeMessageId: string | undefined;

  useChannelEffect(stream, ["messages", "values"], {
    target: { namespace },
    replay: true,
    onEvent(event) {
      if (event.method === "values") {
        const value = event.params.data as { messages?: unknown };
        if (Array.isArray(value?.messages)) {
          for (const msg of value.messages) {
            const m = msg as { id?: string };
            if (m?.id && !sources.has(m.id))
              sources.set(m.id, event.params.namespace);
          }
        }
        // Only this exact scope owns the snapshot; a descendant must not replace it.
        if (
          event.params.namespace.length === namespace.length &&
          namespace.every(
            (part, index) => event.params.namespace[index] === part,
          )
        ) {
          if (Array.isArray(value?.messages)) {
            const nextRaw = value.messages as Array<{
              id?: string;
              tool_calls?: unknown[];
            }>;
            const prev = scopedSnapshot.value;
            // 防洪机制：在流式生成中，如果消息总数未变、首尾 ID 相同且末尾 tool_calls 数量一致，跳过高频全量深拷贝
            const isUnchangedDuringStream =
              stream.isLoading.value &&
              prev.length === nextRaw.length &&
              prev.length > 0 &&
              prev[0]?.id === nextRaw[0]?.id &&
              prev[prev.length - 1]?.id === nextRaw[nextRaw.length - 1]?.id &&
              (prev[prev.length - 1] as unknown as { tool_calls?: unknown[] })
                ?.tool_calls?.length ===
                nextRaw[nextRaw.length - 1]?.tool_calls?.length;

            if (!isUnchangedDuringStream) {
              scopedSnapshot.value = coerce(value.messages);
              if (!stream.isLoading.value) {
                liveReasonings.clear();
                activeMessageId = undefined;
              }
            }
          }
        }
        return;
      }
      if (event.method !== "messages") return;
      const data = event.params.data as unknown;
      const items = Array.isArray(data) ? data : [data];
      for (const item of items) {
        if (!item || typeof item !== "object") continue;
        const entry = item as Record<string, unknown>;
        const id = typeof entry.id === "string" ? entry.id : undefined;
        if (id && !sources.has(id)) sources.set(id, event.params.namespace);
        if (entry.event === "message-start" && id) {
          activeMessageId = id;
        }
        if (
          entry.event === "content-block-delta" &&
          entry.delta &&
          typeof entry.delta === "object"
        ) {
          const delta = entry.delta as Record<string, unknown>;
          if (
            delta.type === "reasoning-delta" &&
            typeof delta.reasoning === "string"
          ) {
            const targetId =
              activeMessageId ??
              (messages.value[messages.value.length - 1]?.id || "__live__");
            const prev = liveReasonings.get(targetId) ?? "";
            liveReasonings.set(targetId, prev + delta.reasoning);
          }
        }
      }
    },
  });

  return computed(() => {
    const rawValues =
      namespace.length === 0 &&
      Array.isArray((stream.values.value as { messages?: unknown })?.messages)
        ? coerce((stream.values.value as { messages?: unknown }).messages)
        : [];
    const snapshot = scopedSnapshot.value.length
      ? scopedSnapshot.value
      : rawValues;
    const owned = new Map(
      snapshot
        .filter((message) => message.id)
        .map((message) => [message.id!, message]),
    );

    // 1. 融入思维链实时增量
    const current = injectLiveReasonings(
      messages.value,
      liveReasonings,
      activeMessageId,
      stream.isLoading.value,
      owned,
    );

    // 2. 权威快照正序合并
    const merged = reconcileSnapshotWithStream(snapshot, current);

    // 3. 提取子智能体防泄漏白名单
    const subagentsList = [...stream.subagents.value.values()];
    const subagents = subagentsList.map((agent) => agent.namespace);
    const subagentTaskInputs = extractSubagentTaskInputs(merged, subagentsList);

    const children = [
      ...stream.subgraphs.value.values(),
      ...stream.subagents.value.values(),
    ]
      .map((graph) => graph.namespace)
      .filter(
        (child) =>
          child.length > namespace.length &&
          namespace.every((part, index) => child[index] === part),
      );

    const isSameNamespace = (source?: readonly string[]) =>
      !source ||
      (source.length === namespace.length &&
        source.every((part, index) => namespace[index] === part));

    // 4. 重试中间状态识别
    const supersededRetryIds = new Set<string>();
    let pendingToollessAiId: string | undefined;
    for (const msg of merged) {
      const type = getMsgType(msg);
      const source = msg.id ? sources.get(msg.id) : undefined;
      if (!isSameNamespace(source)) continue;
      if (type === "human" || type === "tool") {
        pendingToollessAiId = undefined;
      } else if (type === "ai") {
        if (pendingToollessAiId) supersededRetryIds.add(pendingToollessAiId);
        pendingToollessAiId =
          msg.id && !owned.has(msg.id) && !hasToolCalls(msg)
            ? msg.id
            : undefined;
      }
    }

    const lastCurrentHuman = [...merged]
      .reverse()
      .find((m) => getMsgType(m) === "human");
    const hasSnapshotCaughtUp =
      snapshot.length > 0 &&
      (!lastCurrentHuman?.id || owned.has(lastCurrentHuman.id));

    // 5. 过滤与管道最终输出
    return merged.filter((message) => {
      if (message.id && owned.has(message.id)) return true;
      if (message.id && supersededRetryIds.has(message.id)) return false;

      const source = message.id ? sources.get(message.id) : undefined;

      if (
        !stream.isLoading.value &&
        hasSnapshotCaughtUp &&
        isSameNamespace(source)
      ) {
        return false;
      }

      const isFromSubagent =
        !!source &&
        source.length > namespace.length &&
        (subagents.some(
          (sub) =>
            sub.length > namespace.length &&
            sub.length >= source.length &&
            source.every((part, index) => sub[index] === part),
        ) ||
          source
            .slice(namespace.length)
            .some(
              (part) => part.startsWith("tools:") || part.startsWith("task:"),
            ));
      if (isFromSubagent) return false;

      const isHuman = getMsgType(message) === "human";
      if (isHuman) {
        const text =
          typeof message.content === "string"
            ? message.content.trim()
            : Array.isArray(message.content)
              ? message.content
                  .map((b) =>
                    b && typeof b === "object" && "text" in b
                      ? String((b as { text?: unknown }).text ?? "")
                      : "",
                  )
                  .join("")
                  .trim()
              : "";
        if (text && subagentTaskInputs.has(text) && namespace.length === 0) {
          return false;
        }
        if (
          source &&
          children.some((child) =>
            child.every((part, index) => source[index] === part),
          )
        ) {
          return false;
        }
      }

      if (hasToolCalls(message)) return true;
      if (message.type === "tool") return true;

      return (
        !source ||
        !children.some((child) =>
          child.every((part, index) => source[index] === part),
        )
      );
    });
  });
}
