import type { Message } from "@langchain/langgraph-sdk";

/**
 * Extracts a string summary from a message's content, supporting multimodal (text, image, file, etc.).
 * - If text is present, returns the joined text.
 * - If not, returns a label for the first non-text modality (e.g., 'Image', 'Other').
 * - If unknown, returns 'Multimodal message'.
 */
export function getContentString(content: Message["content"]): string {
  if (typeof content === "string") return content;
  const texts = content
    .filter((c): c is { type: "text"; text: string } => c.type === "text")
    .map((c) => c.text);
  return texts.join(" ");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeNewlines(value: string): string {
  return value.replace(/\r\n?/g, "\n");
}

function decodeEscapedText(value: string): string {
  const hasActualNewline = value.includes("\n");
  const escapedNewlineCount = (value.match(/\\n/g) || []).length;
  if (hasActualNewline || escapedNewlineCount < 2) {
    return value;
  }
  return value
    .replace(/\\r\\n/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, "\\");
}

function tryParseJsonString(value: string): unknown {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const looksLikeJson =
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]")) ||
    (trimmed.startsWith('"') && trimmed.endsWith('"'));
  if (!looksLikeJson) {
    return null;
  }
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function scoreTextCandidate(value: string): number {
  const text = value.trim();
  if (!text) {
    return Number.NEGATIVE_INFINITY;
  }
  let score = 0;
  if (text.includes("\n#") || text.startsWith("#")) score += 5;
  if (/\n[-*+]\s+/.test(text)) score += 3;
  if (/\n\d+\.\s+/.test(text)) score += 3;
  if (text.includes("```")) score += 3;
  if (/\[[^\]]+\]\([^)]+\)/.test(text)) score += 2;
  if (/\|.+\|/.test(text)) score += 2;
  if (text.length >= 120) score += 1;
  if (text.length >= 300) score += 1;
  if (text.length >= 600) score += 1;
  if (/request_id|response_time|score/i.test(text)) score -= 2;
  return score;
}

function pickBestCandidate(candidates: string[]): string {
  if (candidates.length === 0) {
    return "";
  }

  const uniqueCandidates = Array.from(
    new Set(candidates.map((item) => item.trim()).filter(Boolean)),
  );
  if (uniqueCandidates.length === 0) {
    return "";
  }
  if (uniqueCandidates.length === 1) {
    return uniqueCandidates[0];
  }

  return uniqueCandidates.sort((a, b) => {
    const scoreDiff = scoreTextCandidate(b) - scoreTextCandidate(a);
    if (scoreDiff !== 0) {
      return scoreDiff;
    }
    return b.length - a.length;
  })[0];
}

function extractToolResultText(value: unknown, depth = 0): string {
  if (depth > 6 || value == null) {
    return "";
  }

  if (typeof value === "string") {
    const decoded = decodeEscapedText(value);
    const parsed = tryParseJsonString(decoded);
    if (parsed != null) {
      const extracted = extractToolResultText(parsed, depth + 1);
      if (extracted.trim()) {
        return extracted;
      }
    }
    return decoded;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    const extractedFromMessageShape = getContentString(value as Message["content"]);
    if (extractedFromMessageShape.trim()) {
      const parsedMessageShape = extractToolResultText(extractedFromMessageShape, depth + 1);
      if (parsedMessageShape.trim()) {
        return parsedMessageShape;
      }
      return extractedFromMessageShape;
    }
    const chunks = value
      .map((item) => extractToolResultText(item, depth + 1))
      .filter((item) => item.trim());
    if (chunks.length > 0) {
      return chunks.join("\n\n");
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }

  if (isRecord(value)) {
    if (
      (value.type === "text" ||
        value.type === "output_text" ||
        value.type === "input_text" ||
        value.type === "markdown") &&
      typeof value.text === "string"
    ) {
      return value.text;
    }

    if (
      (value.type === "text" ||
        value.type === "output_text" ||
        value.type === "input_text" ||
        value.type === "markdown") &&
      isRecord(value.text) &&
      typeof value.text.value === "string"
    ) {
      return value.text.value;
    }

    const priorityKeys = [
      "content",
      "answer",
      "results",
      "result",
      "output",
      "text",
      "message",
      "response",
      "value",
      "kwargs",
      "messages",
      "data",
      "payload",
      "body",
      "artifact",
      "stdout",
      "observation",
      "details",
    ] as const;

    for (const key of priorityKeys) {
      if (!(key in value)) {
        continue;
      }
      const extracted = extractToolResultText(value[key], depth + 1);
      if (extracted.trim()) {
        return extracted;
      }
    }

    const scannedValues = Object.values(value)
      .map((nestedValue) => extractToolResultText(nestedValue, depth + 1))
      .filter((item) => item.trim());
    if (scannedValues.length > 0) {
      return pickBestCandidate(scannedValues);
    }

    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }

  return String(value);
}

function unwrapOuterFence(value: string): string {
  let current = value.trim();
  for (let i = 0; i < 3; i += 1) {
    const fencedMatch = current.match(/^```([a-z0-9_-]+)?\s*\n?([\s\S]*?)\n?```$/i);
    if (!fencedMatch) {
      break;
    }
    current = (fencedMatch[2] ?? "").trim();
  }
  return current;
}

export function getToolResultString(content: Message["content"]): string {
  const extracted = extractToolResultText(content);
  if (!extracted.trim()) {
    return "";
  }
  return unwrapOuterFence(normalizeNewlines(extracted));
}
