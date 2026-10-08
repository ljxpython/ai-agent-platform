import type {
  AvailabilityStatus,
  GraphOutcome,
  ModelErrorCode,
  PhaseOutcome,
  PreparationComponent,
  PreparationErrorCode,
  PreparationOutcome,
  RetryOutcome,
  RetryUnit,
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

/**
 * 格式化调用尝试次数
 * 1 -> "单次调用", 2 -> "重试 1 次"
 */
export function formatAttempts(attempts: number | null | undefined): string {
  if (attempts === 1) return "单次调用";
  if (attempts === 2) return "重试 1 次";
  if (typeof attempts === "number" && attempts > 0)
    return `调用 ${attempts} 次`;
  return "未知尝试";
}

/**
 * 准备组件中文标签映射
 */
export function getPreparationComponentLabel(
  component: PreparationComponent | string | null | undefined,
): string {
  if (component === "workspace") return "工作区";
  return component ?? "未知组件";
}

/**
 * 准备结果中文标签与徽章样式
 */
export function getPreparationOutcomeBadge(
  outcome: PreparationOutcome | string,
): {
  label: string;
  variant: "success" | "blue" | "warning" | "error" | "muted";
} {
  switch (outcome) {
    case "prepared":
      return { label: "已准备", variant: "success" };
    case "reused":
      return { label: "已复用", variant: "blue" };
    case "repaired":
      return { label: "已补齐", variant: "warning" };
    case "failed":
      return { label: "准备失败", variant: "error" };
    default:
      return { label: "未知", variant: "muted" };
  }
}

/**
 * 准备错误码中文说明
 */
export function getPreparationErrorCodeLabel(
  code: PreparationErrorCode | string | null | undefined,
): string {
  if (!code) return "";
  if (code === "prepare_failed") return "准备失败";
  if (code === "resource_unavailable") return "资源不可用";
  return "准备异常";
}

/**
 * 重试单元中文标签
 */
export function getRetryUnitLabel(
  unit: RetryUnit | string | null | undefined,
  role?: string | null | undefined,
): string {
  if (unit === "task") {
    return role ? `子任务 (${role})` : "子任务";
  }
  if (unit === "model") {
    return "模型调用";
  }
  return "调用";
}

/**
 * 核心视觉防坑：重试结果状态及警示等级计算
 * 当整次 Run 已经成功时，失败/耗尽的重试必须降级为 warning（Amber 琥珀色），严禁标红报错误导用户！
 */
export function getRetryOutcomeBadge(
  outcome: RetryOutcome | string,
  runStatus?: string | null | undefined,
): {
  label: string;
  variant: "success" | "warning" | "error" | "muted";
} {
  switch (outcome) {
    case "success":
      return { label: "成功", variant: "success" };
    case "exhausted":
      return {
        label: "重试耗尽",
        variant: runStatus === "success" ? "warning" : "error",
      };
    case "failed":
      return {
        label: "失败",
        variant: runStatus === "success" ? "warning" : "error",
      };
    case "cancelled":
      return { label: "已取消", variant: "muted" };
    case "interrupted":
      return { label: "已中断", variant: "warning" };
    default:
      return { label: "未知", variant: "muted" };
  }
}

/**
 * 重试卡片背景与边框的严重性等级
 */
export function getRetrySeverity(
  outcome: string,
  runStatus?: string | null | undefined,
): "success" | "warning" | "error" | "muted" {
  if (outcome === "success") return "success";
  if (outcome === "cancelled") return "muted";
  if (runStatus === "success") return "warning";
  if (outcome === "failed" || outcome === "exhausted") return "error";
  return "warning";
}
