import type { BaseMessage } from "@langchain/core/messages";

export function extractMessageText(raw: unknown): string {
  if (typeof raw === "string") return raw.trim();
  if (Array.isArray(raw)) {
    return raw
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        if (typeof (item as { text?: unknown }).text === "string") {
          return (item as { text: string }).text;
        }
        return "";
      })
      .filter(Boolean)
      .join("\n")
      .trim();
  }
  return "";
}

export function isHumanMessage(m: BaseMessage | null | undefined): boolean {
  if (!m) return false;
  const raw = m as unknown as Record<string, unknown>;
  const type =
    m.type ||
    (typeof (raw._getType as (() => string) | undefined) === "function"
      ? (raw._getType as () => string)()
      : "");
  if (type === "human" || type === "user") return true;
  return raw.role === "human" || raw.role === "user";
}

export function hasOptimisticEchoed(
  list: readonly BaseMessage[],
  optimistic: BaseMessage | null,
): boolean {
  if (!optimistic) return false;
  if (optimistic.id && list.some((m) => m.id === optimistic.id)) return true;
  const optText = extractMessageText(optimistic.content);
  if (!optText) return false;
  return list.some(
    (m) => isHumanMessage(m) && extractMessageText(m.content) === optText,
  );
}

export interface ResolveDisplayedMessagesOptions {
  baseMessages: BaseMessage[];
  snapshotMessages: BaseMessage[] | null;
  recoveredMessages?: BaseMessage[];
  fallbackMessages: BaseMessage[];
  optimisticUserMessage: BaseMessage | null;
  optimisticBaseCount: number;
  isSessionRunning: boolean;
}

export function resolveDisplayedMessages(
  options: ResolveDisplayedMessagesOptions,
): BaseMessage[] {
  const {
    snapshotMessages,
    recoveredMessages,
    fallbackMessages,
    optimisticUserMessage,
    optimisticBaseCount,
    isSessionRunning,
  } = options;

  let base = snapshotMessages ?? options.baseMessages;

  if (!snapshotMessages && recoveredMessages?.length) {
    const recoveredIds = new Set(recoveredMessages.map((m) => m.id));
    base = [
      ...recoveredMessages,
      ...base.filter((m) => !recoveredIds.has(m.id)),
    ];
  }

  // Cached content is only a placeholder until the controller has messages.
  if (!snapshotMessages && base.length === 0) base = fallbackMessages;

  if (!optimisticUserMessage) return base;
  if (hasOptimisticEchoed(base, optimisticUserMessage)) {
    return base;
  }

  // 严格保卫历史消息时序：新发送的乐观消息永远紧随上一轮历史之后，绝不可穿透倒挂进历史轮次中！
  // 若在提交后产生了当前轮次的实时 AI 流式响应，新消息锚定在历史基线之后、当前轮次实时响应之前。
  if (
    isSessionRunning &&
    optimisticBaseCount >= 0 &&
    optimisticBaseCount < base.length
  ) {
    return [
      ...base.slice(0, optimisticBaseCount),
      optimisticUserMessage,
      ...base.slice(optimisticBaseCount),
    ];
  }
  return [...base, optimisticUserMessage];
}
