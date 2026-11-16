import type { AssistantPendingReview, AssistantReviewAction } from "../types";

export const DEFAULT_REJECT_MESSAGE = "用户选择不执行";

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/**
 * 解析 LangGraph State 中的 Interrupts 列表为平台助手专属的待审批对象
 */
export function parseAssistantReviews(
  interrupts: readonly {
    id?: string;
    value?: unknown;
  }[],
): AssistantPendingReview[] {
  const result: AssistantPendingReview[] = [];

  for (const interrupt of interrupts) {
    if (!interrupt.id || !isRecord(interrupt.value)) continue;

    const val = interrupt.value;
    const actionRequests = Array.isArray(val.action_requests)
      ? val.action_requests
      : [];
    const reviewConfigs = Array.isArray(val.review_configs)
      ? val.review_configs
      : [];

    const actions: AssistantReviewAction[] = [];

    for (const req of actionRequests) {
      if (!isRecord(req) || typeof req.name !== "string") continue;

      const config = reviewConfigs.find(
        (cfg) => isRecord(cfg) && cfg.action_name === req.name,
      );

      const allowedDecisions: ("approve" | "reject")[] = [];
      if (isRecord(config) && Array.isArray(config.allowed_decisions)) {
        for (const dec of config.allowed_decisions) {
          if (dec === "approve" || dec === "reject") {
            allowedDecisions.push(dec);
          }
        }
      }

      // 默认至少具备 approve 和 reject
      if (allowedDecisions.length === 0) {
        allowedDecisions.push("approve", "reject");
      }

      actions.push({
        name: req.name,
        args: isRecord(req.args) ? req.args : {},
        description:
          typeof req.description === "string"
            ? req.description
            : "此操作将修改业务数据。请核对工具、目标和参数，再选择执行或不执行。",
        allowed_decisions: allowedDecisions,
      });
    }

    if (actions.length > 0) {
      result.push({
        interrupt_id: interrupt.id,
        actions,
      });
    }
  }

  return result;
}

/**
 * 构建提交给后端的审批决策 Command Body
 * 按照交接文档规范：
 * 批准: { command: { resume: { "<interrupt_id>": { decisions: [{ type: "approve" }] } } } }
 * 拒绝: { command: { resume: { "<interrupt_id>": { decisions: [{ type: "reject", message: "用户选择不执行" }] } } } }
 */
export function buildAssistantReviewCommand(
  interruptId: string,
  decision: "approve" | "reject",
  customMessage?: string,
): {
  assistant_id: string;
  command: {
    resume: Record<
      string,
      { decisions: Array<{ type: "approve" | "reject"; message?: string }> }
    >;
  };
} {
  if (!interruptId.trim()) {
    throw new Error("缺少有效的审批 interrupt_id");
  }

  const decisionObj: { type: "approve" | "reject"; message?: string } = {
    type: decision,
  };

  if (decision === "reject") {
    decisionObj.message = customMessage?.trim() || DEFAULT_REJECT_MESSAGE;
  }

  return {
    assistant_id: "platform_assistant",
    command: {
      resume: {
        [interruptId]: {
          decisions: [decisionObj],
        },
      },
    },
  };
}
