import { describe, it, expect } from "vitest";
import {
  safeParseRunUsage,
  safeParseThreadUsage,
  tokenCountsSchema,
  usageCostSchema,
} from "./types";
import usageFixtures from "../../../../../../docs/projects/20261007-agent-usage-cost-governance/fixtures/usage-v1.json";

describe("Usage DTO Types & Zod Schemas", () => {
  it("成功解析 usage-v1.json 中的 Run 状态样本", () => {
    const samples = (usageFixtures as any).samples;
    const runKeys = [
      "run_complete_page1",
      "run_cache_ttl",
      "run_partial_missing_usage",
      "run_running",
      "run_unknown_price",
      "run_zero_calls",
      "run_not_recorded",
      "run_backend_unavailable",
      "run_disabled",
      "run_collection_degraded",
      "run_child",
    ];

    for (const key of runKeys) {
      const sample = samples[key];
      expect(sample, `缺少样本 ${key}`).toBeDefined();
      const res = safeParseRunUsage(sample);
      expect(res.success, `样本 ${key} 解析失败: ${res.errorMessage}`).toBe(
        true,
      );
      expect(res.data?.run_id).toBe(sample.run_id);
    }
  });

  it("成功解析 usage-v1.json 中的 thread_complete 样本", () => {
    const threadSample = (usageFixtures as any).samples.thread_complete;
    expect(threadSample).toBeDefined();
    const res = safeParseThreadUsage(threadSample);
    expect(res.success, `thread_complete 解析失败: ${res.errorMessage}`).toBe(
      true,
    );
    expect(res.data?.thread_id).toBe(threadSample.thread_id);
    expect(res.data?.coverage_basis).toBe("recorded_native_runs");
  });

  it("自动安全剔除未知元数据键（strip 策略）", () => {
    const raw = {
      ...(usageFixtures as any).samples.run_complete_page1,
      extra_unknown_field: "dangerous_metadata",
      another_nested: { foo: "bar" },
    };
    const res = safeParseRunUsage(raw);
    expect(res.success).toBe(true);
    expect((res.data as any).extra_unknown_field).toBeUndefined();
  });

  it("拒绝非法金额格式（非十进制数字字符串）", () => {
    const res = usageCostSchema.safeParse({
      status: "estimated",
      estimated_cost_usd: "invalid-currency-$10",
      known_cost_usd: "1.00",
      currency: "USD",
      source: "configured_catalog",
      unpriced_call_count: 0,
      pricing_versions: [],
    });
    expect(res.success).toBe(false);
  });

  it("拒绝超出安全整数范围的 Token", () => {
    const res = tokenCountsSchema.safeParse({
      input_tokens: Number.MAX_SAFE_INTEGER + 100,
      output_tokens: 10,
      total_tokens: 10,
      cache_read_tokens: null,
      cache_creation_tokens: null,
      cache_creation_5m_tokens: null,
      cache_creation_1h_tokens: null,
      reasoning_tokens: null,
    });
    expect(res.success).toBe(false);
  });

  it("拒绝负数 Token", () => {
    const res = tokenCountsSchema.safeParse({
      input_tokens: -1,
      output_tokens: 10,
      total_tokens: 10,
      cache_read_tokens: null,
      cache_creation_tokens: null,
      cache_creation_5m_tokens: null,
      cache_creation_1h_tokens: null,
      reasoning_tokens: null,
    });
    expect(res.success).toBe(false);
  });
});
