import { describe, expect, it, vi } from "vitest";
import { buildLangfuseTraceUrl } from "./langfuse-url";
import { env } from "@/config/env";

describe("buildLangfuseTraceUrl", () => {
  it("returns empty string if traceId is empty", () => {
    expect(buildLangfuseTraceUrl("")).toBe("");
    expect(buildLangfuseTraceUrl("   ")).toBe("");
  });

  it("builds project search URL when projectId is configured", () => {
    const url = buildLangfuseTraceUrl("f878c122-0323-4828-a377-3a111b508f20", {
      projectId: "cmt2gj4cq001fad0dffy9vu9v",
      baseUrl: "https://jp.cloud.langfuse.com",
    });

    expect(url).toContain(
      "https://jp.cloud.langfuse.com/project/cmt2gj4cq001fad0dffy9vu9v/traces?",
    );
    expect(url).toContain("filter=isRootObservation%3Bboolean%3B%3B%3D%3Btrue");
    expect(url).toContain("searchType=id");
    expect(url).toContain("searchType=content");
    expect(url).toContain("traceTab=attributes");
    expect(url).toContain("search=f878c122-0323-4828-a377-3a111b508f20");
  });

  it("builds custom template URL when template is provided", () => {
    const url = buildLangfuseTraceUrl("f878c122", {
      template: "https://my-langfuse.internal/traces/{traceId}?view=tree",
    });
    expect(url).toBe("https://my-langfuse.internal/traces/f878c122?view=tree");
  });

  it("falls back to default /trace/{id} when no projectId and no template", () => {
    const originalProjectId = env.langfuseProjectId;
    const originalTemplate = env.langfuseTraceUrlTemplate;
    env.langfuseProjectId = "";
    env.langfuseTraceUrlTemplate = "";

    try {
      const url = buildLangfuseTraceUrl("f878c122", {
        baseUrl: "https://jp.cloud.langfuse.com",
        projectId: "",
        template: "",
      });
      expect(url).toBe("https://jp.cloud.langfuse.com/trace/f878c122");
    } finally {
      env.langfuseProjectId = originalProjectId;
      env.langfuseTraceUrlTemplate = originalTemplate;
    }
  });
});
