import { describe, it, expect } from "vitest";
import {
  formatTokenCount,
  formatCostUsd,
  calculateCacheHitRate,
  getUsageAvailabilityBadge,
} from "./view-model";

describe("usage view-model", () => {
  describe("formatTokenCount", () => {
    it("null 或 undefined 返回 未采集，绝对不返回 0", () => {
      expect(formatTokenCount(null)).toBe("未采集");
      expect(formatTokenCount(undefined)).toBe("未采集");
    });

    it("真 0 返回 '0'", () => {
      expect(formatTokenCount(0)).toBe("0");
    });

    it("正数千分位格式化", () => {
      expect(formatTokenCount(1234567)).toBe("1,234,567");
    });
  });

  describe("formatCostUsd", () => {
    it("未知或未配置返回 未配置价格", () => {
      const res = formatCostUsd(null, "unknown");
      expect(res.display).toBe("未配置价格");
      expect(res.isUnknown).toBe(true);
    });

    it("not_applicable 或真 0 返回 $0.00", () => {
      const res = formatCostUsd("0.000000000000", "not_applicable");
      expect(res.display).toBe("$0.00");
      expect(res.isZero).toBe(true);
    });

    it("微额正数 (< 0.0001) 严禁显示 $0.00，必须显示 < $0.0001 且保留原始值", () => {
      const res = formatCostUsd("0.000000120000", "estimated");
      expect(res.display).toBe("< $0.0001");
      expect(res.fullUsd).toBe("$0.000000120000");
    });

    it("正常金额正确展示 4 位小数", () => {
      const res = formatCostUsd("0.002580000000", "estimated");
      expect(res.display).toBe("$0.0026");
      expect(res.fullUsd).toBe("$0.002580000000");
    });
  });

  describe("calculateCacheHitRate", () => {
    it("缺值返回未采集", () => {
      expect(calculateCacheHitRate(null, 100)).toBe("未采集");
      expect(calculateCacheHitRate(100, null)).toBe("未采集");
      expect(calculateCacheHitRate(0, 0)).toBe("未采集");
    });

    it("正常计算百分比", () => {
      expect(calculateCacheHitRate(1000, 200)).toBe("20%");
    });
  });

  describe("getUsageAvailabilityBadge", () => {
    it("历史未记录与服务暂不可用分别返回对应文案", () => {
      expect(
        getUsageAvailabilityBadge("unavailable", "not_recorded").label,
      ).toBe("未采集历史");
      expect(
        getUsageAvailabilityBadge("unavailable", "backend_unavailable").label,
      ).toBe("暂不可用");
      expect(getUsageAvailabilityBadge("available").label).toBe("用量已就绪");
    });
  });
});
