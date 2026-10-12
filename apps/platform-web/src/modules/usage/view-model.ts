import type { TokenCounts, UsageCost } from "./types";

export interface AvailabilityBadgeVariant {
  label: string;
  variant: "success" | "warning" | "muted" | "error";
  description: string;
}

/**
 * 格式化整数 Token 计数（带千分位）；null 返回 "—"
 */
export function formatTokenNumber(count: number | null | undefined): string {
  if (count === null || count === undefined) {
    return "—";
  }
  return count.toLocaleString();
}

/**
 * 紧凑格式化 Token 计数（用于图表刻度或微胶囊）：例如 1200 -> 1.2K, 1200000 -> 1.2M
 */
export function formatTokenCompact(count: number | null | undefined): string {
  if (count === null || count === undefined) {
    return "—";
  }
  if (Math.abs(count) >= 1_000_000) {
    return `${(count / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(count) >= 1_000) {
    return `${(count / 1_000).toFixed(1)}K`;
  }
  return String(count);
}

/**
 * 优先使用完整 Token，若缺失则降级为已知小计并打上 partial 标记
 */
export function resolveDisplayTokens(
  tokens: TokenCounts | null | undefined,
  knownTokens: TokenCounts | null | undefined,
): {
  data: TokenCounts | null;
  isPartial: boolean;
  isMissing: boolean;
} {
  if (tokens && tokens.total_tokens !== null) {
    return { data: tokens, isPartial: false, isMissing: false };
  }
  if (knownTokens && knownTokens.total_tokens !== null) {
    return { data: knownTokens, isPartial: true, isMissing: false };
  }
  return { data: null, isPartial: false, isMissing: true };
}

export interface CostViewModel {
  display: string;
  fullUsd: string;
  isPartial: boolean;
  isUnknown: boolean;
}

/**
 * 格式化 USD 金额，严格保留 12 位原文字符串，极小正数保护
 */
export function formatDashboardCost(
  cost: UsageCost | null | undefined,
  availability?: string,
  unavailableReason?: string | null,
): CostViewModel {
  if (!cost || availability === "unavailable") {
    const display =
      unavailableReason === "not_recorded" ? "未采集历史" : "暂不可用";
    return { display, fullUsd: "—", isPartial: false, isUnknown: true };
  }
  if (availability === "disabled") {
    return {
      display: "采集已关闭",
      fullUsd: "—",
      isPartial: false,
      isUnknown: true,
    };
  }

  const rawAmount =
    cost.status === "partial" ? cost.known_cost_usd : cost.estimated_cost_usd;

  if (cost.status === "unknown" || !rawAmount) {
    return {
      display: "未计价/未知",
      fullUsd: "—",
      isPartial: cost.status === "partial",
      isUnknown: true,
    };
  }

  if (cost.status === "not_applicable") {
    return {
      display: "$0.00",
      fullUsd: "$0.000000000000",
      isPartial: false,
      isUnknown: false,
    };
  }

  const num = Number(rawAmount);
  if (isNaN(num) || num === 0) {
    return {
      display: "$0.00",
      fullUsd: "$0.000000000000",
      isPartial: cost.status === "partial",
      isUnknown: false,
    };
  }

  let display: string;
  if (num < 0.0001) {
    display = "< $0.0001";
  } else if (num < 1) {
    display = `$${num.toFixed(4)}`;
  } else {
    display = `$${num.toFixed(2)}`;
  }

  return {
    display,
    fullUsd: `$${rawAmount}`,
    isPartial: cost.status === "partial",
    isUnknown: false,
  };
}

/**
 * 格式化前窗变化比率 (如 +12.5%, -5.2%)
 */
export function formatChangeRatio(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) {
    return "—";
  }
  const pct = (ratio * 100).toFixed(1);
  return ratio > 0 ? `+${pct}%` : `${pct}%`;
}

/**
 * 可用性徽章状态转换
 */
export function getAvailabilityBadge(
  availability: string,
  reason: string | null = null,
): AvailabilityBadgeVariant {
  switch (availability) {
    case "available":
      return {
        label: "正常采集",
        variant: "success",
        description: "该范围内的 Token 及调用用量已完整采集并入账",
      };
    case "partial":
      return {
        label: "部分入账",
        variant: "warning",
        description: "部分调用仍在运行或缺失用量指标，当前展现已知小计",
      };
    case "disabled":
      return {
        label: "采集关闭",
        variant: "muted",
        description: "该项目/范围的新用量采集已关闭，仅可查看历史归档数据",
      };
    case "unavailable":
    default:
      if (reason === "not_recorded") {
        return {
          label: "尚未采集",
          variant: "muted",
          description: "所选时间窗口尚未采集到任何有效运行历史",
        };
      }
      return {
        label: "查询故障",
        variant: "error",
        description: "上游数据库或后端指标暂不可用，请稍后刷新重试",
      };
  }
}
