import { ref, type Ref } from "vue";
import {
  createExpertThread,
  streamExpertTurn,
  type CaseUpsertPayload,
} from "@/services/evaluation/studio";
import { resolvePlatformHttpErrorMessage } from "@/utils/http-error";

export interface ExpertMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  candidates?: CaseUpsertPayload[];
}

function parseCandidateCases(markdown: string): CaseUpsertPayload[] {
  const blocks = [...markdown.matchAll(/```(?:json)?\s*([\s\S]*?)```/gi)];
  const parsed: CaseUpsertPayload[] = [];
  for (const m of blocks) {
    try {
      const raw = JSON.parse(m[1].trim());
      const items = Array.isArray(raw) ? raw : [raw];
      for (const item of items) {
        if (!item || typeof item !== "object" || !item.case_key) continue;
        parsed.push({
          case_key: String(item.case_key),
          split: item.split === "holdout" ? "holdout" : "dev",
          turns: Array.isArray(item.turns)
            ? item.turns
            : item.question
              ? [{ role: "user", content: String(item.question) }]
              : [],
          simulation: item.simulation ?? null,
          expectations:
            item.expectations && typeof item.expectations === "object"
              ? item.expectations
              : item.ground_truth
                ? { expected_answer: String(item.ground_truth) }
                : {},
          metrics: Array.isArray(item.metrics) ? item.metrics : ["completion"],
        });
      }
    } catch {
      // Ignore non-JSON fenced code blocks.
    }
  }
  return parsed;
}

export function useEvalExpertChat(
  projectId: Ref<string>,
  kind: Ref<"eval_copilot" | "eval_diagnosis">,
  defaultModelId: Ref<string>,
) {
  const threadId = ref<string | null>(null);
  const messages = ref<ExpertMessage[]>([]);
  const streaming = ref(false);
  const error = ref("");

  function reset() {
    threadId.value = null;
    messages.value = [];
    error.value = "";
    streaming.value = false;
  }

  async function send(content: string, refId?: string) {
    const trimmed = content.trim();
    if (!trimmed || !projectId.value || streaming.value) return;

    error.value = "";
    streaming.value = true;
    const userMsg: ExpertMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    const assistantMsg: ExpertMessage = {
      id: `a-${Date.now() + 1}`,
      role: "assistant",
      content: "",
    };
    messages.value = [...messages.value, userMsg, assistantMsg];

    try {
      if (!threadId.value) {
        const created = await createExpertThread(
          projectId.value,
          kind.value,
          `${kind.value} ${refId || ""}`.trim(),
        );
        threadId.value = created.thread_id;
      }
      const promptWithContext = refId
        ? `[上下文关联ID: ${refId}]\n${trimmed}`
        : trimmed;
      const finalText = await streamExpertTurn(
        projectId.value,
        threadId.value,
        {
          graph_id: kind.value,
          content: promptWithContext,
          model_id: defaultModelId.value || null,
          ref_id: refId || null,
        },
        {
          onChunk: (fullText) => {
            assistantMsg.content = fullText;
            messages.value = [...messages.value];
          },
          onError: (msg) => {
            error.value = msg;
          },
        },
      );
      assistantMsg.content = finalText || assistantMsg.content;
      if (kind.value === "eval_copilot" && assistantMsg.content) {
        assistantMsg.candidates = parseCandidateCases(assistantMsg.content);
      }
      messages.value = [...messages.value];
    } catch (cause) {
      error.value = resolvePlatformHttpErrorMessage(
        cause,
        "评测专家对话执行失败。",
        kind.value === "eval_copilot" ? "AI 出题专家" : "AI 诊断专家",
      );
    } finally {
      streaming.value = false;
    }
  }

  return {
    threadId,
    messages,
    streaming,
    error,
    reset,
    send,
  };
}
