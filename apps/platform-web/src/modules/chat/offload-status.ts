export type OffloadStatus = "started" | "completed" | "skipped" | "failed";
export type OffloadTrigger = "automatic" | "manual";

export interface ConversationOffloadEventData {
  type: "conversation_offloading";
  status: OffloadStatus;
  trigger?: OffloadTrigger;
  operation_id?: string;
  run_id?: string;
  history_saved?: boolean;
  reason_code?: string;
}

export interface ConversationOffloadPersistedState {
  type: "conversation_offloading";
  status: OffloadStatus;
  trigger?: OffloadTrigger;
  operation_id?: string;
  run_id?: string;
  history_saved?: boolean;
  reason_code?: string;
}

export interface OffloadDisplayState {
  status: OffloadStatus;
  trigger: OffloadTrigger;
  operationId: string;
  runId: string;
  text: string;
  icon: "refresh" | "check" | "info" | "alert";
  variant: "info" | "success" | "neutral" | "danger";
}

/**
 * 校验并解析 SDK custom 帧中的 conversation_offloading 事件。
 * 严格只处理 root namespace（即 namespace 数组为空）的事件，子图/子智能体事件直接忽略。
 */
export function parseOffloadCustomEvent(
  event: unknown,
): ConversationOffloadEventData | null {
  if (!event || typeof event !== "object") return null;
  const raw = event as {
    method?: unknown;
    params?: {
      namespace?: unknown;
      data?: unknown;
    };
  };

  if (raw.method !== "custom" || !raw.params) return null;

  // 严格校验 namespace 必须为根（数组且长度为 0）
  const ns = raw.params.namespace;
  if (!Array.isArray(ns) || ns.length !== 0) return null;

  const data = raw.params.data as Record<string, unknown> | undefined;
  if (!data || typeof data !== "object") return null;

  if (data.type !== "conversation_offloading") return null;

  const status = data.status;
  if (
    status !== "started" &&
    status !== "completed" &&
    status !== "skipped" &&
    status !== "failed"
  ) {
    return null;
  }

  const trigger =
    data.trigger === "manual" || data.trigger === "automatic"
      ? (data.trigger as OffloadTrigger)
      : "automatic";

  return {
    type: "conversation_offloading",
    status,
    trigger,
    operation_id:
      typeof data.operation_id === "string" ? data.operation_id : undefined,
    run_id: typeof data.run_id === "string" ? data.run_id : undefined,
    history_saved:
      typeof data.history_saved === "boolean" ? data.history_saved : undefined,
    reason_code:
      typeof data.reason_code === "string" ? data.reason_code : undefined,
  };
}

/**
 * 将事件数据转换为 UI 显示状态。
 */
export function toOffloadDisplayState(
  data: ConversationOffloadEventData,
): OffloadDisplayState {
  const trigger = data.trigger || "automatic";
  const operationId = data.operation_id || "";
  const runId = data.run_id || "";

  switch (data.status) {
    case "started":
      return {
        status: "started",
        trigger,
        operationId,
        runId,
        text: "正在整理上下文...",
        icon: "refresh",
        variant: "info",
      };
    case "completed":
      return {
        status: "completed",
        trigger,
        operationId,
        runId,
        text: "上下文已整理",
        icon: "check",
        variant: "success",
      };
    case "skipped":
      return {
        status: "skipped",
        trigger,
        operationId,
        runId,
        text: "暂无需要整理的历史",
        icon: "info",
        variant: "neutral",
      };
    case "failed":
      return {
        status: "failed",
        trigger,
        operationId,
        runId,
        text: "上下文整理失败",
        icon: "alert",
        variant: "danger",
      };
  }
}

/**
 * 从 checkpoint values 中提取持久化的 conversation_offloading 终态（用于只读水合对账）。
 */
export function parseOffloadPersistedState(
  values: unknown,
): ConversationOffloadPersistedState | null {
  if (!values || typeof values !== "object") return null;
  const offload = (values as Record<string, unknown>).conversation_offloading;
  if (!offload || typeof offload !== "object") return null;
  const data = offload as Record<string, unknown>;

  if (data.type !== "conversation_offloading") return null;
  const status = data.status;
  if (
    status !== "started" &&
    status !== "completed" &&
    status !== "skipped" &&
    status !== "failed"
  ) {
    return null;
  }

  return {
    type: "conversation_offloading",
    status,
    trigger: data.trigger === "manual" ? "manual" : "automatic",
    operation_id:
      typeof data.operation_id === "string" ? data.operation_id : undefined,
    run_id: typeof data.run_id === "string" ? data.run_id : undefined,
    history_saved:
      typeof data.history_saved === "boolean" ? data.history_saved : undefined,
    reason_code:
      typeof data.reason_code === "string" ? data.reason_code : undefined,
  };
}
