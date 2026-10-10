/**
 * 计划审阅 (Plan Review) DTO 校验、快照解析与恢复回复纯函数。
 * 契约严格对齐 20261008-agent-plan-mode-governance 规范。
 */

export type PlanReviewDecision = "approve" | "request_changes" | "abandon";

export interface AgentPlanSnapshot {
  version: 1;
  type: "agent_plan_review";
  plan_id: string;
  revision: number;
  content_hash: string;
  title: string;
  markdown: string;
  allowed_decisions: PlanReviewDecision[];
}

export interface PendingPlanReview {
  id: string;
  namespace: readonly string[];
  planId: string;
  revision: number;
  contentHash: string;
  title: string;
  markdown: string;
  allowedDecisions: PlanReviewDecision[];
  plan: AgentPlanSnapshot;
  fingerprint: string;
  supported: boolean;
  raw: unknown;
}

export interface AgentPlanState {
  version: 1;
  status: "planning" | "awaiting_review" | "approved" | "abandoned";
  active: boolean;
  plan_id: string;
  revision: number;
  content_hash: string | null;
  title: string;
  markdown: string;
  decision?: PlanReviewDecision | null;
  approved_by?: { user_id: string };
  approved_at?: string;
}

export interface PlanReviewResponsePayload {
  version: 1;
  type: "agent_plan_response";
  plan_id: string;
  revision: number;
  content_hash: string;
  decision: PlanReviewDecision;
  feedback?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isPlanReviewInterrupt(
  target: unknown,
): target is AgentPlanSnapshot {
  if (!isRecord(target)) return false;
  const value = isRecord(target.value) ? target.value : target;
  if (value.type !== "agent_plan_review" || value.version !== 1) return false;
  if (
    typeof value.plan_id !== "string" ||
    !value.plan_id.trim() ||
    value.plan_id.length > 128
  ) {
    return false;
  }
  if (
    typeof value.revision !== "number" ||
    !Number.isInteger(value.revision) ||
    value.revision < 1
  ) {
    return false;
  }
  if (
    typeof value.content_hash !== "string" ||
    !/^sha256:[0-9a-f]{64}$/.test(value.content_hash)
  ) {
    return false;
  }
  if (
    typeof value.title !== "string" ||
    !value.title.trim() ||
    value.title.length > 128
  ) {
    return false;
  }
  if (typeof value.markdown !== "string" || !value.markdown.trim()) {
    return false;
  }
  const encoder = new TextEncoder();
  if (encoder.encode(value.markdown).length > 65536) {
    return false;
  }
  if (
    !Array.isArray(value.allowed_decisions) ||
    !value.allowed_decisions.includes("approve") ||
    !value.allowed_decisions.includes("request_changes") ||
    !value.allowed_decisions.includes("abandon")
  ) {
    return false;
  }
  return true;
}

export function parsePlanReview(interrupt: {
  id?: string;
  value?: unknown;
  ns?: readonly string[];
}): PendingPlanReview | null {
  if (!interrupt.id || !interrupt.value) return null;
  if (!isPlanReviewInterrupt(interrupt)) return null;

  const targetValue = isRecord(interrupt.value) ? interrupt.value : {};
  const plan = targetValue as unknown as AgentPlanSnapshot;
  const fingerprint = JSON.stringify({
    id: interrupt.id,
    plan_id: plan.plan_id,
    revision: plan.revision,
    content_hash: plan.content_hash,
  });

  return {
    id: interrupt.id,
    namespace: interrupt.ns ?? [],
    planId: plan.plan_id,
    revision: plan.revision,
    contentHash: plan.content_hash,
    title: plan.title,
    markdown: plan.markdown,
    allowedDecisions: plan.allowed_decisions,
    plan,
    fingerprint,
    supported: true,
    raw: interrupt.value,
  };
}

export function buildPlanResponse(
  review: PendingPlanReview,
  decision: PlanReviewDecision,
  feedback?: string,
): Record<string, PlanReviewResponsePayload> {
  if (!review.supported || !review.id) {
    throw new Error("不支持的计划审阅中断");
  }

  const allowed =
    review.allowedDecisions ?? review.plan?.allowed_decisions ?? [];
  if (!allowed.includes(decision)) {
    throw new Error(`不允许的操作决定: ${decision}`);
  }

  const planId = review.planId ?? review.plan?.plan_id;
  const revision = review.revision ?? review.plan?.revision;
  const contentHash = review.contentHash ?? review.plan?.content_hash;

  const payload: PlanReviewResponsePayload = {
    version: 1,
    type: "agent_plan_response",
    plan_id: planId,
    revision,
    content_hash: contentHash,
    decision,
  };

  if (decision === "request_changes") {
    const trimmed = feedback?.trim() ?? "";
    if (!trimmed) {
      throw new Error("必须提供具体修改意见");
    }
    if (trimmed.length > 2000) {
      throw new Error("修改意见不能超过 2000 个字符");
    }
    payload.feedback = trimmed;
  } else if (decision === "abandon") {
    if (feedback && feedback.trim()) {
      const trimmed = feedback.trim();
      if (trimmed.length > 2000) {
        throw new Error("放弃原因不能超过 2000 个字符");
      }
      payload.feedback = trimmed;
    }
  }

  return {
    [review.id]: payload,
  };
}

export function extractAgentPlan(stateValues: unknown): AgentPlanState | null {
  if (!isRecord(stateValues)) return null;
  const raw = isRecord(stateValues.agent_plan)
    ? stateValues.agent_plan
    : isRecord(stateValues.values) && isRecord(stateValues.values.agent_plan)
      ? stateValues.values.agent_plan
      : null;

  if (!raw) return null;
  if (raw.version !== undefined && raw.version !== 1) return null;

  const status = String(raw.status);
  if (
    !["planning", "awaiting_review", "approved", "abandoned"].includes(status)
  ) {
    return null;
  }

  return {
    version: 1,
    status: status as AgentPlanState["status"],
    active: Boolean(raw.active),
    plan_id: typeof raw.plan_id === "string" ? raw.plan_id : "",
    revision: typeof raw.revision === "number" ? raw.revision : 0,
    content_hash:
      typeof raw.content_hash === "string" ? raw.content_hash : null,
    title: typeof raw.title === "string" ? raw.title : "",
    markdown: typeof raw.markdown === "string" ? raw.markdown : "",
    decision:
      typeof raw.decision === "string" &&
      ["approve", "request_changes", "abandon"].includes(raw.decision)
        ? (raw.decision as PlanReviewDecision)
        : null,
    approved_by:
      isRecord(raw.approved_by) && typeof raw.approved_by.user_id === "string"
        ? { user_id: raw.approved_by.user_id }
        : undefined,
    approved_at:
      typeof raw.approved_at === "string" ? raw.approved_at : undefined,
  };
}
