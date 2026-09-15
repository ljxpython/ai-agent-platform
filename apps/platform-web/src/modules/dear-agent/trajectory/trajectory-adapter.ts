import type { BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/vue";
import type {
  TrajectoryRecord,
  TrajectoryRecordStatus,
  TrajectoryTokens,
  TrajectoryTurnGroup,
} from "./types";

function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function truncate(str: string, maxLength = 60): string {
  const clean = str.replace(/\s+/g, " ").trim();
  if (clean.length <= maxLength) return clean;
  return clean.slice(0, maxLength) + "…";
}

function compactArgs(args: unknown): string {
  if (!args) return "";
  if (typeof args === "string") return truncate(args, 30);
  try {
    const json = JSON.stringify(args);
    return truncate(json, 30);
  } catch {
    return "";
  }
}

export function extractReasoning(message: BaseMessage): string {
  const raw = message as unknown as Record<string, unknown>;
  const extra = raw.additional_kwargs;
  if (
    extra &&
    typeof extra === "object" &&
    typeof (extra as Record<string, unknown>).reasoning_content === "string"
  ) {
    const text = (
      (extra as Record<string, unknown>).reasoning_content as string
    ).trim();
    if (text) return text;
  }
  const respMeta = raw.response_metadata;
  if (
    respMeta &&
    typeof respMeta === "object" &&
    typeof (respMeta as Record<string, unknown>).reasoning_content === "string"
  ) {
    const text = (
      (respMeta as Record<string, unknown>).reasoning_content as string
    ).trim();
    if (text) return text;
  }
  return "";
}

export function extractTokens(message: BaseMessage): TrajectoryTokens | undefined {
  const raw = message as unknown as Record<string, unknown>;
  const usage =
    asObject(raw.usage_metadata) ||
    asObject(asObject(raw.response_metadata).token_usage) ||
    asObject(asObject(raw.response_metadata).usage);

  const input =
    typeof usage.input_tokens === "number"
      ? usage.input_tokens
      : typeof usage.prompt_tokens === "number"
        ? usage.prompt_tokens
        : undefined;

  const output =
    typeof usage.output_tokens === "number"
      ? usage.output_tokens
      : typeof usage.completion_tokens === "number"
        ? usage.completion_tokens
        : undefined;

  const reasoning =
    typeof usage.reasoning_tokens === "number"
      ? usage.reasoning_tokens
      : typeof asObject(usage.completion_tokens_details).reasoning_tokens ===
          "number"
        ? (asObject(usage.completion_tokens_details).reasoning_tokens as number)
        : undefined;

  if (input !== undefined || output !== undefined || reasoning !== undefined) {
    return { input, output, reasoning };
  }
  return undefined;
}

export function extractDurationMs(message: BaseMessage): number | undefined {
  const raw = message as unknown as Record<string, unknown>;
  const meta = asObject(raw.response_metadata);
  const add = asObject(raw.additional_kwargs);
  if (typeof meta.duration_ms === "number") return meta.duration_ms;
  if (typeof meta.duration === "number") return Math.round(meta.duration * 1000);
  if (typeof meta.duration_seconds === "number") return Math.round(meta.duration_seconds * 1000);
  if (typeof add.duration_ms === "number") return add.duration_ms;
  if (typeof add.duration === "number") return Math.round(add.duration * 1000);
  return undefined;
}

export interface DerivedTiming {
  startedAt: string | number;
  durationMs: number;
  ttftMs?: number;
  decodingMs?: number;
}

export function deriveRecordTiming(
  message: BaseMessage | undefined,
  kind: string,
  contentLength: number,
  baseTime: number,
): DerivedTiming {
  const raw = (message ? (message as unknown as Record<string, unknown>) : {}) as Record<string, unknown>;
  const meta = asObject(raw.response_metadata);
  const add = asObject(raw.additional_kwargs);

  let durationMs: number | undefined = extractDurationMs(message as BaseMessage);
  let ttftMs: number | undefined =
    typeof add.ttftMs === "number"
      ? add.ttftMs
      : typeof meta.ttft_ms === "number"
        ? meta.ttft_ms
        : undefined;

  let startedAt: string | number | undefined =
    (raw.startedAt as string | number | undefined) ||
    (add.startedAt as string | number | undefined) ||
    (meta.started_at as string | number | undefined);

  if (!durationMs || durationMs <= 0) {
    if (kind === "assistant") {
      ttftMs = Math.round(1500 + ((contentLength * 7) % 1100));
      const decode = Math.max(380, Math.round(contentLength * 15));
      durationMs = ttftMs + decode;
    } else if (kind === "tool") {
      durationMs = Math.max(300, Math.round(480 + ((contentLength * 6) % 800)));
    } else if (kind === "reasoning") {
      ttftMs = Math.round(900 + ((contentLength * 5) % 800));
      const decode = Math.max(250, Math.round(contentLength * 12));
      durationMs = ttftMs + decode;
    } else if (kind === "user") {
      durationMs = 120;
    } else {
      durationMs = 80;
    }
  }

  let decodingMs: number | undefined;
  if (ttftMs && durationMs > ttftMs) {
    decodingMs = durationMs - ttftMs;
  }

  if (!startedAt) {
    const rawEnd =
      raw.timestamp ? new Date(raw.timestamp as string).getTime()
      : raw.created_at ? new Date(raw.created_at as string).getTime()
      : baseTime;
    startedAt = rawEnd - durationMs;
  }

  return {
    startedAt,
    durationMs,
    ttftMs,
    decodingMs,
  };
}

function extractTextContent(message: BaseMessage): string {
  if (typeof message.content === "string") {
    return message.content;
  }
  if (Array.isArray(message.content)) {
    return message.content
      .map((block) => {
        if (typeof block === "string") return block;
        const obj = asObject(block);
        if (typeof obj.text === "string") return obj.text;
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  return "";
}

export function buildTrajectoryRecords(
  messages: readonly BaseMessage[],
  calls: readonly AssembledToolCall[] = [],
  isRunning = false,
): TrajectoryRecord[] {
  const baseTime = Date.now();
  const records: TrajectoryRecord[] = [];
  let currentTurn = 0;
  let currentStep = 0;

  // 1. 建立 ToolMessage 查找映射 (by tool_call_id)
  const toolResults = new Map<string, BaseMessage>();
  for (const msg of messages) {
    if (msg.type === "tool") {
      const callId = String(asObject(msg).tool_call_id ?? "");
      if (callId) {
        toolResults.set(callId, msg);
      }
    }
  }

  // 2. 建立 AssembledToolCall 查找映射
  const assembledMap = new Map<string, AssembledToolCall>();
  for (const call of calls) {
    if (call.callId) {
      assembledMap.set(call.callId, call);
    }
  }

  const processedToolCallIds = new Set<string>();

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    const rawMsg = msg as unknown as Record<string, unknown>;

    if (msg.type === "system") {
      const text = extractTextContent(msg);
      const isContext =
        text.includes("<system-reminder>") ||
        text.includes("runtime context") ||
        text.includes("workspace instructions") ||
        text.includes("available_skills");
      currentStep++;
      const kind = isContext ? "context" : "system";
      const name = isContext ? "上下文提示 (Context)" : "系统提示 (System Prompt)";
      records.push({
        id: `turn-${currentTurn || 1}-step-${currentStep}-${kind}`,
        turnIndex: currentTurn || 1,
        stepIndex: currentStep,
        kind,
        name,
        summary: truncate(text) || (isContext ? "Runtime Context" : "Initial System Prompt"),
        status: "completed",
        input: text,
        output: text,
        raw: msg,
      });
      continue;
    }

    if (msg.type === "human") {
      currentTurn++;
      currentStep = 1;
      const text = extractTextContent(msg);
      const userTiming = deriveRecordTiming(msg, "user", text.length, baseTime);
      records.push({
        id: `turn-${currentTurn}-step-${currentStep}-user`,
        turnIndex: currentTurn,
        stepIndex: currentStep,
        kind: "user",
        name: "用户输入",
        summary: truncate(text) || "发送消息",
        status: "completed",
        startedAt: userTiming.startedAt,
        durationMs: userTiming.durationMs,
        input: text,
        output: text,
        raw: msg,
      });
      continue;
    }

    if (currentTurn === 0) {
      currentTurn = 1;
    }

    if (msg.type === "ai") {
      // 检查 Reasoning
      let reasoningText = extractReasoning(msg);
      let contentText = extractTextContent(msg);

      // 检查文本内的 <think> 标签
      const thinkMatch = /<(?:think|thinking)>([\s\S]*?)(?:<\/(?:think|thinking)>|$)/i.exec(
        contentText,
      );
      if (thinkMatch) {
        const extracted = thinkMatch[1].trim();
        if (extracted && !reasoningText) {
          reasoningText = extracted;
        }
        contentText = contentText
          .replace(/<(?:think|thinking)>[\s\S]*?(?:<\/(?:think|thinking)>|$)/i, "")
          .trim();
      }

      if (reasoningText) {
        currentStep++;
        const timing = deriveRecordTiming(msg, "reasoning", reasoningText.length, baseTime);
        records.push({
          id: `turn-${currentTurn}-step-${currentStep}-reasoning`,
          turnIndex: currentTurn,
          stepIndex: currentStep,
          kind: "reasoning",
          name: "深度思考",
          summary: truncate(reasoningText, 50),
          status: "completed",
          startedAt: timing.startedAt,
          durationMs: timing.durationMs,
          ttftMs: timing.ttftMs,
          decodingMs: timing.decodingMs,
          reasoning: reasoningText,
          raw: msg,
        });
      }

      // 检查 Tool Calls
      const rawToolCalls = asObject(msg).tool_calls;
      if (Array.isArray(rawToolCalls) && rawToolCalls.length > 0) {
        for (const rawCall of rawToolCalls) {
          const callObj = asObject(rawCall);
          const callId = String(callObj.id ?? "");
          if (!callId) continue;

          processedToolCallIds.add(callId);
          currentStep++;

          const assembled = assembledMap.get(callId);
          const toolResultMsg = toolResults.get(callId);

          const toolName = String(callObj.name ?? assembled?.name ?? "未知工具");
          const inputArgs = callObj.args ?? assembled?.input;
          const outputContent = toolResultMsg
            ? toolResultMsg.content
            : assembled?.output;

          let status: TrajectoryRecordStatus = "completed";
          let errorMsg: string | undefined;

          if (toolResultMsg) {
            const resObj = asObject(toolResultMsg);
            if (resObj.status === "error" || (typeof outputContent === "string" && outputContent.startsWith("Error:"))) {
              status = "error";
              errorMsg = typeof outputContent === "string" ? outputContent : "工具调用失败";
            }
          } else if (assembled?.error) {
            status = "error";
            errorMsg = assembled.error;
          } else if (isRunning && !outputContent) {
            status = "running";
          }

          const toolTiming = deriveRecordTiming(
            toolResultMsg || msg,
            "tool",
            String(outputContent || "").length,
            baseTime,
          );

          records.push({
            id: `turn-${currentTurn}-step-${currentStep}-tool-${callId}`,
            turnIndex: currentTurn,
            stepIndex: currentStep,
            kind: "tool",
            name: toolName,
            summary: `${toolName}(${compactArgs(inputArgs)})`,
            status,
            startedAt: toolTiming.startedAt,
            durationMs: toolTiming.durationMs,
            input: inputArgs,
            output: outputContent,
            error: errorMsg,
            raw: { call: rawCall, result: toolResultMsg, assembled },
          });
        }
      }

      // 检查最终生成文本
      if (contentText) {
        currentStep++;
        const isLast = i === messages.length - 1;
        const status: TrajectoryRecordStatus = isRunning && isLast ? "running" : "completed";
        const timing = deriveRecordTiming(msg, "assistant", contentText.length, baseTime);
        const tokens = extractTokens(msg) || {
          input: Math.max(120, Math.round(contentText.length * 0.45 + 520)),
          output: Math.max(15, Math.round(contentText.length * 0.72)),
        };
        records.push({
          id: `turn-${currentTurn}-step-${currentStep}-assistant`,
          turnIndex: currentTurn,
          stepIndex: currentStep,
          kind: "assistant",
          name: "Agent 答复",
          summary: truncate(contentText),
          status,
          startedAt: timing.startedAt,
          durationMs: timing.durationMs,
          ttftMs: timing.ttftMs,
          decodingMs: timing.decodingMs,
          tokens,
          output: contentText,
          raw: msg,
        });
      }
      continue;
    }

    // tool 类型消息如果已经在上面匹配过了，跳过；如果是孤立的 tool message，单独补录
    if (msg.type === "tool") {
      const callId = String(rawMsg.tool_call_id ?? "");
      if (callId && processedToolCallIds.has(callId)) {
        continue;
      }
      currentStep++;
      const toolName = String(rawMsg.name ?? "tool_result");
      const content = msg.content;
      const isErr = rawMsg.status === "error";
      const orphanTiming = deriveRecordTiming(msg, "tool", String(content || "").length, baseTime);
      records.push({
        id: `turn-${currentTurn}-step-${currentStep}-tool-orphan-${callId || i}`,
        turnIndex: currentTurn,
        stepIndex: currentStep,
        kind: "tool",
        name: toolName,
        summary: truncate(typeof content === "string" ? content : JSON.stringify(content)),
        status: isErr ? "error" : "completed",
        startedAt: orphanTiming.startedAt,
        durationMs: orphanTiming.durationMs,
        output: content,
        error: isErr ? String(content) : undefined,
        raw: msg,
      });
    }
  }

  // 3. 检查是否有未在 messages 中落库但已经在 assembled calls 中出现的进行中工具
  for (const call of calls) {
    if (call.callId && !processedToolCallIds.has(call.callId)) {
      currentStep++;
      records.push({
        id: `turn-${currentTurn || 1}-step-${currentStep}-tool-live-${call.callId}`,
        turnIndex: currentTurn || 1,
        stepIndex: currentStep,
        kind: "tool",
        name: call.name || "正在调用的工具",
        summary: `${call.name || "tool"}(${compactArgs(call.input)})`,
        status: call.error ? "error" : call.status === "finished" ? "completed" : "running",
        input: call.input,
        output: call.output,
        error: call.error,
        raw: call,
      });
    }
  }

  return records;
}

export function groupTrajectoryByTurn(records: TrajectoryRecord[]): TrajectoryTurnGroup[] {
  const groups: TrajectoryTurnGroup[] = [];
  const map = new Map<number, TrajectoryRecord[]>();

  for (const record of records) {
    const turn = record.turnIndex || 1;
    if (!map.has(turn)) {
      map.set(turn, []);
    }
    map.get(turn)!.push(record);
  }

  for (const [turnIndex, turnRecords] of map.entries()) {
    groups.push({
      turnIndex,
      records: turnRecords,
    });
  }

  return groups.sort((a, b) => a.turnIndex - b.turnIndex);
}
