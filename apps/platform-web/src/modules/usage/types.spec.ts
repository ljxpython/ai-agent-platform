import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  UsageDashboardV1Schema,
  UsageRunPageV1Schema,
  GatewaySeriesV1Schema,
} from "./types";

const fixturesDir = resolve(
  __dirname,
  "../../../../../docs/projects/20261011-token-usage-dashboard/fixtures",
);

function loadFixture(filename: string): unknown {
  const content = readFileSync(resolve(fixturesDir, filename), "utf-8");
  return JSON.parse(content);
}

describe("Usage DTO & Zod Schemas", () => {
  const dashboardFixtures = [
    "dashboard-complete.json",
    "dashboard-partial.json",
    "dashboard-empty.json",
    "dashboard-not_recorded.json",
    "dashboard-disabled.json",
    "dashboard-unavailable.json",
    "dashboard-unpriced.json",
    "dashboard-no-projects.json",
  ];

  for (const filename of dashboardFixtures) {
    it(`should successfully validate dashboard fixture: ${filename}`, () => {
      const data = loadFixture(filename);
      const parsed = UsageDashboardV1Schema.safeParse(data);
      if (!parsed.success) {
        console.error(
          `Validation failed for ${filename}:`,
          parsed.error.format(),
        );
      }
      expect(parsed.success).toBe(true);
    });
  }

  const runPageFixtures = [
    "runs-visible.json",
    "runs-empty.json",
    "runs-empty-with-cursor.json",
  ];

  for (const filename of runPageFixtures) {
    it(`should successfully validate runs fixture: ${filename}`, () => {
      const data = loadFixture(filename);
      const parsed = UsageRunPageV1Schema.safeParse(data);
      if (!parsed.success) {
        console.error(
          `Validation failed for ${filename}:`,
          parsed.error.format(),
        );
      }
      expect(parsed.success).toBe(true);
    });
  }

  it("should successfully extract 503 usage_query_capacity_exhausted error fixture", async () => {
    const errorData = loadFixture("error-query-capacity.json");
    const { extractPlatformHttpError } = await import("@/utils/http-error");
    const extracted = extractPlatformHttpError({
      response: {
        status: 503,
        data: errorData,
      },
    });
    expect(extracted.status).toBe(503);
    expect(extracted.code).toBe("usage_query_capacity_exhausted");
    expect(extracted.message).toBe(
      "Usage query capacity is temporarily unavailable",
    );
  });

  it("should successfully validate gateway series schema", () => {
    const payload = {
      version: 1,
      as_of: "2026-11-17T12:00:00Z",
      window: {
        from: "2026-11-17T11:00:00Z",
        to: "2026-11-17T12:00:00Z",
        timezone: "Asia/Shanghai",
        bucket_seconds: 300,
        time_basis: "model_call_started_at",
      },
      scope: {
        kind: "platform",
        project_ids: [],
        covered_project_count: 0,
      },
      summary: {
        total_requests: 120,
        total_errors: 3,
        error_rate: 0.025,
        total_tokens: 24000,
        total_input_tokens: 16000,
        total_output_tokens: 8000,
        total_cache_read_tokens: 4000,
        total_cache_creation_tokens: 1000,
        cache_hit_ratio: 0.25,
        avg_tokens_per_request: 200.0,
        p90_latency_ms: 1450.5,
        total_cost_usd: "0.048000000000",
      },
      series: [
        {
          timestamp_ms: 1731844800000,
          time_label: "11/17 19:00",
          requests: 60,
          errors: 1,
          latency_p50_ms: 540.2,
          latency_p90_ms: 1420.0,
          latency_p99_ms: 2200.0,
          input_tokens: 8000,
          output_tokens: 4000,
          total_tokens: 12000,
          cache_read_tokens: 2000,
          cache_creation_tokens: 500,
          tokens_per_request: 200.0,
          cost_usd: "0.024000000000",
        },
      ],
      breakdown: [
        {
          key: "deepseek-v4.1",
          requests: 120,
          total_tokens: 24000,
          cost_usd: "0.048000000000",
        },
      ],
      request_id: "req-gw-123",
    };
    const parsed = GatewaySeriesV1Schema.safeParse(payload);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.summary.total_requests).toBe(120);
      expect(parsed.data.series[0].tokens_per_request).toBe(200.0);
    }
  });
});
