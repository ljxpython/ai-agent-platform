import type { BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/langgraph-sdk/stream";
import {
  isValidImageRef,
  type RuntimeImageRef,
} from "@/services/threads/images.service";
import {
  isValidFileRef,
  type RuntimeFileRef,
} from "@/services/threads/files.service";

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
  imageRef?: RuntimeImageRef;
  fileRef?: RuntimeFileRef;
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

export const WORKSPACE_IMAGE_PATH_REGEX =
  /\/workspace\/(?:charts|generated|uploads|outputs)\/[a-zA-Z0-9_-]+\.(?:png|jpg|jpeg|webp)/gi;

/**
 * 提取文本中的多行代码块区间（```...``` 或 ~~~...~~~）与普通非图片超链接 URL。
 * 处于多行代码块内部或普通链接 URL 的路径不应触发图片生成。
 */
export function getFencedCodeAndLinkRanges(text: string): Array<[number, number]> {
  if (!text) return [];
  const ranges: Array<[number, number]> = [];

  // 1. 多行代码块：```...``` 或 ~~~...~~~
  const codeBlockRegex = /(```+|~~~+)[\s\S]*?(?:\1|$)/g;
  let match: RegExpExecArray | null;
  while ((match = codeBlockRegex.exec(text)) !== null) {
    ranges.push([match.index, match.index + match[0].length]);
  }

  // 2. 普通 Markdown 链接 [text](url)，但排除图片语法 ![alt](url)
  const linkRegex = /(?:^|[^!])\[[^\]]*\]\(([^)\s]+)\)/g;
  while ((match = linkRegex.exec(text)) !== null) {
    const fullMatch = match[0];
    const url = match[1];
    if (url) {
      const urlOffset = fullMatch.lastIndexOf(`(${url})`) + 1;
      const start = match.index + urlOffset;
      ranges.push([start, start + url.length]);
    }
  }

  return ranges;
}

export const getMarkdownProtectedRanges = getFencedCodeAndLinkRanges;

export function isOffsetProtected(
  start: number,
  end: number,
  ranges: Array<[number, number]>,
): boolean {
  return ranges.some(([rStart, rEnd]) => start >= rStart && end <= rEnd);
}

export function extractWorkspaceImageRefs(text: string): RuntimeImageRef[] {
  if (!text || typeof text !== "string") return [];
  const protectedRanges = getFencedCodeAndLinkRanges(text);
  const matches: string[] = [];
  let match: RegExpExecArray | null;
  WORKSPACE_IMAGE_PATH_REGEX.lastIndex = 0;
  while ((match = WORKSPACE_IMAGE_PATH_REGEX.exec(text)) !== null) {
    const start = match.index;
    const end = start + match[0].length;
    if (!isOffsetProtected(start, end, protectedRanges)) {
      matches.push(match[0]);
    }
  }
  if (matches.length === 0) return [];
  const uniquePaths = Array.from(new Set(matches));
  return uniquePaths.map((p) => {
    const lower = p.toLowerCase();
    const ext = lower.endsWith(".png")
      ? "png"
      : lower.endsWith(".webp")
        ? "webp"
        : "jpeg";
    return {
      version: 1,
      path: p,
      mime_type: `image/${ext}` as RuntimeImageRef["mime_type"],
      size_bytes: 1,
      sha256: "0".repeat(64),
    };
  });
}

export const WORKSPACE_CHART_PATH_REGEX = WORKSPACE_IMAGE_PATH_REGEX;
export const extractChartWeakImageRefs = extractWorkspaceImageRefs;

export function contentItems(
  content: unknown,
  key: string,
): ContentItem[] {
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
        if (block.extras && typeof block.extras === "object") {
          const runtimeImage = (block.extras as Record<string, unknown>).runtime_image;
          if (isValidImageRef(runtimeImage)) {
            items.push({
              key: itemKey,
              kind: "image",
              text: String(block.text ?? ""),
              imageRef: runtimeImage,
            });
            return;
          }
          const runtimeFile = (block.extras as Record<string, unknown>).runtime_file;
          if (isValidFileRef(runtimeFile)) {
            items.push({
              key: itemKey,
              kind: "file",
              text: String(block.text ?? ""),
              fileRef: runtimeFile,
            });
            return;
          }
        }
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

  function cleanLeadingOrphanLineBreak(text: string): string {
    return text.replace(/^([\u4e00-\u9fa5\w])\r?\n(?!\r?\n)([\u4e00-\u9fa5\w])/g, "$1$2");
  }

  const consolidated: ContentItem[] = [];
  for (const item of items) {
    const last = consolidated[consolidated.length - 1];
    if (item.kind === "text" && last && last.kind === "text") {
      last.text += item.text;
      last.text = cleanLeadingOrphanLineBreak(last.text);
    } else {
      consolidated.push(
        item.kind === "text"
          ? { ...item, text: cleanLeadingOrphanLineBreak(item.text) }
          : { ...item },
      );
    }
  }

  // Markdown 图片语法（带或不带 alt）、行内代码反引号包裹的路径、或裸路径
  // group 1: Markdown 图片路径
  // group 2: 行内代码反引号
  // group 4: 行内代码反引号内的图片路径
  // group 5: 裸路径
  const INLINE_IMAGE_BLOCK_REGEX =
    /!\[[^\]]*\]\((\/workspace\/(?:charts|generated|uploads|outputs)\/[a-zA-Z0-9_-]+\.(?:png|jpg|jpeg|webp))\)|(`+)([^`\n]*?(\/workspace\/(?:charts|generated|uploads|outputs)\/[a-zA-Z0-9_-]+\.(?:png|jpg|jpeg|webp))[^`\n]*?)\2|(\/workspace\/(?:charts|generated|uploads|outputs)\/[a-zA-Z0-9_-]+\.(?:png|jpg|jpeg|webp))/gi;

  /** 把一段含 workspace 图片路径的文本切成有序的文本块 + 图片块序列 */
  function splitTextByImages(
    item: ContentItem,
    existingImagePaths: Set<string>,
  ): ContentItem[] {
    const { text, key } = item;
    const protectedRanges = getFencedCodeAndLinkRanges(text);
    const segments: ContentItem[] = [];
    let lastIndex = 0;
    let imgIdx = 0;
    let match: RegExpExecArray | null;
    INLINE_IMAGE_BLOCK_REGEX.lastIndex = 0;

    while ((match = INLINE_IMAGE_BLOCK_REGEX.exec(text)) !== null) {
      const matchStart = match.index;
      const matchEnd = matchStart + match[0].length;

      // 如果处于多行代码块或普通链接保护区间，跳过不处理
      if (isOffsetProtected(matchStart, matchEnd, protectedRanges)) {
        continue;
      }

      const isCodeSpanImage = Boolean(match[2]);
      const imagePath = match[1] ?? match[4] ?? match[5];
      if (!imagePath) continue;

      if (isCodeSpanImage) {
        // 行内反引号包裹的路径：保留完整代码文本，并将图片卡片紧随其后放在该路径下方
        const before = text.slice(lastIndex, matchEnd).trimEnd();
        if (before) {
          segments.push({ key: `${key}:seg:${imgIdx}:pre`, kind: "text", text: before });
        }
        lastIndex = matchEnd;
      } else {
        // 显式 Markdown 图片或裸路径：将标记从文本中剥离，原位插入图片块
        const before = text.slice(lastIndex, matchStart).trimEnd();
        if (before) {
          segments.push({ key: `${key}:seg:${imgIdx}:pre`, kind: "text", text: before });
        }
        lastIndex = matchEnd;
      }

      // 图片块（已出现过的路径跳过，避免重复渲染）
      if (!existingImagePaths.has(imagePath)) {
        existingImagePaths.add(imagePath);
        const lower = imagePath.toLowerCase();
        const ext = lower.endsWith(".png") ? "png" : lower.endsWith(".webp") ? "webp" : "jpeg";
        segments.push({
          key: `${key}:img:${imgIdx}`,
          kind: "image",
          text: imagePath,
          imageRef: {
            version: 1,
            path: imagePath,
            mime_type: `image/${ext}` as RuntimeImageRef["mime_type"],
            size_bytes: 1,
            sha256: "0".repeat(64),
          },
        });
      }

      imgIdx++;
    }

    // 图片后剩余的文本段
    const tail = text.slice(lastIndex).trimStart();
    if (tail) {
      segments.push({ key: `${key}:seg:${imgIdx}:post`, kind: "text", text: tail });
    }

    return segments.length > 0 ? segments : [item];
  }

  const result: ContentItem[] = [];
  const existingImagePaths = new Set<string>();
  for (const item of consolidated) {
    if (item.kind === "image" && item.imageRef?.path) {
      existingImagePaths.add(item.imageRef.path);
    }
  }

  for (const item of consolidated) {
    WORKSPACE_IMAGE_PATH_REGEX.lastIndex = 0;
    if (item.kind === "text" && item.text && WORKSPACE_IMAGE_PATH_REGEX.test(item.text)) {
      result.push(...splitTextByImages(item, existingImagePaths));
    } else {
      result.push(item);
    }
  }

  return result;
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
  function isInterruptError(err: unknown): boolean {
    if (typeof err !== "string") return false;
    return err.includes("Interrupt(") || err.includes("GraphInterrupt");
  }

  function tool(id: string, name: string, input: unknown): ToolItem {
    shown.add(id);
    const call = callMap.get(id);
    const result = results.get(id);
    const resolvedName = call?.name ?? name;
    const isClarification = resolvedName === "request_information";

    const resultObj = asObject(result);
    const hasResult = Boolean(result);
    const resultIsError = hasResult && resultObj.status === "error";
    const isInterrupt = isInterruptError(call?.error);
    let rawError = call?.error;
    if (isInterrupt) {
      rawError = undefined;
    }

    let status: "running" | "finished" | "error" | "incomplete";
    if (hasResult) {
      status = resultIsError ? "error" : "finished";
    } else if (rawError) {
      status = "error";
    } else if (call?.status && call.status !== "error") {
      status = call.status;
    } else if (isClarification || isInterrupt) {
      status = "running";
    } else {
      status = call?.status ?? "running";
    }

    const isPending = isClarification || isInterrupt;

    return {
      key: `${prefix}:tool:${id}`,
      id,
      name: resolvedName,
      input: call?.input ?? input,
      output: call?.output ?? result?.content,
      artifact: resultObj.artifact,
      status: status === "running" && !running && !isPending ? "incomplete" : status,
      error: rawError,
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
      if (namespace.length === 0 && !requestedIds.has(call.callId)) {
        continue;
      }
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

export function extractRuntimeImages(contentOrArtifact: unknown): RuntimeImageRef[] {
  const refs: RuntimeImageRef[] = [];
  const seen = new Set<string>();

  function add(ref: unknown) {
    if (isValidImageRef(ref)) {
      const key = `${ref.path}:${ref.sha256}`;
      if (!seen.has(key)) {
        seen.add(key);
        refs.push(ref);
      }
    }
  }

  function walk(val: unknown) {
    if (!val || typeof val !== "object") return;
    if (isValidImageRef(val)) {
      add(val);
      return;
    }
    if (Array.isArray(val)) {
      for (const item of val) walk(item);
      return;
    }
    const obj = val as Record<string, unknown>;
    if (obj.extras && typeof obj.extras === "object") {
      const extras = obj.extras as Record<string, unknown>;
      if (extras.runtime_image) {
        add(extras.runtime_image);
      }
    }
    if (Array.isArray(obj.runtime_images)) {
      for (const item of obj.runtime_images) add(item);
    }
    const structured = obj.structured_content || obj.structuredContent;
    if (structured && typeof structured === "object") {
      const sObj = structured as Record<string, unknown>;
      if (Array.isArray(sObj.runtime_images)) {
        for (const item of sObj.runtime_images) add(item);
      }
    }
    for (const key of ["artifact", "content"]) {
      if (obj[key]) walk(obj[key]);
    }
  }

  walk(contentOrArtifact);
  return refs;
}
