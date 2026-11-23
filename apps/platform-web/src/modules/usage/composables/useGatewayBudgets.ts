import { ref, shallowRef, watch, type Ref, type ComputedRef } from "vue";
import {
  getBudgets,
  createBudget,
  updateBudget,
  deleteBudget,
} from "@/services/usage/usage.service";
import type {
  BudgetItem,
  CreateBudgetPolicyInput,
  BudgetDuration,
} from "../types";

export interface CalculateBudgetRatioResult {
  ratio: number;
  percentStr: string;
  isOverBudget: boolean;
}

/**
 * 定点高精度比值与百分比计算纯函数
 * 避免 Number 浮点溢出和 BigInt 整数截断为 0
 */
export function calculateBudgetRatio(
  spendStr: string | null | undefined,
  limitStr: string | null | undefined,
): CalculateBudgetRatioResult {
  if (!spendStr || !limitStr) {
    return { ratio: 0, percentStr: "—", isOverBudget: false };
  }
  const spend = Number(spendStr);
  const limit = Number(limitStr);
  if (!Number.isFinite(spend) || !Number.isFinite(limit) || limit <= 0) {
    return { ratio: 0, percentStr: "—", isOverBudget: false };
  }
  const rawRatio = spend / limit;
  const percentNum = rawRatio * 100;
  const percentStr = `${percentNum.toFixed(1)}%`;
  const isOverBudget = spend >= limit;
  // ratio 用于进度条宽度，最小 0，封顶 1 (100%) 避免破坏布局容器
  const clampedRatio = Math.max(0, Math.min(1, rawRatio));
  return { ratio: clampedRatio, percentStr, isOverBudget };
}

/**
 * 格式化重置周期文案
 */
export function formatDurationLabel(duration?: BudgetDuration | null): string {
  if (!duration) return "—";
  switch (duration.unit) {
    case "DAYS":
      return "每日 (UTC 00:00 重置)";
    case "WEEKS":
      return "每周日 (UTC 00:00 重置)";
    case "MONTHS":
      return "每月 1 日 (UTC 00:00 重置)";
    default:
      return `${duration.value} ${duration.unit}`;
  }
}

/**
 * 格式化动作文案
 */
export function formatActionLabel(action?: string | null): string {
  if (!action) return "—";
  switch (action) {
    case "ALERT":
      return "通知后继续";
    case "REJECT":
      return "阻止后续调用";
    default:
      return action;
  }
}

/**
 * 格式化预算金额展示
 * 去除冗长 12 位小数，常规金额按标准货币优雅保留 2 位小数；对极小微额（< $0.01）按需保留最多 4 位小数
 */
export function formatBudgetAmount(amountStr?: string | null): string {
  if (!amountStr) return "0.00";
  const num = Number(amountStr);
  if (!Number.isFinite(num) || num === 0) return "0.00";
  if (num >= 0.01) {
    return num.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  if (num >= 0.0001) {
    return num.toFixed(4);
  }
  return "< 0.0001";
}

/**
 * 剔除小数末尾冗余的 0（用于输入框回填编辑，例如 200.000000000000 -> 200）
 */
export function stripTrailingZeros(val?: string | null): string {
  if (!val) return "";
  if (!val.includes(".")) return val;
  return val.replace(/\.?0+$/, "");
}

export interface UseGatewayBudgetsOptions {
  projectId?:
    | Ref<string | undefined | null>
    | ComputedRef<string | undefined | null>;
  scopeMode?: Ref<"platform" | "project"> | ComputedRef<"platform" | "project">;
  enabled?: Ref<boolean> | ComputedRef<boolean>;
}

export function useGatewayBudgets(options: UseGatewayBudgetsOptions = {}) {
  const items = shallowRef<BudgetItem[]>([]);
  const revision = ref<number>(0);
  const isLoading = ref<boolean>(false);
  const isSaving = ref<boolean>(false);
  const error = ref<string | null>(null);

  let currentRequestId = 0;
  let activeAbortController: AbortController | null = null;

  function abortActiveRequest() {
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
  }

  async function loadBudgets(): Promise<void> {
    if (options.enabled && !options.enabled.value) {
      return;
    }

    abortActiveRequest();
    activeAbortController = new AbortController();
    const requestId = ++currentRequestId;

    isLoading.value = true;
    error.value = null;

    try {
      const pId =
        options.scopeMode?.value === "project"
          ? options.projectId?.value
          : null;
      const res = await getBudgets(pId, {
        signal: activeAbortController.signal,
      });
      if (requestId !== currentRequestId) {
        return; // 作废前序过时请求，防止跨项目响应穿透
      }
      items.value = res.items;
      revision.value = res.revision;
    } catch (err: unknown) {
      if (
        activeAbortController?.signal.aborted ||
        requestId !== currentRequestId
      ) {
        return;
      }
      const e = err as { message?: string };
      error.value = e.message || "加载预算策略失败";
    } finally {
      if (requestId === currentRequestId) {
        isLoading.value = false;
      }
    }
  }

  async function handleCreate(input: CreateBudgetPolicyInput): Promise<void> {
    isSaving.value = true;
    try {
      await createBudget(input);
      await loadBudgets();
    } finally {
      isSaving.value = false;
    }
  }

  async function handleUpdate(
    policyId: string,
    input: CreateBudgetPolicyInput,
  ): Promise<void> {
    isSaving.value = true;
    try {
      await updateBudget(policyId, input);
      await loadBudgets();
    } finally {
      isSaving.value = false;
    }
  }

  async function handleDelete(policyId: string): Promise<void> {
    isSaving.value = true;
    try {
      await deleteBudget(policyId);
      await loadBudgets();
    } finally {
      isSaving.value = false;
    }
  }

  // 监听 projectId 与 scopeMode 变化自动拉取
  if (options.projectId || options.scopeMode) {
    watch(
      () => [options.projectId?.value, options.scopeMode?.value],
      () => {
        loadBudgets();
      },
      { immediate: true },
    );
  }

  return {
    items,
    revision,
    isLoading,
    isSaving,
    error,
    loadBudgets,
    createBudget: handleCreate,
    updateBudget: handleUpdate,
    deleteBudget: handleDelete,
  };
}
