import { ref, shallowRef, watch } from "vue";
import type { Client } from "@langchain/langgraph-sdk";
import type {
  AssistantAttachedContext,
  AssistantChatMessage,
  AssistantPendingReview,
  AssistantTurnStatus,
} from "../types";
import { usePlatformAssistantStore } from "../stores/usePlatformAssistantStore";
import { createAssistantScopedClient } from "../services/client";
import {
  buildAssistantReviewCommand,
  parseAssistantReviews,
} from "../services/approval";
import { useEvidenceLookup } from "./useEvidenceLookup";

function extractTextContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    const textBlocks: string[] = [];
    for (const block of content) {
      if (
        block &&
        typeof block === "object" &&
        (block as { type?: string }).type === "text" &&
        typeof (block as { text?: string }).text === "string"
      ) {
        textBlocks.push((block as { text: string }).text);
      }
    }
    if (textBlocks.length > 0) return textBlocks.join("\n");
  }
  return "";
}

/**
 * 标准化解包 SSE / JSON-RPC 格式的数据包
 * 兼容 { method: "...", params: { data: ... } } 与原生直接返回的数据对象
 */
function unwrapChunkPayload(data: unknown): unknown {
  if (data && typeof data === "object" && "params" in data) {
    const params = (data as { params?: { data?: unknown } }).params;
    if (params && typeof params === "object" && "data" in params) {
      return params.data;
    }
  }
  return data;
}

