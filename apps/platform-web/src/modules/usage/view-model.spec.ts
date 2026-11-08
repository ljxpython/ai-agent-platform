import { describe, it, expect } from "vitest";
import {
  formatTokenNumber,
  formatCompactTokens,
  formatDashboardCost,
  formatChangeRatio,
} from "./view-model";

describe("Usage ViewModel Utilities", () => {
  describe("formatCompactTokens", () => {
    it("handles null and undefined gracefully", () => {
      expect(formatCompactTokens(null)).toBe("—");
      expect(formatCompactTokens(undefined)).toBe("—");
    });

    it("formats small integers (< 1000) directly", () => {
      expect(formatCompactTokens(0)).toBe("0");
      expect(formatCompactTokens(991)).toBe("991");
    });

    it("formats thousands (1,000 ~ 999,999) with 1 decimal place", () => {
      expect(formatCompactTokens(2206)).toBe("2.2K");
      expect(formatCompactTokens(305257)).toBe("305.3K");
    });

    it("formats millions (>= 1,000,000) with up to 2 decimal places", () => {
      expect(formatCompactTokens(1152362)).toBe("1.15M");
      expect(formatCompactTokens(33134222)).toBe("33.13M");
    });

    it("formats billions (>= 1,000,000,000) with up to 2 decimal places", () => {
      expect(formatCompactTokens(1500000000)).toBe("1.5B");
    });
  });

  describe("formatTokenNumber", () => {
    it("formats numbers with locale commas", () => {
      expect(formatTokenNumber(33134222)).toBe("33,134,222");
      expect(formatTokenNumber(null)).toBe("—");
    });
  });

  describe("formatDashboardCost", () => {
    it("returns unknown when cost.status is unknown", () => {
      const res = formatDashboardCost({
        status: "unknown",
        estimated_cost_usd: null,
        known_cost_usd: null,
        currency: "USD",
        source: null,
        unpriced_call_count: 29,
        pricing_versions: [],
      });
      expect(res.display).toBe("未计价/未知");
      expect(res.isUnknown).toBe(true);
    });

    it("returns partial formatted dollar when partial cost available", () => {
      const res = formatDashboardCost({
        status: "partial",
        estimated_cost_usd: null,
        known_cost_usd: "5.880000000000",
        currency: "USD",
        source: "configured_catalog",
        unpriced_call_count: 521,
        pricing_versions: ["v1"],
      });
      expect(res.display).toBe("$5.88");
      expect(res.isPartial).toBe(true);
      expect(res.isUnknown).toBe(false);
    });
  });

  describe("formatChangeRatio", () => {
    it("formats positive and negative percentages", () => {
      expect(formatChangeRatio(0.125)).toBe("+12.5%");
      expect(formatChangeRatio(-0.052)).toBe("-5.2%");
      expect(formatChangeRatio(null)).toBe("—");
    });
  });
});
