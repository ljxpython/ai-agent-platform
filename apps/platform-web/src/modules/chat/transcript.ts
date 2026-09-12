import type { BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/langgraph-sdk/stream";

export function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function readable(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2) ?? "";
}
export function safeContentUrl(
  value: unknown,
  image = false,
): string | undefined {
  if (typeof value !== "string") return undefined;
  if (
    image &&
    /^data:image\/(png|jpeg|gif|webp);base64,[a-z0-9+/=\s]+$/i.test(value)
  )
    return value;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}
export type ContentItem = {
  key: string;
  kind: "text" | "reasoning" | "image" | "file" | "loading" | "unknown";
  text: string;
  url?: string;
};
export type ToolItem = {
  key: string;
  id: string;
  name: string;
  input: unknown;
  output: unknown;
  artifact?: unknown;
  status: "running" | "finished" | "error" | "incomplete";
  error?: string;
};
export type MessageItem = {
  key: string;
  id?: string;
  role: string;
  blocks: ContentItem[];
  tools: ToolItem[];
};
export type Turn = {
  key: string;
  user?: MessageItem;
  work: MessageItem[];
  answer: MessageItem[];
};

export function extractReasoningFromMessage(message: BaseMessage): string {
  const raw = message as unknown as Record<string, unknown>;
  const extra = raw.additional_kwargs;
  if (extra && typeof extra === "object" && typeof (extra as Record<string, unknown>).reasoning_content === "string") {
    const text = ((extra as Record<string, unknown>).reasoning_content as string).trim();
    if (text) return text;
  }
  const respMeta = raw.response_metadata;
  if (respMeta && typeof respMeta === "object" && typeof (respMeta as Record<string, unknown>).reasoning_content === "string") {
    const text = ((respMeta as Record<string, unknown>).reasoning_content as string).trim();
    if (text) return text;
  }
  return "";
}

