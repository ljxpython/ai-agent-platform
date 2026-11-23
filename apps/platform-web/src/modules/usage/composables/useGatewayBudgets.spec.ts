import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref } from "vue";
import {
  calculateBudgetRatio,
  formatDurationLabel,
  formatActionLabel,
  formatBudgetAmount,
  stripTrailingZeros,
  useGatewayBudgets,
} from "./useGatewayBudgets";
import * as usageService from "@/services/usage/usage.service";

vi.mock("@/services/usage/usage.service");

describe("useGatewayBudgets 纯函数与状态逻辑", () => {
  describe("calculateBudgetRatio 高精度比值计算", () => {
    it("空值或非法输入返回安全占位符", () => {
      expect(calculateBudgetRatio(null, "100")).toEqual({
        ratio: 0,
        percentStr: "—",
        isOverBudget: false,
      });
      expect(calculateBudgetRatio("50", null)).toEqual({
        ratio: 0,
        percentStr: "—",
        isOverBudget: false,
      });
      expect(calculateBudgetRatio("50", "0")).toEqual({
        ratio: 0,
        percentStr: "—",
        isOverBudget: false,
      });
      expect(calculateBudgetRatio("invalid", "100")).toEqual({
        ratio: 0,
        percentStr: "—",
        isOverBudget: false,
      });
    });

    it("正常低于限额的百分比计算", () => {
      const res = calculateBudgetRatio("50.000000000000", "100.000000000000");
      expect(res.ratio).toBe(0.5);
      expect(res.percentStr).toBe("50.0%");
      expect(res.isOverBudget).toBe(false);
    });

    it("恰好达到 80% 警戒线", () => {
      const res = calculateBudgetRatio("80.000000000000", "100.000000000000");
      expect(res.ratio).toBe(0.8);
      expect(res.percentStr).toBe("80.0%");
      expect(res.isOverBudget).toBe(false);
    });

    it("超额 110% 截断 ratio 并不截断 percentStr", () => {
      const res = calculateBudgetRatio("110.000000000000", "100.000000000000");
      expect(res.ratio).toBe(1); // 进度条宽度 clamp 到 100%
      expect(res.percentStr).toBe("110.0%"); // 文字保留真实比例
      expect(res.isOverBudget).toBe(true);
    });

    it("支持极小 12 位小数精准换算", () => {
      const res = calculateBudgetRatio("0.000000000001", "0.000000000002");
      expect(res.ratio).toBe(0.5);
      expect(res.percentStr).toBe("50.0%");
      expect(res.isOverBudget).toBe(false);
    });
  });

  describe("格式化工具", () => {
    it("formatDurationLabel 返回标准中文", () => {
      expect(formatDurationLabel({ unit: "DAYS", value: 1 })).toBe(
        "每日 (UTC 00:00 重置)",
      );
      expect(formatDurationLabel({ unit: "WEEKS", value: 1 })).toBe(
        "每周日 (UTC 00:00 重置)",
      );
      expect(formatDurationLabel({ unit: "MONTHS", value: 1 })).toBe(
        "每月 1 日 (UTC 00:00 重置)",
      );
      expect(formatDurationLabel(null)).toBe("—");
    });

    it("formatActionLabel 返回标准中文", () => {
      expect(formatActionLabel("ALERT")).toBe("通知后继续");
      expect(formatActionLabel("REJECT")).toBe("阻止后续调用");
      expect(formatActionLabel(null)).toBe("—");
    });

    it("formatBudgetAmount 格式化金额小数位数", () => {
      expect(formatBudgetAmount("200.000000000000")).toBe("200.00");
      expect(formatBudgetAmount("7.734293400000")).toBe("7.73");
      expect(formatBudgetAmount("1234.567800000000")).toBe("1,234.57");
      expect(formatBudgetAmount("0.500000000000")).toBe("0.50");
      expect(formatBudgetAmount("0.003500000000")).toBe("0.0035");
      expect(formatBudgetAmount("0.000000000000")).toBe("0.00");
      expect(formatBudgetAmount(null)).toBe("0.00");
      expect(formatBudgetAmount("")).toBe("0.00");
    });

    it("stripTrailingZeros 去除回填编辑多余尾部零", () => {
      expect(stripTrailingZeros("200.000000000000")).toBe("200");
      expect(stripTrailingZeros("7.734293400000")).toBe("7.7342934");
      expect(stripTrailingZeros("0.500000000000")).toBe("0.5");
      expect(stripTrailingZeros("100")).toBe("100");
      expect(stripTrailingZeros("")).toBe("");
      expect(stripTrailingZeros(null)).toBe("");
    });
  });

  describe("useGatewayBudgets 异步竞态防穿透", () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    it("成功拉取策略并赋值", async () => {
      const mockItems = [
        {
          id: "policy-1",
          scope: "GLOBAL" as const,
          budget_amount: "100.000000000000",
          budget_unit: "USD" as const,
          duration: { unit: "MONTHS" as const, value: 1 as const },
          action: "REJECT" as const,
          version: 1,
          definition_version: 1,
          created_at: "2026-11-18T00:00:00Z",
          definition_started_at: "2026-11-18T00:00:00Z",
          updated_at: "2026-11-18T00:00:00Z",
          accounting_status: "complete" as const,
          known_spend: "50.000000000000",
          current_spend: "50.000000000000",
          is_exceeded: false,
          window_start: "2026-11-01T00:00:00Z",
          window_end: "2026-12-01T00:00:00Z",
          as_of: "2026-11-18T10:00:00Z",
          sync_status: "applied" as const,
        },
      ];

      vi.mocked(usageService.getBudgets).mockResolvedValue({
        items: mockItems,
        revision: 1,
      });

      const projectId = ref("proj-1");
      const scopeMode = ref<"platform" | "project">("project");
      const { items, isLoading, loadBudgets } = useGatewayBudgets({
        projectId,
        scopeMode,
      });

      await loadBudgets();
      expect(isLoading.value).toBe(false);
      expect(items.value).toHaveLength(1);
      expect(items.value[0].id).toBe("policy-1");
    });
  });
});
