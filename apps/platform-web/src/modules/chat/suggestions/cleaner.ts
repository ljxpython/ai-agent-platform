import type { SuggestionMessage } from "./types";

const MAX_MESSAGES = 6;
const MAX_SINGLE_MESSAGE_CHARS = 4000;
const MAX_TOTAL_CHARS = 12000;

const THINK_TAG_REGEX =
  /<(?:think|thinking)>[\s\S]*?(?:<\/(?:think|thinking)>|$)/gi;

/**
 * 剥离文本中的思维链标签内容 (<think>...</think>)
 */
export function stripThinkingText(text: string): string {
  if (!text || typeof text !== "string") {
    return "";
  }
  return text.replace(THINK_TAG_REGEX, "").trim();
}

/**
 * 从消息内容字段中提取纯文本正文，剥离思维链、图片附件等非纯文本块
 */
export function extractPureMessageText(content: unknown): string {
  if (typeof content === "string") {
    return stripThinkingText(content);
  }

  if (Array.isArray(content)) {
    const textParts: string[] = [];
    for (const block of content) {
      if (!block || typeof block !== "object") {
        continue;
      }
      const b = block as Record<string, unknown>;
      // 忽略显式的思维链、多模态图片、文件等块
      if (
        b.type === "reasoning" ||
        b.type === "image" ||
        b.type === "image_url" ||
        b.type === "file"
      ) {
        continue;
      }
      if (typeof b.text === "string") {
        const cleaned = stripThinkingText(b.text);
        if (cleaned) {
          textParts.push(cleaned);
        }
      } else if (typeof b.content === "string") {
        const cleaned = stripThinkingText(b.content);
        if (cleaned) {
          textParts.push(cleaned);
        }
      }
    }
    return textParts.join("\n\n").trim();
  }

  return "";
}

/**
 * 将前端消息转化为后端要求的标准清洗消息数组：
 * 1. 过滤非 user/assistant 消息（如 tool, system）
 * 2. 剥离思维链与多模态附件
 * 3. 截取最近至多 6 条
 * 4. 单条不超过 4000 字符，总字符不超过 12000 字符
 * 5. 对象严格只包含 { role, content } 两个键
 */
export function extractRecentSuggestionMessages(
  messages: readonly unknown[],
  maxCount = MAX_MESSAGES,
): SuggestionMessage[] {
  if (!Array.isArray(messages) || messages.length === 0) {
    return [];
  }

  const rawExtracted: SuggestionMessage[] = [];

  for (const item of messages) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const msg = item as Record<string, unknown>;

    // 确定角色类型
    let role: "user" | "assistant" | null = null;
    const rawType =
      (typeof msg._getType === "function" ? msg._getType() : undefined) ??
      msg.type ??
      msg.role;

    if (rawType === "human" || rawType === "user") {
      role = "user";
    } else if (rawType === "ai" || rawType === "assistant") {
      role = "assistant";
    }

    if (!role) {
      continue;
    }

    // 提取纯文本
    let text = extractPureMessageText(msg.content);
    if (!text && typeof msg.text === "string") {
      text = stripThinkingText(msg.text);
    }

    if (!text) {
      continue;
    }

    // 单条安全截断
    if (text.length > MAX_SINGLE_MESSAGE_CHARS) {
      text = text.slice(0, MAX_SINGLE_MESSAGE_CHARS);
    }

    rawExtracted.push({ role, content: text });
  }

  // 截取最近的 maxCount 条
  const recent = rawExtracted.slice(-maxCount);
  if (recent.length === 0) {
    return [];
  }

  // 检查并确保总字符数不超过 12000。如果超长，逆向优先保留最近的消息
  let totalChars = 0;
  const resultReversed: SuggestionMessage[] = [];

  for (let i = recent.length - 1; i >= 0; i--) {
    const item = recent[i]!;
    if (totalChars + item.content.length <= MAX_TOTAL_CHARS) {
      resultReversed.push({ role: item.role, content: item.content });
      totalChars += item.content.length;
    } else {
      const remainingQuota = MAX_TOTAL_CHARS - totalChars;
      if (remainingQuota > 50) {
        // 如果剩余预算足够容纳一段有效文本，做安全切片
        resultReversed.push({
          role: item.role,
          content: item.content.slice(0, remainingQuota),
        });
        totalChars += remainingQuota;
      }
      break;
    }
  }

  return resultReversed.reverse();
}