export function usePlatformAssistantSession() {
  const store = usePlatformAssistantStore();
  const evidenceLookup = useEvidenceLookup();

  const threadId = ref<string | null>(null);
  const turnStatus = ref<AssistantTurnStatus>("idle");
  const messages = ref<AssistantChatMessage[]>([]);
  const pendingReview = ref<AssistantPendingReview | null>(null);
  const currentRunId = ref<string | null>(null);
  const errorBanner = ref<string | null>(null);
  let operationGeneration = 0;

  watch(
    () => store.boundProjectId,
    (projectId, previousId) => {
      if (previousId && projectId !== previousId) startNewSession();
    },
    { flush: "sync" },
  );

  // 内部保持唯一的 Scoped Client
  const scopedClient = shallowRef<Client | null>(null);
  let scopedProjectId = "";

  function getClient(): Client {
    if (!store.boundProjectId) {
      throw new Error("平台助手未完成 Bootstrap 初始化");
    }
    if (!scopedClient.value || scopedProjectId !== store.boundProjectId) {
      scopedClient.value = createAssistantScopedClient(store.boundProjectId);
      scopedProjectId = store.boundProjectId;
    }
    return scopedClient.value;
  }

  /**
   * 将后端的原始 Message 投影为前端标准 AssistantChatMessage
   */
  function normalizeRawMessages(rawList: unknown[]): AssistantChatMessage[] {
    const result: AssistantChatMessage[] = [];
    for (let i = 0; i < rawList.length; i++) {
      const raw = rawList[i];
      if (!raw || typeof raw !== "object") continue;
      const item = raw as Record<string, unknown>;

      const roleStr = (item.role || item.type || "user") as string;
      let role: "user" | "assistant" | "tool" = "user";
      if (roleStr === "assistant" || roleStr === "ai") {
        role = "assistant";
      } else if (roleStr === "tool" || roleStr === "tool_message") {
        role = "tool";
      }

      const content = extractTextContent(item.content);
      const msg: AssistantChatMessage = {
        id: (item.id as string) || `msg-${i}-${Date.now()}`,
        role,
        content,
        name: typeof item.name === "string" ? item.name : undefined,
        tool_call_id:
          typeof item.tool_call_id === "string" ? item.tool_call_id : undefined,
      };

      if (role === "tool") {
        const evId = evidenceLookup.parseAndIndexToolMessage(content);
        if (evId) {
          msg.evidence_id = evId;
        }
      }

      result.push(msg);
    }
    return result;
  }

  /**
   * 加载指定 Thread 的历史消息与当前状态
   */
  async function loadThread(targetThreadId: string) {
    if (!targetThreadId) return;
    if (turnStatus.value === "running") return;
    if (threadId.value === targetThreadId && messages.value.length > 0) return;

    const operation = ++operationGeneration;
    turnStatus.value = "running";
    errorBanner.value = null;
    try {
      await store.ensureBootstrap();
      if (operation !== operationGeneration) return;
      const client = getClient();
      const state = await client.threads.getState(targetThreadId);
      if (operation !== operationGeneration) return;
      threadId.value = targetThreadId;
      store.setActiveThreadId(targetThreadId);

      // 提取消息
      const rawMsgs =
        (state.values as { messages?: unknown[] })?.messages || [];
      evidenceLookup.clearAllEvidence();
      messages.value = normalizeRawMessages(rawMsgs);

      // 检查是否有待审批的 Interrupts
      const interrupts = (state as unknown as { interrupts?: unknown[] })
        ?.interrupts;
      if (Array.isArray(interrupts) && interrupts.length > 0) {
        const parsed = parseAssistantReviews(
          interrupts as readonly { id?: string; value?: unknown }[],
        );
        if (parsed.length > 0) {
          pendingReview.value = parsed[0];
          turnStatus.value = "awaiting_review";
          return;
        }
      }

      pendingReview.value = null;
      turnStatus.value = "idle";
    } catch (err: unknown) {
      if (operation !== operationGeneration) return;
      if (clearForbiddenSession(err)) return;
      turnStatus.value = "error";
      errorBanner.value = err instanceof Error ? err.message : "读取会话失败";
    }
  }

  /**
   * 重置当前会话以新建
   */
  function startNewSession() {
    // 旧请求可能仍在返回，不能再恢复旧Thread或消息。
    operationGeneration++;
    threadId.value = null;
    currentRunId.value = null;
    messages.value = [];
    pendingReview.value = null;
    turnStatus.value = "idle";
    errorBanner.value = null;
    evidenceLookup.clearAllEvidence();
    store.newSession();
  }

  function clearForbiddenSession(error: unknown): boolean {
    if (
      !error ||
      typeof error !== "object" ||
      !("status" in error) ||
      error.status !== 403
    ) {
      return false;
    }
    startNewSession();
    turnStatus.value = "error";
    errorBanner.value = "此会话或资料的读取权限已变更，请新建会话。";
    return true;
  }

  /**
   * 发送用户消息
   */
  async function sendMessage(
    prompt: string,
    attachedContext?: AssistantAttachedContext | null,
  ) {
    const trimmed = prompt.trim();
    if (!trimmed && !attachedContext) return;
    if (["running", "awaiting_review"].includes(turnStatus.value)) return;

    const operation = ++operationGeneration;
    try {
      await store.ensureBootstrap();
      if (operation !== operationGeneration) return;
    } catch (err: unknown) {
      if (operation !== operationGeneration) return;
      if (clearForbiddenSession(err)) return;
      turnStatus.value = "error";
      errorBanner.value =
        err instanceof Error ? err.message : "平台助手初始化失败";
      return;
    }
    const client = getClient();

    errorBanner.value = null;
    turnStatus.value = "running";

    // 1. 若当前尚无 Thread，先新建 Thread
    let currentThreadId = threadId.value;
    if (!currentThreadId) {
      try {
        const created = await (
          client.threads as unknown as {
            create: (
              options: Record<string, unknown>,
            ) => Promise<{ thread_id: string }>;
          }
        ).create({
          graphId: "platform_assistant",
          metadata: {
            graph_id: "platform_assistant",
            title: "平台助手",
          },
        });
        if (operation !== operationGeneration) return;
        currentThreadId = created.thread_id;
        threadId.value = currentThreadId;
        store.setActiveThreadId(currentThreadId);
      } catch (err: unknown) {
        if (operation !== operationGeneration) return;
        if (clearForbiddenSession(err)) return;
        turnStatus.value = "error";
        errorBanner.value = err instanceof Error ? err.message : "创建会话失败";
        return;
      }
    }

    // 2. 拼装用户真实发出的 prompt
    let actualInputContent = trimmed;
    if (attachedContext) {
      actualInputContent = `【错误现场上下文】\n标题: ${attachedContext.title}\n摘要: ${attachedContext.summary}\n${attachedContext.diagnosticMarkdown}\n\n【用户问题】:\n${trimmed || "请根据上述诊断信息分析原因并给出指导。"}`;
    }

    // 3. 追加 User 消息到前端本地视图
    const userMsgId = `user-${Date.now()}`;
    messages.value.push({
      id: userMsgId,
      role: "user",
      content:
        trimmed ||
        (attachedContext ? `[已附带错误上下文: ${attachedContext.title}]` : ""),
      created_at: new Date().toISOString(),
    });

    // 4. 追加占位 Assistant 消息
    const assistantMsgId = `asst-${Date.now()}`;
    const assistantMsg: AssistantChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };
    messages.value.push(assistantMsg);

    // 5. 启动流式运行
    try {
      const stream = client.runs.stream(currentThreadId, "platform_assistant", {
        input: {
          messages: [{ role: "user", content: actualInputContent }],
        },
        streamMode: ["messages", "values"],
        context: {
          model_id: store.currentModelId,
        },
      });

      for await (const chunk of stream) {
        if (operation !== operationGeneration) return;
        if (!chunk) continue;
        const eventName = chunk.event as string;
        const data = chunk.data;
        const payload = unwrapChunkPayload(data);

        if (
          eventName === "metadata" &&
          payload &&
          typeof (payload as { run_id?: string }).run_id === "string"
        ) {
          currentRunId.value = (payload as { run_id: string }).run_id;
        }

        // 1. 处理 messages 流式 token / delta
        if (eventName === "messages") {
          if (Array.isArray(payload)) {
            for (const item of payload) {
              if (!item || typeof item !== "object") continue;
              const itemObj = item as {
                event?: string;
                delta?: { type?: string; text?: string } | string;
                text?: string;
                content?: unknown;
              };
              let chunkText = "";
              if (
                itemObj.delta &&
                typeof itemObj.delta === "object" &&
                typeof itemObj.delta.text === "string"
              ) {
                chunkText = itemObj.delta.text;
              } else if (typeof itemObj.delta === "string") {
                chunkText = itemObj.delta;
              } else if (typeof itemObj.text === "string") {
                chunkText = itemObj.text;
              } else if (itemObj.content && itemObj.event !== "message-start") {
                chunkText = extractTextContent(itemObj.content);
              }

              if (chunkText) {
                assistantMsg.content += chunkText;
                // 确保 messages 数组里的末尾 assistant 消息始终同步响应
                const last = messages.value[messages.value.length - 1];
                if (last && last.role === "assistant") {
                  last.content = assistantMsg.content;
                }
              }
            }
          }
        } else if (eventName === "messages/partial" && Array.isArray(payload)) {
          const lastMsg = payload[payload.length - 1] as
            | Record<string, unknown>
            | undefined;
          if (
            lastMsg &&
            (lastMsg.role === "assistant" || lastMsg.type === "ai")
          ) {
            const extracted = extractTextContent(lastMsg.content);
            if (extracted) {
              assistantMsg.content = extracted;
              const last = messages.value[messages.value.length - 1];
              if (last && last.role === "assistant") {
                last.content = extracted;
              }
            }
          }
        } else if (eventName === "values") {
          // 处理 values 全量状态更新
          const valuesObj = payload as { messages?: unknown[] } | undefined;
          if (valuesObj && Array.isArray(valuesObj.messages)) {
            const newNormalized = normalizeRawMessages(valuesObj.messages);
            if (newNormalized.length > 0) {
              // 检查后端是否已持久化产生了 assistant 消息
              const backendHasAssistant = newNormalized.some(
                (m) => m.role === "assistant" && m.content,
              );

              if (backendHasAssistant) {
                messages.value = newNormalized;
                const lastAsst = [...newNormalized]
                  .reverse()
                  .find((m) => m.role === "assistant");
                if (lastAsst) {
                  assistantMsg.content = lastAsst.content;
                }
              } else {
                // 后端还在前置思考或中间件阶段，绝不冲掉本地思考中/流式中的 assistantMsg！
                messages.value = [...newNormalized, assistantMsg];
              }
            }
          }
        }
      }

      // 6. 运行完毕后，再次读取最新 State 检查 Interrupts
      const finalState = await client.threads.getState(currentThreadId);
      if (operation !== operationGeneration) return;
      const finalRawMsgs =
        (finalState.values as { messages?: unknown[] })?.messages || [];
      if (finalRawMsgs.length > 0) {
        messages.value = normalizeRawMessages(finalRawMsgs);
      }

      const interrupts = (finalState as unknown as { interrupts?: unknown[] })
        ?.interrupts;
      if (Array.isArray(interrupts) && interrupts.length > 0) {
        const parsed = parseAssistantReviews(
          interrupts as readonly { id?: string; value?: unknown }[],
        );
        if (parsed.length > 0) {
          pendingReview.value = parsed[0];
          turnStatus.value = "awaiting_review";
          return;
        }
      }

      // 检查运行终态，避免失败时静默吞掉
      if (currentRunId.value) {
        try {
          const runDetail = await client.runs.get(
            currentThreadId,
            currentRunId.value,
          );
          if (operation !== operationGeneration) return;
          if (runDetail && runDetail.status === "error") {
            turnStatus.value = "error";
            errorBanner.value = "智能体执行失败，请检查会话或重试。";
            return;
          }
        } catch (err: unknown) {
          if (operation !== operationGeneration) return;
          if (clearForbiddenSession(err)) return;
          // run 状态查询失败不阻塞
        }
      }

      pendingReview.value = null;
      turnStatus.value = "idle";
      currentRunId.value = null;
    } catch (err: unknown) {
      if (operation !== operationGeneration) return;
      if (clearForbiddenSession(err)) return;
      turnStatus.value = "error";
      errorBanner.value = err instanceof Error ? err.message : "智能体运行异常";
    }
  }

  /**
   * 提交审批决定 (approve | reject)
   */
  async function submitReview(
    decision: "approve" | "reject",
    customMessage?: string,
  ) {
    if (!threadId.value || !pendingReview.value) return;
    const operation = ++operationGeneration;
    const reviewThreadId = threadId.value;
    const client = getClient();
    const interruptId = pendingReview.value.interrupt_id;

    const commandPayload = buildAssistantReviewCommand(
      interruptId,
      decision,
      customMessage,
    );

    turnStatus.value = "running";
    pendingReview.value = null;
    errorBanner.value = null;

    try {
      const stream = client.runs.stream(
        reviewThreadId,
        "platform_assistant",
        commandPayload as unknown as Record<string, unknown>,
      );

      for await (const chunk of stream) {
        if (operation !== operationGeneration) return;
        if (!chunk) continue;
        const eventName = chunk.event as string;
        const data = chunk.data as Record<string, unknown> | undefined;

        const payload = unwrapChunkPayload(data);

        if (eventName === "values") {
          const valuesObj = payload as { messages?: unknown[] } | undefined;
          if (valuesObj && Array.isArray(valuesObj.messages)) {
            messages.value = normalizeRawMessages(valuesObj.messages);
          }
        }
      }

      // 审批后再次检查状态
      const finalState = await client.threads.getState(reviewThreadId);
      if (operation !== operationGeneration) return;
      const finalRawMsgs =
        (finalState.values as { messages?: unknown[] })?.messages || [];
      if (finalRawMsgs.length > 0) {
        messages.value = normalizeRawMessages(finalRawMsgs);
      }

      const interrupts = (finalState as unknown as { interrupts?: unknown[] })
        ?.interrupts;
      if (Array.isArray(interrupts) && interrupts.length > 0) {
        const parsed = parseAssistantReviews(
          interrupts as readonly { id?: string; value?: unknown }[],
        );
        if (parsed.length > 0) {
          pendingReview.value = parsed[0];
          turnStatus.value = "awaiting_review";
          return;
        }
      }

      turnStatus.value = "idle";
    } catch (err: unknown) {
      if (operation !== operationGeneration) return;
      if (clearForbiddenSession(err)) return;
      turnStatus.value = "error";
      errorBanner.value =
        err instanceof Error ? err.message : "提交审批决策失败";
    }
  }

  /**
   * 停止当前运行
   */
  async function stopCurrentRun() {
    if (!threadId.value || !currentRunId.value) return;
    const operation = operationGeneration;
    const client = getClient();
    try {
      await client.runs.cancel(threadId.value, currentRunId.value);
    } catch (err: unknown) {
      if (operation !== operationGeneration) return;
      clearForbiddenSession(err);
      // 容错处理
    } finally {
      if (operation === operationGeneration) {
        turnStatus.value = "idle";
        currentRunId.value = null;
      }
    }
  }

  return {
    threadId,
    turnStatus,
    messages,
    pendingReview,
    currentRunId,
    errorBanner,
    evidenceLookup,
    loadThread,
    startNewSession,
    sendMessage,
    submitReview,
    stopCurrentRun,
  };
}