export function contentItems(content: unknown, key: string): ContentItem[] {
  const values =
    typeof content === "string"
      ? [{ type: "text", text: content }]
      : Array.isArray(content)
        ? content
        : [content];
  const items: ContentItem[] = [];
  values
    .filter((value) => value != null)
    .forEach((value, index) => {
      const block =
        typeof value === "string"
          ? { type: "text", text: value }
          : asObject(value);
      const itemKey = `${key}:${index}`;
      if (block.type === "text" || block.type === "text-plain") {
        const text = String(block.text ?? "");
        const thinkMatch = /<(?:think|thinking)>([\s\S]*?)(?:<\/(?:think|thinking)>|$)/i.exec(text);
        if (thinkMatch) {
          const thinkContent = thinkMatch[1].trim();
          const remainder = text.replace(/<(?:think|thinking)>[\s\S]*?(?:<\/(?:think|thinking)>|$)/i, "").trim();
          if (thinkContent) {
            items.push({ key: `${itemKey}:think`, kind: "reasoning", text: thinkContent });
          }
          if (remainder || !thinkContent) {
            items.push({ key: itemKey, kind: "text", text: remainder });
          }
          return;
        }
        items.push({ key: itemKey, kind: "text", text });
        return;
      }
      if (["document", "markdown"].includes(String(block.type)) && typeof block.content === "string") {
        items.push({ key: itemKey, kind: "text", text: block.content });
        return;
      }
      if (block.type === "code" && typeof block.code === "string") {
        const fence = "`".repeat(Math.max(3, ...[...block.code.matchAll(/`+/g)].map(match => match[0].length + 1)));
        items.push({ key: itemKey, kind: "text", text: `${fence}${String(block.language ?? "text").replace(/[^\w-]/g, "")}\n${block.code}\n${fence}` });
        return;
      }
      if (block.type === "reasoning") {
        items.push({
          key: itemKey,
          kind: "reasoning",
          text: readable(block.reasoning ?? block.text ?? block.summary),
        });
        return;
      }
      if (["image", "image_url"].includes(String(block.type))) {
        const image = block.image_url;
        const rawUrl =
          block.url ??
          (typeof image === "string" ? image : asObject(image).url) ??
          (typeof block.data === "string"
            ? `data:${block.mime_type ?? block.mimeType};base64,${block.data}`
            : undefined);
        items.push({
          key: itemKey,
          kind: "image",
          text: String(asObject(block.metadata).name ?? "图片"),
          url: safeContentUrl(rawUrl, true),
        });
        return;
      }
      if (block.type === "file") {
        items.push({
          key: itemKey,
          kind: "file",
          text: String(
            block.filename ?? asObject(block.metadata).filename ?? "文件",
          ),
          url: safeContentUrl(block.url),
        });
        return;
      }
      items.push({ key: itemKey, kind: "unknown", text: readable(value) });
    });
  return items;
}

/** A pure view of SDK messages and calls; no event accumulation or state mutation. */
export function buildTranscript(
  messages: readonly BaseMessage[],
  calls: readonly AssembledToolCall[],
  running: boolean,
  namespace: readonly string[] = [],
): Turn[] {
  const prefix = JSON.stringify(namespace);
  const results = new Map<string, BaseMessage>();
  for (const message of messages) {
    const id = asObject(message).tool_call_id;
    if (message.type === "tool" && typeof id === "string")
      results.set(id, message);
  }
  const callMap = new Map(calls.map((call) => [call.callId, call]));
  const requestedIds = new Set<string>();
  for (const message of messages) {
    const requests = asObject(message).tool_calls;
    if (Array.isArray(requests))
      for (const request of requests) {
        const id = asObject(request).id;
        if (typeof id === "string") requestedIds.add(id);
      }
  }
  const shown = new Set<string>();
  function tool(id: string, name: string, input: unknown): ToolItem {
    shown.add(id);
    const call = callMap.get(id);
    const result = results.get(id);
    const status =
      call?.status ??
      (result
        ? asObject(result).status === "error"
          ? "error"
          : "finished"
        : "running");
    return {
      key: `${prefix}:tool:${id}`,
      id,
      name: call?.name ?? name,
      input: call?.input ?? input,
      output: call?.output ?? result?.content,
      artifact: asObject(result).artifact,
      status: status === "running" && !running ? "incomplete" : status,
      error: call?.error,
    };
  }
  const turns: Turn[] = [];
  let turn: Turn | undefined;
  for (const [index, message] of messages.entries()) {
    const key = `${prefix}:${message.id ?? `position-${index}`}`;
    if (!turn || message.type === "human") {
      turn = { key, work: [], answer: [] };
      turns.push(turn);
    }
    const blocks = message.contentBlocks ?? message.content;
    const parsedBlocks = contentItems(
      Array.isArray(blocks)
        ? blocks.filter(
            (block) =>
              !["tool_call", "tool_call_chunk"].includes(
                String(asObject(block).type),
              ),
          )
        : blocks,
      key,
    );
    const extraReasoning = extractReasoningFromMessage(message);
    if (extraReasoning && !parsedBlocks.some((b) => b.kind === "reasoning")) {
      parsedBlocks.unshift({
        key: `${key}:reasoning:extra`,
        kind: "reasoning",
        text: extraReasoning,
      });
    }
    const item: MessageItem = {
      key,
      id: message.id,
      role: message.type,
      blocks: parsedBlocks,
      tools: [],
    };
    const requested = asObject(message).tool_calls;
    if (Array.isArray(requested))
      for (const [callIndex, raw] of requested.entries()) {
        const call = asObject(raw);
        const id =
          typeof call.id === "string" ? call.id : `${key}:call-${callIndex}`;
        if (!shown.has(id))
          item.tools.push(tool(id, String(call.name ?? "未知工具"), call.args));
      }
    if (message.type === "tool") {
      const id = asObject(message).tool_call_id;
      if (typeof id === "string" && (shown.has(id) || requestedIds.has(id)))
        continue;
      item.blocks = [];
      item.tools = [
        tool(String(id ?? key), message.name ?? "未关联的工具结果", undefined),
      ];
      if (id == null) item.tools[0]!.output = message.content;
      turn.work.push(item);
    } else if (message.type === "human") turn.user = item;
    else {
      turn.work.push(...turn.answer);
      turn.answer = [];
      if (item.tools.length) turn.work.push(item);
      else turn.answer.push(item);
    }
  }
  for (const call of calls)
    if (!shown.has(call.callId)) {
      if (!turn) {
        turn = { key: `${prefix}:tools`, work: [], answer: [] };
        turns.push(turn);
      }
      turn.work.push({
        key: `${prefix}:call:${call.callId}`,
        role: "tool",
        blocks: [],
        tools: [tool(call.callId, call.name, call.input)],
      });
    }
  return turns;
}
