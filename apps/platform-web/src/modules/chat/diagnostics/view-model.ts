import type {
  AvailabilityStatus,
  GraphOutcome,
  ModelErrorCode,
  PhaseOutcome,
  UnavailableReason,
} from "./types";

/**
 * 格式化执行耗时（毫秒）
 * 严格区分 0 与 null/undefined：0 是瞬时完成（显示 "0 ms"），null/undefined 是未采集（显示 "未知"）
 */
export function formatDuration(durationMs: number | null | undefined): string {
  if (
    durationMs === null ||
    durationMs === undefined ||
    Number.isNaN(durationMs)
  ) {
    return "未知";
  }
  if (durationMs < 0) {
    return "未知";
  }
  if (durationMs === 0) {
    return "0 ms";
  }
  if (durationMs < 10) {
    return `${durationMs.toFixed(1)} ms`;
  }
  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`;
  }
  return `${(durationMs / 1000).toFixed(2)} s`;
}

/**
 * 模型错误码中文标签映射
 */
const MODEL_ERROR_CODE_MAP: Record<ModelErrorCode, string> = {
  provider_rate_limited: "模型服务限流",
  provider_overloaded: "模型服务繁忙",
  context_too_long: "模型上下文超出限制",
  model_unavailable: "模型暂不可用",
  provider_auth_failed: "模型连接认证失败",
  provider_access_denied: "模型服务拒绝访问",
  provider_timeout: "模型调用超时",
  provider_unavailable: "模型服务连接异常",
  model_call_failed: "模型调用异常",
};

export function getModelErrorCodeLabel(
  code: string | null | undefined,
): string {
  if (!code) return "模型调用异常";
  return MODEL_ERROR_CODE_MAP[code as ModelErrorCode] ?? "模型调用异常";
}

/**
 * 启动阶段结果中文映射
 */
export function getPhaseOutcomeLabel(outcome: PhaseOutcome | string): string {
  switch (outcome) {
    case "completed":
      return "已完成";
    case "failed":
      return "失败";
    case "cancelled":
      return "已取消";
    case "incomplete":
      return "未完成";
    default:
      return "未知";
  }
}

/**
 * 图观察执行结果中文映射
 */
export function getGraphOutcomeLabel(outcome: GraphOutcome | string): string {
  switch (outcome) {
    case "success":
      return "成功";
    case "failed":
      return "失败";
    case "timeout":
      return "超时";
    case "cancelled":
      return "已取消";
    case "interrupted":
      return "等待处理";
    default:
      return "未知";
  }
}

/**
 * 诊断可用性状态中文及样式
 */
export function getAvailabilityBadge(
  availability: AvailabilityStatus | string,
  reason: UnavailableReason | null | undefined,
): { label: string; variant: "success" | "warning" | "error" | "muted" } {
  switch (availability) {
    case "available":
      return { label: "完整诊断", variant: "success" };
    case "partial":
      return { label: "部分诊断", variant: "warning" };
    case "disabled":
      return { label: "未启用诊断", variant: "muted" };
    case "unavailable":
      if (reason === "not_recorded") {
        return { label: "暂无记录", variant: "muted" };
      }
      if (reason === "backend_unavailable") {
        return { label: "服务不可用", variant: "error" };
      }
      return { label: "暂不可用", variant: "muted" };
    default:
      return { label: "未知状态", variant: "muted" };
  }
}

/**
 * 原生 Run 状态徽章映射
 */
export function getRunStatusBadge(runStatus: string | null | undefined): {
  label: string;
  variant: "success" | "running" | "error" | "warning" | "muted";
} {
  switch (runStatus) {
    case "success":
      return { label: "已完成", variant: "success" };
    case "running":
    case "pending":
      return { label: "运行中", variant: "running" };
    case "error":
      return { label: "执行失败", variant: "error" };
    case "interrupted":
      return { label: "等待处理", variant: "warning" };
    case "cancelled":
      return { label: "已取消", variant: "muted" };
    default:
      return {
        label: runStatus ? runStatus.toUpperCase() : "未知状态",
        variant: "muted",
      };
  }
}

/**
 * 核心视觉防坑：计算模型失败记录的警示等级
 * 若整次 Run 已经成功（Fallback 成功或重试恢复），严禁整屏标红，使用 warning（Amber 警示）
 */
export function getModelErrorSeverity(
  runStatus: string | null | undefined,
): "warning" | "error" {
  if (runStatus === "success") {
    return "warning";
  }
  return "error";
}

/**
 * 格式化 ISO 时间字符串为易读时间
 */
export function formatIsoTimestamp(
  isoString: string | null | undefined,
): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return isoString;
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

/**
 * 截短 UUID 用于标题显示
 */
export function truncateIdentifier(
  id: string | null | undefined,
  head = 8,
): string {
  if (!id) return "—";
  if (id.length <= head) return id;
  return `${id.slice(0, head)}...`;
}
