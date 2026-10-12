import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { UsageDashboardV1Schema, UsageRunPageV1Schema } from "./types";

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
});
