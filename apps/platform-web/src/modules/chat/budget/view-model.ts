import {
  BUDGET_SAFETY_ERROR_CODES,
  BudgetNoticeSchema,
  BudgetSafetyErrorSchema,
  type BudgetCode,
  type BudgetNotice,
  type BudgetSafetyError,
  type BudgetSafetyErrorCode,
  type BudgetScope,
  type BudgetUnit,
} from "./types";

export interface BudgetViewModel {
  level: "warning" | "error";
  title: string;
  description: string;
  code: BudgetCode | BudgetSafetyErrorCode;
  scope: BudgetScope | "unknown";
  unit?: BudgetUnit;
  remaining?: number | null;
  limit?: number | null;
  used?: number | null;
  actionType: "adjust_draft" | "new_thread" | "none";
  actionLabel?: string;
  isTerminal: boolean;
}

/**
 * Robustly unpack a potential BudgetNotice from heterogeneous incoming payloads:
 * - Outer transport wrapper: `{ event: "custom", payload: { ... } }`
 * - v3 Protocol raw event: `{ method: "custom", params: { data: notice } }`
 * - Direct SSE payload: `{ version: 1, type: "runtime_budget_notice", ... }`
 * - Message additional kwargs: `message.additional_kwargs?.runtime_budget_notice`
 */
export function safeExtractBudgetNotice(raw: unknown): BudgetNotice | null {
  if (!raw || typeof raw !== "object") return null;

  let candidate: Record<string, unknown> = raw as Record<string, unknown>;

  // 1. Check if wrapped in transport payload (SSE event structure)
  if (
    "payload" in candidate &&
    candidate.payload &&
    typeof candidate.payload === "object"
  ) {
    candidate = candidate.payload as Record<string, unknown>;
  }

  // 2. Check if wrapped in protocol params (v3 raw event)
  if (
    "params" in candidate &&
    candidate.params &&
    typeof candidate.params === "object"
  ) {
    const params = candidate.params as Record<string, unknown>;
    if ("data" in params && params.data && typeof params.data === "object") {
      candidate = params.data as Record<string, unknown>;
    }
  } else if (
    "data" in candidate &&
    candidate.data &&
    typeof candidate.data === "object"
  ) {
    candidate = candidate.data as Record<string, unknown>;
  }

  // 3. Check if it looks like a runtime_budget_notice
  if (candidate.type !== "runtime_budget_notice") {
    return null;
  }

  const result = BudgetNoticeSchema.safeParse(candidate);
  return result.success ? result.data : null;
}

