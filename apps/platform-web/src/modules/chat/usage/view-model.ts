/**
 * 用量与成本展示纯函数 (View Model)
 * 严格遵从契约：
 * - null 绝不能格式化为 0
 * - 极小非零成本绝不能显示为免费 $0.00
 * - 缓存命中率分母/值未知时显示“未采集”
 */

export interface CostDisplayInfo {
  display: string;
  fullUsd: string;
  isUnknown: boolean;
  isPartial: boolean;
  isZero: boolean;
}

/**
 * 格式化 Token 计数
 */
export function formatTokenCount(count: number | null | undefined): string {
  if (count === null || count === undefined) {
    return "未采集";
  }
  return count.toLocaleString();
}

/**
 * 格式化金额 (USD)
 * 保护极小非零金额：严禁四舍五入为 $0.00
 * 支持结合可用性状态精准分流文案，避免误导为“未配置价格”
 */
export function formatCostUsd(
  amountStr: string | null | undefined,
  status?: string,
  availability?: string,
  unavailableReason?: string | null,
): CostDisplayInfo {
  if (availability === "disabled") {
    return {
      display: "采集已关闭",
      fullUsd: "",
      isUnknown: true,
      isPartial: false,
      isZero: false,
    };
  }

  if (availability === "unavailable") {
    const display =
      unavailableReason === "not_recorded" ? "未采集历史" : "暂不可用";
    return {
      display,
      fullUsd: "",
      isUnknown: true,
      isPartial: false,
      isZero: false,
    };
  }

  if (status === "unknown" || !amountStr) {
    return {
      display: "未配置价格",
      fullUsd: "",
      isUnknown: true,
      isPartial: status === "partial",
      isZero: false,
    };
  }

  if (status === "not_applicable") {
    return {
      display: "$0.00",
      fullUsd: "$0.000000000000",
      isUnknown: false,
      isPartial: false,
      isZero: true,
    };
  }

  const num = Number(amountStr);
  if (isNaN(num) || num === 0) {
    return {
      display: "$0.00",
      fullUsd: "$0.000000000000",
      isUnknown: false,
      isPartial: status === "partial",
      isZero: true,
    };
  }

  // 极小正数保护
  let display: string;
  if (num < 0.0001) {
    display = "< $0.0001";
  } else if (num < 0.01) {
    display = `$${num.toFixed(4)}`;
  } else {
    display = `$${num.toFixed(4)}`;
  }

  return {
    display,
    fullUsd: `$${amountStr}`,
    isUnknown: false,
    isPartial: status === "partial",
    isZero: false,
  };
}

/**
 * 计算缓存命中率
 * cacheReadTokens / (inputTokens)
 * 若任一为 null 或 inputTokens <= 0 则返回“未采集”
 */
export function calculateCacheHitRate(
  inputTokens: number | null | undefined,
  cacheReadTokens: number | null | undefined,
): string {
  if (
    inputTokens === null ||
    cacheReadTokens === null ||
    inputTokens === undefined ||
    cacheReadTokens === undefined
  ) {
    return "未采集";
  }

  if (inputTokens <= 0) {
    return "未采集";
  }

  const rate = Math.round((cacheReadTokens / inputTokens) * 100);
  return `${Math.min(Math.max(rate, 0), 100)}%`;
}

/**
 * 可用性徽章状态
 */
export function getUsageAvailabilityBadge(
  availability: string,
  reason?: string | null,
): { label: string; variant: "success" | "warning" | "error" | "muted" } {
  switch (availability) {
    case "available":
      return { label: "用量已就绪", variant: "success" };
    case "partial":
      return { label: "部分采集", variant: "warning" };
    case "disabled":
      return { label: "采集已关闭", variant: "muted" };
    case "unavailable":
      if (reason === "not_recorded") {
        return { label: "未采集历史", variant: "muted" };
      }
      if (reason === "backend_unavailable") {
        return { label: "暂不可用", variant: "warning" };
      }
      return { label: "暂无记录", variant: "muted" };
    default:
      return { label: "未知状态", variant: "muted" };
  }
}

/**
 * 调用 Scope 语义
 */
export function getCallScopeBadge(scope: string): {
  label: string;
  variant: string;
} {
  switch (scope) {
    case "primary":
      return { label: "主代理", variant: "blue" };
    case "subagent":
      return { label: "子代理", variant: "purple" };
    case "auxiliary":
      return { label: "辅助调用", variant: "gray" };
    default:
      return { label: scope, variant: "gray" };
  }
}

/**
 * 调用 Purpose 语义
 */
export function getCallPurposeLabel(purpose: string): string {
  switch (purpose) {
    case "agent":
      return "核心推理";
    case "summarization":
      return "文本摘要";
    case "memory_extraction":
      return "记忆提取";
    case "vision":
      return "视觉多模态";
    case "other":
      return "其他";
    default:
      return purpose;
  }
}

/**
 * 紧凑型 Token 格式化 (借鉴 open-swe)
 */
export function formatTokenCompact(count: number | null | undefined): string {
  if (count === null || count === undefined) return "未采集";
  if (count >= 1_000_000)
    return `${(count / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (count >= 1_000)
    return `${(count / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  return String(count);
}

/**
 * 格式化模型调用耗时
 */
export function formatCallDuration(
  startedAt: string,
  endedAt: string | null,
): string {
  if (!endedAt) return "执行中";
  const start = new Date(startedAt).getTime();
  const end = new Date(endedAt).getTime();
  if (isNaN(start) || isNaN(end) || end < start) return "--";
  const ms = end - start;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * 模型调用 Outcome 状态胶囊
 */
export function getCallOutcomeBadge(outcome: string): {
  label: string;
  variant: "success" | "error" | "warning" | "muted";
} {
  switch (outcome) {
    case "completed":
      return { label: "完成", variant: "success" };
    case "failed":
      return { label: "失败", variant: "error" };
    case "cancelled":
      return { label: "取消", variant: "muted" };
    case "started":
      return { label: "执行中", variant: "warning" };
    default:
      return { label: outcome, variant: "muted" };
  }
}

/**
 * 采集质量 Quality 状态
 */
export function getCallQualityBadge(quality: string): {
  label: string;
  isDegraded: boolean;
} {
  switch (quality) {
    case "reported":
      return { label: "完整", isDegraded: false };
    case "derived_from_reported":
      return { label: "推导", isDegraded: false };
    case "partial":
      return { label: "部分缺失", isDegraded: true };
    case "missing":
      return { label: "未报告", isDegraded: true };
    case "invalid":
      return { label: "无效数据", isDegraded: true };
    default:
      return { label: quality, isDegraded: false };
  }
}
