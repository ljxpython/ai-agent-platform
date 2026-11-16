import { ref, shallowRef } from "vue";
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

function deriveTitleFromPrompt(prompt: string): string {
  const cleaned = prompt.replace(/\s+/g, " ").trim();
  if (cleaned.length <= 20) return cleaned || "平台助手";
  return cleaned.slice(0, 20) + "...";
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

  // 内部保持唯一的 Scoped Client
  const scopedClient = shallowRef<Client | null>(null);

  function getClient(): Client {
    if (!store.boundProjectId) {
      throw new Error("平台助手未完成 Bootstrap 初始化");
    }
    if (!scopedClient.value) {
      scopedClient.value = createAssistantScopedClient(store.boundProjectId);
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
    await store.ensureBootstrap();
    const client = getClient();

    turnStatus.value = "running";
    errorBanner.value = null;
    try {
      const state = await client.threads.getState(targetThreadId);
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
      turnStatus.value = "error";
      errorBanner.value = err instanceof Error ? err.message : "读取会话失败";
    }
  }

  /**
   * 重置当前会话以新建
   */
  function startNewSession() {
    threadId.value = null;
    currentRunId.value = null;
    messages.value = [];
    pendingReview.value = null;
    turnStatus.value = "idle";
    errorBanner.value = null;
    evidenceLookup.clearAllEvidence();
    store.newSession();
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
    if (turnStatus.value === "running") return;

    await store.ensureBootstrap();
    const client = getClient();

    errorBanner.value = null;
    turnStatus.value = "running";

    // 1. 若当前尚无 Thread，先新建 Thread
    let currentThreadId = threadId.value;
    const isFirstTurn = !currentThreadId;
    if (!currentThreadId) {
      try {
        const created = await client.threads.create({
          metadata: {
            graph_id: "platform_assistant",
            title: "平台助手",
          },
        });
        currentThreadId = created.thread_id;
        threadId.value = currentThreadId;
        store.setActiveThreadId(currentThreadId);
      } catch (err: unknown) {
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
        context: {
          model_id: store.currentModelId,
        },
      });

      for await (const chunk of stream) {
        if (!chunk) continue;
        const eventName = chunk.event;
        const data = chunk.data as Record<string, unknown> | undefined;

        if (
          eventName === "metadata" &&
          data &&
          typeof data.run_id === "string"
        ) {
          currentRunId.value = data.run_id;
        }

        if (eventName === "messages/partial" && Array.isArray(data)) {
          const lastMsg = data[data.length - 1] as
            | Record<string, unknown>
            | undefined;
          if (
            lastMsg &&
            (lastMsg.role === "assistant" || lastMsg.type === "ai")
          ) {
            assistantMsg.content = extractTextContent(lastMsg.content);
          }
        } else if (
          eventName === "values" &&
          data &&
          Array.isArray(data.messages)
        ) {
          // 同步全量 values 消息
          messages.value = normalizeRawMessages(data.messages);
        }
      }

      // 6. 运行完毕后，再次读取最新 State 检查 Interrupts
      const finalState = await client.threads.getState(currentThreadId);
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

      // 7. 首轮成功问答后，自动生成并更新会话标题
      if (isFirstTurn && trimmed) {
        const newTitle = deriveTitleFromPrompt(trimmed);
        try {
          await (
            client.threads as unknown as {
              update: (
                id: string,
                body: Record<string, unknown>,
              ) => Promise<unknown>;
            }
          ).update(currentThreadId, {
            metadata: {
              graph_id: "platform_assistant",
              title: newTitle,
            },
          });
        } catch {
          // 标题更新失败不影响正常使用
        }
      }

      pendingReview.value = null;
      turnStatus.value = "idle";
      currentRunId.value = null;
    } catch (err: unknown) {
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
        threadId.value,
        "platform_assistant",
        commandPayload as unknown as Record<string, unknown>,
      );

      for await (const chunk of stream) {
        if (!chunk) continue;
        const eventName = chunk.event;
        const data = chunk.data as Record<string, unknown> | undefined;

        if (eventName === "values" && data && Array.isArray(data.messages)) {
          messages.value = normalizeRawMessages(data.messages);
        }
      }

      // 审批后再次检查状态
      const finalState = await client.threads.getState(threadId.value);
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
    const client = getClient();
    try {
      await client.runs.cancel(threadId.value, currentRunId.value);
    } catch {
      // 容错处理
    } finally {
      turnStatus.value = "idle";
      currentRunId.value = null;
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