function findNestedErrorCode(target: unknown, depth = 0): string | null {
  if (!target || typeof target !== "object" || depth > 3) return null;
  const obj = target as Record<string, unknown>;
  if (
    "code" in obj &&
    typeof obj.code === "string" &&
    (BUDGET_SAFETY_ERROR_CODES as readonly string[]).includes(obj.code)
  ) {
    return obj.code;
  }
  for (const key of ["error", "cause", "response", "data", "body", "details"]) {
    if (key in obj && obj[key] && typeof obj[key] === "object") {
      const found = findNestedErrorCode(obj[key], depth + 1);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Extract safety error code and details from native error payload
 */
export function safeExtractBudgetSafetyError(
  raw: unknown,
): BudgetSafetyError | null {
  if (!raw) return null;

  // 1. Direct object matching with schema parse
  let candidate: Record<string, unknown> | null = null;
  if (typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    if (
      "code" in obj &&
      typeof obj.code === "string" &&
      (BUDGET_SAFETY_ERROR_CODES as readonly string[]).includes(obj.code)
    ) {
      candidate = obj;
    } else if ("error" in obj && obj.error && typeof obj.error === "object") {
      const inner = obj.error as Record<string, unknown>;
      if (
        "code" in inner &&
        typeof inner.code === "string" &&
        (BUDGET_SAFETY_ERROR_CODES as readonly string[]).includes(inner.code)
      ) {
        candidate = inner;
      }
    }
  }

  if (candidate) {
    const result = BudgetSafetyErrorSchema.safeParse(candidate);
    if (result.success) return result.data;
  }

  // 2. Direct property check on raw object (in case schema parse was too strict)
  if (typeof raw === "object" && raw !== null) {
    const asAny = raw as Record<string, unknown>;
    const code =
      asAny.code || (asAny.error as any)?.code || (asAny.cause as any)?.code;
    const type =
      asAny.type || (asAny.error as any)?.type || (asAny.cause as any)?.type;
    if (
      code === "runtime_graph_step_limit_reached" ||
      type === "GraphRecursionError"
    ) {
      return {
        code: "runtime_graph_step_limit_reached",
        message: "Graph step limit reached",
      };
    }
    if (
      code === "runtime_model_call_limit_reached" ||
      type === "ModelCallLimitExceededError"
    ) {
      return {
        code: "runtime_model_call_limit_reached",
        message: "Model call limit reached",
      };
    }
    if (
      code === "runtime_tool_call_limit_reached" ||
      type === "ToolCallLimitExceededError"
    ) {
      return {
        code: "runtime_tool_call_limit_reached",
        message: "Tool call limit reached",
      };
    }
    if (code === "runtime_run_timeout" || type === "RunTimedOut") {
      return {
        code: "runtime_run_timeout",
        message: "Run time limit reached",
      };
    }
    if (
      code === "runtime_token_budget_exhausted" ||
      type === "TokenBudgetExceededError"
    ) {
      return {
        code: "runtime_token_budget_exhausted",
        message: "本次执行因 Token 额度停止，任务可能未完成。",
      };
    }
    if (
      code === "runtime_token_budget_unverifiable" ||
      type === "TokenBudgetUnverifiableError"
    ) {
      return {
        code: "runtime_token_budget_unverifiable",
        message: "用量无法确认，本次执行已停止新增工作。",
      };
    }

    // Support inferring from completed run object with status === 'error'
    if (asAny.status === "error") {
      const config = (asAny.kwargs as any)?.config || asAny.config;
      const recursionLimit = config?.recursion_limit;
      if (typeof recursionLimit === "number" && recursionLimit <= 50) {
        return {
          code: "runtime_graph_step_limit_reached",
          message: "Graph step limit reached",
        };
      }
    }
  }

  // 3. Deep nested object code search
  const nestedCode = findNestedErrorCode(raw);
  if (nestedCode) {
    return {
      code: nestedCode as BudgetSafetyErrorCode,
      message: nestedCode.replace(/^runtime_/, "").replace(/_/g, " "),
    };
  }

  // 4. Fallback: extract safety error from Error properties, cause, or raw text inspection
  let text = "";
  if (typeof raw === "string") {
    text = raw;
  } else if (typeof raw === "object" && raw !== null) {
    try {
      const props = Object.getOwnPropertyNames(raw);
      text = JSON.stringify(raw, props);
    } catch {
      text = "";
    }
    if (raw instanceof Error) {
      text += " " + raw.message + " " + String((raw as any).stack || "");
      if ((raw as any).cause) {
        try {
          text += " " + JSON.stringify((raw as any).cause);
        } catch {
          // ignore
        }
      }
    }
    for (const key of Object.keys(raw)) {
      const val = (raw as any)[key];
      if (val && typeof val === "object") {
        try {
          text += " " + JSON.stringify(val);
        } catch {
          // ignore cyclic
        }
      }
    }
  }

  if (
    text.includes("runtime_graph_step_limit_reached") ||
    text.includes("Graph step limit reached") ||
    text.includes("Recursion limit of") ||
    text.includes("GraphRecursionError")
  ) {
    return {
      code: "runtime_graph_step_limit_reached",
      message: "Graph step limit reached",
    };
  }
  if (
    text.includes("runtime_model_call_limit_reached") ||
    text.includes("Model call limit reached") ||
    text.includes("ModelCallLimitExceededError")
  ) {
    return {
      code: "runtime_model_call_limit_reached",
      message: "Model call limit reached",
    };
  }
  if (
    text.includes("runtime_tool_call_limit_reached") ||
    text.includes("Tool call limit reached") ||
    text.includes("ToolCallLimitExceededError")
  ) {
    return {
      code: "runtime_tool_call_limit_reached",
      message: "Tool call limit reached",
    };
  }
  if (
    text.includes("runtime_run_timeout") ||
    text.includes("Run time limit reached") ||
    text.includes("RunTimedOut")
  ) {
    return {
      code: "runtime_run_timeout",
      message: "Run time limit reached",
    };
  }

  return null;
}

/**
 * Derive unified BudgetViewModel from notice, native safety error, and run execution status.
 * Evaluates priority:
 * Hard limit stops (reached / safety error / end marker) > approaching / wrapup warnings
 */
export function deriveBudgetViewModel(
  notice: BudgetNotice | null,
  safetyError: BudgetSafetyError | null,
  nativeStatus?: string,
  historicalStopCode?:
    | "token_budget_exhausted"
    | "token_budget_unverifiable"
    | null,
): BudgetViewModel | null {
  const isRunning = nativeStatus === "running" || nativeStatus === "pending";

  // 1. Thread-level limit reached (highest restriction, confirmed by notice)
  if (
    notice &&
    notice.code === "model_call_limit_reached" &&
    notice.budget_scope === "thread"
  ) {
    return {
      level: "error",
      isTerminal: true,
      title: "本会话累计调用额度已耗尽",
      description:
        "会话累计模型调用次数已达上限，新请求无法继续执行。请创建新会话或在分支继续。",
      code: "model_call_limit_reached",
      scope: "thread",
      unit: "model_calls",
      limit: notice.limit,
      used: notice.used,
      remaining: 0,
      actionType: "new_thread",
      actionLabel: "新建会话",
    };
  }

  // 2. Run-level model limit reached (reached custom notice or native end marker, confirmed by notice)
  if (
    notice &&
    notice.code === "model_call_limit_reached" &&
    notice.budget_scope === "run"
  ) {
    return {
      level: "error",
      isTerminal: true,
      title: "本次执行因额度限制停止",
      description:
        "模型调用额度已耗尽，任务可能尚未完成。可调整并精简请求后重新发送。",
      code: "model_call_limit_reached",
      scope: "run",
      unit: "model_calls",
      limit: notice.limit,
      used: notice.used,
      remaining: 0,
      actionType: "adjust_draft",
      actionLabel: "调整请求",
    };
  }

  // 3. Token budget hard stops (notice / safety error / historical stop code)
  const isTokenExhausted =
    notice?.code === "token_budget_exhausted" ||
    safetyError?.code === "runtime_token_budget_exhausted" ||
    historicalStopCode === "token_budget_exhausted";

  if (isTokenExhausted) {
    if (isRunning) {
      // 在途触限过渡态：不清 busy、不发新请求、等待原生终态
      return {
        level: "warning",
        isTerminal: false,
        title: "Token额度已耗尽",
        description: "已触发额度保护，正在确认执行结果",
        code: "token_budget_exhausted",
        scope: "run",
        unit: "tokens_total",
        remaining: 0,
        limit: notice?.limit ?? null,
        used: notice?.used ?? null,
        actionType: "none",
      };
    }
    // 原生已进入终态 (error / failed)
    return {
      level: "error",
      isTerminal: true,
      title: "本次执行因Token额度停止",
      description: "本次执行因Token额度停止，任务可能未完成",
      code: "token_budget_exhausted",
      scope: "run",
      unit: "tokens_total",
      remaining: 0,
      limit: notice?.limit ?? null,
      used: notice?.used ?? null,
      actionType: "adjust_draft",
      actionLabel: "调整请求",
    };
  }

  const isTokenUnverifiable =
    notice?.code === "token_budget_unverifiable" ||
    safetyError?.code === "runtime_token_budget_unverifiable" ||
    historicalStopCode === "token_budget_unverifiable";

  if (isTokenUnverifiable) {
    if (isRunning) {
      // 在途不可验证过渡态
      return {
        level: "warning",
        isTerminal: false,
        title: "Token用量无法确认",
        description: "已触发额度保护，正在确认执行结果",
        code: "token_budget_unverifiable",
        scope: "run",
        unit: "tokens_total",
        remaining: null,
        limit: notice?.limit ?? null,
        used: notice?.used ?? null,
        actionType: "none",
      };
    }
    // 原生终态不可确认：不提供重试按钮，避免再次触发
    return {
      level: "error",
      isTerminal: true,
      title: "用量无法确认",
      description: "用量无法确认，本次执行已停止新增工作",
      code: "token_budget_unverifiable",
      scope: "run",
      unit: "tokens_total",
      remaining: null,
      limit: notice?.limit ?? null,
      used: notice?.used ?? null,
      actionType: "none",
    };
  }

  // 4. Other safety error codes (hard stops without custom notice or on error path)
  if (safetyError) {
    switch (safetyError.code) {
      case "runtime_model_call_limit_reached":
        return {
          level: "error",
          isTerminal: true,
          title: "本次执行因额度限制停止",
          description: "模型调用额度已耗尽，任务可能尚未完成。",
          code: safetyError.code,
          scope: "unknown",
          unit: "model_calls",
          remaining: 0,
          actionType: "none",
        };
      case "runtime_graph_step_limit_reached":
        return {
          level: "error",
          isTerminal: true,
          title: "本次执行达到图步骤上限",
          description:
            "已达智能体单次执行的最大步数限制。任务由于步骤上限中断，并非授权或服务故障。可调整或精简请求后重新发送。",
          code: safetyError.code,
          scope: "graph",
          unit: "graph_supersteps",
          remaining: 0,
          actionType: "adjust_draft",
          actionLabel: "调整请求",
        };
      case "runtime_tool_call_limit_reached":
        return {
          level: "error",
          isTerminal: true,
          title: "工具调用额度已耗尽",
          description:
            "工具调用次数达到上限，任务可能尚未完成。可调整请求后重新发送。",
          code: safetyError.code,
          scope: "run",
          remaining: 0,
          actionType: "adjust_draft",
          actionLabel: "调整请求",
        };
      case "runtime_run_timeout":
        return {
          level: "error",
          isTerminal: true,
          title: "本次执行已超时",
          description: "执行超过最大时限；部分工具操作可能需要核对结果。",
          code: safetyError.code,
          scope: "run",
          unit: "seconds",
          remaining: 0,
          actionType: "none",
        };
    }
  }

  // 5. In-flight warnings (approaching / soft wrapup)
  if (notice) {
    // If native status is finished/success and notice was only approaching,
    // it was completed normally, warning should not persist as terminal error
    if (nativeStatus === "success") {
      return null;
    }

    if (notice.code === "token_budget_approaching") {
      const detail =
        typeof notice.remaining === "number"
          ? `剩余 Token 约 ${notice.remaining.toLocaleString()}，正在收尾`
          : "正在收尾";
      return {
        level: "warning",
        isTerminal: false,
        title: "Token额度接近上限",
        description: detail,
        code: notice.code,
        scope: notice.budget_scope,
        unit: notice.unit,
        remaining: notice.remaining,
        limit: notice.limit,
        used: notice.used,
        actionType: "none",
      };
    }

    if (notice.code === "model_call_limit_approaching") {
      const detail =
        typeof notice.remaining === "number"
          ? `剩余模型调用 ${notice.remaining} 次，正在收尾`
          : "正在收尾";
      return {
        level: "warning",
        isTerminal: false,
        title: "模型调用额度接近上限",
        description: detail,
        code: notice.code,
        scope: notice.budget_scope,
        unit: notice.unit,
        remaining: notice.remaining,
        limit: notice.limit,
        used: notice.used,
        actionType: "none",
      };
    }

    if (notice.code === "graph_step_limit_approaching") {
      const detail =
        typeof notice.remaining === "number"
          ? `剩余步骤 ${notice.remaining} supersteps，正在收尾`
          : "正在收尾";
      return {
        level: "warning",
        isTerminal: false,
        title: "执行步骤接近上限",
        description: detail,
        code: notice.code,
        scope: notice.budget_scope,
        unit: notice.unit,
        remaining: notice.remaining,
        limit: notice.limit,
        used: notice.used,
        actionType: "none",
      };
    }

    if (notice.code === "wrapup_started") {
      return {
        level: "warning",
        isTerminal: false,
        title: "运行时间较长",
        description: "正在收尾",
        code: notice.code,
        scope: notice.budget_scope,
        unit: notice.unit,
        remaining: null,
        limit: notice.limit,
        used: notice.used,
        actionType: "none",
      };
    }
  }

  return null;
}
